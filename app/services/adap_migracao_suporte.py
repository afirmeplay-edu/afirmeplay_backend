# -*- coding: utf-8 -*-
"""Migração dos alunos de turmas de Suporte (Educação Especial) para a subturma ADAP da turma regular.

Rodada 1: só casos limpos. O aluno sai da turma "Suporte N" e entra na subturma ADAP N
da turma regular do mesmo ano (turma única ou turma A). Quando existe cadastro regular
duplicado (mesmo nome normalizado e mesmo ano) sem nota, esse cadastro é desvinculado
da turma e da escola e recebe a marca ``cadastro_descartado`` em ``users.traits``.
Com ``incluir_questionario_descartado`` (desligado por padrão), antes disso destinatários e
respostas do questionário passam do usuário descartado para o mantido (destinatário pendente
do mantido no mesmo formulário sai, com a linha guardada no log).

Nada é excluído. Simulação por padrão; gravação só com ``write=True``.
Cada aluno é gravado numa transação própria. O log guarda o antes e o depois para reversão.
"""
from __future__ import annotations

import copy
import json
import logging
import os
import re
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

ADAP_EDUCATION_STAGE_ID = "247c4af5-2688-41b0-95fa-443f503a9d87"
PRODUCTION_HOSTS = {h.strip() for h in os.environ.get("ADAP_PRODUCTION_HOSTS", "").split(",") if h.strip()}
PRODUCTION_DATABASES = {"afirmeplay_prod"}
DISCARD_TRAIT_KEY = "cadastro_descartado"
DISCARD_REASON = "duplicidade_adap_rodada1"
QUESTIONARIO_OPCOES = ("criar", "nao-criar")
STUDENT_FORM_TYPES = ("aluno-jovem", "aluno-velho")
CLOSED_CLASS_TEST_STATUS = {"concluida", "concluído", "concluido", "encerrada", "finalizada", "expirada"}

_SCHEMA_RE = re.compile(r"^city_[0-9a-f_]+$")
_SUPPORT_GRADE_RE = re.compile(r"^\s*(suporte|adap)\s*([123])\s*$", re.IGNORECASE)
_ANO_RE = re.compile(r"(\d+)\s*\S?\s*ano")
_STOPWORDS_RE = re.compile(r"\b(de|da|do|das|dos|e)\b")
_ACCENTS = str.maketrans("áàâãäéèêëíìîïóòôõöúùûüçñ", "aaaaaeeeeiiiiooooouuuucn")

MOTIVOS = {
    "suporte_3": "Suporte 3 (fora do escopo)",
    "nivel_indefinido": "Nível de suporte não identificado na série",
    "sem_destino": "Sem turma de destino clara",
    "mais_de_uma_turma_suporte": "Aluno em mais de uma turma de suporte",
    "prova_em_andamento": "Prova em andamento (sessão aberta ou aplicação aberta sem resultado)",
    "homonimo_outro_ano": "Homônimo na turma regular de outro ano (confirmar com a escola)",
    "duplicado_iniciais_ou_login": "Duplicado só por iniciais ou login",
    "mais_de_um_candidato_forte": "Mais de um cadastro regular com o mesmo nome e ano",
    "nota_nos_dois": "Nota nos dois cadastros",
    "nota_so_no_regular": "Nota só no cadastro regular",
    "sem_nota_em_nenhum": "Sem nota em nenhum dos cadastros",
    "questionario_no_descartado": "Resposta do questionário no cadastro que seria descartado",
    "questionario_nos_dois": "Os dois cadastros responderam (ou começaram) o mesmo formulário do questionário",
    "excluido_manual": "Excluído desta rodada por id (--excluir-aluno)",
}


class MigracaoError(RuntimeError):
    """Erro de uso ou de ambiente que impede a execução."""


# ---------------------------------------------------------------------------
# Normalização (mesmas regras das consultas C2/C3 do diagnóstico)
# ---------------------------------------------------------------------------

def nome_normalizado(name: Any) -> str:
    text = str(name or "").lower().translate(_ACCENTS)
    text = _STOPWORDS_RE.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


def ano_do_texto(text: Any) -> Optional[int]:
    match = _ANO_RE.search(str(text or "").lower())
    return int(match.group(1)) if match else None


def nivel_da_serie(grade_name: Any) -> Optional[int]:
    match = _SUPPORT_GRADE_RE.match(str(grade_name or ""))
    return int(match.group(2)) if match else None


def serie_especial(grade: Any) -> bool:
    return (
        str(getattr(grade, "education_stage_id", "") or "") == ADAP_EDUCATION_STAGE_ID
        or bool(_SUPPORT_GRADE_RE.match(str(getattr(grade, "name", "") or "")))
    )


def _sid(value: Any) -> Optional[str]:
    return None if value is None else str(value)


def _uuid(value: Any) -> Optional[uuid.UUID]:
    if value in (None, ""):
        return None
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


def _iso(value: Any) -> Optional[str]:
    return value.isoformat() if isinstance(value, datetime) else (None if value is None else str(value))


def _dt(value: Any) -> Optional[datetime]:
    return datetime.fromisoformat(value) if value else None


def is_cadastro_descartado(user: Any) -> bool:
    traits = getattr(user, "traits", None)
    return isinstance(traits, dict) and bool(traits.get(DISCARD_TRAIT_KEY))


# ---------------------------------------------------------------------------
# Ambiente
# ---------------------------------------------------------------------------

def database_target() -> Dict[str, Any]:
    from app import db

    url = db.engine.url
    return {"host": url.host, "port": url.port, "database": url.database}


def assert_environment(schema: str, *, write: bool, confirmar_producao: Optional[str]) -> Dict[str, Any]:
    from app import db
    from sqlalchemy import text

    if not schema or not _SCHEMA_RE.match(schema):
        raise MigracaoError("Informe --schema city_… (um município por vez).")
    exists = db.session.execute(
        text("SELECT 1 FROM pg_namespace WHERE nspname = :s"), {"s": schema}
    ).scalar()
    if not exists:
        raise MigracaoError(f"Schema {schema} não existe neste banco.")
    target = database_target()
    is_prod = target["host"] in PRODUCTION_HOSTS or target["database"] in PRODUCTION_DATABASES
    target["producao"] = is_prod
    if write and is_prod and confirmar_producao != schema:
        raise MigracaoError(
            f"Banco de PRODUÇÃO ({target['host']}). Para gravar, repita o schema em "
            f"--confirmar-producao {schema}."
        )
    return target


