# -*- coding: utf-8 -*-
"""
Cálculo do mapa de questões — prova digital (Test + StudentAnswer).
"""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set
from uuid import UUID

from sqlalchemy.orm import joinedload

from app.mapa_questoes.services.helpers import (
    answer_to_letter,
    build_question_row,
    empty_payload,
    gabarito_letter,
    is_objective_question,
    letters_for_alternatives,
    media_acertos_percentual,
)
from app.models.city import City
from app.evaluations.models.evaluationResult import EvaluationResult
from app.exams.models.question import Question
from app.models.student import Student
from app.exams.models.studentAnswer import StudentAnswer
from app.exams.models.test import Test
from app.exams.models.testQuestion import TestQuestion
from app.permissions import get_user_permission_scope
from app.participation_report.services import _fetch_class_tests
from app.evaluations.services.evaluation_result_snapshot import query_evaluation_results_for_stats
from app.services.skills_map_service import (
    _extract_skill_ids_from_question_field,
    _fetch_skills_batch,
    _habilidade_codigo_e_descricao,
    _norm_skill_key,
)
from app.utils.response_formatters import _get_all_subjects_from_test
from app.utils.tenant_middleware import city_id_to_schema_name, set_search_path

logger = logging.getLogger(__name__)


def _ensure_tenant_schema(municipio_id: str) -> None:
    set_search_path(city_id_to_schema_name(str(municipio_id).strip()))


def _skill_codes_for_question(question: Question, skills_db: Dict[str, Any]) -> str:
    raw_ids = _extract_skill_ids_from_question_field(getattr(question, "skill", None))
    codes: List[str] = []
    seen: Set[str] = set()
    for sid in raw_ids:
        obj = skills_db.get(_norm_skill_key(sid)) or skills_db.get(str(sid))
        if obj:
            codigo, _ = _habilidade_codigo_e_descricao(str(sid), obj)
        else:
            try:
                UUID(str(sid).strip())
                codigo = "N/A"
            except ValueError:
                codigo = str(sid).strip() or "N/A"
        if codigo and codigo not in seen:
            codes.append(codigo)
            seen.add(codigo)
    return ", ".join(codes) if codes else "N/A"


def _disciplinas_header(test: Test, objective_questions: List[Question]) -> List[Dict[str, str]]:
    header: List[Dict[str, str]] = []
    seen: Set[str] = set()

    try:
        from_test = _get_all_subjects_from_test(test) or []
    except Exception:
        from_test = []
    for item in from_test:
        sid = str(item.get("id") or "")
        nome = (item.get("name") or item.get("nome") or "").strip()
        if sid and sid not in seen:
            seen.add(sid)
            header.append({"id": sid, "nome": nome})

    for q in objective_questions:
        sid = str(q.subject_id) if getattr(q, "subject_id", None) else ""
        nome = q.subject.name if getattr(q, "subject", None) else "Sem disciplina"
        if sid and sid not in seen:
            seen.add(sid)
            header.append({"id": sid, "nome": nome})
        elif not sid:
            key = "sem_disciplina"
            if key not in seen:
                seen.add(key)
                header.append({"id": key, "nome": "Sem disciplina"})
    return header


def _best_result_by_student(results: List[EvaluationResult]) -> Dict[Any, EvaluationResult]:
    best: Dict[Any, EvaluationResult] = {}
    for er in results:
        if not er.student_id:
            continue
        prev = best.get(er.student_id)
        if prev is None:
            best[er.student_id] = er
            continue
        prev_ts = getattr(prev, "calculated_at", None)
        cur_ts = getattr(er, "calculated_at", None)
        if cur_ts and (not prev_ts or cur_ts > prev_ts):
            best[er.student_id] = er
    return best


def _student_marked_letter(answer: Optional[StudentAnswer], question: Question) -> Optional[str]:
    if not answer or answer.answer is None or str(answer.answer).strip() == "":
        return None
    return answer_to_letter(answer.answer, question.alternatives)


