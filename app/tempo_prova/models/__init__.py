# -*- coding: utf-8 -*-
"""DTOs e helpers de persistência do tempo estimado de prova.

A coluna ``estimated_time`` vive em ``tenant.test`` (``app.models.test.Test``).
"""
from __future__ import annotations

from typing import Any, Optional

from app.report_analysis.evaluation_time import resolve_estimated_time_minutes


def apply_estimated_time_to_test(test: Any, grade_name: Optional[str] = None) -> int:
    """Preenche ``test.estimated_time`` a partir da série, se ainda não houver valor."""
    minutes = resolve_estimated_time_minutes(test=test, grade_name=grade_name)
    if getattr(test, "estimated_time", None) in (None, 0):
        test.estimated_time = minutes
    return int(test.estimated_time)


def estimated_time_from_grade_name(grade_name: Optional[str]) -> int:
    from app.report_analysis.evaluation_time import estimated_time_minutes_for_grade

    return estimated_time_minutes_for_grade(grade_name)