# ---------------------------------------------------------------------------
# Seleção
# ---------------------------------------------------------------------------

@dataclass
class Candidato:
    student_id: str
    nome: str
    escola_id: str
    escola: str
    turma_suporte_id: str
    turma_suporte: str
    nivel: Optional[int]
    ano: Optional[int]
    destino_id: Optional[str] = None
    destino: Optional[str] = None
    situacao_destino: str = ""
    regular_id: Optional[str] = None
    regular_nome: Optional[str] = None
    regular_turma: Optional[str] = None
    criterio: Optional[str] = None
    categoria: str = ""
    notas_suporte: int = 0
    notas_regular: int = 0
    motivo: Optional[str] = None

    @property
    def elegivel(self) -> bool:
        return self.motivo is None

    @property
    def tipo(self) -> str:
        return "duplicado_forte" if self.regular_id else "so_no_suporte"

    def as_dict(self) -> Dict[str, Any]:
        out = dict(self.__dict__)
        out["tipo"] = self.tipo
        out["motivo_texto"] = MOTIVOS.get(self.motivo) if self.motivo else None
        return out


@dataclass
class Selecao:
    elegiveis: List[Candidato] = field(default_factory=list)
    excluidos: List[Candidato] = field(default_factory=list)


def _load_rows():
    from app import db
    from sqlalchemy import func
    from app.models.answerSheetResult import AnswerSheetResult
    from app.models.classTest import ClassTest
    from app.models.evaluationResult import EvaluationResult
    from app.models.grades import Grade
    from app.models.school import School
    from app.models.student import Student
    from app.models.studentClass import Class
    from app.models.testSession import TestSession
    from app.models.user import User
    from app.socioeconomic_forms.models.form import Form
    from app.socioeconomic_forms.models.form_recipient import FormRecipient
    from app.socioeconomic_forms.models.form_response import FormResponse

    grades = {str(g.id): g for g in Grade.query.all()}
    classes = {str(c.id): c for c in Class.query.all()}
    schools = {str(s.id): s.name for s in School.query.all()}
    students = db.session.query(
        Student.id, Student.name, Student.class_id, Student.school_id, Student.user_id
    ).all()
    user_ids = [s.user_id for s in students if s.user_id]
    emails = {}
    for chunk_start in range(0, len(user_ids), 1000):
        chunk = user_ids[chunk_start:chunk_start + 1000]
        for uid, email in db.session.query(User.id, User.email).filter(User.id.in_(chunk)).all():
            emails[uid] = email
    er = dict(db.session.query(EvaluationResult.student_id, func.count()).group_by(EvaluationResult.student_id).all())
    asr = dict(db.session.query(AnswerSheetResult.student_id, func.count()).group_by(AnswerSheetResult.student_id).all())
    respondeu = {
        uid for (uid,) in db.session.query(FormRecipient.user_id)
        .join(Form, Form.id == FormRecipient.form_id)
        .filter(Form.form_type.in_(STUDENT_FORM_TYPES), FormRecipient.status == "completed")
        .distinct().all()
    }
    sessoes_abertas = {
        sid for (sid,) in db.session.query(TestSession.student_id)
        .filter(TestSession.status == "em_andamento").distinct().all()
    }
    abertas_por_turma: Dict[str, Set[str]] = defaultdict(set)
    for class_id, test_id, status in db.session.query(ClassTest.class_id, ClassTest.test_id, ClassTest.status).all():
        if str(status or "").strip().lower() not in CLOSED_CLASS_TEST_STATUS:
            abertas_por_turma[str(class_id)].add(str(test_id))
    feitas = defaultdict(set)
    if abertas_por_turma:
        tests_abertos = list({t for ts in abertas_por_turma.values() for t in ts})
        for sid, tid in db.session.query(EvaluationResult.student_id, EvaluationResult.test_id).filter(
            EvaluationResult.test_id.in_(tests_abertos)
        ).all():
            feitas[str(sid)].add(str(tid))
    estado_form: Dict[str, Dict[str, str]] = defaultdict(dict)
    for model in (FormRecipient, FormResponse):
        for uid, fid, status in db.session.query(model.user_id, model.form_id, model.status).all():
            atual = estado_form[uid].get(fid)
            novo = _estado_formulario(status)
            if atual is None or _ORDEM_ESTADO_FORM[novo] > _ORDEM_ESTADO_FORM[atual]:
                estado_form[uid][fid] = novo
    return (grades, classes, schools, students, emails, er, asr, respondeu, sessoes_abertas,
            abertas_por_turma, feitas, estado_form)


_ORDEM_ESTADO_FORM = {"pendente": 0, "em_andamento": 1, "respondido": 2}


def _estado_formulario(status: Any) -> str:
    st = str(status or "").strip().lower()
    if st == "completed":
        return "respondido"
    if st == "in_progress":
        return "em_andamento"
    return "pendente"


def conflito_questionario(forms_regular: Dict[str, str], forms_mantido: Dict[str, str]) -> List[str]:
    """Formulários que o cadastro regular respondeu e o mantido também respondeu ou começou."""
    return sorted(
        fid for fid, estado in (forms_regular or {}).items()
        if estado == "respondido" and (forms_mantido or {}).get(fid) in ("respondido", "em_andamento")
    )


