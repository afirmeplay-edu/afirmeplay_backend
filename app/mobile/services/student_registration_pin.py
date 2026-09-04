"""Geração de PIN de 4 dígitos em ``student.registration`` (único por schema city_*)."""

from __future__ import annotations

from typing import Optional, Set

from sqlalchemy.orm import Session

from app.mobile.services.student_registration_pin_core import (
    PIN_LENGTH,
    PIN_SPACE,
    MAX_GENERATION_ATTEMPTS,
    allocate_unique_pin,
    generate_pin_candidate,
    is_valid_pin_format,
    normalize_registration,
)

__all__ = [
    "PIN_LENGTH",
    "PIN_SPACE",
    "MAX_GENERATION_ATTEMPTS",
    "allocate_unique_pin",
    "assign_registration_pin",
    "collect_used_student_registrations",
    "generate_pin_candidate",
    "is_valid_pin_format",
    "normalize_registration",
]


def collect_used_student_registrations(session: Session) -> Set[str]:
    from app.models.student import Student

    used: Set[str] = set()
    rows = (
        session.query(Student.registration)
        .filter(Student.registration.isnot(None))
        .all()
    )
    for (reg,) in rows:
        norm = normalize_registration(reg)
        if norm:
            used.add(norm)
    return used


def assign_registration_pin(student, session: Session, used: Optional[Set[str]] = None) -> str:
    from app.models.student import Student  # noqa: F401 — tipo do parâmetro

    if used is None:
        used = collect_used_student_registrations(session)
    pin = allocate_unique_pin(used)
    student.registration = pin
    used.add(pin)
    return pin
