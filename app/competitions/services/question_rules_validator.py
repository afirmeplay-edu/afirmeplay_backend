# -*- coding: utf-8 -*-
"""
Validação das regras de seleção de questões (question_rules) de competições.

Estrutura recomendada de question_rules (JSON):

{
  "num_questions": 20,
  "grade_filter": {
    "grade_ids": ["6EF", "7EF"],
    "min_grade_level": 6,
    "max_grade_level": 7
  },
  "difficulty_filter": {
    "levels": ["easy", "medium"]
  },
  "tags_filter": ["fractions", "geometry"],
  "allow_repeated_questions": false,
  "random_seed": null,
  "strategy": "uniform"
}

Campos antigos ainda são aceitos para compatibilidade:
- grade_ids (top-level)  -> equivalente a grade_filter.grade_ids
- difficulty_level       -> equivalente a difficulty_filter.levels com um único valor
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, Optional

from app.competitions.exceptions import ValidationError


def validate_question_rules(rules: Optional[Dict[str, Any]]) -> None:
    """
    Valida o JSON question_rules.

    Não obriga a presença de todos os campos, mas valida o formato e tipos
    quando presentes. Levanta ValidationError em caso de inconsistência.
    """
    if rules is None:
        # Sem regras explícitas: o serviço usará defaults (ex.: num_questions = 10)
        return

    if not isinstance(rules, dict):
        raise ValidationError("question_rules deve ser um objeto JSON")

    _validate_num_questions(rules)
    _validate_grade_filter(rules)
    _validate_difficulty_filter(rules)
    _validate_tags_filter(rules)
    _validate_allow_repeated_questions(rules)
    _validate_random_seed(rules)
    _validate_strategy(rules)


def _validate_num_questions(rules: Dict[str, Any]) -> None:
    if "num_questions" not in rules:
        # Permitido: service pode assumir default
        return
    value = rules["num_questions"]
    try:
        value_int = int(value)
    except (TypeError, ValueError):
        raise ValidationError("question_rules.num_questions deve ser um inteiro") from None
    if value_int < 1:
        raise ValidationError("question_rules.num_questions deve ser >= 1")


def _validate_grade_filter(rules: Dict[str, Any]) -> None:
    grade_filter = rules.get("grade_filter")
    # Compatibilidade: grade_ids no nível raiz é aceito sem grade_filter
    if grade_filter is None:
        if "grade_ids" in rules:
            _ensure_iterable_of_str(rules["grade_ids"], "question_rules.grade_ids")
        return

    if not isinstance(grade_filter, dict):
        raise ValidationError("question_rules.grade_filter deve ser um objeto JSON")

    if "grade_ids" in grade_filter:
        _ensure_iterable_of_str(
            grade_filter["grade_ids"],
            "question_rules.grade_filter.grade_ids",
        )

    min_lvl = grade_filter.get("min_grade_level")
    max_lvl = grade_filter.get("max_grade_level")

    if min_lvl is not None:
        _ensure_int(min_lvl, "question_rules.grade_filter.min_grade_level")
    if max_lvl is not None:
        _ensure_int(max_lvl, "question_rules.grade_filter.max_grade_level")
    if min_lvl is not None and max_lvl is not None:
        try:
            if int(min_lvl) > int(max_lvl):
                raise ValidationError(
                    "question_rules.grade_filter.min_grade_level "
                    "não pode ser maior que max_grade_level"
                )
        except (TypeError, ValueError):
            # Já foi validado acima; aqui é só uma segurança extra
            raise ValidationError(
                "question_rules.grade_filter.min_grade_level e "
                "max_grade_level devem ser inteiros"
            ) from None


def _validate_difficulty_filter(rules: Dict[str, Any]) -> None:
    difficulty_filter = rules.get("difficulty_filter")

    # Compatibilidade: difficulty_level no nível raiz
    if difficulty_filter is None:
        if "difficulty_level" in rules:
            if not isinstance(rules["difficulty_level"], str):
                raise ValidationError(
                    "question_rules.difficulty_level deve ser uma string"
                )
        return

    if not isinstance(difficulty_filter, dict):
        raise ValidationError("question_rules.difficulty_filter deve ser um objeto JSON")

    levels = difficulty_filter.get("levels")
    if levels is None:
        return

    if not isinstance(levels, (list, tuple)):
        raise ValidationError("question_rules.difficulty_filter.levels deve ser uma lista")
    if not levels:
        raise ValidationError(
            "question_rules.difficulty_filter.levels não pode ser uma lista vazia"
        )

    for lvl in levels:
        if not isinstance(lvl, str):
            raise ValidationError(
                "question_rules.difficulty_filter.levels deve conter apenas strings"
            )


def _validate_tags_filter(rules: Dict[str, Any]) -> None:
    if "tags_filter" not in rules:
        return
    _ensure_iterable_of_str(rules["tags_filter"], "question_rules.tags_filter")


def _validate_allow_repeated_questions(rules: Dict[str, Any]) -> None:
    if "allow_repeated_questions" not in rules:
        return
    value = rules["allow_repeated_questions"]
    if not isinstance(value, bool):
        raise ValidationError(
            "question_rules.allow_repeated_questions deve ser booleano (true/false)"
        )


def _validate_random_seed(rules: Dict[str, Any]) -> None:
    if "random_seed" not in rules or rules["random_seed"] is None:
        return
    _ensure_int(rules["random_seed"], "question_rules.random_seed")


def _validate_strategy(rules: Dict[str, Any]) -> None:
    if "strategy" not in rules or rules["strategy"] is None:
        return
    strategy = rules["strategy"]
    if not isinstance(strategy, str):
        raise ValidationError("question_rules.strategy deve ser uma string")
    # Nesta etapa só suportamos 'uniform'; outros valores são reservados para o futuro
    if strategy not in ("uniform",):
        raise ValidationError("question_rules.strategy inválido; use 'uniform'")


def _ensure_int(value: Any, field: str) -> None:
    try:
        int(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{field} deve ser um inteiro") from None


def _ensure_iterable_of_str(value: Any, field: str) -> None:
    if not isinstance(value, (list, tuple)):
        raise ValidationError(f"{field} deve ser uma lista")
    for item in value:
        if not isinstance(item, str):
            raise ValidationError(f"{field} deve conter apenas strings")

