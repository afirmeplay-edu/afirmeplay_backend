"""Códigos de plano municipal (public.city.plan_code)."""

from typing import FrozenSet

PLAN_BASIC = "basic"
PLAN_PLUS = "plus"

VALID_PLAN_CODES: FrozenSet[str] = frozenset({PLAN_BASIC, PLAN_PLUS})
DEFAULT_PLAN_CODE = PLAN_BASIC


def normalize_plan_code(value) -> str:
    """Valida e normaliza plan_code; levanta ValueError se inválido."""
    if value is None:
        return DEFAULT_PLAN_CODE
    code = str(value).strip().lower()
    if code not in VALID_PLAN_CODES:
        raise ValueError(
            f"plan_code inválido: '{value}'. Valores permitidos: {', '.join(sorted(VALID_PLAN_CODES))}"
        )
    return code
