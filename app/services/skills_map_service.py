# -*- coding: utf-8 -*-
"""
Agregação do mapa de habilidades (% acertos por faixa) e drill-down de alunos que erraram.
Avaliação online (Test + StudentAnswer) e cartão-resposta (AnswerSheetGabarito + AnswerSheetResult).
"""
from __future__ import annotations

import json
import unicodedata
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple
from uuid import UUID

from sqlalchemy.orm import joinedload

from app.answer_sheets.models.answerSheetGabarito import AnswerSheetGabarito
from app.answer_sheets.models.answerSheetResult import AnswerSheetResult
from app.evaluations.models.evaluationResult import EvaluationResult
from app.exams.models.question import Question
from app.models.skill import Skill
from app.models.subject import Subject
from app.models.student import Student
from app.exams.models.studentAnswer import StudentAnswer
from app.models.studentClass import Class
from app.exams.models.testQuestion import TestQuestion
from app.reports.report_analysis.answer_sheet_report_builder import question_skills_map_for_answer_sheet
from app.answer_sheets.services.cartao_resposta.proficiency_by_subject import _extract_blocks_with_questions
from app.evaluations.services.evaluation_result_service import EvaluationResultService
from app.utils.decimal_helpers import round_to_two_decimals

FAIXA_ABAIXO = "abaixo_do_basico"
FAIXA_BASICO = "basico"
FAIXA_ADEQUADO = "adequado"
FAIXA_AVANCADO = "avancado"


def faixa_from_percent(pct: float) -> str:
    if pct < 30:
        return FAIXA_ABAIXO
    if pct < 60:
        return FAIXA_BASICO
    if pct < 80:
        return FAIXA_ADEQUADO
    return FAIXA_AVANCADO