def selecionar_rodada1(
    escola_ids: Optional[Set[str]] = None, incluir_questionario_descartado: bool = False,
    excluir_alunos: Optional[Set[str]] = None,
) -> Selecao:
    """Classifica os alunos das turmas de Suporte do schema atual (regras C2/C3)."""
    (grades, classes, schools, students, emails, er, asr, respondeu,
     sessoes_abertas, abertas_por_turma, feitas, estado_form) = _load_rows()

    def grade_of(class_obj):
        return grades.get(str(class_obj.grade_id)) if class_obj is not None and class_obj.grade_id else None

    # Turmas regulares por escola e ano (C2: ano vem da série)
    regulares: Dict[Tuple[str, int], List[Any]] = defaultdict(list)
    for c in classes.values():
        g = grade_of(c)
        if g is None or serie_especial(g):
            continue
        ano = ano_do_texto(g.name)
        if ano is not None and c.school_id:
            regulares[(str(c.school_id), ano)].append(c)

    def destino(school_id: str, ano: Optional[int], nivel: Optional[int]) -> Tuple[Optional[Any], str]:
        if nivel is None:
            return None, "NIVEL INDEFINIDO"
        if nivel == 3:
            return None, "NIVEL FORA DO ESCOPO (3)"
        if ano is None:
            return None, "SEM ANO NO NOME"
        regs = regulares.get((school_id, ano), [])
        if not regs:
            return None, "SEM TURMA REGULAR DO ANO"
        if len(regs) == 1:
            return regs[0], "OK"
        turmas_a = [c for c in regs if str(c.name or "").strip().upper() == "A"]
        if not turmas_a:
            return None, "SEM TURMA A"
        if len(turmas_a) > 1:
            return None, "MAIS DE UMA TURMA A"
        return turmas_a[0], "OK"

    rows = []
    for s in students:
        if not s.class_id or not s.school_id:
            continue
        c = classes.get(str(s.class_id))
        if c is None or str(s.school_id) not in schools:
            continue
        g = grade_of(c)
        if g is None:
            continue
        nome_norm = nome_normalizado(s.name)
        login = (emails.get(s.user_id) or "").split("@")[0].lower() if emails.get(s.user_id) else None
        rows.append({
            "id": str(s.id), "name": s.name, "school_id": str(s.school_id), "class_id": str(s.class_id),
            "class_name": c.name, "user_id": s.user_id, "especial": serie_especial(g),
            "nivel": nivel_da_serie(g.name),
            "ano": ano_do_texto(g.name) if ano_do_texto(g.name) is not None else ano_do_texto(c.name),
            "ano_turma": ano_do_texto(c.name),
            "nome_norm": nome_norm,
            "iniciais": "".join(w[:1] for w in nome_norm.split(" ")),
            "primeiro": nome_norm.split(" ")[0] if nome_norm else "",
            "login_base": re.sub(r"\d+$", "", login) if login is not None else None,
            "notas": int(er.get(str(s.id), 0) or 0) + int(asr.get(str(s.id), 0) or 0),
            "respondeu": bool(s.user_id and s.user_id in respondeu),
            "formularios": estado_form.get(s.user_id, {}) if s.user_id else {},
        })

    sup = [r for r in rows if r["especial"]]
    regs_by_school: Dict[str, List[dict]] = defaultdict(list)
    for r in rows:
        if not r["especial"]:
            regs_by_school[r["school_id"]].append(r)
    multi = Counter((r["school_id"], r["nome_norm"]) for r in sup)

    selecao = Selecao()
    for s in sup:
        if escola_ids and s["school_id"] not in escola_ids:
            continue
        dest, situacao = destino(s["school_id"], s["ano_turma"], s["nivel"])
        cand = Candidato(
            student_id=s["id"], nome=s["name"], escola_id=s["school_id"], escola=schools.get(s["school_id"], ""),
            turma_suporte_id=s["class_id"], turma_suporte=s["class_name"], nivel=s["nivel"], ano=s["ano"],
            destino_id=_sid(dest.id) if dest is not None else None,
            destino=dest.name if dest is not None else None, situacao_destino=situacao,
            notas_suporte=s["notas"],
        )
        # Pares com cadastros regulares (C3)
        pares = []
        for r in regs_by_school.get(s["school_id"], []):
            mesmo_ano = s["ano"] is not None and s["ano"] == r["ano"]
            ini = mesmo_ano and s["iniciais"] == r["iniciais"] and s["primeiro"] == r["primeiro"]
            log = mesmo_ano and bool(s["login_base"]) and s["login_base"] == r["login_base"]
            if not (s["nome_norm"] == r["nome_norm"] or ini or log):
                continue
            if s["nome_norm"] == r["nome_norm"] and mesmo_ano:
                crit = "A_FORTE_nome_e_ano"
            elif ini:
                crit = "B_MEDIO_iniciais_1nome_ano"
            elif mesmo_ano and s["login_base"] is not None and s["login_base"] == r["login_base"]:
                crit = "C_FRACO_login_ano"
            else:
                crit = "D_HOMONIMO_outro_ano"
            pares.append((crit, r))
        pares.sort(key=lambda p: p[0])
        melhor = pares[0] if pares else None
        fortes = [p for p in pares if p[0].startswith("A")]
        if melhor and not melhor[0].startswith("D"):
            crit, r = melhor
            cand.criterio = crit
            cand.regular_id, cand.regular_nome, cand.regular_turma = r["id"], r["name"], r["class_name"]
            cand.notas_regular = r["notas"]
            if s["notas"] > 0 and r["notas"] > 0:
                cand.categoria = "DUP_nota_nos_dois"
            elif s["notas"] > 0:
                cand.categoria = "DUP_nota_so_no_suporte"
            elif r["notas"] > 0:
                cand.categoria = "DUP_nota_so_no_regular"
            else:
                cand.categoria = "DUP_sem_nota_em_nenhum"
        else:
            cand.criterio = melhor[0] if melhor else None
            cand.categoria = "SO_NO_SUPORTE_com_nota" if s["notas"] > 0 else "SO_NO_SUPORTE_sem_nota"

        # Motivo de exclusão (primeiro que se aplica)
        tem_prova_aberta = s["id"] in sessoes_abertas or bool(
            abertas_por_turma.get(s["class_id"], set()) - feitas.get(s["id"], set())
        )
        if s["nivel"] == 3:
            cand.motivo = "suporte_3"
        elif s["nivel"] is None:
            cand.motivo = "nivel_indefinido"
        elif dest is None:
            cand.motivo = "sem_destino"
        elif multi[(s["school_id"], s["nome_norm"])] > 1:
            cand.motivo = "mais_de_uma_turma_suporte"
        elif tem_prova_aberta:
            cand.motivo = "prova_em_andamento"
        elif melhor and melhor[0].startswith("D"):
            cand.motivo = "homonimo_outro_ano"
        elif cand.regular_id and not cand.criterio.startswith("A"):
            cand.motivo = "duplicado_iniciais_ou_login"
        elif cand.regular_id and len(fortes) > 1:
            cand.motivo = "mais_de_um_candidato_forte"
        elif cand.categoria == "DUP_nota_nos_dois":
            cand.motivo = "nota_nos_dois"
        elif cand.categoria == "DUP_nota_so_no_regular":
            cand.motivo = "nota_so_no_regular"
        elif cand.categoria == "DUP_sem_nota_em_nenhum":
            cand.motivo = "sem_nota_em_nenhum"
        elif not incluir_questionario_descartado and cand.regular_id and melhor[1]["respondeu"] and not s["respondeu"]:
            cand.motivo = "questionario_no_descartado"
        elif incluir_questionario_descartado and cand.regular_id and conflito_questionario(
            melhor[1]["formularios"], s["formularios"]
        ):
            cand.motivo = "questionario_nos_dois"
        if cand.motivo is None and excluir_alunos and s["id"] in excluir_alunos:
            cand.motivo = "excluido_manual"

        (selecao.elegiveis if cand.elegivel else selecao.excluidos).append(cand)

    selecao.elegiveis.sort(key=lambda c: (c.escola, c.turma_suporte, c.nivel or 0, c.nome))
    selecao.excluidos.sort(key=lambda c: (c.escola, c.motivo or "", c.nome))
    return selecao


