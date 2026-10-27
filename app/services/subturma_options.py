# -*- coding: utf-8 -*-
"""Listagem de subturmas ADAP para formulários (prova subjetiva e cartão-resposta).

Cada tela decide o rótulo e o recorte. Sem filtros extras, a lista traz todos os
níveis e também subturmas sem aluno, na ordem série, turma e nível.
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, Iterable, List, Optional, Sequence


def _uuid_list(values: Sequence[Any]) -> List[Any]:
    out = []
    for value in values:
        if isinstance(value, uuid.UUID):
            out.append(value)
            continue
        try:
            out.append(uuid.UUID(str(value).strip()))
        except (TypeError, ValueError, AttributeError):
            continue
    return out


def list_subturma_rows(
    *,
    grade_ids: Optional[Sequence[Any]] = None,
    school_ids: Optional[Sequence[Any]] = None,
    allowed_class_ids: Optional[Sequence[Any]] = None,
    levels: Optional[Iterable[int]] = None,
    only_with_students: bool = False,
    exclude_special_parent: bool = False,
) -> List[Dict[str, Any]]:
    """
    Linhas {subturma, class, grade, school, students_count}.

    school_ids / allowed_class_ids: None não filtra; lista vazia não devolve nada.
    exclude_special_parent: tira turmas-mãe de série Suporte N / etapa ADAP.
    """
    from sqlalchemy import func

    from app import db
    from app.models.grades import Grade
    from app.models.school import School
    from app.models.student import Student
    from app.models.studentClass import Class
    from app.models.subturma import Subturma
    from app.services.special_education import (
        is_adap_education_stage,
        support_level_from_exact_grade_name,
    )

    if school_ids is not None and not list(school_ids):
        return []
    if allowed_class_ids is not None and not list(allowed_class_ids):
        return []

    query = (
        db.session.query(Subturma, Class, Grade)
        .join(Class, Class.id == Subturma.class_id)
        .join(Grade, Grade.id == Class.grade_id)
    )
    if grade_ids:
        query = query.filter(Class.grade_id.in_(_uuid_list(grade_ids)))
    if school_ids is not None:
        query = query.filter(Class.school_id.in_([str(item) for item in school_ids]))
    if allowed_class_ids is not None:
        query = query.filter(Class.id.in_(_uuid_list(allowed_class_ids)))
    if levels is not None:
        query = query.filter(Subturma.support_level.in_([int(level) for level in levels]))
    rows = query.order_by(Grade.name.asc(), Class.name.asc(), Subturma.support_level.asc()).all()
    if not rows:
        return []

    counts = {
        str(subturma_id): int(total)
        for subturma_id, total in (
            db.session.query(Student.subturma_id, func.count(Student.id))
            .filter(Student.subturma_id.in_([sub.id for sub, _, _ in rows]))
            .group_by(Student.subturma_id)
            .all()
        )
    }
    school_map = {
        str(item.id): item
        for item in School.query.filter(
            School.id.in_({str(cls.school_id) for _, cls, _ in rows if cls.school_id})
        ).all()
    }

    out: List[Dict[str, Any]] = []
    for sub, class_obj, grade in rows:
        total = counts.get(str(sub.id), 0)
        if only_with_students and total == 0:
            continue
        if exclude_special_parent and (
            is_adap_education_stage(getattr(grade, "education_stage_id", None))
            or support_level_from_exact_grade_name(getattr(grade, "name", None)) is not None
        ):
            continue
        out.append({
            "subturma": sub,
            "class": class_obj,
            "grade": grade,
            "school": school_map.get(str(class_obj.school_id)) if class_obj.school_id else None,
            "students_count": total,
        })
    return out