def _clean_skill_id(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    s = str(raw).replace("{", "").replace("}", "").strip()
    return s or None


def _norm_skill_key(sid: str) -> str:
    try:
        return str(UUID(str(sid).strip()))
    except ValueError:
        return str(sid).strip()


def _digital_stat_bucket_key(skill_norm: str, question_ref: str) -> str:
    return f"{skill_norm}||q:{str(question_ref).strip()}"


def _habilidade_codigo_e_descricao(sk: str, obj: Optional[Skill]) -> Tuple[str, str]:
    """
    Textos para o mapa / modal: não usar UUID como código ou título.
    """
    if obj:
        code = (getattr(obj, "code", None) or "").strip()
        desc = (getattr(obj, "description", None) or "").strip()
        if code:
            return code, (desc or "—")
        if desc:
            short = desc if len(desc) <= 80 else f"{desc[:77]}…"
            return short, desc
        return "Habilidade", "—"
    return (
        "Habilidade (sem cadastro)",
        "Esta habilidade não foi encontrada na base de habilidades.",
    )


def _fetch_skills_batch(skill_ids: Set[str]) -> Dict[str, Skill]:
    uuids = []
    for raw in skill_ids:
        if not raw:
            continue
        try:
            uuids.append(UUID(str(raw).strip()))
        except ValueError:
            continue
    if not uuids:
        return {}
    rows = Skill.query.filter(Skill.id.in_(uuids)).all()
    return {str(s.id): s for s in rows}


def _extract_skill_ids_from_question_field(raw_skill: Any) -> List[str]:
    """Extrai IDs/códigos de habilidade do campo `Question.skill` (string/lista/json)."""
    if raw_skill is None:
        return []

    values: List[str] = []
    if isinstance(raw_skill, list):
        values = [str(x) for x in raw_skill if x]
    else:
        s = str(raw_skill).strip()
        if not s:
            return []
        if s.startswith("[") and s.endswith("]"):
            try:
                parsed = json.loads(s)
                if isinstance(parsed, list):
                    values = [str(x) for x in parsed if x]
                else:
                    values = [s]
            except Exception:
                values = [s]
        else:
            # Historicamente pode vir "id1,id2" ou único valor.
            values = [p.strip() for p in s.split(",") if p and p.strip()]

    out: List[str] = []
    seen: Set[str] = set()
    for v in values:
        clean = _clean_skill_id(v)
        if not clean:
            continue
        if clean not in seen:
            out.append(clean)
            seen.add(clean)
    return out


def _fallback_question_skills_from_test(
    test_id: Optional[str], allowed_qn: Set[int]
) -> Dict[int, List[str]]:
    """Fallback para mapa de questões→habilidades via prova vinculada ao gabarito."""
    if not test_id:
        return {}

    test_questions = (
        TestQuestion.query.filter_by(test_id=test_id)
        .join(Question)
        .options(joinedload(TestQuestion.question))
        .order_by(TestQuestion.order)
        .all()
    )
    if not test_questions:
        return {}

    out: Dict[int, List[str]] = {}
    for idx, tq in enumerate(test_questions, start=1):
        qn = idx
        try:
            if tq.order is not None:
                qn = int(tq.order)
        except (TypeError, ValueError):
            qn = idx

        if allowed_qn and qn not in allowed_qn:
            continue
        q = tq.question
        if not q:
            continue
        sids = _extract_skill_ids_from_question_field(getattr(q, "skill", None))
        if sids:
            out[qn] = sids
    return out


def build_disciplinas_e_questoes_digital(
    test_id: str,
    subject_id_filter: Optional[str],
) -> Tuple[List[Dict[str, str]], List[Tuple[Question, str]]]:
    """
    Retorna disciplinas disponíveis (id/nome) e lista (Question, clean_skill_id) respeitando filtro de disciplina.
    subject_id_filter None ou 'all' = todas as disciplinas.
    """
    test_questions = (
        TestQuestion.query.filter_by(test_id=test_id)
        .join(Question)
        .options(joinedload(TestQuestion.question).joinedload(Question.subject))
        .order_by(TestQuestion.order)
        .all()
    )

    by_subject: Dict[str, str] = {}
    questoes_com_habilidade: List[Tuple[Question, str]] = []

    for tq in test_questions:
        q = tq.question
        sid_subj = str(q.subject_id) if q.subject_id else "sem_disciplina"
        nome = q.subject.name if q.subject else "Sem Disciplina"
        by_subject[sid_subj] = nome

        sk = _clean_skill_id(q.skill)
        if not sk:
            continue
        if subject_id_filter and str(subject_id_filter).strip().lower() not in ("", "all"):
            if sid_subj != str(subject_id_filter).strip():
                continue
        questoes_com_habilidade.append((q, sk))

    disciplinas = [{"id": k, "nome": v} for k, v in sorted(by_subject.items(), key=lambda x: x[1])]
    return disciplinas, questoes_com_habilidade


def compute_digital_aggregate(
    test_id: str,
    students: List[Student],
    subject_id_filter: Optional[str],
) -> Dict[str, Any]:
    disciplinas, questoes_com_habilidade = build_disciplinas_e_questoes_digital(test_id, subject_id_filter)
    skill_ids_set = {sid for _, sid in questoes_com_habilidade}
    skills_db = _fetch_skills_batch(skill_ids_set)

    if not students:
        return {
            "disciplinas_disponiveis": disciplinas,
            "habilidades": [],
            "por_faixa": {FAIXA_ABAIXO: [], FAIXA_BASICO: [], FAIXA_ADEQUADO: [], FAIXA_AVANCADO: []},
            "_skill_to_question_ids": {},
        }

    student_ids = [s.id for s in students]
    answers_rows = StudentAnswer.query.filter(
        StudentAnswer.test_id == test_id,
        StudentAnswer.student_id.in_(student_ids),
    ).all()
    answers_by_student: Dict[str, Dict[str, StudentAnswer]] = {}
    for a in answers_rows:
        if a.student_id not in answers_by_student:
            answers_by_student[a.student_id] = {}
        answers_by_student[a.student_id][a.question_id] = a

    # Participante = mesmo critério de GET /evaluation-results/avaliacoes: existe
    # `evaluation_results` para o teste (rascunho só com StudentAnswer não conta).
    eval_student_ids = {
        row[0]
        for row in EvaluationResult.query.filter(
            EvaluationResult.test_id == str(test_id),
            EvaluationResult.student_id.in_(student_ids),
        )
        .with_entities(EvaluationResult.student_id)
        .distinct()
        .all()
    }
    participating_students = [s for s in students if s.id in eval_student_ids]

    stats: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {"correct": 0, "total": 0, "question_ref": "", "subject_id": None}
    )
    failed_by_skill: Dict[str, Set[str]] = defaultdict(set)

    for student in participating_students:
        sid = student.id
        for q, skill_key in questoes_com_habilidade:
            sk = _norm_skill_key(skill_key)
            bucket = _digital_stat_bucket_key(sk, str(q.id))
            resposta = answers_by_student.get(sid, {}).get(q.id)
            acertou = False
            if resposta:
                if q.question_type == "multiple_choice":
                    acertou = EvaluationResultService.check_multiple_choice_answer(
                        resposta.answer, q.correct_answer
                    )
                else:
                    acertou = (
                        str(resposta.answer).strip().lower()
                        == str(q.correct_answer).strip().lower()
                    )
            stats[bucket]["total"] += 1
            if not stats[bucket]["question_ref"]:
                stats[bucket]["question_ref"] = str(q.id)
            if not stats[bucket]["subject_id"]:
                stats[bucket]["subject_id"] = (
                    str(q.subject_id) if getattr(q, "subject_id", None) else "sem_disciplina"
                )
            if acertou:
                stats[bucket]["correct"] += 1
            else:
                failed_by_skill[bucket].add(sid)

    skill_to_question_ids: Dict[str, Set[str]] = defaultdict(set)
    for q, skill_key in questoes_com_habilidade:
        skill_to_question_ids[_norm_skill_key(skill_key)].add(q.id)

    subj_nome_por_id: Dict[str, str] = {str(d["id"]): str(d["nome"]) for d in disciplinas}

    habilidades: List[Dict[str, Any]] = []
    for bucket, agg in stats.items():
        if "||q:" in bucket:
            sk, question_ref = bucket.rsplit("||q:", 1)
        else:
            sk, question_ref = bucket, ""
        total = int(agg["total"])
        correct = int(agg["correct"])
        pct = round_to_two_decimals((correct / total * 100.0) if total > 0 else 0.0)
        faixa = faixa_from_percent(pct)
        obj = skills_db.get(sk)
        codigo, descricao = _habilidade_codigo_e_descricao(sk, obj)
        subj_id = str(agg.get("subject_id") or "sem_disciplina")

        disciplina_nome = subj_nome_por_id.get(subj_id or "", "") or "Sem disciplina"

        habilidades.append(
            {
                "skill_id": sk,
                "codigo": codigo,
                "descricao": descricao,
                "subject_id": subj_id,
                "disciplina_nome": disciplina_nome,
                "question_ref": question_ref,
                "percentual_acertos": pct,
                "faixa": faixa,
                "total_tentativas": total,
            }
        )

    habilidades.sort(
        key=lambda x: (
            x["faixa"],
            str(x.get("subject_id") or ""),
            -x["percentual_acertos"],
            x["codigo"],
            str(x.get("question_ref") or ""),
        )
    )

    por_faixa = {FAIXA_ABAIXO: [], FAIXA_BASICO: [], FAIXA_ADEQUADO: [], FAIXA_AVANCADO: []}
    for h in habilidades:
        por_faixa[h["faixa"]].append(h)

    return {
        "disciplinas_disponiveis": disciplinas,
        "habilidades": habilidades,
        "por_faixa": por_faixa,
        "_failed_by_skill": {k: v for k, v in failed_by_skill.items()},
        "_skill_to_question_ids": {k: list(v) for k, v in skill_to_question_ids.items()},
        "_students_snapshot": participating_students,
    }