def build_mapa_questoes_digital(
    user: dict,
    estado: str,
    municipio_id: str,
    avaliacao_id: str,
    escola_ids: Optional[List[str]] = None,
    serie_ids: Optional[List[str]] = None,
    turma_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    permissao = get_user_permission_scope(user)
    if not permissao.get("permitted"):
        raise PermissionError(permissao.get("error") or "Sem permissão")

    city = City.query.get(municipio_id)
    if not city:
        raise ValueError("Município não encontrado")
    if permissao.get("scope") != "all":
        user_city = str(user.get("city_id") or user.get("tenant_id") or "")
        if user_city != str(city.id):
            raise PermissionError("Sem permissão para este município")

    _ensure_tenant_schema(municipio_id)

    payload = empty_payload(
        estado, municipio_id, avaliacao_id, escola_ids, serie_ids, turma_ids
    )

    test = Test.query.get(str(avaliacao_id))
    if not test:
        raise LookupError("Avaliação não encontrada")

    payload["avaliacao"]["nome"] = test.title or ""

    class_tests = _fetch_class_tests(
        municipio_id,
        user,
        permissao,
        avaliacao_ids=[str(avaliacao_id)],
        escola_ids=escola_ids or None,
        serie_ids=serie_ids or None,
        turma_ids=turma_ids or None,
    )
    class_ids = list({ct.class_id for ct in class_tests if ct.class_id is not None})

    test_questions = (
        TestQuestion.query.filter_by(test_id=str(avaliacao_id))
        .join(Question)
        .options(joinedload(TestQuestion.question).joinedload(Question.subject))
        .order_by(TestQuestion.order)
        .all()
    )

    objective_items: List[Dict[str, Any]] = []
    skill_ids: Set[str] = set()
    for idx, tq in enumerate(test_questions, start=1):
        q = tq.question
        if not q or not is_objective_question(q.question_type, q.alternatives):
            continue
        numero = int(tq.order) if tq.order is not None else idx
        for sid in _extract_skill_ids_from_question_field(getattr(q, "skill", None)):
            skill_ids.add(sid)
        objective_items.append({"numero": numero, "question": q})

    skills_db = _fetch_skills_batch(skill_ids)
    questions = [item["question"] for item in objective_items]
    payload["avaliacao"]["disciplinas"] = _disciplinas_header(test, questions)
    payload["metricas"]["total_questoes"] = len(objective_items)

    if not objective_items:
        return payload

    participant_ids: List[Any] = []
    if class_ids:
        base_students = Student.query.filter(Student.class_id.in_(class_ids)).all()
        base_ids = [s.id for s in base_students]
        escopo_calculo = {"tipo": "municipio", "municipio_id": municipio_id}
        resultados = query_evaluation_results_for_stats(
            [str(avaliacao_id)], escopo_calculo, class_ids, base_ids
        ).all()
        participant_ids = list(_best_result_by_student(resultados).keys())

    n_alunos = len(participant_ids)
    payload["metricas"]["total_alunos_realizaram"] = n_alunos

    answers_by_student: Dict[Any, Dict[Any, StudentAnswer]] = defaultdict(dict)
    if participant_ids:
        for row in StudentAnswer.query.filter(
            StudentAnswer.test_id == str(avaliacao_id),
            StudentAnswer.student_id.in_(participant_ids),
        ).all():
            answers_by_student[row.student_id][row.question_id] = row

    total_acertos = 0
    por_disciplina_map: Dict[str, Dict[str, Any]] = {}
    disciplina_ordem: List[str] = []

    for item in objective_items:
        q: Question = item["question"]
        letters = letters_for_alternatives(q.alternatives)
        gabarito = gabarito_letter(q.correct_answer, q.alternatives)
        mark_counts: Dict[str, int] = {L: 0 for L in letters}
        mark_counts["sem_resposta"] = 0
        acertaram = 0

        for sid in participant_ids:
            ans = answers_by_student.get(sid, {}).get(q.id)
            marked = _student_marked_letter(ans, q)
            if not marked:
                mark_counts["sem_resposta"] += 1
            elif marked in mark_counts:
                mark_counts[marked] += 1
            else:
                mark_counts[marked] = mark_counts.get(marked, 0) + 1
            if gabarito and marked == gabarito:
                acertaram += 1
                total_acertos += 1

        disciplina_id = str(q.subject_id) if q.subject_id else "sem_disciplina"
        disciplina_nome = q.subject.name if q.subject else "Sem disciplina"
        if disciplina_id not in por_disciplina_map:
            disciplina_ordem.append(disciplina_id)
            por_disciplina_map[disciplina_id] = {
                "disciplina_id": disciplina_id,
                "disciplina": disciplina_nome,
                "questoes": [],
            }

        por_disciplina_map[disciplina_id]["questoes"].append(
            build_question_row(
                numero=item["numero"],
                disciplina=disciplina_nome,
                disciplina_id=disciplina_id,
                habilidade=_skill_codes_for_question(q, skills_db),
                gabarito=gabarito,
                letters=letters,
                mark_counts=mark_counts,
                acertaram=acertaram,
                n_alunos=n_alunos,
            )
        )

    payload["metricas"]["media_acertos_percentual"] = media_acertos_percentual(
        total_acertos, n_alunos, len(objective_items)
    )
    payload["por_disciplina"] = [por_disciplina_map[k] for k in disciplina_ordem]
    logger.info(
        "mapa_questoes digital test=%s alunos=%s questoes=%s media=%s",
        avaliacao_id,
        n_alunos,
        len(objective_items),
        payload["metricas"]["media_acertos_percentual"],
    )
    return payload
