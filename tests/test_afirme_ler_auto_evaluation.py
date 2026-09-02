# -*- coding: utf-8 -*-
from app.afirme_ler.services.auto_evaluation.align import align_tokens
from app.afirme_ler.services.auto_evaluation.levenshtein import (
    levenshtein_distance,
    similarity,
)
from app.afirme_ler.services.auto_evaluation.metrics import (
    calculate_accuracy,
    calculate_ica,
    calculate_plcm,
    evaluate_reading,
    fluency_level_2nd_grade,
    fluency_score_for_ica,
    precision_level,
)
from app.afirme_ler.services.auto_evaluation.normalize import normalize_text, tokenize
from app.afirme_ler.services.auto_evaluation.phonetic import to_phonetic


def test_normalize_removes_accents_and_punct():
    assert normalize_text("Olá, mundo!") == "ola mundo"
    assert tokenize("Casa, bola; MESA") == ["casa", "bola", "mesa"]


def test_phonetic_common_ptbr():
    assert to_phonetic("açúcar") == to_phonetic("assucar")
    assert to_phonetic("queijo").startswith("k")
    assert to_phonetic("chave").startswith("x")


def test_levenshtein_and_similarity():
    assert levenshtein_distance("casa", "casa") == 0
    assert levenshtein_distance("casa", "caza") == 1
    assert similarity("casa", "casa") == 1.0
    assert similarity("casa", "caza") >= 0.75


def test_align_correct_and_error():
    result = align_tokens(
        ["casa", "bola", "mesa"],
        ["casa", "bola", "mesa"],
        window=4,
    )
    assert result.correct_count == 3
    assert result.errors_count == 0

    result_err = align_tokens(
        ["casa", "bola", "mesa"],
        ["casa", "pato", "mesa"],
        window=4,
    )
    assert result_err.errors_count >= 1


def test_plcm_and_accuracy_formulas():
    # words=120, errors=8, time=90s → correct=112 → accuracy=93.33, plcm=74.67
    assert calculate_accuracy(120, 8) == 93.33
    assert calculate_plcm(120, 8, 90) == 74.67


def test_precision_and_fluency_levels():
    assert precision_level(95) == "Independente"
    assert precision_level(90) == "Instrucional"
    assert precision_level(89.9) == "Frustração"
    assert fluency_level_2nd_grade(39.9) == "abaixo"
    assert fluency_level_2nd_grade(40) == "esperado"
    assert fluency_level_2nd_grade(60) == "esperado"
    assert fluency_level_2nd_grade(60.1) == "acima"


def test_ica_formula():
    assert fluency_score_for_ica(60) == 100.0
    assert fluency_score_for_ica(30) == 50.0
    ica = calculate_ica(
        accuracy_lista1=100,
        accuracy_lista2=100,
        accuracy_texto=100,
        comprehension=100,
        plcm=60,
    )
    assert ica is not None
    assert ica["icaScore"] == 100.0

    incomplete = calculate_ica(
        accuracy_lista1=100,
        accuracy_lista2=None,
        accuracy_texto=100,
        comprehension=100,
        plcm=60,
    )
    assert incomplete is None


def test_evaluate_reading_end_to_end():
    metrics = evaluate_reading(
        ["o", "gato", "correu"],
        "o gato correu",
        part="text",
        duration_seconds=60,
        content_kind="text",
    )
    assert metrics.accuracy == 100.0
    assert metrics.plcm == 3.0
    assert metrics.precision_level == "Independente"