def _student_row_dict(st: Student, school_by_id: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    turma_nome = "N/A"
    serie_nome = "N/A"
    escola_nome = "N/A"
    if st.class_:
        turma_nome = st.class_.name or "N/A"
        if st.class_.grade:
            serie_nome = st.class_.grade.name or "N/A"
        scid = getattr(st.class_, "school_id", None)
        if scid and school_by_id and scid in school_by_id:
            escola_nome = school_by_id[scid].name or "N/A"
    shift = ""
    if st.class_:
        shift = (st.class_.shift or "").strip() if getattr(st.class_, "shift", None) else ""
    return {
        "id": str(st.id),
        "nome": st.name or "N/A",
        "escola": escola_nome,
        "serie": serie_nome,
        "turma": turma_nome,
        "shift": shift,
    }


def digital_students_passed_vs_failed_for_bucket(
    students: List[Student],
    failed_by_skill: Dict[str, Set[str]],
    bucket_key: str,
    school_by_id: Optional[Dict[str, Any]] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], int, int, int]:
    """
    Participantes no escopo vs quem errou ao menos uma questão da habilidade (bucket)
    vs quem acertou todas as questões dessa habilidade no escopo.
    bucket_key: chave em failed_by_skill (skill normalizada no online; skill||bloco no cartão).
    """
    failed_ids = failed_by_skill.get(bucket_key, set())
    student_by_id = {s.id: s for s in students}
    all_ids = set(student_by_id.keys())
    passed_ids = all_ids - failed_ids
    n_tot = len(students)
    n_err = len(failed_ids)
    n_ok = len(passed_ids)

    def _sort_key(sid: str) -> str:
        st = student_by_id.get(sid)
        return (st.name or "") if st else ""

    alunos_err: List[Dict[str, Any]] = []
    for fid in sorted(failed_ids, key=_sort_key):
        st = student_by_id.get(fid)
        if not st:
            continue
        alunos_err.append(_student_row_dict(st, school_by_id))

    alunos_ok: List[Dict[str, Any]] = []
    for pid in sorted(passed_ids, key=_sort_key):
        st = student_by_id.get(pid)
        if not st:
            continue
        alunos_ok.append(_student_row_dict(st, school_by_id))

    return alunos_err, alunos_ok, n_err, n_ok, n_tot


def digital_students_who_failed_skill(
    students: List[Student],
    skill_id: str,
    failed_by_skill: Dict[str, Set[str]],
    school_by_id: Optional[Dict[str, Any]] = None,
) -> Tuple[List[Dict[str, Any]], int, int]:
    sk = _norm_skill_key(skill_id)
    alunos_err, _, n_err, _, n_tot = digital_students_passed_vs_failed_for_bucket(
        students, failed_by_skill, sk, school_by_id
    )
    return alunos_err, n_err, n_tot


def _gabarito_answer_map(gabarito: AnswerSheetGabarito) -> Dict[int, str]:
    raw = gabarito.correct_answers or {}
    if isinstance(raw, str):
        raw = json.loads(raw) or {}
    out: Dict[int, str] = {}
    for k, v in (raw or {}).items():
        try:
            out[int(k)] = str(v).upper() if v else ""
        except (TypeError, ValueError):
            continue
    return out


def _disciplinas_config_from_gabarito_blocks(blocks_config: Any) -> List[Dict[str, Any]]:
    """Mesma lógica de answer_sheet_routes._extrair_blocos_por_disciplina_cartao (sem import circular)."""
    blocks = _extract_blocks_with_questions(blocks_config or {})
    by_subject: Dict[str, Dict[str, Any]] = {}
    for b in blocks:
        sid = b.get("subject_id") or f"block_{b.get('block_id', 0)}"
        sid = str(sid)
        name = b.get("subject_name") or "Outras"
        if sid not in by_subject:
            by_subject[sid] = {"id": sid, "nome": name, "question_numbers": []}
        by_subject[sid]["question_numbers"].extend(b.get("question_numbers", []))
    return list(by_subject.values())


def _question_num_to_subject_id(
    disciplinas_config: List[Dict[str, Any]],
    gab_map: Dict[int, str],
) -> Dict[int, str]:
    """Número da questão -> id do bloco/disciplina (para não misturar habilidades entre disciplinas)."""
    out: Dict[int, str] = {}
    for b in disciplinas_config:
        sid = str(b["id"])
        for x in b.get("question_numbers", []):
            try:
                out[int(x)] = sid
            except (TypeError, ValueError):
                continue
    if not out and gab_map:
        for qn in gab_map.keys():
            out[int(qn)] = "geral"
    return out


def _participating_answer_sheet_result(r: AnswerSheetResult) -> bool:
    """Aluno com cartão corrigido e ao menos um sinal de participação.

    Regra principal: excluir faltantes/folha em branco, mas evitar falso-negativo quando o pipeline
    grava `classification/grade/proficiency` sem preencher `answered_questions/detected_answers`.
    """
    if not r:
        return False
    # Se não há correção registrada, não considerar participante.
    if getattr(r, "corrected_at", None) is None:
        return False
    if (r.answered_questions or 0) > 0:
        return True
    det = _parse_detected(r.detected_answers)
    for v in det.values():
        if v is None:
            continue
        if str(v).strip():
            return True
    # Fallback: alguns fluxos podem persistir apenas nota/classificação/proficiência.
    if getattr(r, "classification", None):
        if str(getattr(r, "classification", "")).strip():
            return True
    if getattr(r, "grade", None) is not None:
        return True
    if getattr(r, "proficiency", None) is not None:
        return True
    return False


