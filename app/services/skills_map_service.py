# -*- coding: utf-8 -*-
"""
Agregação do mapa de habilidades (% acertos por faixa) e drill-down de alunos que erraram.
Avaliação online (Test + StudentAnswer) e cartão-resposta (AnswerSheetGabarito + AnswerSheetResult).
"""
from __future__ import annotations

import json
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple
from uuid import UUID

from sqlalchemy.orm import joinedload

from app.models.answerSheetGabarito import AnswerSheetGabarito
from app.models.answerSheetResult import AnswerSheetResult
from app.models.question import Question
from app.models.skill import Skill
from app.models.student import Student
from app.models.studentAnswer import StudentAnswer
from app.models.studentClass import Class
from app.models.testQuestion import TestQuestion
from app.report_analysis.answer_sheet_report_builder import _question_skills_map_from_gabarito
from app.services.cartao_resposta.proficiency_by_subject import _extract_blocks_with_questions
from app.services.evaluation_result_service import EvaluationResultService
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

    stats: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"correct": 0, "total": 0})
    failed_by_skill: Dict[str, Set[str]] = defaultdict(set)

    for student in students:
        sid = student.id
        for q, skill_key in questoes_com_habilidade:
            sk = _norm_skill_key(skill_key)
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
            stats[sk]["total"] += 1
            if acertou:
                stats[sk]["correct"] += 1
            else:
                failed_by_skill[sk].add(sid)

    skill_to_question_ids: Dict[str, Set[str]] = defaultdict(set)
    for q, skill_key in questoes_com_habilidade:
        skill_to_question_ids[_norm_skill_key(skill_key)].add(q.id)

    subj_nome_por_id: Dict[str, str] = {str(d["id"]): str(d["nome"]) for d in disciplinas}

    habilidades: List[Dict[str, Any]] = []
    for sk, agg in stats.items():
        total = int(agg["total"])
        correct = int(agg["correct"])
        pct = round_to_two_decimals((correct / total * 100.0) if total > 0 else 0.0)
        faixa = faixa_from_percent(pct)
        obj = skills_db.get(sk)
        codigo, descricao = _habilidade_codigo_e_descricao(sk, obj)
        subj_id = None
        for q, sk0 in questoes_com_habilidade:
            if _norm_skill_key(sk0) == sk:
                subj_id = str(q.subject_id) if q.subject_id else "sem_disciplina"
                break

        disciplina_nome = subj_nome_por_id.get(subj_id or "", "") or "Sem disciplina"

        habilidades.append(
            {
                "skill_id": sk,
                "codigo": codigo,
                "descricao": descricao,
                "subject_id": subj_id,
                "disciplina_nome": disciplina_nome,
                "percentual_acertos": pct,
                "faixa": faixa,
                "total_tentativas": total,
            }
        )

    habilidades.sort(
        key=lambda x: (x["faixa"], -x["percentual_acertos"], x["codigo"], x["skill_id"])
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
    }


def digital_students_who_failed_skill(
    students: List[Student],
    skill_id: str,
    failed_by_skill: Dict[str, Set[str]],
    school_by_id: Optional[Dict[str, Any]] = None,
) -> Tuple[List[Dict[str, Any]], int, int]:
    sk = _norm_skill_key(skill_id)
    failed_ids = failed_by_skill.get(sk, set())
    total_escopo = len(students)
    if total_escopo == 0:
        return [], 0, 0
    pct_err = round_to_two_decimals(len(failed_ids) / total_escopo * 100.0)

    student_by_id = {s.id: s for s in students}
    alunos_out: List[Dict[str, Any]] = []
    for fid in sorted(
        failed_ids,
        key=lambda x: (student_by_id.get(x).name or "") if student_by_id.get(x) else "",
    ):
        st = student_by_id.get(fid)
        if not st:
            continue
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
        alunos_out.append(
            {
                "id": str(st.id),
                "nome": st.name or "N/A",
                "escola": escola_nome,
                "serie": serie_nome,
                "turma": turma_nome,
            }
        )
    return alunos_out, len(failed_ids), total_escopo


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
    """Aluno com cartão corrigido e ao menos uma resposta detectada (exclui faltantes / folha em branco)."""
    if not r:
        return False
    if (r.answered_questions or 0) > 0:
        return True
    det = _parse_detected(r.detected_answers)
    for v in det.values():
        if v is None:
            continue
        if str(v).strip():
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


def _answer_sheet_stat_bucket_key(skill_norm: str, block_subject_id: str) -> str:
    return f"{skill_norm}||{str(block_subject_id).strip()}"


def _resolve_failed_bucket_key(
    failed_by_skill: Dict[str, Set[str]],
    skill_id: str,
    bloco_disciplina: Optional[str],
) -> str:
    """Resolve a chave usada em _failed_by_skill (habilidade||disciplina)."""
    sk = _norm_skill_key(skill_id)
    b = (str(bloco_disciplina).strip() if bloco_disciplina else "")
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

    q_skills = _question_skills_map_from_gabarito(gabarito)
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
        }

    students_all = (
        Student.query.options(joinedload(Student.class_).joinedload(Class.grade))
        .filter(Student.class_id.in_(class_ids))
        .all()
    )
    student_ids_all = [s.id for s in students_all]
    results = AnswerSheetResult.query.filter(
        AnswerSheetResult.gabarito_id == gabarito_id,
        AnswerSheetResult.student_id.in_(student_ids_all),
    ).all()
    result_by_student = {r.student_id: r for r in results}
    students = [
        s
        for s in students_all
        if s.id in result_by_student and _participating_answer_sheet_result(result_by_student[s.id])
    ]

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
                bucket = _answer_sheet_stat_bucket_key(sk, block_sid)
                stats[bucket]["total"] += 1
                if ok:
                    stats[bucket]["correct"] += 1
                else:
                    failed_by_skill[bucket].add(st.id)

    habilidades: List[Dict[str, Any]] = []
    for bucket, agg in stats.items():
        if "||" in bucket:
            sk, block_sid = bucket.split("||", 1)
        else:
            sk, block_sid = bucket, "geral"
        total = int(agg["total"])
        correct = int(agg["correct"])
        pct = round_to_two_decimals((correct / total * 100.0) if total > 0 else 0.0)
        faixa = faixa_from_percent(pct)
        obj = skills_db_map.get(sk)
        codigo, descricao = _habilidade_codigo_e_descricao(sk, obj)
        dn = nome_por_disciplina.get(block_sid) or nome_por_disciplina.get(str(block_sid))
        habilidades.append(
            {
                "skill_id": sk,
                "codigo": codigo,
                "descricao": descricao,
                "subject_id": block_sid,
                "disciplina_nome": dn or ("Geral" if block_sid == "geral" else "Outras"),
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
    }


def answer_sheet_students_who_failed(
    students: List[Student],
    skill_id: str,
    failed_by_skill: Dict[str, Set[str]],
    school_by_id: Optional[Dict[str, Any]] = None,
    bloco_disciplina: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], int, int]:
    key = _resolve_failed_bucket_key(failed_by_skill, skill_id, bloco_disciplina)
    adapted: Dict[str, Set[str]] = {key: failed_by_skill.get(key, set())}
    return digital_students_who_failed_skill(students, key, adapted, school_by_id)
