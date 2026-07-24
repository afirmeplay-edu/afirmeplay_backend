# -*- coding: utf-8 -*-
"""
Cálculo de participação: matriculados / avaliados únicos, turmas e detalhe.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy import String, and_, cast, func, or_
from sqlalchemy.orm import joinedload

from app.models.city import City
from app.models.classTest import ClassTest
from app.models.evaluationResult import EvaluationResult
from app.models.school import School
from app.models.student import Student
from app.models.studentClass import Class
from app.models.test import Test
from app.permissions import (
    get_manager_school,
    get_teacher_classes,
    get_user_permission_scope,
)
from app.permissions.roles import Roles
from app.services.evaluation_result_snapshot import (
    merge_participant_student_ids,
    query_evaluation_results_for_stats,
)
from app.utils.uuid_helpers import ensure_uuid_list
from app.utils.class_label_helpers import format_grade_class_label, normalize_shift


def _filtros_avaliacao_permitida():
    """Exclui olimpíada e espelhos de avaliação subjetiva (por enquanto)."""
    return and_(
        or_(Test.type.is_(None), func.upper(Test.type) != "OLIMPIADA"),
        or_(Test.evaluation_mode.is_(None), func.lower(Test.evaluation_mode) != "subjective"),
    )


def _percentual(avaliados: int, matriculados: int) -> float:
    if matriculados <= 0:
        return 0.0
    return round(100.0 * avaliados / matriculados, 2)


def _restrict_class_ids_for_user(user: dict, permissao: dict) -> Optional[Set[Any]]:
    """None = sem restrição extra; set = só essas turmas."""
    role = Roles.normalize(user.get("role", ""))
    if permissao.get("scope") != "escola":
        return None
    if role == Roles.PROFESSOR:
        return set(get_teacher_classes(user["id"]) or [])
    if role in (Roles.DIRETOR, Roles.COORDENADOR):
        school_id = get_manager_school(user["id"])
        if not school_id:
            return set()
        rows = Class.query.with_entities(Class.id).filter(Class.school_id == school_id).all()
        return {r[0] for r in rows}
    return None


def _fetch_class_tests(
    municipio_id: str,
    user: dict,
    permissao: dict,
    avaliacao_ids: Optional[List[str]] = None,
    escola_ids: Optional[List[str]] = None,
    serie_ids: Optional[List[str]] = None,
    turma_ids: Optional[List[str]] = None,
) -> List[ClassTest]:
    city = City.query.get(municipio_id)
    if not city:
        return []
    if permissao.get("scope") != "all":
        user_city = str(user.get("city_id") or user.get("tenant_id") or "")
        if user_city != str(city.id):
            return []

    query = (
        ClassTest.query.join(Class, ClassTest.class_id == Class.id)
        .join(School, School.id == cast(Class.school_id, String))
        .join(City, School.city_id == City.id)
        .join(Test, ClassTest.test_id == Test.id)
        .options(joinedload(ClassTest.class_).joinedload(Class.grade))
        .filter(City.id == city.id, _filtros_avaliacao_permitida())
    )

    if avaliacao_ids:
        query = query.filter(ClassTest.test_id.in_([str(t) for t in avaliacao_ids]))
    if escola_ids:
        query = query.filter(School.id.in_([str(e) for e in escola_ids]))
    if serie_ids:
        serie_uuids = ensure_uuid_list(serie_ids)
        if serie_uuids:
            query = query.filter(Class.grade_id.in_(serie_uuids))
        else:
            return []
    if turma_ids:
        turma_uuids = ensure_uuid_list(turma_ids)
        if turma_uuids:
            query = query.filter(Class.id.in_(turma_uuids))
        else:
            return []

    restrict = _restrict_class_ids_for_user(user, permissao)
    if restrict is not None:
        if not restrict:
            return []
        query = query.filter(Class.id.in_(list(restrict)))

    # Diretor/coordenador: também garantir escola do manager se escolas não veio no filtro
    role = Roles.normalize(user.get("role", ""))
    if role in (Roles.DIRETOR, Roles.COORDENADOR) and not escola_ids:
        school_id = get_manager_school(user["id"])
        if school_id:
            query = query.filter(School.id == school_id)
        else:
            return []

    return query.distinct().all()


def _placement_for_student(
    student: Student,
    result: Optional[EvaluationResult],
) -> Tuple[Optional[str], Optional[Any], Optional[Any]]:
    """
    Retorna (escola_id, turma_id, serie_id) preferindo snapshot do resultado.
    """
    if result is not None:
        has_snap = bool(
            getattr(result, "school_id_snapshot", None)
            or getattr(result, "class_id_snapshot", None)
        )
        if has_snap:
            school_id = (
                str(result.school_id_snapshot) if result.school_id_snapshot else None
            )
            class_id = result.class_id_snapshot
            grade_id = result.grade_id_snapshot
            if class_id is not None and grade_id is None:
                cls_obj = Class.query.get(class_id)
                if cls_obj is not None:
                    grade_id = getattr(cls_obj, "grade_id", None)
                    if school_id is None and getattr(cls_obj, "school_id", None):
                        school_id = str(cls_obj.school_id)
            return school_id, class_id, grade_id

    school_id = str(student.school_id) if getattr(student, "school_id", None) else None
    class_id = getattr(student, "class_id", None)
    grade_id = getattr(student, "grade_id", None)
    if class_id and (school_id is None or grade_id is None):
        cls_obj = getattr(student, "class_", None) or Class.query.get(class_id)
        if cls_obj is not None:
            if school_id is None and getattr(cls_obj, "school_id", None):
                school_id = str(cls_obj.school_id)
            if grade_id is None:
                grade_id = getattr(cls_obj, "grade_id", None)
    return school_id, class_id, grade_id


def build_participation_report(
    user: dict,
    estado: str,
    municipio_id: str,
    avaliacao_ids: Optional[List[str]] = None,
    escola_ids: Optional[List[str]] = None,
    serie_ids: Optional[List[str]] = None,
    turma_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    permissao = get_user_permission_scope(user)
    if not permissao.get("permitted"):
        raise PermissionError(permissao.get("error") or "Sem permissão")

    class_tests = _fetch_class_tests(
        municipio_id,
        user,
        permissao,
        avaliacao_ids=avaliacao_ids or None,
        escola_ids=escola_ids or None,
        serie_ids=serie_ids or None,
        turma_ids=turma_ids or None,
    )

    escopo = {
        "estado": estado,
        "municipio_id": str(municipio_id),
        "avaliacoes": list(avaliacao_ids or []),
        "escolas": list(escola_ids or []),
        "series": list(serie_ids or []),
        "turmas": [str(t) for t in (turma_ids or [])],
    }

    empty = {
        "escopo": escopo,
        "metricas": {
            "matriculados": 0,
            "avaliados": 0,
            "total_turmas": 0,
            "percentual_participacao": 0.0,
        },
        "por_escola": [],
        "por_turma": [],
    }

    if not class_tests:
        return empty

    test_ids = list({str(ct.test_id) for ct in class_tests if ct.test_id})
    class_ids = list({ct.class_id for ct in class_tests if ct.class_id is not None})
    total_turmas = len(class_ids)

    # Mapa turma → escola / série a partir dos ClassTest
    class_meta: Dict[Any, Dict[str, Any]] = {}
    school_class_ids: Dict[str, Set[Any]] = defaultdict(set)
    school_ids_needed: Set[str] = set()
    for ct in class_tests:
        cls_obj = ct.class_
        if not cls_obj:
            continue
        school_id = str(cls_obj.school_id) if cls_obj.school_id else None
        grade_id = cls_obj.grade_id
        class_meta[ct.class_id] = {
            "escola_id": school_id,
            "serie_id": grade_id,
            "turma_nome": cls_obj.name or "",
            "shift": normalize_shift(getattr(cls_obj, "shift", None)) or "",
            "serie_nome": (cls_obj.grade.name if cls_obj.grade else "") or "",
        }
        if school_id:
            school_class_ids[school_id].add(ct.class_id)
            school_ids_needed.add(school_id)

    schools_by_id: Dict[str, School] = {}
    if school_ids_needed:
        for sch in School.query.filter(School.id.in_(list(school_ids_needed))).all():
            schools_by_id[str(sch.id)] = sch
    for cid, meta in class_meta.items():
        sid = meta.get("escola_id")
        if sid and sid in schools_by_id:
            meta["escola_nome"] = schools_by_id[sid].name or ""
        else:
            meta["escola_nome"] = ""

    escopo_calculo = {"tipo": "municipio", "municipio_id": municipio_id}

    base_students = (
        Student.query.filter(Student.class_id.in_(class_ids))
        .options(joinedload(Student.class_).joinedload(Class.grade))
        .all()
        if class_ids
        else []
    )
    base_ids = {s.id for s in base_students}
    merged_ids = merge_participant_student_ids(
        test_ids, escopo_calculo, class_ids, set(base_ids)
    )

    students = (
        Student.query.filter(Student.id.in_(list(merged_ids)))
        .options(joinedload(Student.class_).joinedload(Class.grade))
        .all()
        if merged_ids
        else []
    )
    students_by_id = {s.id: s for s in students}

    resultados = (
        query_evaluation_results_for_stats(
            test_ids, escopo_calculo, class_ids, list(base_ids)
        ).all()
        if test_ids
        else []
    )

    # Um resultado por aluno (mais recente) para colocação e unicidade de avaliados
    best_result_by_student: Dict[Any, EvaluationResult] = {}
    for er in resultados:
        if not er.student_id:
            continue
        prev = best_result_by_student.get(er.student_id)
        if prev is None:
            best_result_by_student[er.student_id] = er
            continue
        prev_ts = getattr(prev, "calculated_at", None) or getattr(prev, "created_at", None)
        cur_ts = getattr(er, "calculated_at", None) or getattr(er, "created_at", None)
        if cur_ts and (not prev_ts or cur_ts > prev_ts):
            best_result_by_student[er.student_id] = er

    avaliados_ids: Set[Any] = set(best_result_by_student.keys())

    # Garantir que alunos só presentes via snapshot estejam em students_by_id
    missing = (merged_ids | avaliados_ids) - set(students_by_id.keys())
    if missing:
        extra = (
            Student.query.filter(Student.id.in_(list(missing)))
            .options(joinedload(Student.class_).joinedload(Class.grade))
            .all()
        )
        for s in extra:
            students_by_id[s.id] = s

    matriculados_ids = set(students_by_id.keys()) | set(merged_ids) | set(avaliados_ids)
    # Filtrar só IDs que existem em students_by_id (ou forçar load)
    still_missing = matriculados_ids - set(students_by_id.keys())
    if still_missing:
        for s in Student.query.filter(Student.id.in_(list(still_missing))).all():
            students_by_id[s.id] = s
    matriculados_ids = set(students_by_id.keys())
    matriculados = len(matriculados_ids)
    avaliados = len(avaliados_ids)

    # Detalhe por escola / turma
    mat_by_school: Dict[str, Set[Any]] = defaultdict(set)
    av_by_school: Dict[str, Set[Any]] = defaultdict(set)
    mat_by_class: Dict[Any, Set[Any]] = defaultdict(set)
    av_by_class: Dict[Any, Set[Any]] = defaultdict(set)
    school_names: Dict[str, str] = {}
    class_labels: Dict[Any, Dict[str, Any]] = {}

    for sid in matriculados_ids:
        student = students_by_id.get(sid)
        if not student:
            continue
        result = best_result_by_student.get(sid)
        school_id, class_id, grade_id = _placement_for_student(student, result)

        # Se a colocação caiu fora das turmas do ClassTest filtrado, preferir turma atual no escopo
        if class_id not in class_meta and student.class_id in class_meta:
            class_id = student.class_id
            meta = class_meta[class_id]
            school_id = meta.get("escola_id") or school_id
            grade_id = meta.get("serie_id") or grade_id

        if school_id:
            mat_by_school[school_id].add(sid)
            if sid in avaliados_ids:
                av_by_school[school_id].add(sid)
            if school_id not in school_names:
                name = ""
                for meta in class_meta.values():
                    if meta.get("escola_id") == school_id and meta.get("escola_nome"):
                        name = meta["escola_nome"]
                        break
                if not name:
                    sch = schools_by_id.get(school_id) or School.query.get(school_id)
                    name = sch.name if sch else school_id
                school_names[school_id] = name

        if class_id is not None:
            mat_by_class[class_id].add(sid)
            if sid in avaliados_ids:
                av_by_class[class_id].add(sid)
            if class_id not in class_labels:
                meta = class_meta.get(class_id) or {}
                turma_nome = meta.get("turma_nome")
                serie_nome = meta.get("serie_nome")
                shift = meta.get("shift") or ""
                if not turma_nome:
                    cls_obj = Class.query.get(class_id)
                    if cls_obj:
                        turma_nome = cls_obj.name or ""
                        serie_nome = cls_obj.grade.name if cls_obj.grade else ""
                        shift = normalize_shift(getattr(cls_obj, "shift", None)) or ""
                        grade_id = grade_id or cls_obj.grade_id
                        school_id = school_id or (
                            str(cls_obj.school_id) if cls_obj.school_id else None
                        )
                class_labels[class_id] = {
                    "turma_id": str(class_id),
                    "turma_nome": format_grade_class_label(
                        serie_nome, turma_nome, shift, include_shift=bool(shift)
                    )
                    if serie_nome or turma_nome
                    else (turma_nome or str(class_id)),
                    "escola_id": school_id,
                    "serie_id": str(grade_id) if grade_id is not None else (
                        str(meta.get("serie_id")) if meta.get("serie_id") is not None else None
                    ),
                }

    # Incluir turmas do ClassTest mesmo sem alunos (matriculados 0)
    for cid, meta in class_meta.items():
        if cid not in class_labels:
            class_labels[cid] = {
                "turma_id": str(cid),
                "turma_nome": format_grade_class_label(
                    meta.get("serie_nome"),
                    meta.get("turma_nome"),
                    meta.get("shift"),
                    include_shift=bool(meta.get("shift")),
                ),
                "escola_id": meta.get("escola_id"),
                "serie_id": str(meta["serie_id"]) if meta.get("serie_id") is not None else None,
            }
        sid_school = meta.get("escola_id")
        if sid_school and sid_school not in school_names:
            school_names[sid_school] = meta.get("escola_nome") or sid_school

    por_escola = []
    for school_id in sorted(school_names.keys(), key=lambda x: school_names.get(x, x)):
        m = len(mat_by_school.get(school_id, set()))
        a = len(av_by_school.get(school_id, set()))
        turmas_escola = len(school_class_ids.get(school_id, set()))
        por_escola.append(
            {
                "escola_id": school_id,
                "escola_nome": school_names.get(school_id) or school_id,
                "matriculados": m,
                "avaliados": a,
                "total_turmas": turmas_escola,
                "percentual_participacao": _percentual(a, m),
            }
        )

    por_turma = []
    for class_id, label in sorted(
        class_labels.items(),
        key=lambda item: (item[1].get("escola_id") or "", item[1].get("turma_nome") or ""),
    ):
        m = len(mat_by_class.get(class_id, set()))
        a = len(av_by_class.get(class_id, set()))
        por_turma.append(
            {
                "turma_id": label["turma_id"],
                "turma_nome": label["turma_nome"],
                "escola_id": label.get("escola_id"),
                "serie_id": label.get("serie_id"),
                "matriculados": m,
                "avaliados": a,
                "percentual_participacao": _percentual(a, m),
            }
        )

    logging.info(
        "participation_report municipio=%s tests=%s classes=%s matriculados=%s avaliados=%s",
        municipio_id,
        len(test_ids),
        total_turmas,
        matriculados,
        avaliados,
    )

    return {
        "escopo": escopo,
        "metricas": {
            "matriculados": matriculados,
            "avaliados": avaliados,
            "total_turmas": total_turmas,
            "percentual_participacao": _percentual(avaliados, matriculados),
        },
        "por_escola": por_escola,
        "por_turma": por_turma,
    }