def _parse_detected(detected: Any) -> Dict[int, str]:
    if not detected:
        return {}
    if isinstance(detected, str):
        try:
            detected = json.loads(detected)
        except Exception:
            return {}
    out: Dict[int, str] = {}
    for k, v in (detected or {}).items():
        try:
            kn = int(k)
            out[kn] = str(v).upper() if v else ""
        except (TypeError, ValueError):
            continue
    return out


def _answer_sheet_stat_bucket_key(
    skill_norm: str, block_subject_id: str, question_ref: Optional[str] = None
) -> str:
    base = f"{skill_norm}||{str(block_subject_id).strip()}"
    if question_ref is None or str(question_ref).strip() == "":
        return base
    return f"{base}||q:{str(question_ref).strip()}"


def _resolve_failed_bucket_key(
    failed_by_skill: Dict[str, Set[str]],
    skill_id: str,
    bloco_disciplina: Optional[str],
    question_ref: Optional[str] = None,
) -> str:
    """Resolve a chave usada em _failed_by_skill (habilidade||disciplina)."""
    sk = _norm_skill_key(skill_id)
    b = (str(bloco_disciplina).strip() if bloco_disciplina else "")
    qref = (str(question_ref).strip() if question_ref else "")
    if b and b.lower() != "all":
        return _answer_sheet_stat_bucket_key(sk, b, qref or None)
    if qref:
        q_matches = [k for k in failed_by_skill if k.startswith(f"{sk}||") and k.endswith(f"||q:{qref}")]
        if len(q_matches) == 1:
            return q_matches[0]
    if b and b.lower() != "all":
        return _answer_sheet_stat_bucket_key(sk, b)
    if sk in failed_by_skill:
        return sk
    prefixed = [k for k in failed_by_skill if k.startswith(f"{sk}||")]
    if len(prefixed) == 1:
        return prefixed[0]
    geral = _answer_sheet_stat_bucket_key(sk, "geral")
    if geral in failed_by_skill:
        return geral
    return _answer_sheet_stat_bucket_key(sk, "geral")


def resolve_participating_students_answer_sheet(
    gabarito: AnswerSheetGabarito,
    class_ids: List[str],
) -> Tuple[List[Student], Dict[str, AnswerSheetResult], int]:
    """
    Alunos participantes (cartão efetivamente corrigido) de um gabarito, dentro do
    escopo de turmas informado. Fonte única desta regra: usada tanto pelo mapa de
    habilidades quanto por qualquer outro relatório que precise do mesmo denominador
    ("total de participantes", em branco contando como erro) para não divergir dele.

    Regra: `_participating_answer_sheet_result` (cartão com `corrected_at` e algum sinal
    de participação) + alinhamento com `evaluation_results` quando o gabarito está
    vinculado a uma prova (test_id), mesmo critério de participante de
    `GET /evaluation-results/avaliacoes`.

    Retorna (alunos_participantes, resultado_por_aluno, total_alunos_no_escopo_da_turma).
    """
    if not class_ids:
        return [], {}, 0
    from app.answer_sheets.services.answer_sheet_result_snapshot import (
        query_answer_sheet_results_for_class_group,
        student_ids_for_answer_sheet_class_group,
    )

    students_base = (
        Student.query.options(joinedload(Student.class_).joinedload(Class.grade))
        .filter(Student.class_id.in_(class_ids))
        .all()
    )
    base_ids = {s.id for s in students_base}
    merged_ids = student_ids_for_answer_sheet_class_group(
        str(gabarito.id), class_ids, base_ids
    )
    students_all = (
        Student.query.options(joinedload(Student.class_).joinedload(Class.grade))
        .filter(Student.id.in_(list(merged_ids)))
        .all()
        if merged_ids
        else []
    )
    results = query_answer_sheet_results_for_class_group(
        str(gabarito.id), class_ids, list(base_ids)
    ).all()
    result_by_student = {r.student_id: r for r in results}
    students = [
        s
        for s in students_all
        if s.id in result_by_student and _participating_answer_sheet_result(result_by_student[s.id])
    ]
    linked_test_id = getattr(gabarito, "test_id", None)
    if linked_test_id and students:
        sid_list = [s.id for s in students]
        eval_ids = {
            row[0]
            for row in EvaluationResult.query.filter(
                EvaluationResult.test_id == str(linked_test_id),
                EvaluationResult.student_id.in_(sid_list),
            )
            .with_entities(EvaluationResult.student_id)
            .distinct()
            .all()
        }
        students = [s for s in students if s.id in eval_ids]
    return students, result_by_student, len(students_all)


def compute_question_percentuals_answer_sheet(
    gabarito_id: str,
    class_ids: List[str],
) -> Dict[int, float]:
    """
    Percentual de acertos por número de questão (independente de habilidade),
    usando exatamente a mesma base de participantes do mapa de habilidades
    (`resolve_participating_students_answer_sheet`): corretas / total de alunos
    participantes; quem deixou a questão em branco conta como erro no denominador.

    Fonte única para a coluna "% da turma" da tabela detalhada de
    GET /answer-sheets/resultados-agregados, para que ela nunca mais divirja do
    mapa de habilidades (GET /answer-sheets/mapa-habilidades) para a mesma questão.
    """
    gabarito = AnswerSheetGabarito.query.get(gabarito_id)
    if not gabarito:
        return {}
    gab_map = _gabarito_answer_map(gabarito)
    if not gab_map:
        return {}

    students, result_by_student, _ = resolve_participating_students_answer_sheet(gabarito, class_ids)
    total = len(students)
    if total == 0:
        return {qn: 0.0 for qn in gab_map.keys()}

    correct_counts: Dict[int, int] = defaultdict(int)
    for st in students:
        r = result_by_student.get(st.id)
        detected = _parse_detected(r.detected_answers if r else None)
        for qn, ca in gab_map.items():
            st_ans = detected.get(qn, "")
            if ca and st_ans and st_ans == ca:
                correct_counts[qn] += 1

    return {
        qn: round_to_two_decimals((correct_counts.get(qn, 0) / total) * 100.0)
        for qn in gab_map.keys()
    }


