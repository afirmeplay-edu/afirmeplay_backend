# -*- coding: utf-8 -*-
"""Helpers para sincronizar turmas configuradas (test.classes) e aplicadas (class_test)."""

import json
import logging
from typing import Any, Dict, List, Optional, Set

from app import db
from app.models.classTest import ClassTest
from app.models.evaluationResult import EvaluationResult
from app.models.grades import Grade
from app.models.school import School
from app.models.student import Student
from app.models.studentAnswer import StudentAnswer
from app.models.studentClass import Class
from app.utils.uuid_helpers import ensure_uuid, ensure_uuid_list


def parse_test_class_ids(test) -> List:
    """Extrai lista de IDs de turmas do campo test.classes."""
    if not test or not test.classes:
        return []

    class_ids = test.classes
    if isinstance(class_ids, str):
        try:
            parsed = json.loads(class_ids)
            class_ids = parsed if isinstance(parsed, list) else [parsed]
        except (json.JSONDecodeError, TypeError):
            class_ids = [class_ids]
    elif not isinstance(class_ids, list):
        class_ids = [class_ids]

    return class_ids


def _build_class_info(class_obj) -> Optional[Dict[str, Any]]:
    if not class_obj:
        return None

    school_obj = School.query.filter(School.id == str(class_obj.school_id)).first()
    grade_obj = Grade.query.get(class_obj.grade_id)
    students_count = len(class_obj.students) if class_obj.students else 0

    return {
        "id": class_obj.id,
        "name": class_obj.name,
        "students_count": students_count,
        "school": {
            "id": school_obj.id,
            "name": school_obj.name,
        } if school_obj else None,
        "grade": {
            "id": grade_obj.id,
            "name": grade_obj.name,
        } if grade_obj else None,
    }


def resolve_test_classes(test, class_tests=None) -> List[Dict[str, Any]]:
    """
    União de test.classes (configuradas) com metadados de ClassTest.
    Retorna turmas configuradas enriquecidas com status e datas de aplicação.
    """
    if class_tests is None:
        class_tests = ClassTest.query.filter_by(test_id=str(test.id)).all()

    class_test_by_class_id = {ct.class_id: ct for ct in class_tests}
    configured_ids = ensure_uuid_list(parse_test_class_ids(test))
    classes_info = []

    if configured_ids:
        specific_classes = Class.query.filter(Class.id.in_(configured_ids)).all()
        class_by_id = {c.id: c for c in specific_classes}

        for class_id in configured_ids:
            class_obj = class_by_id.get(class_id)
            if not class_obj:
                continue

            class_info = _build_class_info(class_obj)
            if not class_info:
                continue

            ct = class_test_by_class_id.get(class_id)
            if ct:
                classes_info.append({
                    "class_test_id": ct.id,
                    "class": class_info,
                    "students_count": class_info["students_count"],
                    "application": ct.application if ct.application else None,
                    "expiration": ct.expiration if ct.expiration else None,
                    "status": "applied",
                })
            else:
                classes_info.append({
                    "class_test_id": None,
                    "class": class_info,
                    "students_count": class_info["students_count"],
                    "application": None,
                    "expiration": None,
                    "status": "configured",
                })
        return classes_info

    if class_tests:
        for ct in class_tests:
            class_obj = Class.query.get(ct.class_id)
            if not class_obj:
                continue
            class_info = _build_class_info(class_obj)
            if not class_info:
                continue
            classes_info.append({
                "class_test_id": ct.id,
                "class": class_info,
                "students_count": class_info["students_count"],
                "application": ct.application if ct.application else None,
                "expiration": ct.expiration if ct.expiration else None,
                "status": "applied",
            })
        return classes_info

    return []


def resolve_test_classes_from_schools(test) -> List[Dict[str, Any]]:
    """Fallback: turmas de todas as escolas configuradas em test.schools."""
    if not test or not test.schools:
        return []

    school_ids = test.schools
    if isinstance(school_ids, str):
        try:
            parsed = json.loads(school_ids)
            school_ids = parsed if isinstance(parsed, list) else [parsed]
        except (json.JSONDecodeError, TypeError):
            school_ids = [school_ids]
    elif not isinstance(school_ids, list):
        school_ids = [school_ids]

    if not school_ids:
        return []

    all_classes = Class.query.filter(Class.school_id.in_(school_ids)).all()
    classes_info = []
    for class_obj in all_classes:
        class_info = _build_class_info(class_obj)
        if not class_info:
            continue
        classes_info.append({
            "class_test_id": None,
            "class": class_info,
            "students_count": class_info["students_count"],
            "application": None,
            "expiration": None,
            "status": "configured",
        })
    return classes_info


