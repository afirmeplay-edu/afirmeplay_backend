# -*- coding: utf-8 -*-
"""
Contexto canônico da avaliação: course_name e has_matematica.

Uma avaliação pertence a um único curso. Não misturar cursos da escola.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Optional, Sequence

logger = logging.getLogger(__name__)


def resolve_course_name_from_test(test: Any) -> str:
    """Resolve EducationStage a partir de ``Test.course`` (UUID ou nome)."""
    if test is None:
        return "Anos Iniciais"
    raw = getattr(test, "course", None)
    if not raw:
        return "Anos Iniciais"
    text = str(raw).strip()
    if not text:
        return "Anos Iniciais"

    try:
        from app.models.educationStage import EducationStage

        try:
            stage_id = uuid.UUID(text)
            stage = EducationStage.query.get(stage_id)
            if stage and getattr(stage, "name", None):
                return str(stage.name)
        except (ValueError, TypeError):
            stage = EducationStage.query.filter(
                EducationStage.name.ilike(text)
            ).first()
            if stage and getattr(stage, "name", None):
                return str(stage.name)
            # Já é um rótulo textual utilizável.
            return text
    except Exception as exc:
        logger.warning("resolve_course_name_from_test: %s", exc)
    return "Anos Iniciais"


def resolve_course_name_from_test_id(test_id: Any) -> str:
    if not test_id:
        return "Anos Iniciais"
    try:
        from app.models.test import Test

        test = Test.query.get(str(test_id))
        return resolve_course_name_from_test(test)
    except Exception:
        return "Anos Iniciais"


def infer_has_matematica_from_test(test: Any) -> Optional[bool]:
    """True se a prova tem Matemática; False se só outras; None se indeterminado."""
    if test is None:
        return None
    names = []
    try:
        subjects_info = getattr(test, "subjects_info", None) or []
        if isinstance(subjects_info, list):
            for item in subjects_info:
                if isinstance(item, dict):
                    names.append(str(item.get("name") or item.get("subject_name") or ""))
                else:
                    names.append(str(item))
        rel = getattr(test, "subject_rel", None)
        if rel is not None and getattr(rel, "name", None):
            names.append(str(rel.name))
    except Exception:
        pass

    known = [n for n in names if n.strip()]
    if not known:
        return None
    if any("matem" in n.lower() for n in known):
        return True
    return False


def infer_has_matematica_from_results(results: Sequence[Any]) -> Optional[bool]:
    """Detecta Matemática a partir de subject_results / proficiency_by_subject."""
    saw_any = False
    for row in results or []:
        raw = getattr(row, "subject_results", None) or getattr(
            row, "proficiency_by_subject", None
        )
        if not isinstance(raw, dict):
            continue
        for data in raw.values():
            if not isinstance(data, dict):
                continue
            name = str(data.get("subject_name") or "")
            if not name:
                continue
            saw_any = True
            if "matem" in name.lower():
                return True
    if saw_any:
        return False
    return None


def resolve_contexto_avaliacao(
    test_ids: Sequence[Any],
    *,
    results: Optional[Sequence[Any]] = None,
) -> tuple:
    """
    Retorna ``(course_name, has_matematica)`` para o pacote de provas.

    Usa o curso da primeira prova; has_matematica agrega todas.
    """
    ids = [str(t) for t in (test_ids or []) if t]
    course_name = "Anos Iniciais"
    has_mat: Optional[bool] = None
    if ids:
        course_name = resolve_course_name_from_test_id(ids[0])
        try:
            from app.models.test import Test

            tests = Test.query.filter(Test.id.in_(ids)).all()
            flags = [infer_has_matematica_from_test(t) for t in tests]
            if any(f is True for f in flags):
                has_mat = True
            elif flags and all(f is False for f in flags):
                has_mat = False
        except Exception:
            has_mat = None
    if has_mat is None and results:
        has_mat = infer_has_matematica_from_results(results)
    return course_name, has_mat
