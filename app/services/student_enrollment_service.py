# -*- coding: utf-8 -*-
"""Matrícula (student_school_enrollment): fechar vigente e abrir nova conforme colocação atual."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from app.models.student import Student

logger = logging.getLogger(__name__)


def _session(session: Optional[Session]) -> Session:
    if session is not None:
        return session
    from app import db

    return db.session


def close_active_enrollment(session: Optional[Session], student_id: str, valid_to: Optional[datetime] = None) -> int:
    """
    Encerra períodos vigentes (valid_to IS NULL) do aluno.
    Retorna número de linhas atualizadas.
    """
    from app.models.studentSchoolEnrollment import StudentSchoolEnrollment

    sess = _session(session)
    vt = valid_to or datetime.utcnow()
    q = sess.query(StudentSchoolEnrollment).filter(
        StudentSchoolEnrollment.student_id == student_id,
        StudentSchoolEnrollment.valid_to.is_(None),
    )
    n = q.update({StudentSchoolEnrollment.valid_to: vt}, synchronize_session=False)
    if n:
        logger.debug("Fechadas %s matrícula(ões) vigente(s) do aluno %s", n, student_id)
    return n


def open_enrollment(
    session: Optional[Session],
    student_id: str,
    *,
    school_id: Optional[str],
    class_id: Optional[object],
    valid_from: Optional[datetime] = None,
) -> None:
    """Abre novo período de matrícula (vigente). Chame após close_active_enrollment."""
    from app.models.studentSchoolEnrollment import StudentSchoolEnrollment

    sess = _session(session)
    rec = StudentSchoolEnrollment(
        student_id=student_id,
        school_id=school_id,
        class_id=class_id,
        valid_from=valid_from or datetime.utcnow(),
        valid_to=None,
    )
    sess.add(rec)


def sync_enrollment_from_student_placement(session: Optional[Session], student: "Student") -> None:
    """
    Alinha matrícula vigente à colocação atual do aluno (class_id / school_id).
    Sem turma e sem escola: apenas encerra vigência.
    """
    close_active_enrollment(session, student.id)
    if student.class_id is not None and student.school_id:
        open_enrollment(session, student.id, school_id=student.school_id, class_id=student.class_id)
    elif student.school_id:
        open_enrollment(session, student.id, school_id=student.school_id, class_id=None)


def assert_same_municipality_two_schools(
    session: Optional[Session],
    school_id_a: str,
    school_id_b: str,
) -> None:
    """Garante duas escolas distintas no mesmo município (city_id)."""
    from app.models.school import School

    sess = _session(session)
    if str(school_id_a) == str(school_id_b):
        raise ValueError("A escola de destino deve ser diferente da escola de origem.")
    sa = sess.query(School).filter(School.id == str(school_id_a)).first()
    sb = sess.query(School).filter(School.id == str(school_id_b)).first()
    if not sa or not sb:
        raise ValueError("Escola não encontrada.")
    if not sa.city_id or sa.city_id != sb.city_id:
        raise ValueError("As escolas precisam pertencer ao mesmo município (city_id).")


def transfer_student_to_class(
    session: Optional[Session],
    student: "Student",
    new_class: object,
    *,
    update_user_city: bool = True,
) -> None:
    """
    Move aluno para outra turma (e escola da turma), atualizando matrícula e opcionalmente city_id do usuário.
    """
    from app.models.school import School

    sess = _session(session)
    new_sid = new_class.school_id
    old_sid = student.school_id

    to_school = sess.query(School).filter(School.id == str(new_sid)).first()
    if not to_school:
        raise ValueError("Escola da turma de destino não encontrada.")

    if old_sid and str(old_sid) != str(new_sid):
        assert_same_municipality_two_schools(sess, str(old_sid), str(new_sid))
    else:
        if student.user and student.user.city_id and student.user.city_id != to_school.city_id:
            raise ValueError("A turma de destino deve estar no mesmo município (city_id) do cadastro do aluno.")

    close_active_enrollment(sess, student.id)
    student.class_id = new_class.id
    student.school_id = new_sid

    if update_user_city and student.user and to_school.city_id:
        if student.user.city_id != to_school.city_id:
            student.user.city_id = to_school.city_id

    open_enrollment(sess, student.id, school_id=new_sid, class_id=new_class.id)


def transfer_class_to_school(
    session: Optional[Session],
    class_obj: object,
    target_school_id: str,
) -> int:
    """
    Move a turma inteira para outra escola do mesmo município.
    Atualiza class.school_id e school_id de todos os alunos da turma; renova matrículas.
    Retorna quantidade de alunos atualizados.
    """
    from app.models.school import School
    from app.models.student import Student

    sess = _session(session)
    old_school_id = class_obj.school_id
    assert_same_municipality_two_schools(sess, str(old_school_id), str(target_school_id))

    ns = sess.query(School).filter(School.id == str(target_school_id)).first()
    if not ns:
        raise ValueError("Escola de destino não encontrada.")

    class_obj.school_id = target_school_id
    students = sess.query(Student).filter(Student.class_id == class_obj.id).all()
    for st in students:
        close_active_enrollment(sess, st.id)
        st.school_id = target_school_id
        if st.user and ns.city_id and st.user.city_id != ns.city_id:
            st.user.city_id = ns.city_id
        open_enrollment(sess, st.id, school_id=target_school_id, class_id=class_obj.id)
    return len(students)
