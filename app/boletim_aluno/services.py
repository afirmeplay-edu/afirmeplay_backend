# -*- coding: utf-8 -*-
"""Cálculo do boletim — prova digital."""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy import func
from sqlalchemy.orm import joinedload

from app.boletim_aluno.helpers import (
    build_cards,
    build_questao_boletim,
    empty_boletim_payload,
    pagination_meta,
)
from app.mapa_questoes.helpers import (
    answer_to_letter,
    gabarito_letter,
    is_objective_question,
)
from app.mapa_questoes.services import _skill_codes_for_question
from app.models.city import City
from app.models.evaluationResult import EvaluationResult
from app.models.grades import Grade
from app.models.question import Question
from app.models.school import School
from app.models.student import Student
from app.models.studentAnswer import StudentAnswer
from app.models.studentClass import Class
from app.models.test import Test
from app.models.testQuestion import TestQuestion
from app.permissions import get_user_permission_scope
from app.participation_report.services import _fetch_class_tests, _placement_for_student
from app.services.evaluation_result_snapshot import query_evaluation_results_for_stats
from app.services.skills_map_service import (
    _extract_skill_ids_from_question_field,
    _fetch_skills_batch,
)
from app.utils.tenant_middleware import city_id_to_schema_name, set_search_path

logger = logging.getLogger(__name__)


def _ensure_tenant_schema(municipio_id: str) -> None:
    set_search_path(city_id_to_schema_name(str(municipio_id).strip()))


def _assert_municipio(user: dict, municipio_id: str, permissao: dict) -> City:
    city = City.query.get(municipio_id)
    if not city:
        raise ValueError("Município não encontrado")
    if permissao.get("scope") != "all":
        user_city = str(user.get("city_id") or user.get("tenant_id") or "")
        if user_city != str(city.id):
            raise PermissionError("Sem permissão para este município")
    return city


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


def _load_objective_items(avaliacao_id: str) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
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
    return objective_items, _fetch_skills_batch(skill_ids)


def _participant_results(
    municipio_id: str,
    avaliacao_id: str,
    class_ids: List[Any],
) -> Dict[Any, EvaluationResult]:
    if not class_ids:
        return {}
    base_ids = [
        s.id for s in Student.query.filter(Student.class_id.in_(class_ids)).all()
    ]
    resultados = query_evaluation_results_for_stats(
        [str(avaliacao_id)],
        {"tipo": "municipio", "municipio_id": municipio_id},
        class_ids,
        base_ids,
    ).all()
    return _best_result_by_student(resultados)


def _student_query(participant_ids: List[Any], nome: Optional[str]):
    query = Student.query.filter(Student.id.in_(list(participant_ids)))
    if nome:
        query = query.filter(Student.name.ilike(f"%{nome.strip()}%"))
    return query


def _school_name_map(school_ids: Set[str]) -> Dict[str, str]:
    ids = [s for s in school_ids if s]
    if not ids:
        return {}
    return {str(s.id): (s.name or "") for s in School.query.filter(School.id.in_(ids)).all()}


def _grade_name_map(grade_ids: Set[Any]) -> Dict[str, str]:
    ids = [g for g in grade_ids if g]
    if not ids:
        return {}
    return {str(g.id): (g.name or "") for g in Grade.query.filter(Grade.id.in_(list(ids))).all()}


def _aluno_publico(
    student: Student,
    result: Optional[EvaluationResult],
    school_names: Dict[str, str],
    grade_names: Dict[str, str],
) -> Dict[str, Any]:
    school_id, class_id, grade_id = _placement_for_student(student, result)
    turma_nome = ""
    serie_nome = grade_names.get(str(grade_id), "") if grade_id else ""
    cls_obj = getattr(student, "class_", None)
    if class_id and (not cls_obj or str(cls_obj.id) != str(class_id)):
        cls_obj = Class.query.get(class_id)
    if cls_obj:
        turma_nome = cls_obj.name or ""
        if not serie_nome and cls_obj.grade:
            serie_nome = cls_obj.grade.name or ""
        if not school_id and cls_obj.school_id:
            school_id = str(cls_obj.school_id)
    return {
        "id": str(student.id),
        "nome": student.name or "",
        "matricula": student.registration or "",
        "escola": school_names.get(str(school_id), "") if school_id else "",
        "serie": serie_nome,
        "turma": turma_nome,
    }


def _resolve_digital(
    user: dict,
    municipio_id: str,
    avaliacao_id: str,
    escola_ids: Optional[List[str]],
    serie_ids: Optional[List[str]],
    turma_ids: Optional[List[str]],
) -> Tuple[dict, Test, List[Any], Dict[Any, EvaluationResult], List[Dict[str, Any]], Dict[str, Any]]:
    permissao = get_user_permission_scope(user)
    if not permissao.get("permitted"):
        raise PermissionError(permissao.get("error") or "Sem permissão")
    _assert_municipio(user, municipio_id, permissao)
    _ensure_tenant_schema(municipio_id)

    test = Test.query.get(str(avaliacao_id))
    if not test:
        raise LookupError("Avaliação não encontrada")

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
    best = _participant_results(municipio_id, avaliacao_id, class_ids)
    objective_items, skills_db = _load_objective_items(str(avaliacao_id))
    return permissao, test, class_ids, best, objective_items, skills_db


