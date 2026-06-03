# -*- coding: utf-8 -*-
"""Operações sobre student_password_log (relatório de senhas e limpeza)."""
from __future__ import annotations

import unicodedata
import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Query, Session

if TYPE_CHECKING:
    from app.models.student import Student


def _normalize_person_name(name: Optional[str]) -> str:
    if not name:
        return ""
    decomposed = unicodedata.normalize("NFD", name)
    ascii_name = "".join(c for c in decomposed if unicodedata.category(c) != "Mn")
    return " ".join(ascii_name.upper().split())


def migrate_password_logs_to_new_school(
    session: Session,
    student_id: str,
    old_school_id: str,
    *,
    new_school_id: str,
    class_id: Optional[object] = None,
    grade_id: Optional[object] = None,
    city_id: Optional[str] = None,
) -> int:
    """
    Move logs de senha da escola de origem para a colocação na escola de destino
    (credenciais acompanham o aluno em transferência entre escolas).
    """
    from app.models.studentPasswordLog import StudentPasswordLog

    if not student_id or not old_school_id or not new_school_id:
        return 0
    if str(old_school_id) == str(new_school_id):
        return 0

    values = {
        "school_id": str(new_school_id),
        "class_id": class_id,
        "grade_id": grade_id,
    }
    if city_id:
        values["city_id"] = city_id

    n = (
        session.query(StudentPasswordLog)
        .filter(
            StudentPasswordLog.student_id == student_id,
            StudentPasswordLog.school_id == str(old_school_id),
        )
        .update(values, synchronize_session=False)
    )
    if n:
        return n

    from app.models.student import Student

    student = session.query(Student).filter(Student.id == student_id).first()
    if not student or not student.user_id:
        return 0

    return (
        session.query(StudentPasswordLog)
        .filter(
            StudentPasswordLog.user_id == student.user_id,
            StudentPasswordLog.school_id == str(old_school_id),
        )
        .update(
            {**values, "student_id": student_id},
            synchronize_session=False,
        )
    )


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


def sync_password_logs_with_student_placement(
    session: Session,
    student: "Student",
) -> int:
    """
    Alinha class_id, grade_id, school_id e city_id dos logs à matrícula atual do aluno
    na escola em que está matriculado.
    """
    from app.models.school import School
    from app.models.studentPasswordLog import StudentPasswordLog

    if not student.id or not student.school_id:
        return 0

    school_id = str(student.school_id)
    values = {
        "class_id": student.class_id,
        "grade_id": student.grade_id,
        "school_id": school_id,
    }
    school = session.query(School).filter(School.id == school_id).first()
    if school and school.city_id:
        values["city_id"] = school.city_id

    return (
        session.query(StudentPasswordLog)
        .filter(
            StudentPasswordLog.student_id == student.id,
            StudentPasswordLog.school_id == school_id,
        )
        .update(values, synchronize_session=False)
    )


def sync_password_logs_for_class_school_relocation(
    session: Session,
    class_id: object,
    old_school_id: str,
    new_school_id: str,
    *,
    city_id: Optional[str] = None,
) -> int:
    """Atualiza school_id (e city_id) dos logs da turma ao mover a turma de escola."""
    from app.models.studentPasswordLog import StudentPasswordLog

    if not class_id or not old_school_id or not new_school_id:
        return 0

    values = {"school_id": str(new_school_id)}
    if city_id:
        values["city_id"] = city_id

    return (
        session.query(StudentPasswordLog)
        .filter(
            StudentPasswordLog.class_id == class_id,
            StudentPasswordLog.school_id == str(old_school_id),
        )
        .update(values, synchronize_session=False)
    )


def _create_password_log_from_template(
    session: Session,
    student: "Student",
    template_log: object,
) -> object:
    from app.models.school import School
    from app.models.studentPasswordLog import StudentPasswordLog
    from app.models.user import User

    school = session.query(School).filter(School.id == str(student.school_id)).first()
    user = session.query(User).get(student.user_id) if student.user_id else None
    display_name = (student.name or (user.name if user else None) or template_log.student_name)
    email = (user.email if user and user.email else template_log.email)
    registration = (
        student.registration
        or (user.registration if user else None)
        or template_log.registration
    )
    new_log = StudentPasswordLog(
        id=str(uuid.uuid4()),
        student_name=display_name,
        email=email,
        password=template_log.password,
        registration=registration,
        user_id=student.user_id or template_log.user_id,
        student_id=student.id,
        class_id=student.class_id,
        grade_id=student.grade_id,
        school_id=str(student.school_id),
        city_id=(school.city_id if school and school.city_id else template_log.city_id),
    )
    session.add(new_log)
    return new_log


