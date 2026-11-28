# -*- coding: utf-8 -*-
"""Alocação e lookup do token OMR ID-Grid (6 hex) persistido no tenant."""

from __future__ import annotations

import logging
import secrets
import uuid
from typing import Any, Dict, Optional

from app import db
from app.models.answerSheetIdentityCode import AnswerSheetIdentityCode
from app.services.cartao_resposta.identity_grid import (
    KIND_GABARITO,
    KIND_PHYSICAL,
    checksum_nibble,
    decode_token,
)

logger = logging.getLogger(__name__)

_MAX_CODE_ATTEMPTS = 32


def _build_code_from_token5(token5: str) -> str:
    payload = (token5 or "").strip().upper()
    if len(payload) != 5 or any(ch not in "0123456789ABCDEF" for ch in payload):
        raise ValueError(f"token5 inválido: {token5!r}")
    return f"{payload}{checksum_nibble(payload):X}"


def _generate_unique_code() -> str:
    """Gera code 6 hex (5 aleatórios + checksum) ainda livre no tenant."""
    for _ in range(_MAX_CODE_ATTEMPTS):
        token5 = f"{secrets.randbits(20):05X}"
        code = _build_code_from_token5(token5)
        exists = (
            AnswerSheetIdentityCode.query.filter_by(code=code).limit(1).first()
        )
        if not exists:
            return code
    raise RuntimeError("Não foi possível alocar code ID-Grid sem colisão")


def get_by_code(code: str) -> Optional[AnswerSheetIdentityCode]:
    """Lookup por code impresso. None se checksum inválido ou ausente."""
    decoded = decode_token(code)
    if not decoded:
        return None
    return AnswerSheetIdentityCode.query.filter_by(code=decoded["raw"]).first()


def allocate_code(
    kind: str,
    student_id: str,
    *,
    gabarito_id: Optional[str] = None,
    test_id: Optional[str] = None,
) -> str:
    """
    Garante 1 code : 1 aluno : 1 gabarito|prova.

    Reimpressão devolve o mesmo code. Cria linha se ainda não existir.
    """
    k = str(kind or "").strip()[:1]
    sid = str(student_id or "").strip()
    gid = str(gabarito_id or "").strip() or None
    tid = str(test_id or "").strip() or None

    if not sid:
        raise ValueError("student_id obrigatório para allocate_code")
    if k == KIND_GABARITO:
        if not gid:
            raise ValueError("gabarito_id obrigatório para kind=1")
        tid = None
        existing = AnswerSheetIdentityCode.query.filter_by(
            student_id=sid, gabarito_id=gid
        ).first()
    elif k == KIND_PHYSICAL:
        if not tid:
            raise ValueError("test_id obrigatório para kind=2")
        gid = None
        existing = AnswerSheetIdentityCode.query.filter_by(
            student_id=sid, test_id=tid
        ).first()
    else:
        raise ValueError(f"kind inválido: {kind!r}")

    if existing:
        return existing.code

    code = _generate_unique_code()
    row = AnswerSheetIdentityCode(
        id=str(uuid.uuid4()),
        code=code,
        kind=k,
        student_id=sid,
        gabarito_id=gid,
        test_id=tid,
    )
    db.session.add(row)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        # Corrida: outro worker pode ter inserido o par 1:1:1
        if k == KIND_GABARITO:
            again = AnswerSheetIdentityCode.query.filter_by(
                student_id=sid, gabarito_id=gid
            ).first()
        else:
            again = AnswerSheetIdentityCode.query.filter_by(
                student_id=sid, test_id=tid
            ).first()
        if again:
            return again.code
        raise

    logger.info(
        "ID-Grid token alocado code=%s kind=%s student=%s… doc=%s…",
        code,
        k,
        sid[:8],
        (gid or tid or "")[:8],
    )
    return code


def identity_dict_from_code(code: str) -> Optional[Dict[str, Any]]:
    """Checksum + lookup → dict com IDs completos (espelho do QR)."""
    row = get_by_code(code)
    if not row:
        return None
    return row.to_identity_dict()
