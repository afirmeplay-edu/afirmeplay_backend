# -*- coding: utf-8 -*-
"""Curso por série e ordem estável no Relatório Geral (consolidado)."""

from app.reports.services.consolidated_report_service import (
    _annotate_proficiency_level_labels,
    _course_name_for_serie,
    _order_rows_by_requested_ids,
    _unique_course_names_from_series_colunas,
)
from app.evaluations.services.evaluation_calculator import EvaluationCalculator


def test_course_name_for_serie_iniciais_vs_finais():
    assert _course_name_for_serie("5º Ano") == "Anos Iniciais"
    assert _course_name_for_serie("9º Ano") == "Anos Finais"
    assert _course_name_for_serie("Suporte 1 9º Ano") == "Anos Finais"


def test_order_rows_by_requested_ids_is_stable():
    rows = [type("T", (), {"id": "b"})(), type("T", (), {"id": "a"})()]
    ordered = _order_rows_by_requested_ids(rows, ["a", "b"], lambda x: x.id)
    assert [r.id for r in ordered] == ["a", "b"]


def test_unique_courses_detects_mixed_scales():
    cols = [
        {"serie_id": "1", "serie_nome": "5º Ano"},
        {"serie_id": "2", "serie_nome": "9º Ano"},
    ]
    assert _unique_course_names_from_series_colunas(cols) == [
        "Anos Iniciais",
        "Anos Finais",
    ]


def test_annotate_niveis_por_serie_uses_per_serie_scale():
    cols = [
        {"serie_id": "1", "serie_nome": "5º Ano"},
        {"serie_id": "2", "serie_nome": "9º Ano"},
    ]
    # 200: Adequado em Iniciais Outras; Básico em Finais Outras
    m = {
        "linhas": [
            {
                "escola_id": "e",
                "escola_nome": "E",
                "valores_por_serie": [200.0, 200.0],
                "taxa_geral_escola": 200.0,
            }
        ],
        "medias_da_rede": {"por_serie": [200.0, 200.0], "taxa_geral": 200.0},
    }
    _annotate_proficiency_level_labels(
        m, cols, subject_name="GERAL", has_matematica=False
    )
    niveis = m["linhas"][0]["niveis_por_serie"]
    assert niveis[0] == EvaluationCalculator.determine_classification(
        200.0, "Anos Iniciais", "GERAL", has_matematica=False
    )
    assert niveis[1] == EvaluationCalculator.determine_classification(
        200.0, "Anos Finais", "GERAL", has_matematica=False
    )
    assert niveis[0] != niveis[1]
    # Média geral misturando cursos → sem nível único
    assert m["medias_da_rede"]["nivel_media_geral"] is None
    assert m["linhas"][0]["nivel_media_escola"] is None


def test_grade_formula_differs_by_serie_course():
    """Mesma proficiência → notas diferentes em Iniciais vs Finais (bug do 5º em finais)."""
    prof = 264.7
    nota_iniciais = EvaluationCalculator.calculate_grade(
        prof, "Anos Iniciais", "GERAL", has_matematica=False
    )
    nota_finais = EvaluationCalculator.calculate_grade(
        prof, "Anos Finais", "GERAL", has_matematica=False
    )
    assert nota_iniciais != nota_finais
    assert _course_name_for_serie("9º Ano") == "Anos Finais"