def ensure_password_log_for_student_placement(session: Session, student: "Student") -> bool:
    """
    Garante um log de senha na escola/turma atuais do aluno.
    Reutiliza log do mesmo student_id, user_id ou cadastro legado com nome equivalente.
    """
    from app.models.school import School
    from app.models.studentPasswordLog import StudentPasswordLog
    from app.models.user import User

    if not student.id or not student.school_id:
        return False

    school_id = str(student.school_id)
    if (
        session.query(StudentPasswordLog)
        .filter(
            StudentPasswordLog.student_id == student.id,
            StudentPasswordLog.school_id == school_id,
        )
        .first()
    ):
        sync_password_logs_with_student_placement(session, student)
        return True

    other_school_log = (
        session.query(StudentPasswordLog)
        .filter(
            StudentPasswordLog.student_id == student.id,
            StudentPasswordLog.school_id != school_id,
        )
        .first()
    )
    if other_school_log:
        school = session.query(School).filter(School.id == school_id).first()
        migrate_password_logs_to_new_school(
            session,
            student.id,
            str(other_school_log.school_id),
            new_school_id=school_id,
            class_id=student.class_id,
            grade_id=student.grade_id,
            city_id=school.city_id if school else None,
        )
        return True

    if student.user_id:
        user_log = (
            session.query(StudentPasswordLog)
            .filter(StudentPasswordLog.user_id == student.user_id)
            .order_by(StudentPasswordLog.created_at.desc())
            .first()
        )
        if user_log:
            if str(user_log.school_id) == school_id and user_log.student_id == student.id:
                sync_password_logs_with_student_placement(session, student)
            elif str(user_log.school_id) != school_id:
                school = session.query(School).filter(School.id == school_id).first()
                migrate_password_logs_to_new_school(
                    session,
                    student.id,
                    str(user_log.school_id),
                    new_school_id=school_id,
                    class_id=student.class_id,
                    grade_id=student.grade_id,
                    city_id=school.city_id if school else None,
                )
            else:
                _create_password_log_from_template(session, student, user_log)
            return True

    display_name = student.name
    if not display_name and student.user_id:
        user = session.query(User).get(student.user_id)
        display_name = user.name if user else None
    norm = _normalize_person_name(display_name)
    if norm:
        for legacy_log in (
            session.query(StudentPasswordLog)
            .filter(StudentPasswordLog.student_id != student.id)
            .order_by(StudentPasswordLog.created_at.desc())
        ):
            if _normalize_person_name(legacy_log.student_name) == norm:
                _create_password_log_from_template(session, student, legacy_log)
                return True

    return False


def provision_password_logs_for_report_scope(
    session: Session,
    *,
    school_id: Optional[str] = None,
    class_id: Optional[object] = None,
    grade_id: Optional[object] = None,
) -> int:
    """Cria ou alinha logs para alunos matriculados no recorte antes de gerar relatório."""
    from app.models.student import Student

    q = session.query(Student).filter(Student.school_id.isnot(None))
    if school_id:
        q = q.filter(Student.school_id == str(school_id))
    if class_id:
        q = q.filter(Student.class_id == class_id)
    if grade_id:
        q = q.filter(Student.grade_id == grade_id)

    created = 0
    for student in q.all():
        if ensure_password_log_for_student_placement(session, student):
            created += 1
    session.flush()
    return created


def apply_active_student_password_log_filter(query: Query) -> Query:
    """
    Restringe o relatório a logs cujo aluno ainda está matriculado na escola do registro.
    Exclui alunos desvinculados, transferidos ou removidos diretamente do banco.
    """
    from app.models.student import Student
    from app.models.studentPasswordLog import StudentPasswordLog

    return query.join(
        Student, StudentPasswordLog.student_id == Student.id
    ).filter(
        Student.school_id == StudentPasswordLog.school_id,
        or_(
            Student.class_id == StudentPasswordLog.class_id,
            (Student.class_id.is_(None) & StudentPasswordLog.class_id.is_(None)),
        ),
    )


def build_password_report_query(session: Session) -> Query:
    """
    Query base do relatório de senhas (Excel/PDF) com filtro de aluno ativo.

    Credenciais vêm do log; escola, turma e série refletem a matrícula atual (Student).
    """
    from app.models.city import City
    from app.models.grades import Grade
    from app.models.school import School
    from app.models.student import Student
    from app.models.studentClass import Class
    from app.models.studentPasswordLog import StudentPasswordLog

    return (
        apply_active_student_password_log_filter(
            session.query(
                StudentPasswordLog,
                School,
                City,
                Class,
                Grade,
            )
        )
        .outerjoin(School, Student.school_id == School.id)
        .outerjoin(City, School.city_id == City.id)
        .outerjoin(Class, Student.class_id == Class.id)
        .outerjoin(Grade, Student.grade_id == Grade.id)
    )
