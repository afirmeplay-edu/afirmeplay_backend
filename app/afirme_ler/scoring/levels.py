# -*- coding: utf-8 -*-
"""Códigos, rótulos e ordem dos perfis de fluência (PL1…LF)."""
from __future__ import annotations

from typing import Dict, Optional, Tuple

LEVEL_PL1 = "PL1"
LEVEL_PL2 = "PL2"
LEVEL_PL3 = "PL3"
LEVEL_PL4 = "PL4"
LEVEL_LI = "LI"
LEVEL_LF = "LF"

LEVEL_CODES: Tuple[str, ...] = (
    LEVEL_PL1,
    LEVEL_PL2,
    LEVEL_PL3,
    LEVEL_PL4,
    LEVEL_LI,
    LEVEL_LF,
)

LEVEL_LABELS: Dict[str, str] = {
    LEVEL_PL1: "PL1",
    LEVEL_PL2: "PL2",
    LEVEL_PL3: "PL3",
    LEVEL_PL4: "PL4",
    LEVEL_LI: "Leitor Iniciante",
    LEVEL_LF: "Leitor Fluente",
}

SEM_PERFIL_LABEL = "Sem perfil"

PRE_LEITOR_CODES: Tuple[str, ...] = (LEVEL_PL1, LEVEL_PL2, LEVEL_PL3, LEVEL_PL4)

LEVEL_RANK: Dict[str, int] = {code: index for index, code in enumerate(LEVEL_CODES)}

STATUS_PRESENTE = "presente"
STATUS_AUSENTE = "ausente"
STATUS_NAO_AVALIADO = "não avaliado"
STATUS_NAO_ELEGIVEL = "não elegível"

_STATUS_ALIASES = {
    "presente": STATUS_PRESENTE,
    "finalizada": STATUS_PRESENTE,
    "ausente": STATUS_AUSENTE,
    "não avaliado": STATUS_NAO_AVALIADO,
    "nao avaliado": STATUS_NAO_AVALIADO,
    "pendente": STATUS_NAO_AVALIADO,
    "em_andamento": STATUS_NAO_AVALIADO,
    "não elegível": STATUS_NAO_ELEGIVEL,
    "nao elegivel": STATUS_NAO_ELEGIVEL,
    "nao elegível": STATUS_NAO_ELEGIVEL,
    "não elegivel": STATUS_NAO_ELEGIVEL,
}


def normalize_status(value: Optional[str]) -> str:
    if value is None or value == "":
        return STATUS_NAO_AVALIADO
    key = str(value).strip().lower()
    return _STATUS_ALIASES.get(key, STATUS_NAO_AVALIADO)


def is_presente(status: Optional[str]) -> bool:
    return normalize_status(status) == STATUS_PRESENTE


def nivel_label(nivel: Optional[str]) -> str:
    if not nivel:
        return SEM_PERFIL_LABEL
    return LEVEL_LABELS.get(nivel, SEM_PERFIL_LABEL)
