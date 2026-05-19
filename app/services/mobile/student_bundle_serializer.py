"""Serialização de alunos para pacotes mobile (sync/bundle e offline-pack/redeem)."""
from __future__ import annotations

from typing import Any, Dict

from sqlalchemy.orm import Query, joinedload

from app.models.student import Student


def student_bundle_query_options(query: Query) -> Query:
    """Evita N+1 ao resolver nomes de escola, série e turma."""
    return query.options(
        joinedload(Student.school),
        joinedload(Student.grade),
        joinedload(Student.class_),
    )


def serialize_student_for_bundle(student: Student) -> Dict[str, Any]:
    school_name = student.school.name if student.school else None
    grade_name = student.grade.name if student.grade else None
    class_name = student.class_.name if student.class_ else None

    return {
        "id": student.id,
        "name": student.name,
        "registration": student.registration,
        "user_id": student.user_id,
        "class_id": str(student.class_id) if student.class_id else None,
        "grade_id": str(student.grade_id) if student.grade_id else None,
        "school_id": student.school_id,
        "school_name": school_name,
        "grade_name": grade_name,
        "class_name": class_name,
    }