def list_alunos_digital(
    user: dict,
    municipio_id: str,
    avaliacao_id: str,
    escola_ids: Optional[List[str]] = None,
    serie_ids: Optional[List[str]] = None,
    turma_ids: Optional[List[str]] = None,
    nome: Optional[str] = None,
    page: int = 1,
    per_page: int = 20,
) -> Dict[str, Any]:
    _, _, _, best, _, _ = _resolve_digital(
        user, municipio_id, avaliacao_id, escola_ids, serie_ids, turma_ids
    )
    participant_ids = list(best.keys())
    if not participant_ids:
        return {"alunos": [], "paginacao": pagination_meta(0, page, per_page)}

    query = (
        _student_query(participant_ids, nome)
        .options(joinedload(Student.class_).joinedload(Class.grade))
        .order_by(func.lower(Student.name).asc())
    )
    total = query.count()
    offset = (page - 1) * per_page
    students = query.offset(offset).limit(per_page).all()

    school_ids: Set[str] = set()
    grade_ids: Set[Any] = set()
    placements = {}
    for st in students:
        school_id, _, grade_id = _placement_for_student(st, best.get(st.id))
        placements[st.id] = (school_id, grade_id)
        if school_id:
            school_ids.add(str(school_id))
        if grade_id:
            grade_ids.add(grade_id)
        if st.class_ and st.class_.school_id:
            school_ids.add(str(st.class_.school_id))
    school_names = _school_name_map(school_ids)
    grade_names = _grade_name_map(grade_ids)

    alunos = [
        _aluno_publico(st, best.get(st.id), school_names, grade_names) for st in students
    ]
    return {"alunos": alunos, "paginacao": pagination_meta(total, page, per_page)}


def _build_one_boletim(
    student: Student,
    result: Optional[EvaluationResult],
    objective_items: List[Dict[str, Any]],
    answers: Dict[Any, StudentAnswer],
    skills_db: Dict[str, Any],
    school_names: Dict[str, str],
    grade_names: Dict[str, str],
) -> Dict[str, Any]:
    por_disciplina_map: Dict[str, Dict[str, Any]] = {}
    disciplina_ordem: List[str] = []
    acertou_total = 0

    for item in objective_items:
        q: Question = item["question"]
        gabarito = gabarito_letter(q.correct_answer, q.alternatives)
        ans = answers.get(q.id)
        marked = None
        if ans and ans.answer is not None and str(ans.answer).strip():
            marked = answer_to_letter(ans.answer, q.alternatives)
        respondeu = marked is not None
        acertou = bool(gabarito and marked == gabarito)
        if acertou:
            acertou_total += 1

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
            build_questao_boletim(
                numero=item["numero"],
                habilidade=_skill_codes_for_question(q, skills_db),
                resposta=marked,
                gabarito=gabarito,
                acertou=acertou,
                respondeu=respondeu,
            )
        )

    return {
        "aluno": _aluno_publico(student, result, school_names, grade_names),
        "por_disciplina": [por_disciplina_map[k] for k in disciplina_ordem],
        "cards": build_cards(
            acertou_total,
            len(objective_items),
            getattr(result, "grade", None) if result else 0,
            getattr(result, "proficiency", None) if result else 0,
            getattr(result, "classification", None) if result else None,
        ),
    }


def build_boletins_digital(
    user: dict,
    estado: str,
    municipio_id: str,
    avaliacao_id: str,
    escola_ids: Optional[List[str]] = None,
    serie_ids: Optional[List[str]] = None,
    turma_ids: Optional[List[str]] = None,
    aluno_id: Optional[str] = None,
    nome: Optional[str] = None,
    page: int = 1,
    per_page: int = 20,
) -> Dict[str, Any]:
    _, test, _, best, objective_items, skills_db = _resolve_digital(
        user, municipio_id, avaliacao_id, escola_ids, serie_ids, turma_ids
    )
    payload = empty_boletim_payload(
        estado,
        municipio_id,
        avaliacao_id,
        escola_ids,
        serie_ids,
        turma_ids,
        aluno_id,
        page,
        per_page,
    )
    payload["avaliacao"]["nome"] = test.title or ""

    participant_ids = list(best.keys())
    if aluno_id:
        match = next((x for x in participant_ids if str(x) == str(aluno_id)), None)
        if match is None:
            raise LookupError("Aluno não realizou esta avaliação no recorte selecionado")
        participant_ids = [match]
        nome = None
        page, per_page = 1, 1

    if not participant_ids:
        return payload

    query = (
        _student_query(participant_ids, nome)
        .options(joinedload(Student.class_).joinedload(Class.grade))
        .order_by(func.lower(Student.name).asc())
    )
    total = query.count()
    if aluno_id:
        students = query.all()
        page, per_page = 1, max(total, 1)
    else:
        students = query.offset((page - 1) * per_page).limit(per_page).all()

    payload["paginacao"] = pagination_meta(total, page, per_page)
    if not students:
        return payload

    page_ids = [s.id for s in students]
    answers_by_student: Dict[Any, Dict[Any, StudentAnswer]] = defaultdict(dict)
    for row in StudentAnswer.query.filter(
        StudentAnswer.test_id == str(avaliacao_id),
        StudentAnswer.student_id.in_(page_ids),
    ).all():
        answers_by_student[row.student_id][row.question_id] = row

    school_ids: Set[str] = set()
    grade_ids: Set[Any] = set()
    for st in students:
        school_id, _, grade_id = _placement_for_student(st, best.get(st.id))
        if school_id:
            school_ids.add(str(school_id))
        if grade_id:
            grade_ids.add(grade_id)
        if st.class_ and st.class_.school_id:
            school_ids.add(str(st.class_.school_id))
    school_names = _school_name_map(school_ids)
    grade_names = _grade_name_map(grade_ids)

    payload["boletins"] = [
        _build_one_boletim(
            st,
            best.get(st.id),
            objective_items,
            answers_by_student.get(st.id, {}),
            skills_db,
            school_names,
            grade_names,
        )
        for st in students
    ]
    logger.info(
        "boletim_aluno digital test=%s alunos_pagina=%s total=%s",
        avaliacao_id,
        len(students),
        total,
    )
    return payload