def resolver_escolas(escola: Optional[str]) -> Optional[Set[str]]:
    """Aceita id exato ou parte do nome (precisa casar uma única escola)."""
    if not escola:
        return None
    from app.models.school import School

    rows = School.query.all()
    exact = [s for s in rows if str(s.id) == escola]
    if exact:
        return {str(exact[0].id)}
    alvo = nome_normalizado(escola)
    found = [s for s in rows if alvo and alvo in nome_normalizado(s.name)]
    if len(found) != 1:
        nomes = ", ".join(sorted(s.name for s in found)) or "nenhuma"
        raise MigracaoError(f"--escola '{escola}' casou {len(found)} escola(s): {nomes}")
    return {str(found[0].id)}


# ---------------------------------------------------------------------------
# Snapshots (antes/depois) para o log e a reversão
# ---------------------------------------------------------------------------

def _snapshot(student) -> Dict[str, Any]:
    from app import db
    from app.models.studentPasswordLog import StudentPasswordLog
    from app.models.studentSchoolEnrollment import StudentSchoolEnrollment
    from app.socioeconomic_forms.models.form_recipient import FormRecipient

    db.session.flush()
    user = student.user
    enrollments = (
        StudentSchoolEnrollment.query.filter(StudentSchoolEnrollment.student_id == student.id)
        .order_by(StudentSchoolEnrollment.valid_from).all()
    )
    recipients = FormRecipient.query.filter(FormRecipient.user_id == student.user_id).all() if student.user_id else []
    logs = StudentPasswordLog.query.filter(StudentPasswordLog.student_id == student.id).all()
    return {
        "student": {
            "class_id": _sid(student.class_id),
            "school_id": _sid(student.school_id),
            "grade_id": _sid(student.grade_id),
            "subturma_id": _sid(student.subturma_id),
        },
        "user": {
            "id": _sid(student.user_id),
            "city_id": _sid(getattr(user, "city_id", None)),
            "traits": copy.deepcopy(getattr(user, "traits", None)),
        },
        "matriculas": [
            {"id": e.id, "school_id": _sid(e.school_id), "class_id": _sid(e.class_id),
             "valid_from": _iso(e.valid_from), "valid_to": _iso(e.valid_to)}
            for e in enrollments
        ],
        "destinatarios": [
            {"id": r.id, "form_id": r.form_id, "status": r.status, "school_id": _sid(r.school_id)}
            for r in recipients
        ],
        "logs_senha": [
            {"id": l.id, "class_id": _sid(l.class_id), "grade_id": _sid(l.grade_id),
             "school_id": _sid(l.school_id), "city_id": _sid(l.city_id)}
            for l in logs
        ],
    }


def _user_respondeu(user_id: Optional[str]) -> bool:
    if not user_id:
        return False
    from app.socioeconomic_forms.models.form_recipient import FormRecipient
    from app.socioeconomic_forms.models.form_response import FormResponse

    if FormResponse.query.filter(FormResponse.user_id == user_id, FormResponse.status == "completed").first():
        return True
    return bool(
        FormRecipient.query.filter(FormRecipient.user_id == user_id, FormRecipient.status == "completed").first()
    )


def _novos_destinatarios_previstos(student, destino_class, ja_extra: Iterable[str] = ()) -> List[str]:
    """Formulários ativos que passariam a incluir o aluno na turma de destino (simulação)."""
    from app.socioeconomic_forms.models.form import Form
    from app.socioeconomic_forms.models.form_recipient import FormRecipient
    from app.socioeconomic_forms.services.distribution_service import DistributionService

    if not student.user_id or destino_class is None or not destino_class.grade_id:
        return []
    ja = {r.form_id for r in FormRecipient.query.filter(FormRecipient.user_id == student.user_id).all()}
    ja |= set(ja_extra)
    forms = Form.query.filter(Form.is_active.is_(True), Form.form_type.in_(STUDENT_FORM_TYPES)).all()
    return [
        f.id for f in forms
        if f.id not in ja and DistributionService._student_matches_form_scope(
            f, str(destino_class.school_id), str(destino_class.grade_id), str(destino_class.id)
        )
    ]


# ---------------------------------------------------------------------------
# Questionário: do cadastro descartado para o mantido
# ---------------------------------------------------------------------------

def _linha(obj) -> Dict[str, Any]:
    from sqlalchemy import inspect as sa_inspect

    return {attr.key: getattr(obj, attr.key) for attr in sa_inspect(obj).mapper.column_attrs}


def _recriar(model, dados: Dict[str, Any]):
    from decimal import Decimal
    from sqlalchemy import DateTime, Numeric, inspect as sa_inspect

    valores = {}
    for attr in sa_inspect(model).column_attrs:
        if attr.key not in dados:
            continue
        valor = dados[attr.key]
        tipo = attr.columns[0].type
        if isinstance(valor, str) and isinstance(tipo, DateTime):
            valor = datetime.fromisoformat(valor)
        elif isinstance(valor, str) and isinstance(tipo, Numeric):
            valor = Decimal(valor)
        valores[attr.key] = valor
    return model(**valores)