def build_skills_map_answer_sheet(
    gabarito_id: str,
    class_ids: List[str],
    disciplina_block_id: Optional[str],
) -> Dict[str, Any]:
    gabarito = AnswerSheetGabarito.query.get(gabarito_id)
    if not gabarito:
        return {
            "disciplinas_disponiveis": [],
            "habilidades": [],
            "por_faixa": {FAIXA_ABAIXO: [], FAIXA_BASICO: [], FAIXA_ADEQUADO: [], FAIXA_AVANCADO: []},
            "_failed_by_skill": {},
            "_students_all_count": 0,
        }

    blocks_config = getattr(gabarito, "blocks_config", None) or {}
    gab_map = _gabarito_answer_map(gabarito)
    disciplinas_config = _disciplinas_config_from_gabarito_blocks(blocks_config)
    if not disciplinas_config:
        disciplinas_config = [
            {"id": "geral", "nome": "Geral", "question_numbers": sorted(gab_map.keys())}
        ]

    disciplinas_disponiveis = [
        {"id": str(b["id"]), "nome": b.get("nome") or "Outras"} for b in disciplinas_config
    ]
    nome_por_disciplina = {str(b["id"]): (b.get("nome") or "Outras") for b in disciplinas_config}

    q_skills = question_skills_map_for_answer_sheet(gabarito)
    question_to_subject = _question_num_to_subject_id(disciplinas_config, gab_map)

    allowed_qn: Set[int] = set()
    filt = str(disciplina_block_id).strip().lower() if disciplina_block_id else ""
    if filt and filt != "all":
        for b in disciplinas_config:
            if str(b["id"]) == str(disciplina_block_id).strip():
                for x in b.get("question_numbers", []):
                    try:
                        allowed_qn.add(int(x))
                    except (TypeError, ValueError):
                        continue
                break
    else:
        for b in disciplinas_config:
            for x in b.get("question_numbers", []):
                try:
                    allowed_qn.add(int(x))
                except (TypeError, ValueError):
                    continue

    # Fallback: quando o gabarito/topologia não trouxe "skills" por questão,
    # tenta reaproveitar skills da prova vinculada (test_id) para não zerar o mapa.
    if not any((q_skills.get(qn) or []) for qn in allowed_qn):
        q_skills = _fallback_question_skills_from_test(getattr(gabarito, "test_id", None), allowed_qn)

    question_nums = sorted(allowed_qn & (set(q_skills.keys()) | set(gab_map.keys())))
    if not question_nums:
        question_nums = sorted(allowed_qn)

    skill_ids_for_norm: List[str] = []
    for qn in question_nums:
        for sid in q_skills.get(qn) or []:
            if sid:
                skill_ids_for_norm.append(str(sid).strip())
    skills_db_map = _fetch_skills_batch({_norm_skill_key(s) for s in skill_ids_for_norm if s})

    if not class_ids:
        return {
            "disciplinas_disponiveis": disciplinas_disponiveis,
            "habilidades": [],
            "por_faixa": {FAIXA_ABAIXO: [], FAIXA_BASICO: [], FAIXA_ADEQUADO: [], FAIXA_AVANCADO: []},
            "_failed_by_skill": {},
            "_students_all_count": 0,
        }

    students, result_by_student, students_all_count = resolve_participating_students_answer_sheet(
        gabarito, class_ids
    )

    stats: Dict[str, Dict[str, int]] = defaultdict(lambda: {"correct": 0, "total": 0})
    failed_by_skill: Dict[str, Set[str]] = defaultdict(set)

    for st in students:
        r = result_by_student.get(st.id)
        detected = _parse_detected(r.detected_answers if r else None)
        for qn in question_nums:
            ca = gab_map.get(qn)
            st_ans = detected.get(qn, "")
            ok = bool(ca is not None and st_ans and st_ans == ca)
            sids = q_skills.get(qn) or []
            if not sids:
                continue
            block_sid = question_to_subject.get(qn) or "geral"
            for raw_sid in sids:
                if not raw_sid:
                    continue
                sk = _norm_skill_key(str(raw_sid).strip())
                bucket = _answer_sheet_stat_bucket_key(sk, block_sid, str(qn))
                stats[bucket]["total"] += 1
                if ok:
                    stats[bucket]["correct"] += 1
                else:
                    failed_by_skill[bucket].add(st.id)

    habilidades: List[Dict[str, Any]] = []
    for bucket, agg in stats.items():
        sk = bucket
        block_sid = "geral"
        question_ref = ""
        if "||q:" in bucket:
            left, question_ref = bucket.rsplit("||q:", 1)
        else:
            left = bucket
        if "||" in left:
            sk, block_sid = left.split("||", 1)
        else:
            sk, block_sid = left, "geral"
        total = int(agg["total"])
        correct = int(agg["correct"])
        pct = round_to_two_decimals((correct / total * 100.0) if total > 0 else 0.0)
        faixa = faixa_from_percent(pct)
        obj = skills_db_map.get(sk)
        codigo, descricao = _habilidade_codigo_e_descricao(sk, obj)
        dn = nome_por_disciplina.get(block_sid) or nome_por_disciplina.get(str(block_sid))
        questao_numero = None
        try:
            questao_numero = int(str(question_ref))
        except (TypeError, ValueError):
            questao_numero = None
        habilidades.append(
            {
                "skill_id": sk,
                "codigo": codigo,
                "descricao": descricao,
                "subject_id": block_sid,
                "disciplina_nome": dn or ("Geral" if block_sid == "geral" else "Outras"),
                "question_ref": question_ref or None,
                "questao_numero": questao_numero,
                "percentual_acertos": pct,
                "faixa": faixa,
                "total_tentativas": total,
            }
        )

    habilidades.sort(
        key=lambda x: (
            x["faixa"],
            str(x.get("subject_id") or ""),
            int(x.get("questao_numero")) if x.get("questao_numero") is not None else 10**9,
            -x["percentual_acertos"],
            x["codigo"],
            x["skill_id"],
        )
    )
    por_faixa = {FAIXA_ABAIXO: [], FAIXA_BASICO: [], FAIXA_ADEQUADO: [], FAIXA_AVANCADO: []}
    for h in habilidades:
        por_faixa[h["faixa"]].append(h)

    return {
        "disciplinas_disponiveis": disciplinas_disponiveis,
        "habilidades": habilidades,
        "por_faixa": por_faixa,
        "_failed_by_skill": {k: set(v) for k, v in failed_by_skill.items()},
        "_students_snapshot": students,
        "_students_all_count": students_all_count,
    }


