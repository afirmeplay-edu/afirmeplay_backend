# -*- coding: utf-8 -*-
"""Utilitários de parse e validação do módulo Afirme Ler."""
from __future__ import annotations

import json
import re
import unicodedata
from typing import Any, List, Optional, Tuple

ALLOWED_TEXT_DIFFICULTIES = frozenset({
    "VERY_EASY",
    "EASY",
    "MEDIUM",
    "HARD",
    "VERY_HARD",
})

ALLOWED_WORD_LIST_KINDS = frozenset({
    "PALAVRAS_CONHECIDAS",
    "POUCO_COMUNS",
})

WORD_LIST_KIND_ALIASES = {
    "PALAVRAS": "PALAVRAS_CONHECIDAS",
    "CONHECIDAS": "PALAVRAS_CONHECIDAS",
    "KNOWN": "PALAVRAS_CONHECIDAS",
}

ALLOWED_EVALUATION_KINDS = frozenset({
    "entrada",
    "formativa",
    "saida",
})

EVALUATION_KIND_LABELS = {
    "entrada": "Avaliação de Entrada",
    "formativa": "Avaliação Formativa",
    "saida": "Avaliação de Saída",
}

EVALUATION_KIND_ALIASES = {
    "entrada": "entrada",
    "avaliacao de entrada": "entrada",
    "avaliacao_de_entrada": "entrada",
    "avaliacao_entrada": "entrada",
    "formativa": "formativa",
    "avaliacao formativa": "formativa",
    "avaliacao_formativa": "formativa",
    "saida": "saida",
    "avaliacao de saida": "saida",
    "avaliacao_de_saida": "saida",
    "avaliacao_saida": "saida",
}

KIND_PALAVRAS_CONHECIDAS = "PALAVRAS_CONHECIDAS"
KIND_POUCO_COMUNS = "POUCO_COMUNS"

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

ALLOWED_GUIDED_SESSION_STATUSES = frozenset({
    "em_andamento",
    "finalizada",
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
    normalized = value.strip().upper().replace("-", "_").replace(" ", "_")
    normalized = WORD_LIST_KIND_ALIASES.get(normalized, normalized)
    if normalized not in ALLOWED_WORD_LIST_KINDS:
        allowed = ", ".join(sorted(ALLOWED_WORD_LIST_KINDS))
        raise ValueError(f"kind inválido. Valores permitidos: {allowed}.")
    return normalized


def _strip_accents(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value)
    return "".join(char for char in decomposed if unicodedata.category(char) != "Mn")


def validate_evaluation_kind(value: str) -> str:
    if not value or not isinstance(value, str):
        raise ValueError("evaluationKind é obrigatório.")
    normalized = _strip_accents(value.strip().lower())
    normalized = " ".join(normalized.split())
    mapped = EVALUATION_KIND_ALIASES.get(normalized, normalized)
    if mapped not in ALLOWED_EVALUATION_KINDS:
        allowed = ", ".join(sorted(ALLOWED_EVALUATION_KINDS))
        raise ValueError(f"evaluationKind inválido. Valores permitidos: {allowed}.")
    return mapped


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


def validate_guided_session_status(value: str) -> str:
    if not value or not isinstance(value, str):
        raise ValueError("status é obrigatório.")
    normalized = value.strip().lower()
    if normalized not in ALLOWED_GUIDED_SESSION_STATUSES:
        allowed = ", ".join(sorted(ALLOWED_GUIDED_SESSION_STATUSES))
        raise ValueError(f"status inválido. Valores permitidos: {allowed}.")
    return normalized


def validate_prosody_level(value: Any) -> int:
    try:
        level = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("prosodyLevel deve ser um inteiro entre 1 e 5.") from exc
    if level < 1 or level > 5:
        raise ValueError("prosodyLevel deve ser um inteiro entre 1 e 5.")
    return level


def calculate_guided_metrics(words_read: int, errors_count: int, reading_time_seconds: int):
    """Retorna (calculated_plcm, calculated_accuracy)."""
    correct_words = max(0, words_read - errors_count)
    accuracy = None
    plcm = None
    if words_read > 0:
        accuracy = round(100.0 * correct_words / words_read, 2)
    if reading_time_seconds > 0:
        plcm = round(correct_words / (reading_time_seconds / 60.0), 2)
    return plcm, accuracy
