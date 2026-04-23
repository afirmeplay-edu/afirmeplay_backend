import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from flask import g
from sqlalchemy import func

from app import db
from app.models.school import School
from app.models.student import Student
from app.models.studentClass import Class
from app.models.classTest import ClassTest
from app.models.test import Test
from app.models.testQuestion import TestQuestion
from app.models.question import Question
from app.models.user import User
from app.models.mobile_models import MobileSyncBundleGeneration

from app.services.mobile.content_hash import compute_test_content_version, question_to_canon
from app.utils.response_formatters import _get_all_subjects_from_test


def _ttl_hours() -> int:
    try:
        return int(os.getenv("MOBILE_BUNDLE_TTL_HOURS", "48"))
    except ValueError:
        return 48


def _current_bundle_version(school_id: str) -> int:
    v = (
        db.session.query(func.max(MobileSyncBundleGeneration.sync_bundle_version))
        .filter(MobileSyncBundleGeneration.school_id == school_id)
        .scalar()
    )
    return int(v or 0)


def _latest_generation(school_id: str) -> Optional[MobileSyncBundleGeneration]:
    return (
        MobileSyncBundleGeneration.query.filter_by(school_id=school_id)
        .order_by(MobileSyncBundleGeneration.sync_bundle_version.desc())
        .first()
    )


def ensure_bundle_generation(
    school_id: str,
    since_bundle_version: Optional[int],
    refresh: bool,
    page: int,
) -> Tuple[int, datetime, bool]:
    """
    Retorna (sync_bundle_version, bundle_valid_until, is_unchanged_shortcut).
    Atalho unchanged apenas na página 1 (checagem de snapshot completo).
    """
    current = _current_bundle_version(school_id)
    if (
        since_bundle_version is not None
        and since_bundle_version == current
        and current > 0
        and not refresh
        and page == 1
    ):
        row = _latest_generation(school_id)
        if row:
            return row.sync_bundle_version, row.bundle_valid_until, True

    if since_bundle_version is not None and since_bundle_version > current:
        raise ValueError("since_bundle_version inválido (maior que a versão atual)")

    if current == 0 or refresh:
        new_v = (current + 1) if current > 0 else 1
        valid_until = datetime.utcnow() + timedelta(hours=_ttl_hours())
        row = MobileSyncBundleGeneration(
            school_id=school_id,
            sync_bundle_version=new_v,
            bundle_valid_until=valid_until,
        )
        db.session.add(row)
        db.session.flush()
        return new_v, valid_until, False

    row = _latest_generation(school_id)
    if not row:
        raise RuntimeError("estado de bundle inconsistente")
    return row.sync_bundle_version, row.bundle_valid_until, False


def collect_school_scope(school_id: str) -> Tuple[List[str], Dict[str, Test], List[Tuple[str, str]]]:
    school = School.query.get(school_id)
    if not school:
        raise ValueError("escola não encontrada")

    class_ids = [c.id for c in Class.query.filter_by(school_id=school_id).all()]
    if not class_ids:
        return [], {}, []

    class_tests = ClassTest.query.filter(ClassTest.class_id.in_(class_ids)).all()
    test_ids = list({ct.test_id for ct in class_tests})

    student_links: List[Tuple[str, str]] = []
    seen = set()
    for ct in class_tests:
        studs = Student.query.filter_by(class_id=ct.class_id).all()
        for s in studs:
            key = (s.id, ct.test_id)
            if key not in seen:
                seen.add(key)
                student_links.append((s.id, ct.test_id))

    tests: Dict[str, Test] = {}
    if test_ids:
        for t in Test.query.filter(Test.id.in_(test_ids)).all():
            tests[t.id] = t
    return test_ids, tests, student_links