def answer_sheet_students_who_failed(
    students: List[Student],
    skill_id: str,
    failed_by_skill: Dict[str, Set[str]],
    school_by_id: Optional[Dict[str, Any]] = None,
    bloco_disciplina: Optional[str] = None,
    question_ref: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], int, int]:
    key = _resolve_failed_bucket_key(failed_by_skill, skill_id, bloco_disciplina, question_ref)
    adapted: Dict[str, Set[str]] = {key: failed_by_skill.get(key, set())}
    return digital_students_who_failed_skill(students, key, adapted, school_by_id)


def answer_sheet_students_passed_vs_failed(
    students: List[Student],
    skill_id: str,
    failed_by_skill: Dict[str, Set[str]],
    school_by_id: Optional[Dict[str, Any]] = None,
    bloco_disciplina: Optional[str] = None,
    question_ref: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], int, int, int]:
    key = _resolve_failed_bucket_key(failed_by_skill, skill_id, bloco_disciplina, question_ref)
    return digital_students_passed_vs_failed_for_bucket(
        students, failed_by_skill, key, school_by_id
    )


CRITICAL_FAIXAS = frozenset({FAIXA_ABAIXO, FAIXA_BASICO})
MAX_CRITICAL_SKILLS_PER_ROW = 8


def _subject_id_from_discipline_name(
    disciplinas: List[Dict[str, str]], discipline_name: str
) -> Optional[str]:
    target = (discipline_name or "").strip().lower()
    if not target:
        return None
    for item in disciplinas:
        if str(item.get("nome") or "").strip().lower() == target:
            return str(item.get("id") or "").strip() or None
    return None


