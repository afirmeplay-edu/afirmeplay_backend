"""
Disponibilidade de avaliações e cartões-resposta para o município.

Admin e tecadm sempre veem e operam o conteúdo. Demais papéis municipais
(diretor, coordenador, professor, aplicador) só listam/aplicam/geram quando:

    available_to_municipality is True
    AND (available_from is NULL OR now >= available_from)

Aluno continua usando a janela de ClassTest (application/expiration).
Registros existentes ficam visíveis (default True, available_from NULL).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

UNAVAILABLE_CODE = "NOT_AVAILABLE_TO_MUNICIPALITY"
UNAVAILABLE_MESSAGE = "Conteúdo ainda não disponível para o município"

_OVERRIDE_ROLES = frozenset({"admin", "tecadm"})


def _normalize_role(role: Any) -> str:
    if role is None:
        return ""
    if hasattr(role, "value"):
        role = role.value
    text = str(role).strip().lower()
    if "." in text:
        text = text.split(".")[-1]
    return text


def role_bypasses_municipality_availability(role: Any) -> bool:
    return _normalize_role(role) in _OVERRIDE_ROLES


def user_bypasses_municipality_availability(user: Optional[dict]) -> bool:
    if not user:
        return False
    return role_bypasses_municipality_availability(user.get("role"))


def parse_available_to_municipality(value: Any, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "sim"}:
            return True
        if normalized in {"false", "0", "no", "nao", "não"}:
            return False
    return default


def parse_available_from(value: Any) -> Tuple[Optional[datetime], Optional[str]]:
    """
    Converte ISO-8601 em datetime aware (UTC).
    None ou '' limpa a data. Retorna (datetime|None, erro|None).
    """
    if value is None or value == "":
        return None, None
    if isinstance(value, datetime):
        dt = value
    else:
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None, "available_from deve ser uma data/hora ISO-8601"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt, None


def is_available_to_municipality(record: Any, now: Optional[datetime] = None) -> bool:
    if not bool(getattr(record, "available_to_municipality", True)):
        return False
    available_from = getattr(record, "available_from", None)
    if available_from is None:
        return True
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    else:
        current = current.astimezone(timezone.utc)
    start = available_from
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    else:
        start = start.astimezone(timezone.utc)
    return current >= start


def user_can_access_municipality_content(user: Optional[dict], record: Any) -> bool:
    if user_bypasses_municipality_availability(user):
        return True
    role = _normalize_role((user or {}).get("role", ""))
    if role == "aluno":
        return True
    return is_available_to_municipality(record)


def apply_municipality_availability_filter(query, model, user: Optional[dict]):
    if user_bypasses_municipality_availability(user):
        return query
    from sqlalchemy import or_

    now = datetime.now(timezone.utc)
    return query.filter(
        model.available_to_municipality.is_(True),
        or_(model.available_from.is_(None), model.available_from <= now),
    )


def municipality_availability_payload(record: Any) -> Dict[str, Any]:
    available_from = getattr(record, "available_from", None)
    return {
        "available_to_municipality": bool(
            getattr(record, "available_to_municipality", True)
        ),
        "available_from": available_from.isoformat() if available_from else None,
        "is_available_to_municipality_now": is_available_to_municipality(record),
    }


def apply_availability_fields(
    record: Any,
    data: dict,
    user: Optional[dict],
) -> Tuple[bool, Optional[str]]:
    """
    Aplica available_to_municipality / available_from no record.
    Só admin/tecadm podem alterar; demais papéis ignoram os campos.
    """
    if not user_bypasses_municipality_availability(user):
        return False, None
    if not isinstance(data, dict):
        return False, None

    changed = False
    if "available_to_municipality" in data:
        new_flag = parse_available_to_municipality(
            data.get("available_to_municipality"),
            default=True,
        )
        if bool(getattr(record, "available_to_municipality", True)) != new_flag:
            record.available_to_municipality = new_flag
            changed = True
        else:
            record.available_to_municipality = new_flag

    if "available_from" in data:
        parsed, err = parse_available_from(data.get("available_from"))
        if err:
            return False, err
        record.available_from = parsed
        changed = True

    return changed, None


def resolve_availability_for_create(
    data: dict,
    user: Optional[dict],
) -> Tuple[bool, Optional[datetime], Optional[str]]:
    """Valores iniciais na criação. Papéis sem override sempre nascem visíveis."""
    if not user_bypasses_municipality_availability(user):
        return True, None, None
    flag = parse_available_to_municipality(
        data.get("available_to_municipality") if isinstance(data, dict) else None,
        default=True,
    )
    parsed = None
    if isinstance(data, dict) and "available_from" in data:
        parsed, err = parse_available_from(data.get("available_from"))
        if err:
            return True, None, err
    return flag, parsed, None


def unavailable_to_municipality_response():
    from flask import jsonify

    return (
        jsonify({
            "error": UNAVAILABLE_MESSAGE,
            "code": UNAVAILABLE_CODE,
        }),
        403,
    )
