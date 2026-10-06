# -*- coding: utf-8 -*-
"""
Resolução de destinatários por vínculo, em consultas agregadas (sem N+1).

- diretor/coordenador da escola: public.manager.school_id + users.role
- professores da escola: tenant.school_teacher → tenant.teacher → users (role professor)
- tecadm do município: users.city_id + users.role

Alunos e aplicadores nunca entram. Não usa school_managers nem os destinatários do calendário.
"""
from __future__ import annotations

from typing import Dict, Iterable, List

from app import db
from app.models.manager import Manager
from app.models.schoolTeacher import SchoolTeacher
from app.models.teacher import Teacher
from app.models.user import RoleEnum, User

_ROLE_PRIORITY = {RoleEnum.DIRETOR: 0, RoleEnum.COORDENADOR: 1, RoleEnum.PROFESSOR: 2}


def school_staff_by_school(school_ids: Iterable[str]) -> Dict[str, List[Dict[str, str]]]:
    """
    {school_id: [{'user_id', 'school_id', 'role'}]} com diretor, coordenador e professores.
    Ordenado por diretor → coordenador → professor; quem tem mais de um vínculo aparece
    uma vez por escola, com o perfil de maior prioridade.
    """
    ids = sorted({str(s) for s in school_ids if s})
    result: Dict[str, List[Dict[str, str]]] = {sid: [] for sid in ids}
    if not ids:
        return result

    managers = (
        db.session.query(Manager.school_id, User.id, User.role)
        .join(User, User.id == Manager.user_id)
        .filter(
            Manager.school_id.in_(ids),
            User.role.in_([RoleEnum.DIRETOR, RoleEnum.COORDENADOR]),
        )
        .all()
    )
    teachers = (
        db.session.query(SchoolTeacher.school_id, User.id, User.role)
        .join(Teacher, Teacher.id == SchoolTeacher.teacher_id)
        .join(User, User.id == Teacher.user_id)
        .filter(SchoolTeacher.school_id.in_(ids), User.role == RoleEnum.PROFESSOR)
        .all()
    )

    best: Dict[tuple, RoleEnum] = {}
    for school_id, user_id, role in list(managers) + list(teachers):
        key = (str(school_id), str(user_id))
        current = best.get(key)
        if current is None or _ROLE_PRIORITY[role] < _ROLE_PRIORITY[current]:
            best[key] = role

    ordered = sorted(best.items(), key=lambda kv: (kv[0][0], _ROLE_PRIORITY[kv[1]], kv[0][1]))
    for (school_id, user_id), role in ordered:
        result.setdefault(school_id, []).append(
            {"user_id": user_id, "school_id": school_id, "role": role.value}
        )
    return result


def city_tecadms(city_id: str) -> List[Dict[str, str]]:
    """[{'user_id', 'school_id': None, 'role': 'tecadm'}] do município."""
    if not city_id:
        return []
    rows = (
        db.session.query(User.id)
        .filter(User.role == RoleEnum.TECADM, User.city_id == str(city_id))
        .order_by(User.id)
        .all()
    )
    return [
        {"user_id": str(user_id), "school_id": None, "role": RoleEnum.TECADM.value}
        for (user_id,) in rows
    ]