def _discipline_lookup_key(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", (value or "").strip().lower())
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn")


def merge_critical_skills_for_row(
    by_student: Dict[str, Dict[str, List[str]]],
    student_id: str,
    discipline_name: str = "",
) -> List[str]:
    """Une códigos de habilidades críticas do aluno, opcionalmente filtrando por disciplina."""
    per_discipline = by_student.get(student_id, {})
    if discipline_name:
        direct = discipline_name.strip().lower()
        if direct in per_discipline:
            return list(per_discipline[direct])[:MAX_CRITICAL_SKILLS_PER_ROW]
        target = _discipline_lookup_key(discipline_name)
        for key, codes in per_discipline.items():
            if _discipline_lookup_key(key) == target:
                return list(codes)[:MAX_CRITICAL_SKILLS_PER_ROW]
        return []
    merged: List[str] = []
    for codes in per_discipline.values():
        for code in codes:
            if code not in merged:
                merged.append(code)
            if len(merged) >= MAX_CRITICAL_SKILLS_PER_ROW:
                return merged
    return merged


def compute_student_critical_skills_digital(
    test_id: str,
    student_ids: List[str],
) -> Dict[str, Dict[str, List[str]]]:
    """
    Habilidades em que cada aluno está em faixa abaixo do básico ou básico
    na avaliação (test_id), agrupadas por nome de disciplina (lower).
    """
    if not test_id or not student_ids:
        return {}

    disciplinas, questoes_com_habilidade = build_disciplinas_e_questoes_digital(test_id, None)
    if not questoes_com_habilidade:
        return {sid: {} for sid in student_ids}

    subj_name_by_id = {str(d["id"]): str(d["nome"]).strip().lower() for d in disciplinas}
    by_skill_questions: Dict[str, List[Question]] = defaultdict(list)
    skill_discipline: Dict[str, str] = {}
    for question, skill_key in questoes_com_habilidade:
        skill_norm = _norm_skill_key(skill_key)
        by_skill_questions[skill_norm].append(question)
        subj_id = str(question.subject_id) if question.subject_id else "sem_disciplina"
        skill_discipline[skill_norm] = subj_name_by_id.get(subj_id, "sem disciplina")

    answers_rows = StudentAnswer.query.filter(
        StudentAnswer.test_id == test_id,
        StudentAnswer.student_id.in_(student_ids),
    ).all()
    answers_by_student: Dict[str, Dict[str, StudentAnswer]] = defaultdict(dict)
    for answer in answers_rows:
        answers_by_student[answer.student_id][answer.question_id] = answer

    skills_db = _fetch_skills_batch(set(by_skill_questions.keys()))
    result: Dict[str, Dict[str, List[str]]] = {sid: {} for sid in student_ids}

    for student_id in student_ids:
        student_answers = answers_by_student.get(student_id, {})
        for skill_norm, questions in by_skill_questions.items():
            total = len(questions)
            if total <= 0:
                continue
            correct = 0
            for question in questions:
                answer = student_answers.get(question.id)
                if not answer:
                    continue
                if question.question_type == "multiple_choice":
                    if EvaluationResultService.check_multiple_choice_answer(
                        answer.answer, question.correct_answer
                    ):
                        correct += 1
                elif question.correct_answer and str(answer.answer).strip().lower() == str(
                    question.correct_answer
                ).strip().lower():
                    correct += 1
            pct = round_to_two_decimals((correct / total * 100.0) if total > 0 else 0.0)
            if faixa_from_percent(pct) not in CRITICAL_FAIXAS:
                continue
            codigo, _ = _habilidade_codigo_e_descricao(skill_norm, skills_db.get(skill_norm))
            if not codigo or codigo.startswith("Habilidade"):
                continue
            disc_key = skill_discipline.get(skill_norm, "sem disciplina")
            bucket = result[student_id].setdefault(disc_key, [])
            if codigo not in bucket and len(bucket) < MAX_CRITICAL_SKILLS_PER_ROW:
                bucket.append(codigo)

    return result


def compute_student_critical_skills_answer_sheet(
    gabarito_id: str,
    student_ids: List[str],
) -> Dict[str, Dict[str, List[str]]]:
    """
    Habilidades em que cada aluno está em faixa abaixo do básico ou básico
    no cartão-resposta (gabarito_id), agrupadas por nome de disciplina (lower).
    """
    if not gabarito_id or not student_ids:
        return {}

    gabarito = AnswerSheetGabarito.query.get(gabarito_id)
    if not gabarito:
        return {sid: {} for sid in student_ids}

    blocks_config = getattr(gabarito, "blocks_config", None) or {}
    gab_map = _gabarito_answer_map(gabarito)
    disciplinas_config = _disciplinas_config_from_gabarito_blocks(blocks_config)
    if not disciplinas_config:
        disciplinas_config = [
            {"id": "geral", "nome": "Geral", "question_numbers": sorted(gab_map.keys())}
        ]
    nome_por_disciplina = {
        str(b["id"]): str(b.get("nome") or "Outras").strip().lower() for b in disciplinas_config
    }

    q_skills = question_skills_map_for_answer_sheet(gabarito)
    question_to_subject = _question_num_to_subject_id(disciplinas_config, gab_map)
    question_nums: Set[int] = set()
    for block in disciplinas_config:
        for raw_num in block.get("question_numbers", []):
            try:
                question_nums.add(int(raw_num))
            except (TypeError, ValueError):
                continue
    if not question_nums:
        question_nums = set(gab_map.keys())

    skill_ids_for_norm: List[str] = []
    for qn in question_nums:
        for sid in q_skills.get(qn) or []:
            if sid:
                skill_ids_for_norm.append(str(sid).strip())
    skills_db_map = _fetch_skills_batch({_norm_skill_key(s) for s in skill_ids_for_norm if s})

    results = AnswerSheetResult.query.filter(
        AnswerSheetResult.gabarito_id == gabarito_id,
        AnswerSheetResult.student_id.in_(student_ids),
    ).all()
    result_by_student = {row.student_id: row for row in results}

    # student_id -> (skill_norm, disciplina_lower) -> {correct, total}
    stats: Dict[str, Dict[Tuple[str, str], Dict[str, int]]] = defaultdict(
        lambda: defaultdict(lambda: {"correct": 0, "total": 0})
    )

    for student_id in student_ids:
        sheet_result = result_by_student.get(student_id)
        if not sheet_result or not _participating_answer_sheet_result(sheet_result):
            continue
        detected = _parse_detected(sheet_result.detected_answers if sheet_result else None)
        for qn in question_nums:
            correct_answer = gab_map.get(qn)
            student_answer = detected.get(qn, "")
            is_correct = bool(correct_answer is not None and student_answer and student_answer == correct_answer)
            block_sid = question_to_subject.get(qn) or "geral"
            disc_key = nome_por_disciplina.get(block_sid, "outras")
            for raw_sid in q_skills.get(qn) or []:
                if not raw_sid:
                    continue
                skill_norm = _norm_skill_key(str(raw_sid).strip())
                bucket = stats[student_id][(skill_norm, disc_key)]
                bucket["total"] += 1
                if is_correct:
                    bucket["correct"] += 1

    output: Dict[str, Dict[str, List[str]]] = {sid: {} for sid in student_ids}
    for student_id, skill_stats in stats.items():
        for (skill_norm, disc_key), agg in skill_stats.items():
            total = int(agg["total"])
            if total <= 0:
                continue
            correct = int(agg["correct"])
            pct = round_to_two_decimals((correct / total * 100.0) if total > 0 else 0.0)
            if faixa_from_percent(pct) not in CRITICAL_FAIXAS:
                continue
            codigo, _ = _habilidade_codigo_e_descricao(skill_norm, skills_db_map.get(skill_norm))
            if not codigo or codigo.startswith("Habilidade"):
                continue
            bucket = output[student_id].setdefault(disc_key, [])
            if codigo not in bucket and len(bucket) < MAX_CRITICAL_SKILLS_PER_ROW:
                bucket.append(codigo)

    return output


def normalize_skill_code(value: Any) -> str:
    decomposed = unicodedata.normalize("NFD", str(value or "").strip().upper())
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn")


def _discipline_names_match(left: Any, right: Any) -> bool:
    left_key = _discipline_lookup_key(str(left or ""))
    right_key = _discipline_lookup_key(str(right or ""))
    return bool(left_key) and left_key == right_key


def _skill_code_from_raw(raw: str, skills_db: Dict[str, Skill]) -> str:
    key = _norm_skill_key(raw)
    obj = skills_db.get(key)
    code, _ = _habilidade_codigo_e_descricao(raw, obj)
    return code


def _raw_skill_matches_code(raw: str, target_code: str, skills_db: Dict[str, Skill]) -> bool:
    if not target_code:
        return False
    if normalize_skill_code(raw) == target_code:
        return True
    return normalize_skill_code(_skill_code_from_raw(raw, skills_db)) == target_code


def _find_skill_by_code(codigo: str) -> Optional[Skill]:
    target = normalize_skill_code(codigo)
    if not target:
        return None
    for row in Skill.query.filter(Skill.code.isnot(None)).all():
        if normalize_skill_code(row.code) == target:
            return row
    return None


def get_instrument_skill_detail(
    source_type: str,
    source_id: str,
    codigo: str,
    disciplina: str = "",
) -> Dict[str, Any]:
    """
    Detalhe de uma habilidade no instrumento (avaliação ou gabarito):
    cadastro (nome/descrição) e questões em que a habilidade aparece.
    """
    from app.exams.models.testQuestion import TestQuestion

    codigo_input = (codigo or "").strip()
    target_code = normalize_skill_code(codigo_input)
    if not target_code or not (source_id or "").strip():
        return {
            "codigo": codigo_input,
            "nome": codigo_input,
            "descricao": "Informe o código da habilidade e a avaliação/cartão.",
            "disciplina": (disciplina or "").strip(),
            "skill_id": None,
            "questoes": [],
        }

    skill_row = _find_skill_by_code(codigo_input)
    codigo_display, descricao = (
        _habilidade_codigo_e_descricao(str(skill_row.id), skill_row)
        if skill_row
        else (codigo_input, "Esta habilidade não foi encontrada na base de habilidades.")
    )
    disciplina_cadastro = ""
    if skill_row and skill_row.subject_id:
        subject_row = Subject.query.get(skill_row.subject_id)
        if subject_row and subject_row.name:
            disciplina_cadastro = str(subject_row.name).strip()

    disciplina_filter = (disciplina or "").strip()
    questoes: List[Dict[str, Any]] = []
    seen_nums: Set[Tuple[int, str]] = set()

    def _append_question(numero: int, disc_name: str) -> None:
        if disciplina_filter and not _discipline_names_match(disc_name, disciplina_filter):
            return
        key = (int(numero), _discipline_lookup_key(disc_name))
        if key in seen_nums:
            return
        seen_nums.add(key)
        questoes.append({"numero": int(numero), "disciplina": disc_name or "—"})

    if source_type == "avaliacao":
        test_id = str(source_id).strip()
        test_questions = (
            TestQuestion.query.filter_by(test_id=test_id)
            .join(Question)
            .options(joinedload(TestQuestion.question).joinedload(Question.subject))
            .order_by(TestQuestion.order)
            .all()
        )
        raw_ids: Set[str] = set()
        for tq in test_questions:
            q = tq.question
            if not q:
                continue
            for sid in _extract_skill_ids_from_question_field(getattr(q, "skill", None)):
                raw_ids.add(sid)
            cleaned = _clean_skill_id(getattr(q, "skill", None))
            if cleaned:
                raw_ids.add(cleaned)
        skills_db = _fetch_skills_batch(raw_ids)
        if skill_row:
            skills_db[str(skill_row.id)] = skill_row

        for idx, tq in enumerate(test_questions, start=1):
            q = tq.question
            if not q:
                continue
            try:
                numero = int(tq.order) if tq.order is not None else idx
            except (TypeError, ValueError):
                numero = idx
            disc_name = q.subject.name if q.subject else "Sem disciplina"
            raw_list = _extract_skill_ids_from_question_field(getattr(q, "skill", None))
            cleaned = _clean_skill_id(getattr(q, "skill", None))
            if cleaned and cleaned not in raw_list:
                raw_list.append(cleaned)
            if any(_raw_skill_matches_code(raw, target_code, skills_db) for raw in raw_list):
                _append_question(numero, disc_name)
    else:
        gabarito = AnswerSheetGabarito.query.get(str(source_id).strip())
        if gabarito:
            q_skills = question_skills_map_for_answer_sheet(gabarito)
            blocks_config = getattr(gabarito, "blocks_config", None) or {}
            disciplinas_config = _disciplinas_config_from_gabarito_blocks(blocks_config)
            if not disciplinas_config:
                gab_map = _gabarito_answer_map(gabarito)
                disciplinas_config = [
                    {
                        "id": "geral",
                        "nome": "Geral",
                        "question_numbers": sorted(gab_map.keys()),
                    }
                ]
            nome_por_disciplina = {
                str(b["id"]): str(b.get("nome") or "Outras").strip() for b in disciplinas_config
            }
            question_to_subject = _question_num_to_subject_id(disciplinas_config, _gabarito_answer_map(gabarito))

            raw_ids: Set[str] = set()
            for sids in q_skills.values():
                for sid in sids:
                    if sid:
                        raw_ids.add(str(sid).strip())
            skills_db = _fetch_skills_batch({_norm_skill_key(s) for s in raw_ids if s})
            if skill_row:
                skills_db[str(skill_row.id)] = skill_row

            for qnum in sorted(q_skills.keys()):
                block_sid = question_to_subject.get(int(qnum)) or "geral"
                disc_name = nome_por_disciplina.get(str(block_sid), "Outras")
                sids = q_skills.get(qnum) or []
                if any(_raw_skill_matches_code(str(raw), target_code, skills_db) for raw in sids):
                    _append_question(int(qnum), disc_name)

    questoes.sort(key=lambda item: (str(item.get("disciplina") or "").lower(), int(item.get("numero") or 0)))
    disciplina_resposta = disciplina_filter or disciplina_cadastro
    if not disciplina_resposta and questoes:
        disciplina_resposta = str(questoes[0].get("disciplina") or "")

    return {
        "codigo": codigo_display,
        "nome": codigo_display,
        "descricao": descricao,
        "disciplina": disciplina_resposta,
        "skill_id": str(skill_row.id) if skill_row else None,
        "questoes": questoes,
    }
