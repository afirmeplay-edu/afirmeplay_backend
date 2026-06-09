"""Testes para helpers de rótulo de turma/série/turno."""

from app.utils.class_label_helpers import (
    class_filter_option,
    format_grade_class_label,
    format_serie_turno_label,
    format_turma_display_name,
    normalize_shift,
)


def test_normalize_shift():
    assert normalize_shift(None) is None
    assert normalize_shift("") is None
    assert normalize_shift("  Manhã  ") == "Manhã"


def test_format_grade_class_label_without_shift():
    assert format_grade_class_label("6º ano", "A") == "6º ano - A"
    assert format_grade_class_label("6º ano", "A", "Manhã") == "6º ano - A"
    assert (
        format_grade_class_label("6º ano", "A", "Manhã", include_shift=True)
        == "6º ano - A (Manhã)"
    )


def test_format_serie_turno_label():
    assert format_serie_turno_label("6º ano", "A", "Tarde") == "6º ano - A (Tarde)"


def test_class_filter_option():
    assert class_filter_option("uuid-1", "A", "Manhã") == {
        "id": "uuid-1",
        "name": "A",
        "shift": "Manhã",
    }
    assert class_filter_option("uuid-2", None, None)["name"] == "Turma uuid-2"


def test_format_turma_display_name():
    assert format_turma_display_name("A", "Tarde") == "A — Tarde"
    assert format_turma_display_name("A", None) == "A"