def plano_questionario(regular_user_id: Optional[str], mantido_user_id: Optional[str]) -> Dict[str, Any]:
    """O que acontece com cada formulário do usuário descartado (sem gravar)."""
    from app.socioeconomic_forms.models.form_recipient import FormRecipient
    from app.socioeconomic_forms.models.form_response import FormResponse

    plano: Dict[str, Any] = {"usuario_regular": regular_user_id, "usuario_mantido": mantido_user_id,
                             "mover": [], "remover_do_mantido": [], "ficam_no_descartado": [], "conflitos": []}
    if not regular_user_id or not mantido_user_id or regular_user_id == mantido_user_id:
        return plano

    def por_form(model, uid):
        return {r.form_id: r for r in model.query.filter(model.user_id == uid).all()}

    rec_reg, resp_reg = por_form(FormRecipient, regular_user_id), por_form(FormResponse, regular_user_id)
    rec_man, resp_man = por_form(FormRecipient, mantido_user_id), por_form(FormResponse, mantido_user_id)

    def estado(rec, resp):
        estados = [_estado_formulario(x.status) for x in (rec, resp) if x is not None]
        return max(estados, key=_ORDEM_ESTADO_FORM.get) if estados else None

    for fid in sorted(set(rec_reg) | set(resp_reg)):
        rec, resp = rec_reg.get(fid), resp_reg.get(fid)
        item = {"form_id": fid, "recipient_id": rec.id if rec else None,
                "response_id": resp.id if resp else None, "estado": estado(rec, resp)}
        estado_man = estado(rec_man.get(fid), resp_man.get(fid))
        if estado_man is None:
            plano["mover"].append(item)
        elif item["estado"] == "respondido" and estado_man == "pendente":
            plano["remover_do_mantido"].append({"form_id": fid, "recipient_id": getattr(rec_man.get(fid), "id", None),
                                                "response_id": getattr(resp_man.get(fid), "id", None)})
            plano["mover"].append(item)
        elif item["estado"] == "respondido":
            plano["conflitos"].append({**item, "estado_mantido": estado_man})
        else:
            plano["ficam_no_descartado"].append({**item, "estado_mantido": estado_man})
    return plano


def _mover_questionario(regular, aluno) -> Dict[str, Any]:
    """Passa destinatários e respostas do usuário descartado para o mantido; o log guarda o que saiu."""
    from app import db
    from app.socioeconomic_forms.models.form_recipient import FormRecipient
    from app.socioeconomic_forms.models.form_response import FormResponse

    plano = plano_questionario(_sid(regular.user_id), _sid(aluno.user_id))
    if plano["conflitos"]:
        raise MigracaoError(f"Os dois cadastros responderam o mesmo formulário: {plano['conflitos']}")

    removidos = []
    for alvo in plano["remover_do_mantido"]:
        rec = FormRecipient.query.get(alvo["recipient_id"]) if alvo["recipient_id"] else None
        resp = FormResponse.query.get(alvo["response_id"]) if alvo["response_id"] else None
        removidos.append({"form_id": alvo["form_id"],
                          "destinatario": _linha(rec) if rec else None,
                          "resposta": _linha(resp) if resp else None})
        if resp is not None:
            db.session.delete(resp)
        if rec is not None:
            db.session.delete(rec)
    db.session.flush()

    rec_ids = [m["recipient_id"] for m in plano["mover"] if m["recipient_id"]]
    resp_ids = [m["response_id"] for m in plano["mover"] if m["response_id"]]
    if rec_ids:
        db.session.query(FormRecipient).filter(FormRecipient.id.in_(rec_ids)).update(
            {FormRecipient.user_id: plano["usuario_mantido"]}, synchronize_session=False)
    if resp_ids:
        # updated_at tem onupdate=now(); a troca de dono não é uma edição da resposta.
        db.session.query(FormResponse).filter(FormResponse.id.in_(resp_ids)).update(
            {FormResponse.user_id: plano["usuario_mantido"], FormResponse.updated_at: FormResponse.updated_at},
            synchronize_session=False)
    db.session.flush()
    db.session.expire_all()
    return {"usuario_regular": plano["usuario_regular"], "usuario_mantido": plano["usuario_mantido"],
            "movidos": plano["mover"], "removidos_do_mantido": removidos,
            "ficam_no_descartado": plano["ficam_no_descartado"]}


def _desfazer_questionario(mov: Optional[Dict[str, Any]], conflitos: List[str]) -> None:
    from app import db
    from app.socioeconomic_forms.models.form_recipient import FormRecipient
    from app.socioeconomic_forms.models.form_response import FormResponse

    if not mov or not (mov.get("movidos") or mov.get("removidos_do_mantido")):
        return
    reg_uid, man_uid = mov["usuario_regular"], mov["usuario_mantido"]
    for model, chave in ((FormRecipient, "recipient_id"), (FormResponse, "response_id")):
        ids = [m[chave] for m in mov.get("movidos", []) if m.get(chave)]
        if not ids:
            continue
        atuais = {r.id: r.user_id for r in model.query.filter(model.id.in_(ids)).all()}
        devolver = [i for i in ids if atuais.get(i) == man_uid]
        for i in ids:
            if i not in devolver:
                conflitos.append(f"{model.__tablename__} {i}: dono atual {atuais.get(i)!r}, esperado {man_uid}; não devolvido")
        if devolver:
            valores = {model.user_id: reg_uid}
            if model is FormResponse:
                valores[FormResponse.updated_at] = FormResponse.updated_at
            db.session.query(model).filter(model.id.in_(devolver)).update(valores, synchronize_session=False)
    db.session.flush()

    for rem in mov.get("removidos_do_mantido", []):
        for model, chave in ((FormRecipient, "destinatario"), (FormResponse, "resposta")):
            dados = rem.get(chave)
            if not dados:
                continue
            ocupado = model.query.filter(model.form_id == dados["form_id"], model.user_id == dados["user_id"]).first()
            if model.query.get(dados["id"]) is not None or ocupado is not None:
                conflitos.append(f"{model.__tablename__} {dados['id']} (form {dados['form_id']}) não recriado: já existe")
                continue
            db.session.add(_recriar(model, dados))
            db.session.flush()
    db.session.expire_all()


# ---------------------------------------------------------------------------
# Execução
# ---------------------------------------------------------------------------

def _get_or_create_subturma(class_obj, nivel: int) -> Tuple[Any, bool]:
    from app.models.subturma import Subturma
    from app.services.subturma_service import create_subturma

    existing = Subturma.query.filter(Subturma.class_id == class_obj.id, Subturma.support_level == nivel).first()
    if existing is not None:
        return existing, False
    return create_subturma(class_obj, nivel), True


