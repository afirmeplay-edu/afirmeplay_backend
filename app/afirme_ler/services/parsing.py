# -*- coding: utf-8 -*-
"""Utilitários de parse e validação do módulo Afirme Ler."""
from __future__ import annotations

import json
import re
from typing import Any, List, Optional, Tuple

ALLOWED_TEXT_DIFFICULTIES = frozenset({
    "VERY_EASY",
    "EASY",
    "MEDIUM",
    "HARD",
    "VERY_HARD",
})

ALLOWED_WORD_LIST_KINDS = frozenset({
    "PALAVRAS",
    "POUCO_COMUNS",
})

ALLOWED_ASSESSMENT_TYPES = frozenset({
    "fluencia",
    "compreensao",
    "completa",
})

ALLOWED_EVALUATION_STATUSES = frozenset({
    "rascunho",
    "agendada",
    "em_andamento",
    "concluida",
    "cancelada",
})

ALLOWED_SESSION_STATUSES = frozenset({
    "pendente",
    "em_andamento",
    "finalizada",
    "ausente",
})

SCOPE_GLOBAL = "GLOBAL"
SCOPE_CITY = "CITY"
SCOPE_PRIVATE = "PRIVATE"


def get_field(data: dict, *keys: str, default=None):
    for key in keys:
        if key in data:
            return data[key]
    return default


def parse_string_list(value: Any, *, split_words: bool = False) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return []
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        except json.JSONDecodeError:
            pass
        if split_words:
            parts = re.split(r"[\n,;]+", raw)
            return [part.strip() for part in parts if part.strip()]
        return [raw]
    raise ValueError("Valor deve ser uma lista ou string JSON.")


def validate_difficulty_level(value: str) -> str:
    if not value or not isinstance(value, str):
        raise ValueError("difficultyLevel é obrigatório.")
    normalized = value.strip().upper()
    if normalized not in ALLOWED_TEXT_DIFFICULTIES:
        allowed = ", ".join(sorted(ALLOWED_TEXT_DIFFICULTIES))
        raise ValueError(f"difficultyLevel inválido. Valores permitidos: {allowed}.")
    return normalized


def validate_word_list_kind(value: str) -> str:
    if not value or not isinstance(value, str):
        raise ValueError("kind é obrigatório.")
    normalized = value.strip().upper()
    if normalized not in ALLOWED_WORD_LIST_KINDS:
        allowed = ", ".join(sorted(ALLOWED_WORD_LIST_KINDS))
        raise ValueError(f"kind inválido. Valores permitidos: {allowed}.")
    return normalized


def validate_assessment_type(value: str) -> str:
    if not value or not isinstance(value, str):
        raise ValueError("assessmentType é obrigatório.")
    normalized = value.strip().lower()
    if normalized not in ALLOWED_ASSESSMENT_TYPES:
        allowed = ", ".join(sorted(ALLOWED_ASSESSMENT_TYPES))
        raise ValueError(f"assessmentType inválido. Valores permitidos: {allowed}.")
    return normalized


def validate_evaluation_status(value: str) -> str:
    if not value or not isinstance(value, str):
        raise ValueError("status é obrigatório.")
    normalized = value.strip().lower()
    if normalized not in ALLOWED_EVALUATION_STATUSES:
        allowed = ", ".join(sorted(ALLOWED_EVALUATION_STATUSES))
        raise ValueError(f"status inválido. Valores permitidos: {allowed}.")
    return normalized


def validate_question_options(
    options: Any,
    correct_option: Optional[int],
) -> Tuple[List[str], Optional[int]]:
    parsed = parse_string_list(options)
    if len(parsed) < 2:
        raise ValueError("options deve conter pelo menos 2 alternativas.")
    if correct_option is not None:
        if not isinstance(correct_option, int):
            raise ValueError("correctOption deve ser um número inteiro.")
        if correct_option < 0 or correct_option >= len(parsed):
            raise ValueError("correctOption fora do intervalo das alternativas.")
    return parsed, correct_option