def build_tests_questions_payload(
    tests: Dict[str, Test]
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, str], Dict[str, List[Dict[str, Any]]]]:
    """
    Busca questões em public.question. Retorna:
    tests_payload, test_content_version_by_id, questions_list_by_test
    """
    out_tests: Dict[str, Dict[str, Any]] = {}
    versions: Dict[str, str] = {}
    q_by_test: Dict[str, List[Dict[str, Any]]] = {}

    for tid, test in tests.items():
        tq_rows = (
            TestQuestion.query.filter_by(test_id=tid).order_by(TestQuestion.order.asc()).all()
        )
        q_ids = [r.question_id for r in tq_rows]

        # Question está em public.* (metadata); não depende de search_path.
        q_objs = Question.query.filter(Question.id.in_(q_ids)).all() if q_ids else []

        q_map = {q.id: q for q in q_objs}
        ordered_payload: List[Dict[str, Any]] = []
        for r in tq_rows:
            q = q_map.get(r.question_id)
            if not q:
                continue
            item = question_to_canon(q)
            item["order"] = r.order
            ordered_payload.append(item)

        test_dict = {
            "id": test.id,
            "title": test.title,
            "description": test.description,
            "intructions": test.intructions,
            "type": test.type,
            "max_score": test.max_score,
            "duration": test.duration,
            "evaluation_mode": test.evaluation_mode,
            "subject": test.subject,
            "subjects_info": _get_all_subjects_from_test(test),
            "grade_id": str(test.grade_id) if test.grade_id else None,
            "status": test.status,
        }
        out_tests[tid] = test_dict
        versions[tid] = compute_test_content_version(test_dict, ordered_payload)
        q_by_test[tid] = ordered_payload

    return out_tests, versions, q_by_test


def serialize_students_page(
    school_id: str,
    page: int,
    page_size: int,
) -> Tuple[List[Dict[str, Any]], int, int]:
    """Lista alunos da escola paginada; total alunos da escola."""
    q = Student.query.filter_by(school_id=school_id).order_by(Student.name.asc())
    total = q.count()
    items = q.offset((page - 1) * page_size).limit(page_size).all()
    out = []
    for s in items:
        u = User.query.get(s.user_id) if s.user_id else None
        out.append(
            {
                "id": s.id,
                "name": s.name,
                "registration": s.registration,
                "email": u.email if u else None,
                "user_id": s.user_id,
                "password_hash": u.password_hash if u else None,
                "class_id": str(s.class_id) if s.class_id else None,
                "grade_id": str(s.grade_id) if s.grade_id else None,
                "school_id": s.school_id,
            }
        )
    total_pages = max(1, (total + page_size - 1) // page_size)
    return out, total, total_pages


def build_bundle_response(
    school_id: str,
    since_bundle_version: Optional[int],
    page: int,
    page_size: int,
    refresh: bool,
) -> Dict[str, Any]:
    gen_version, valid_until, unchanged = ensure_bundle_generation(
        school_id, since_bundle_version, refresh, page
    )
    if unchanged:
        return {
            "sync_bundle_version": gen_version,
            "bundle_valid_until": valid_until.isoformat() + "Z",
            "unchanged": True,
            "school_id": school_id,
            "page": page,
            "page_size": page_size,
            "students": [],
            "tests": {},
            "questions_by_test": {},
            "test_content_version": {},
            "student_test_links": [],
        }

    test_ids, tests_map, student_links = collect_school_scope(school_id)
    tests_payload, content_versions, questions_by_test = build_tests_questions_payload(tests_map)

    links_out = [{"student_id": a, "test_id": b} for a, b in student_links]

    include_full = page == 1
    if include_full:
        students, total_students, total_pages = serialize_students_page(
            school_id, page, page_size
        )
        body: Dict[str, Any] = {
            "sync_bundle_version": gen_version,
            "bundle_valid_until": valid_until.isoformat() + "Z",
            "unchanged": False,
            "school_id": school_id,
            "page": page,
            "page_size": page_size,
            "total_students": total_students,
            "total_pages": total_pages,
            "students": students,
            "tests": tests_payload,
            "questions_by_test": questions_by_test,
            "test_content_version": content_versions,
            "student_test_links": links_out,
        }
        return body

    students, total_students, total_pages = serialize_students_page(
        school_id, page, page_size
    )
    return {
        "sync_bundle_version": gen_version,
        "bundle_valid_until": valid_until.isoformat() + "Z",
        "unchanged": False,
        "school_id": school_id,
        "page": page,
        "page_size": page_size,
        "total_students": total_students,
        "total_pages": total_pages,
        "students": students,
        "tests": {},
        "questions_by_test": {},
        "test_content_version": {},
        "student_test_links": [],
        "includes_full_payload": False,
    }