def _migrar_um(
    cand: Candidato, questionario: str, agora: datetime, mover_questionario: bool = False
) -> Dict[str, Any]:
    from app import db
    from app.models.student import Student
    from app.models.studentClass import Class
    from app.services.student_enrollment_service import close_active_enrollment, transfer_student_to_class
    from app.services.subturma_service import link_student_to_subturma
    from app.socioeconomic_forms.models.form_recipient import FormRecipient

    aluno = Student.query.get(cand.student_id)
    destino = Class.query.get(_uuid(cand.destino_id))
    regular = Student.query.get(cand.regular_id) if cand.regular_id else None
    entry: Dict[str, Any] = {
        "student_id": cand.student_id, "nome": cand.nome, "escola": cand.escola, "tipo": cand.tipo,
        "nivel": cand.nivel, "turma_suporte": cand.turma_suporte, "destino": cand.destino,
        "destino_id": cand.destino_id, "regular_id": cand.regular_id,
        "antes": {"aluno": _snapshot(aluno), "regular": _snapshot(regular) if regular else None},
    }
    entry["questionario_movido"] = (
        _mover_questionario(regular, aluno) if regular is not None and mover_questionario else None
    )
    movidos_ids = {m["recipient_id"] for m in (entry["questionario_movido"] or {}).get("movidos", [])}

    subturma, criada = _get_or_create_subturma(destino, int(cand.nivel))
    entry["subturma_id"] = _sid(subturma.id)
    entry["subturma_criada"] = criada

    transfer_student_to_class(db.session, aluno, destino)
    db.session.flush()
    link_student_to_subturma(aluno, subturma)
    db.session.flush()

    antes_ids = {r["id"] for r in entry["antes"]["aluno"]["destinatarios"]} | movidos_ids
    novos = [r for r in FormRecipient.query.filter(FormRecipient.user_id == aluno.user_id).all()
             if r.id not in antes_ids] if aluno.user_id else []
    removidos = []
    if novos and questionario == "nao-criar" and _user_respondeu(aluno.user_id):
        for r in novos:
            removidos.append(r.form_id)
            db.session.delete(r)
        db.session.flush()
    entry["questionario"] = {
        "opcao": questionario,
        "novos_destinatarios": [r.form_id for r in novos if r.form_id not in removidos],
        "nao_criados_por_ja_ter_respondido": removidos,
    }

    if regular is not None:
        regular.subturma_id = None
        regular.class_id = None
        regular.school_id = None
        close_active_enrollment(db.session, regular.id, valid_to=agora)
        user = regular.user
        if user is not None:
            traits = dict(user.traits) if isinstance(user.traits, dict) else {}
            traits[DISCARD_TRAIT_KEY] = {
                "motivo": DISCARD_REASON,
                "mantido_student_id": cand.student_id,
                "data": agora.isoformat(),
            }
            user.traits = traits
        db.session.flush()

    entry["depois"] = {"aluno": _snapshot(aluno), "regular": _snapshot(regular) if regular else None}
    return entry


def _default_log_dir() -> str:
    return os.path.join(os.path.expanduser("~"), "afirmeplay_backups", "adap_migracao")


def _assert_log_dir_outside_repo(log_dir: str) -> str:
    repo = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    path = os.path.abspath(log_dir)
    if os.path.commonpath([repo, path]) == repo:
        raise MigracaoError(f"O log contém dados de alunos e não pode ficar dentro do repositório: {path}")
    os.makedirs(path, exist_ok=True)
    return path


