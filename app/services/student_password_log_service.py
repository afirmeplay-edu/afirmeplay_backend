# -*- coding: utf-8 -*-
"""Operações sobre student_password_log (relatório de senhas e limpeza)."""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Query, Session


def delete_password_logs_for_student_at_school(
    session: Session,
    student_id: str,
    school_id: str,
) -> int:
    """Remove logs de senha do aluno na escola informada."""
    from app.models.studentPasswordLog import StudentPasswordLog

    if not student_id or not school_id:
        return 0
    return (
        session.query(StudentPasswordLog)
        .filter(
            StudentPasswordLog.student_id == student_id,
            StudentPasswordLog.school_id == school_id,
        )
        .delete(synchronize_session=False)
    )


def apply_active_student_password_log_filter(query: Query) -> Query:
    """
    Restringe o relatório a logs cujo aluno ainda está matriculado na escola do registro.
    Exclui alunos desvinculados, transferidos ou removidos diretamente do banco.
    """
    from app.models.student import Student
    from app.models.studentPasswordLog import StudentPasswordLog

    return query.join(
        Student, StudentPasswordLog.student_id == Student.id
    ).filter(Student.school_id == StudentPasswordLog.school_id)


def build_password_report_query(session: Session) -> Query:
    """Query base do relatório de senhas (Excel/PDF) com filtro de aluno ativo."""
    from app.models.city import City
    from app.models.grades import Grade
    from app.models.school import School
    from app.models.studentClass import Class
    from app.models.studentPasswordLog import StudentPasswordLog

    return apply_active_student_password_log_filter(
        session.query(
            StudentPasswordLog,
            School,
            City,
            Class,
            Grade,
        )
        .outerjoin(School, StudentPasswordLog.school_id == School.id)
        .outerjoin(City, StudentPasswordLog.city_id == City.id)
        .outerjoin(Class, StudentPasswordLog.class_id == Class.id)
        .outerjoin(Grade, StudentPasswordLog.grade_id == Grade.id)
    )
