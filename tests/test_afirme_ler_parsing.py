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
    assert validate_word_list_kind("palavras") == "PALAVRAS_CONHECIDAS"
    assert validate_word_list_kind("PALAVRAS_CONHECIDAS") == "PALAVRAS_CONHECIDAS"
    assert validate_word_list_kind("POUCO_COMUNS") == "POUCO_COMUNS"


def test_validate_evaluation_kind():
    from app.afirme_ler.services.parsing import validate_evaluation_kind

    assert validate_evaluation_kind("entrada") == "entrada"
    assert validate_evaluation_kind("Avaliação de Saída") == "saida"
    assert validate_evaluation_kind("formativa") == "formativa"


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


def test_validate_evaluation_kind_rejects_invalid():
    from app.afirme_ler.services.parsing import validate_evaluation_kind

    with pytest.raises(ValueError, match="evaluationKind inválido"):
        validate_evaluation_kind("diagnostica")


def test_validate_assessment_type():
    from app.afirme_ler.services.parsing import validate_assessment_type

    assert validate_assessment_type("completa") == "completa"
    assert validate_assessment_type("FLUENCIA") == "fluencia"


def test_validate_question_options_rejects_out_of_range():
    with pytest.raises(ValueError, match="fora do intervalo"):
        validate_question_options(["A", "B"], 5)


def test_validate_question_options_requires_correct_answer():
    with pytest.raises(ValueError, match="alternativa correta"):
        validate_question_options(["A", "B", "C"], None)


def test_validate_question_options_accepts_is_correct_objects():
    options, correct = validate_question_options(
        [
            {"text": "Correu", "isCorrect": False},
            {"text": "Andou devagar", "isCorrect": True},
            {"text": "Voou", "isCorrect": False},
        ]
    )
    assert options == ["Correu", "Andou devagar", "Voou"]
    assert correct == 1


def test_validate_question_options_rejects_multiple_is_correct():
    with pytest.raises(ValueError, match="exatamente uma"):
        validate_question_options(
            [
                {"text": "A", "isCorrect": True},
                {"text": "B", "isCorrect": True},
            ]
        )


def test_validate_question_options_rejects_is_correct_mismatch():
    with pytest.raises(ValueError, match="não corresponde"):
        validate_question_options(
            [
                {"text": "A", "isCorrect": False},
                {"text": "B", "isCorrect": True},
            ],
            0,
        )


def test_parse_grade_id_filters():
    from app.afirme_ler.services.parsing import parse_grade_id_filters

    one = "11111111-1111-1111-1111-111111111111"
    two = "22222222-2222-2222-2222-222222222222"
    assert parse_grade_id_filters({"gradeId": one}) == [one]
    assert parse_grade_id_filters({"gradeIds": f"{one},{two}"}) == [one, two]
    assert parse_grade_id_filters({"gradeId": one, "gradeIds": two}) == [two, one]
    assert parse_grade_id_filters({}) == []
    with pytest.raises(ValueError, match="gradeId inválido"):
        parse_grade_id_filters({"gradeId": "nao-e-uuid"})


def test_parse_reading_question_payload_accepts_enunciado():
    from app.afirme_ler.services.parsing import parse_reading_question_payload

    payload = parse_reading_question_payload(
        {
            "enunciado": "Quem ganhou a corrida?",
            "options": ["Lebre", "Tartaruga"],
            "correctOption": 1,
            "descriptor": "Localizar informação",
        }
    )
    assert payload["statement"] == "Quem ganhou a corrida?"
    assert payload["correct_option"] == 1
    assert payload["options"] == ["Lebre", "Tartaruga"]
