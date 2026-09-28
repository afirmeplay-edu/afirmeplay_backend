# -*- coding: utf-8 -*-
"""Criar subturmas ADAP e manter o vínculo do aluno na mesma turma."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.permissions.utils import get_manager_school, get_teacher_classes
from app.services.special_education import class_is_special_education


class SubturmaError(ValueError):
    """Regra de negócio da subturma."""


class SubturmaPermissionError(PermissionError):
    """Papel ou escopo sem acesso."""


def class_ids_differ(current_id: Any, new_id: Any) -> bool:
    """Verdadeiro só quando a turma muda. O mesmo id em texto ou UUID não muda."""
    return _norm_id(current_id) != _norm_id(new_id)


def clear_subturma_if_class_changes(student: Any, new_class_id: Any) -> bool:
    """
    Zera subturma_id antes de trocar a turma. Se a turma for a mesma, não mexe.
    Retorna True quando a turma mudou.
    """
    if not class_ids_differ(getattr(student, "class_id", None), new_class_id):
        return False
    student.subturma_id = None
    return True


def _norm_id(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip().lower()
    return text or None


def _level(value: Any) -> int:
    try:
        level = int(value)
    except (TypeError, ValueError):
        raise SubturmaError("Nível inválido. Use 1, 2 ou 3.")
    if level not in (1, 2, 3):
        raise SubturmaError("Nível inválido. Use 1, 2 ou 3.")
    return level


def assert_regular_class(class_obj: Any) -> None:
    if class_is_special_education(class_obj):
        raise SubturmaError("Esta turma é de Educação Especial e não pode ter subturma.")


def validate_support_level_available(class_obj: Any, support_level: Any, existing_levels) -> int:
    assert_regular_class(class_obj)
    level = _level(support_level)
    if int(level) in {int(item) for item in existing_levels}:
        raise SubturmaError(f"Já existe ADAP {level} nesta turma.")
    return level


def link_student_to_subturma(student: Any, subturma: Any) -> None:
    if class_ids_differ(getattr(student, "class_id", None), getattr(subturma, "class_id", None)):
        raise SubturmaError("O aluno não pertence a esta turma.")
    student.subturma_id = subturma.id


def unlink_student_from_subturma(student: Any, subturma: Any) -> None:
    if _norm_id(getattr(student, "subturma_id", None)) != _norm_id(getattr(subturma, "id", None)):
        raise SubturmaError("O aluno não está nesta subturma.")
    student.subturma_id = None


def authorize_subturma_access(user: Dict[str, Any], class_obj: Any, *, write: bool) -> None:
    """
    Escrita: admin, tecadm (município), diretor e coordenador (escola).
    Leitura do professor: só turma em que ele tem vínculo (teacher_class).
    """
    role = str((user or {}).get("role") or "").strip().lower()
    if write and role == "professor":
        raise SubturmaPermissionError("Professor apenas visualiza subturmas.")
    if role == "admin":
        return
    if role == "professor":
        linked = {_norm_id(item) for item in get_teacher_classes(user.get("id"))}
        if _norm_id(getattr(class_obj, "id", None)) not in linked:
            raise SubturmaPermissionError("Você não tem vínculo com esta turma.")
        return
    if role in ("diretor", "coordenador"):
        school_id = get_manager_school(user.get("id"))
        if not school_id or _norm_id(school_id) != _norm_id(getattr(class_obj, "school_id", None)):
            raise SubturmaPermissionError("Você não tem permissão para esta turma.")
        return
    if role == "tecadm":
        city_id = (user or {}).get("tenant_id") or (user or {}).get("city_id")
        school = _school_of(class_obj)
        if not city_id or not school or str(school.city_id) != str(city_id):
            raise SubturmaPermissionError("Você não tem permissão para esta turma.")
        return
    raise SubturmaPermissionError("Você não tem permissão para esta turma.")


def _school_of(class_obj: Any):
    school = getattr(class_obj, "school", None)
    if school is not None:
        return school
    school_id = getattr(class_obj, "school_id", None)
    if not school_id:
        return None
    from app.models.school import School

    return School.query.filter(School.id == str(school_id)).first()


def list_subturma_payload(class_obj: Any) -> List[dict]:
    from app.models.student import Student
    from app.models.subturma import Subturma

    rows = (
        Subturma.query.filter(Subturma.class_id == class_obj.id)
        .order_by(Subturma.support_level.asc())
        .all()
    )
    if not rows:
        return []
    ids = [row.id for row in rows]
    alunos = Student.query.filter(Student.subturma_id.in_(ids)).all()
    by_sub = {}
    for aluno in alunos:
        by_sub.setdefault(_norm_id(aluno.subturma_id), []).append(aluno)
    payload = []
    for row in rows:
        group = by_sub.get(_norm_id(row.id), [])
        group.sort(key=lambda item: (item.name or "").lower())
        payload.append(
            {
                "id": str(row.id),
                "class_id": str(row.class_id),
                "support_level": int(row.support_level),
                "display_name": row.display_name,
                "alunos": [{"id": str(item.id), "name": item.name} for item in group],
            }
        )
    return payload


def remove_subturma(session, subturma: Any) -> None:
    """Apaga a subturma. O class_id dos alunos não é alterado aqui; a FK zera subturma_id."""
    session.delete(subturma)


def create_subturma(class_obj: Any, support_level: Any):
    from app import db
    from app.models.subturma import Subturma

    existing = Subturma.query.filter(Subturma.class_id == class_obj.id).all()
    level = validate_support_level_available(
        class_obj,
        support_level,
        [item.support_level for item in existing],
    )
    row = Subturma(class_id=class_obj.id, support_level=level)
    db.session.add(row)
    db.session.flush()
    return row