def class_test_has_responses(test_id: str, class_id) -> bool:
    """Verifica se há respostas ou resultados para a combinação test + turma."""
    class_id_uuid = ensure_uuid(class_id)
    if not class_id_uuid:
        return False

    has_answers = (
        StudentAnswer.query.filter_by(test_id=str(test_id))
        .join(Student, Student.id == StudentAnswer.student_id)
        .filter(Student.class_id == class_id_uuid)
        .first()
        is not None
    )
    if has_answers:
        return True

    has_results = (
        EvaluationResult.query.filter_by(test_id=str(test_id))
        .filter(
            db.or_(
                EvaluationResult.class_id_snapshot == class_id_uuid,
                db.and_(
                    EvaluationResult.class_id_snapshot.is_(None),
                    EvaluationResult.student_id.in_(
                        db.session.query(Student.id).filter(Student.class_id == class_id_uuid)
                    ),
                ),
            )
        )
        .first()
        is not None
    )
    return has_results


def remove_orphaned_class_tests(test_id: str, new_class_ids: List) -> Dict[str, List[str]]:
    """
    Remove ClassTest de turmas que saíram de test.classes.
    Mantém registros com respostas de alunos e retorna avisos.
    """
    new_class_ids_set: Set = set(ensure_uuid_list(new_class_ids))
    class_tests = ClassTest.query.filter_by(test_id=str(test_id)).all()

    removed = []
    kept_with_responses = []

    for ct in class_tests:
        if ct.class_id in new_class_ids_set:
            continue
        if class_test_has_responses(test_id, ct.class_id):
            kept_with_responses.append(str(ct.class_id))
            logging.warning(
                "ClassTest %s mantido: turma %s possui respostas para test %s",
                ct.id, ct.class_id, test_id,
            )
            continue
        db.session.delete(ct)
        removed.append(str(ct.class_id))

    return {
        "removed_class_ids": removed,
        "kept_with_responses_class_ids": kept_with_responses,
    }


def merge_apply_classes_payload(
    test,
    payload_classes: List[Dict[str, Any]],
    sync_configured_classes: bool = True,
) -> tuple:
    """
    Mescla turmas do payload com test.classes ausentes.
    Retorna (classes_to_process, skipped_class_ids).
    """
    classes_to_process = list(payload_classes or [])
    seen_class_ids = set()

    for item in classes_to_process:
        class_id = item.get("class_id")
        class_id_uuid = ensure_uuid(class_id)
        if class_id_uuid:
            seen_class_ids.add(class_id_uuid)

    skipped = []
    if not sync_configured_classes:
        return classes_to_process, skipped

    reference_application = None
    reference_expiration = None
    for item in classes_to_process:
        if item.get("application"):
            reference_application = item.get("application")
        if item.get("expiration"):
            reference_expiration = item.get("expiration")
        if reference_application and reference_expiration:
            break

    configured_ids = ensure_uuid_list(parse_test_class_ids(test))
    for class_id in configured_ids:
        if class_id in seen_class_ids:
            continue
        if not reference_application or not reference_expiration:
            skipped.append(str(class_id))
            continue
        classes_to_process.append({
            "class_id": str(class_id),
            "application": reference_application,
            "expiration": reference_expiration,
        })
        seen_class_ids.add(class_id)

    return classes_to_process, skipped


def count_pending_classes(test, class_tests=None) -> int:
    """Conta turmas em test.classes sem registro em ClassTest."""
    if class_tests is None:
        class_tests = ClassTest.query.filter_by(test_id=str(test.id)).all()

    configured_ids = set(ensure_uuid_list(parse_test_class_ids(test)))
    if not configured_ids:
        return 0

    applied_ids = {ct.class_id for ct in class_tests}
    return len(configured_ids - applied_ids)