def _write_log(log_dir: str, payload: Dict[str, Any], prefix: str) -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    escola = "_escola" if payload.get("escola_filtro") else ""
    path = os.path.join(log_dir, f"{prefix}_{payload['schema']}{escola}_{payload['modo']}_{stamp}.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1, default=str)
    return path


def _resumo_selecao(selecao: Selecao) -> Dict[str, Any]:
    eleg = selecao.elegiveis
    return {
        "elegiveis": len(eleg),
        "por_tipo": dict(Counter(c.tipo for c in eleg)),
        "por_tipo_nivel": {f"{k[0]}|nivel {k[1]}": v for k, v in Counter((c.tipo, c.nivel) for c in eleg).items()},
        "escolas": len({c.escola_id for c in eleg}),
        "por_escola": dict(Counter(c.escola for c in eleg)),
        "subturmas_destino": len({(c.destino_id, c.nivel) for c in eleg}),
        "turmas_destino": len({c.destino_id for c in eleg}),
        "cadastros_regulares_a_desvincular": sum(1 for c in eleg if c.regular_id),
        "excluidos": len(selecao.excluidos),
        "excluidos_por_motivo": dict(Counter(c.motivo for c in selecao.excluidos)),
    }


def _affected_ids(entries: Iterable[Dict[str, Any]]) -> Tuple[Set[str], Set[str], Set[str], Set[str]]:
    classes, schools, students, users = set(), set(), set(), set()
    for e in entries:
        for lado in ("antes", "depois"):
            for chave in ("aluno", "regular"):
                snap = (e.get(lado) or {}).get(chave)
                if not snap:
                    continue
                st = snap["student"]
                if st.get("class_id"):
                    classes.add(st["class_id"])
                if st.get("school_id"):
                    schools.add(st["school_id"])
                if snap["user"].get("id"):
                    users.add(snap["user"]["id"])
        students.add(e["student_id"])
        if e.get("regular_id"):
            students.add(e["regular_id"])
    return classes, schools, students, users


def invalidar_caches(entries: List[Dict[str, Any]]) -> Dict[str, int]:
    """Marca como desatualizados os caches de relatório das provas, gabaritos e formulários afetados."""
    from app import db
    from sqlalchemy import or_
    from app.models.answerSheetGabarito import AnswerSheetGabarito
    from app.models.classTest import ClassTest
    from app.models.evaluationResult import EvaluationResult
    from app.models.test import Test
    from app.report_analysis.answer_sheet_aggregate_service import AnswerSheetReportAggregateService
    from app.report_analysis.services import ReportAggregateService
    from app.socioeconomic_forms.models.form_recipient import FormRecipient
    from app.socioeconomic_forms.services.results_cache_service import ResultsCacheService

    if not entries:
        return {"provas": 0, "gabaritos": 0, "formularios": 0}
    classes, schools, students, users = _affected_ids(entries)
    class_uuids = [_uuid(c) for c in classes]
    tests = {str(t) for (t,) in db.session.query(ClassTest.test_id).filter(ClassTest.class_id.in_(class_uuids)).all()}
    tests |= {str(t) for (t,) in db.session.query(EvaluationResult.test_id)
              .filter(EvaluationResult.student_id.in_(list(students))).distinct().all()}
    if tests and hasattr(Test, "paired_regular_test_id"):
        tests |= {str(p) for (p,) in db.session.query(Test.paired_regular_test_id)
                  .filter(Test.id.in_(list(tests)), Test.paired_regular_test_id.isnot(None)).all()}
    for tid in tests:
        ReportAggregateService.mark_all_dirty_for_test(tid, commit=False)
    gabaritos = [str(g) for (g,) in db.session.query(AnswerSheetGabarito.id).filter(or_(
        AnswerSheetGabarito.class_id.in_(class_uuids),
        AnswerSheetGabarito.school_id.in_(list(schools)),
        AnswerSheetGabarito.scope_type == "city",
    )).all()]
    for gid in gabaritos:
        AnswerSheetReportAggregateService.mark_all_dirty_for_gabarito(gid, commit=False)
    forms = {f for (f,) in db.session.query(FormRecipient.form_id)
             .filter(FormRecipient.user_id.in_(list(users))).distinct().all()} if users else set()
    for e in entries:
        mov = e.get("questionario_movido") or {}
        forms |= {m["form_id"] for m in mov.get("movidos", [])}
        forms |= {m["form_id"] for m in mov.get("removidos_do_mantido", [])}
    for fid in forms:
        ResultsCacheService._mark_dirty_all_for_form(fid, commit=False)
    db.session.commit()
    return {"provas": len(tests), "gabaritos": len(gabaritos), "formularios": len(forms)}


def executar(
    *,
    schema: str,
    escola: Optional[str] = None,
    write: bool = False,
    questionario: Optional[str] = None,
    log_dir: Optional[str] = None,
    confirmar_producao: Optional[str] = None,
    incluir_questionario_descartado: bool = False,
    excluir_alunos: Optional[Set[str]] = None,
) -> Dict[str, Any]:
    """Seleciona a Rodada 1 e, com ``write=True``, migra aluno a aluno (uma transação por aluno).

    ``incluir_questionario_descartado`` (desligado por padrão): inclui quem respondeu o
    questionário só no cadastro descartado, passando as respostas para o cadastro mantido.
    """
    from app import db
    from app.models.student import Student
    from app.models.studentClass import Class

    target = assert_environment(schema, write=write, confirmar_producao=confirmar_producao)
    if write and questionario not in QUESTIONARIO_OPCOES:
        raise MigracaoError("No --write é obrigatório escolher --questionario-quem-respondeu criar|nao-criar.")
    if questionario is not None and questionario not in QUESTIONARIO_OPCOES:
        raise MigracaoError("--questionario-quem-respondeu aceita: criar, nao-criar.")
    log_dir = _assert_log_dir_outside_repo(log_dir or _default_log_dir())
    escola_ids = resolver_escolas(escola)

    excluir_alunos = {str(i).strip() for i in (excluir_alunos or []) if str(i).strip()}
    selecao = selecionar_rodada1(escola_ids, incluir_questionario_descartado, excluir_alunos)
    resumo = _resumo_selecao(selecao)

    # Impacto no questionário (as duas opções), calculado sem gravar
    previsao = {"alunos_com_formulario_novo": 0, "destinatarios_novos": 0,
                "alunos_que_ja_responderam_com_formulario_novo": 0, "destinatarios_novos_de_quem_ja_respondeu": 0}
    mover = {"alunos": 0, "destinatarios": 0, "respostas": 0, "removidos_do_mantido": 0,
             "ficam_no_descartado": 0, "por_aluno": []}
    for cand in selecao.elegiveis:
        aluno = Student.query.get(cand.student_id)
        regular = Student.query.get(cand.regular_id) if cand.regular_id else None
        plano = (
            plano_questionario(_sid(regular.user_id), _sid(aluno.user_id))
            if regular is not None and incluir_questionario_descartado else None
        )
        if plano and (plano["mover"] or plano["ficam_no_descartado"]):
            mover["alunos"] += 1
            mover["destinatarios"] += sum(1 for m in plano["mover"] if m["recipient_id"])
            mover["respostas"] += sum(1 for m in plano["mover"] if m["response_id"])
            mover["removidos_do_mantido"] += len(plano["remover_do_mantido"])
            mover["ficam_no_descartado"] += len(plano["ficam_no_descartado"])
            mover["por_aluno"].append({"student_id": cand.student_id, "nome": cand.nome, **plano})
        movidos = [m["form_id"] for m in plano["mover"]] if plano else []
        novos = _novos_destinatarios_previstos(aluno, Class.query.get(_uuid(cand.destino_id)), movidos)
        if novos:
            previsao["alunos_com_formulario_novo"] += 1
            previsao["destinatarios_novos"] += len(novos)
            respondeu_movido = any(m["estado"] == "respondido" for m in (plano or {}).get("mover", []))
            if _user_respondeu(aluno.user_id) or respondeu_movido:
                previsao["alunos_que_ja_responderam_com_formulario_novo"] += 1
                previsao["destinatarios_novos_de_quem_ja_respondeu"] += len(novos)
    resumo["questionario_previsto"] = {
        "opcao_criar": previsao["destinatarios_novos"],
        "opcao_nao_criar": previsao["destinatarios_novos"] - previsao["destinatarios_novos_de_quem_ja_respondeu"],
        **previsao,
    }
    resumo["questionario_mover"] = mover
    db.session.rollback()

    payload: Dict[str, Any] = {
        "tipo": "adap_migracao_suporte_rodada1",
        "schema": schema, "escola_filtro": escola, "escola_ids": sorted(escola_ids or []),
        "modo": "gravacao" if write else "simulacao", "questionario_quem_respondeu": questionario,
        "incluir_questionario_descartado": incluir_questionario_descartado,
        "excluir_alunos": sorted(excluir_alunos),
        "banco": target, "inicio": datetime.now().isoformat(),
        "resumo": resumo,
        "elegiveis": [c.as_dict() for c in selecao.elegiveis],
        "excluidos": [c.as_dict() for c in selecao.excluidos],
        "alunos": [], "erros": [],
    }

    if write:
        agora = datetime.utcnow()
        for cand in selecao.elegiveis:
            try:
                entry = _migrar_um(cand, questionario, agora, incluir_questionario_descartado)
                db.session.commit()
                payload["alunos"].append(entry)
            except Exception as exc:  # um aluno com erro não interrompe os demais
                db.session.rollback()
                logger.exception("Falha ao migrar aluno %s", cand.student_id)
                payload["erros"].append({"student_id": cand.student_id, "nome": cand.nome, "erro": str(exc)})
        payload["subturmas_criadas"] = sorted({e["subturma_id"] for e in payload["alunos"] if e["subturma_criada"]})
        payload["caches"] = invalidar_caches(payload["alunos"])
        payload["gravados"] = len(payload["alunos"])
    payload["fim"] = datetime.now().isoformat()
    payload["log"] = _write_log(log_dir, payload, "adap_rodada1")
    return payload


# ---------------------------------------------------------------------------
# Reversão
# ---------------------------------------------------------------------------

def _estado_atual_confere(student, esperado: Dict[str, Any]) -> bool:
    atual = _snapshot(student)["student"]
    return all(atual.get(k) == esperado["student"].get(k) for k in ("class_id", "school_id", "subturma_id"))


def _restaurar(student, antes: Dict[str, Any], depois: Dict[str, Any], conflitos: List[str]) -> None:
    from app import db
    from app.models.studentPasswordLog import StudentPasswordLog
    from app.models.studentSchoolEnrollment import StudentSchoolEnrollment
    from app.models.user import User
    from app.socioeconomic_forms.models.form_recipient import FormRecipient

    st = antes["student"]
    student.subturma_id = None
    db.session.flush()
    student.class_id = _uuid(st["class_id"])
    student.school_id = st["school_id"]
    student.grade_id = _uuid(st["grade_id"])
    db.session.flush()
    student.subturma_id = _uuid(st["subturma_id"])

    user = User.query.get(antes["user"]["id"]) if antes["user"].get("id") else None
    if user is not None:
        user.city_id = antes["user"]["city_id"]
        user.traits = copy.deepcopy(antes["user"]["traits"])

    antes_mat = {m["id"]: m for m in antes["matriculas"]}
    matriculas = StudentSchoolEnrollment.query.filter(StudentSchoolEnrollment.student_id == student.id).all()
    for e in matriculas:
        if e.id not in antes_mat:
            db.session.delete(e)
    # uq_student_school_enrollment_one_active: a matrícula nova sai antes de a antiga reabrir.
    db.session.flush()
    for e in matriculas:
        if e.id in antes_mat:
            e.valid_to = _dt(antes_mat[e.id]["valid_to"])

    if student.user_id:
        antes_dest = {r["id"] for r in antes["destinatarios"]}
        for r in FormRecipient.query.filter(FormRecipient.user_id == student.user_id).all():
            if r.id in antes_dest:
                continue
            if r.status == "pending":
                db.session.delete(r)
            else:
                conflitos.append(f"destinatário {r.id} (form {r.form_id}) já está '{r.status}'; mantido")

    antes_logs = {l["id"]: l for l in antes["logs_senha"]}
    for l in StudentPasswordLog.query.filter(StudentPasswordLog.student_id == student.id).all():
        if l.id not in antes_logs:
            db.session.delete(l)
            continue
        old = antes_logs[l.id]
        l.class_id = _uuid(old["class_id"])
        l.grade_id = _uuid(old["grade_id"])
        l.school_id = old["school_id"]
        l.city_id = old["city_id"]
    db.session.flush()


def reverter(
    *,
    log_path: str,
    write: bool = False,
    forcar: bool = False,
    log_dir: Optional[str] = None,
    confirmar_producao: Optional[str] = None,
) -> Dict[str, Any]:
    """Desfaz uma gravação a partir do log. Simulação por padrão."""
    from app import db
    from app.models.student import Student
    from app.models.subturma import Subturma

    with open(log_path, encoding="utf-8") as fh:
        origem = json.load(fh)
    if origem.get("tipo") != "adap_migracao_suporte_rodada1" or origem.get("modo") != "gravacao":
        raise MigracaoError("O log informado não é de uma gravação da migração ADAP.")
    schema = origem["schema"]
    target = assert_environment(schema, write=write, confirmar_producao=confirmar_producao)
    if origem.get("banco", {}).get("host") != target["host"] or origem.get("banco", {}).get("database") != target["database"]:
        raise MigracaoError(
            f"O log foi gravado em {origem.get('banco')} e o banco atual é {target}. Reversão recusada."
        )
    log_dir = _assert_log_dir_outside_repo(log_dir or _default_log_dir())

    resultado: Dict[str, Any] = {
        "tipo": "adap_migracao_suporte_reversao", "schema": schema, "escola_filtro": origem.get("escola_filtro"),
        "modo": "gravacao" if write else "simulacao", "log_origem": log_path, "banco": target,
        "inicio": datetime.now().isoformat(), "alunos": [], "erros": [],
    }
    for entry in reversed(origem.get("alunos", [])):
        item = {"student_id": entry["student_id"], "nome": entry["nome"], "regular_id": entry.get("regular_id")}
        try:
            aluno = Student.query.get(entry["student_id"])
            regular = Student.query.get(entry["regular_id"]) if entry.get("regular_id") else None
            if _estado_atual_confere(aluno, entry["antes"]["aluno"]) and (
                regular is None or _estado_atual_confere(regular, entry["antes"]["regular"])
            ):
                item["situacao"] = "ja_revertido"
            elif not _estado_atual_confere(aluno, entry["depois"]["aluno"]) or (
                regular is not None and not _estado_atual_confere(regular, entry["depois"]["regular"])
            ):
                item["situacao"] = "conflito_estado_mudou" if not forcar else "forcado"
            else:
                item["situacao"] = "a_reverter"
            if item["situacao"] in ("a_reverter", "forcado") and write:
                conflitos: List[str] = []
                _desfazer_questionario(entry.get("questionario_movido"), conflitos)
                _restaurar(aluno, entry["antes"]["aluno"], entry["depois"]["aluno"], conflitos)
                if regular is not None:
                    _restaurar(regular, entry["antes"]["regular"], entry["depois"]["regular"], conflitos)
                db.session.commit()
                item["situacao"] = "revertido"
                item["avisos"] = conflitos
            else:
                db.session.rollback()
        except Exception as exc:
            db.session.rollback()
            logger.exception("Falha ao reverter aluno %s", entry.get("student_id"))
            item["situacao"] = "erro"
            resultado["erros"].append({"student_id": entry.get("student_id"), "erro": str(exc)})
        resultado["alunos"].append(item)

    subturmas = []
    for sub_id in origem.get("subturmas_criadas", []):
        sub = Subturma.query.get(_uuid(sub_id))
        if sub is None:
            subturmas.append({"id": sub_id, "situacao": "ja_removida"})
            continue
        vinculados = Student.query.filter(Student.subturma_id == sub.id).count()
        if vinculados:
            subturmas.append({"id": sub_id, "situacao": f"mantida ({vinculados} aluno(s) vinculado(s))"})
            continue
        if write:
            db.session.delete(sub)
            db.session.commit()
            subturmas.append({"id": sub_id, "situacao": "removida"})
        else:
            subturmas.append({"id": sub_id, "situacao": "seria_removida"})
    resultado["subturmas"] = subturmas
    resultado["resumo"] = dict(Counter(a["situacao"] for a in resultado["alunos"]))
    if write:
        resultado["caches"] = invalidar_caches(origem.get("alunos", []))
    resultado["fim"] = datetime.now().isoformat()
    resultado["log"] = _write_log(log_dir, resultado, "adap_reversao")
    return resultado
