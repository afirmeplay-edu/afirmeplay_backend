"""Geração de PIN de 4 dígitos (sem dependências Flask/SQLAlchemy)."""

from __future__ import annotations

import secrets
from typing import AbstractSet, Optional

PIN_LENGTH = 4
PIN_SPACE = 10**PIN_LENGTH
MAX_GENERATION_ATTEMPTS = 2000


def normalize_registration(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    return s if s else None


def is_valid_pin_format(value: str) -> bool:
    return len(value) == PIN_LENGTH and value.isdigit()


def generate_pin_candidate() -> str:
    return f"{secrets.randbelow(PIN_SPACE):04d}"


def allocate_unique_pin(used: AbstractSet[str]) -> str:
    if len(used) >= PIN_SPACE:
        raise RuntimeError(
            f"Esgotados os {PIN_SPACE} PINs possíveis neste município (schema)."
        )
    for _ in range(MAX_GENERATION_ATTEMPTS):
        pin = generate_pin_candidate()
        if pin not in used:
            return pin
    raise RuntimeError(
        f"Não foi possível gerar PIN único após {MAX_GENERATION_ATTEMPTS} tentativas."
    )
