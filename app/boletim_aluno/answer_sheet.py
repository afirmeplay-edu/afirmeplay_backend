# -*- coding: utf-8 -*-
"""Boletim do aluno — cartão-resposta."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy import func
from sqlalchemy.orm import joinedload

from app.boletim_aluno.helpers import (
    build_cards,
    build_questao_boletim,
    empty_boletim_payload,
    pagination_meta,
)
from app.boletim_aluno.services import (
    _aluno_publico,
    _grade_name_map,
    _school_name_map,
    _student_query,
)
from app.mapa_questoes.answer_sheet import _resolve_subject_name, _skill_code_for_question
from app.models.answerSheetGabarito import AnswerSheetGabarito
from app.models.answerSheetResult import AnswerSheetResult
from app.models.city import City
from app.models.student import Student
from app.models.studentClass import Class
from app.permissions import get_user_permission_scope
from app.participation_report.answer_sheet import _filter_classes, _placement_for_student
from app.report_analysis.answer_sheet_report_builder import question_skills_map_for_answer_sheet
from app.services.skills_map_service import (
    _disciplinas_config_from_gabarito_blocks,
    _fetch_skills_batch,
    _gabarito_answer_map,
    _parse_detected,
    _question_num_to_subject_id,
    resolve_participating_students_answer_sheet,
)
from app.utils.tenant_middleware import city_id_to_schema_name, set_search_path
from app.utils.uuid_helpers import ensure_uuid_list

logger = logging.getLogger(__name__)


def _ensure_tenant_schema(municipio_id: str) -> None:
    set_search_path(city_id_to_schema_name(str(municipio_id).strip()))


def _norm_ids(escola_ids, serie_ids, turma_ids):
    serie_ids_norm = [str(x) for x in (serie_ids or [])]
    turma_ids_norm = [str(x) for x in (ensure_uuid_list(turma_ids) or turma_ids or [])]
    if turma_ids and not turma_ids_norm:
        turma_ids_norm = [str(x) for x in turma_ids]
    escola_ids_norm = [str(x) for x in (escola_ids or [])]
    return escola_ids_norm, serie_ids_norm, turma_ids_norm


def _resolve_answer_sheet(
    user: dict,
    municipio_id: str,
    gabarito_id: str,
    escola_ids: Optional[List[str]],
    serie_ids: Optional[List[str]],
    turma_ids: Optional[List[str]],
) -> Tuple[AnswerSheetGabarito, List, Dict[str, AnswerSheetResult], Dict[int, str], List[Dict[str, Any]], Dict[int, str], Dict[int, List[str]], Dict[str, Any], Dict[str, str]]:
    from app.routes.answer_sheet_evaluation_listing import (
        answer_sheet_target_classes_visible_for_user,
    )

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

    gab = AnswerSheetGabarito.query.get(str(gabarito_id))
    if not gab:
        raise LookupError("Gabarito não encontrado")

    escola_ids_norm, serie_ids_norm, turma_ids_norm = _norm_ids(
        escola_ids, serie_ids, turma_ids
    )
    classes = answer_sheet_target_classes_visible_for_user(gab, user, permissao, municipio_id)
    classes = _filter_classes(
        classes,
        escola_ids_norm or None,
        serie_ids_norm or None,
        turma_ids_norm or None,
    )
    class_ids = [c.id for c in classes]

    students, result_by_student, _ = (
        resolve_participating_students_answer_sheet(gab, class_ids)
        if class_ids
        else ([], {}, 0)
    )
    allowed_ids = {s.id for s in students}
    result_by_student = {
        sid: r for sid, r in result_by_student.items() if sid in allowed_ids
    }

    gab_map = _gabarito_answer_map(gab)
    question_numbers = sorted(gab_map.keys())
    blocks_config = getattr(gab, "blocks_config", None) or {}
    disciplinas_config = _disciplinas_config_from_gabarito_blocks(blocks_config)
    if not disciplinas_config:
        disciplinas_config = [
            {"id": "geral", "nome": "Geral", "question_numbers": question_numbers}
        ]
    q_to_subject = _question_num_to_subject_id(disciplinas_config, gab_map)
    nome_por_disciplina = {
        str(b["id"]): (b.get("nome") or "Outras") for b in disciplinas_config
    }
    q_skills = question_skills_map_for_answer_sheet(gab)
    skill_ids: Set[str] = set()
    for sids in q_skills.values():
        for sid in sids or []:
            skill_ids.add(str(sid))
    skills_db = _fetch_skills_batch(skill_ids)

    return (
        gab,
        students,
        result_by_student,
        gab_map,
        disciplinas_config,
        q_to_subject,
        q_skills,
        skills_db,
        nome_por_disciplina,
    )


def list_alunos_answer_sheet(
    user: dict,
    municipio_id: str,
    gabarito_id: str,
    escola_ids: Optional[List[str]] = None,
    serie_ids: Optional[List[str]] = None,
    turma_ids: Optional[List[str]] = None,
    nome: Optional[str] = None,
    page: int = 1,
    per_page: int = 20,
) -> Dict[str, Any]:
    _, students, result_by_student, *_ = _resolve_answer_sheet(
        user, municipio_id, gabarito_id, escola_ids, serie_ids, turma_ids
    )
    participant_ids = [s.id for s in students]
    if not participant_ids:
        return {"alunos": [], "paginacao": pagination_meta(0, page, per_page)}

    query = (
        _student_query(participant_ids, nome)
        .options(joinedload(Student.class_).joinedload(Class.grade))
        .order_by(func.lower(Student.name).asc())
    )
    total = query.count()
    page_students = query.offset((page - 1) * per_page).limit(per_page).all()

    school_ids: Set[str] = set()
    grade_ids: Set[Any] = set()
    for st in page_students:
        school_id, _, grade_id = _placement_for_student(st, result_by_student.get(st.id))
        if school_id:
            school_ids.add(str(school_id))
        if grade_id:
            grade_ids.add(grade_id)
        if st.class_ and st.class_.school_id:
            school_ids.add(str(st.class_.school_id))
    school_names = _school_name_map(school_ids)
    grade_names = _grade_name_map(grade_ids)
    alunos = [
        _aluno_publico(st, result_by_student.get(st.id), school_names, grade_names)
        for st in page_students
    ]
    return {"alunos": alunos, "paginacao": pagination_meta(total, page, per_page)}


def _build_one_boletim_as(
    student: Student,
    result: Optional[AnswerSheetResult],
    gab_map: Dict[int, str],
    q_to_subject: Dict[int, str],
    nome_por_disciplina: Dict[str, str],
    q_skills: Dict[int, List[str]],
    skills_db: Dict[str, Any],
    school_names: Dict[str, str],
    grade_names: Dict[str, str],
) -> Dict[str, Any]:
    detected = _parse_detected(result.detected_answers if result else None)
    por_disciplina_map: Dict[str, Dict[str, Any]] = {}
    disciplina_ordem: List[str] = []
    acertou_total = 0
    question_numbers = sorted(gab_map.keys())

    for qn in question_numbers:
        gabarito = (gab_map.get(qn) or "").strip().upper() or None
        marked = (detected.get(qn) or "").strip().upper() or None
        respondeu = bool(marked)
        acertou = bool(gabarito and marked == gabarito)
        if acertou:
            acertou_total += 1

        disciplina_id = str(q_to_subject.get(qn) or "geral")
        disciplina_nome = _resolve_subject_name(
            disciplina_id, nome_por_disciplina.get(disciplina_id, "Geral")
        )
        if disciplina_id not in por_disciplina_map:
            disciplina_ordem.append(disciplina_id)
            por_disciplina_map[disciplina_id] = {
                "disciplina_id": disciplina_id,
                "disciplina": disciplina_nome,
                "questoes": [],
            }
        por_disciplina_map[disciplina_id]["questoes"].append(
            build_questao_boletim(
                numero=qn,
                habilidade=_skill_code_for_question(q_skills.get(qn) or [], skills_db),
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
            len(question_numbers),
            getattr(result, "grade", None) if result else 0,
            getattr(result, "proficiency", None) if result else 0,
            getattr(result, "classification", None) if result else None,
        ),
    }


def build_boletins_answer_sheet(
    user: dict,
    estado: str,
    municipio_id: str,
    gabarito_id: str,
    escola_ids: Optional[List[str]] = None,
    serie_ids: Optional[List[str]] = None,
    turma_ids: Optional[List[str]] = None,
    aluno_id: Optional[str] = None,
    nome: Optional[str] = None,
    page: int = 1,
    per_page: int = 20,
) -> Dict[str, Any]:
    (
        gab,
        students,
        result_by_student,
        gab_map,
        _disciplinas_config,
        q_to_subject,
        q_skills,
        skills_db,
        nome_por_disciplina,
    ) = _resolve_answer_sheet(
        user, municipio_id, gabarito_id, escola_ids, serie_ids, turma_ids
    )

    payload = empty_boletim_payload(
        estado,
        municipio_id,
        gabarito_id,
        escola_ids,
        serie_ids,
        turma_ids,
        aluno_id,
        page,
        per_page,
    )
    payload["escopo"]["report_entity_type"] = "answer_sheet"
    payload["avaliacao"]["nome"] = gab.title or ""

    participant_ids = [s.id for s in students]
    participant_id_strs = {str(x) for x in participant_ids}
    if aluno_id:
        if aluno_id not in participant_id_strs and aluno_id not in participant_ids:
            raise LookupError("Aluno não realizou esta avaliação no recorte selecionado")
        participant_ids = [aluno_id]
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
        page_students = query.all()
        page, per_page = 1, max(total, 1)
    else:
        page_students = query.offset((page - 1) * per_page).limit(per_page).all()

    payload["paginacao"] = pagination_meta(total, page, per_page)
    if not page_students:
        return payload

    school_ids: Set[str] = set()
    grade_ids: Set[Any] = set()
    for st in page_students:
        school_id, _, grade_id = _placement_for_student(st, result_by_student.get(st.id))
        if school_id:
            school_ids.add(str(school_id))
        if grade_id:
            grade_ids.add(grade_id)
        if st.class_ and st.class_.school_id:
            school_ids.add(str(st.class_.school_id))
    school_names = _school_name_map(school_ids)
    grade_names = _grade_name_map(grade_ids)

    payload["boletins"] = [
        _build_one_boletim_as(
            st,
            result_by_student.get(st.id),
            gab_map,
            q_to_subject,
            nome_por_disciplina,
            q_skills,
            skills_db,
            school_names,
            grade_names,
        )
        for st in page_students
    ]
    logger.info(
        "boletim_aluno answer_sheet gabarito=%s alunos_pagina=%s total=%s",
        gabarito_id,
        len(page_students),
        total,
    )
    return payload
