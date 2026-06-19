# -*- coding: utf-8 -*-
import pytest

from app.afirme_ler.services.parsing import (
    parse_string_list,
    validate_difficulty_level,
    validate_question_options,
    validate_word_list_kind,
)


def test_validate_difficulty_level_accepts_mvp_values():
    assert validate_difficulty_level("medium") == "MEDIUM"
    assert validate_difficulty_level("VERY_HARD") == "VERY_HARD"


def test_validate_difficulty_level_rejects_invalid():
    with pytest.raises(ValueError, match="difficultyLevel inválido"):
        validate_difficulty_level("ULTRA_HARD")


def test_validate_word_list_kind():
    assert validate_word_list_kind("palavras") == "PALAVRAS"
    assert validate_word_list_kind("POUCO_COMUNS") == "POUCO_COMUNS"


def test_parse_string_list_from_json_string():
    assert parse_string_list('["A", "B"]') == ["A", "B"]


def test_parse_string_list_split_words():
    assert parse_string_list("NEVE, LATA\nPIPOCA", split_words=True) == [
        "NEVE",
        "LATA",
        "PIPOCA",
    ]


def test_validate_question_options_requires_minimum_two():
    with pytest.raises(ValueError, match="pelo menos 2"):
        validate_question_options(["A"], None)


def test_validate_question_options_correct_index():
    options, correct = validate_question_options(["A", "B", "C"], 1)
    assert options == ["A", "B", "C"]
    assert correct == 1


def test_validate_assessment_type():
    from app.afirme_ler.services.parsing import validate_assessment_type

    assert validate_assessment_type("completa") == "completa"
    assert validate_assessment_type("FLUENCIA") == "fluencia"


def test_validate_question_options_rejects_out_of_range():
    with pytest.raises(ValueError, match="fora do intervalo"):
        validate_question_options(["A", "B"], 5)
