"""Período (YYYY-MM) só na busca de instrumentos; dados agregados ignoram o mês."""
import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.routes.answer_sheet_routes import (
    _apply_answer_sheet_result_period_filter,
    _parse_cartao_periodo_bounds,
    _periodo_bounds_dados_cartao,
)
from app.routes.evaluation_results_routes import (
    _filtrar_alunos_mapa_digital_por_periodo_aplicacao,
    _parse_periodo_bounds,
    _periodo_bounds_dados_digital,
)


class TestPeriodoFilterResults(unittest.TestCase):
    def test_periodo_bounds_dados_cartao_sempre_none(self):
        self.assertIsNone(_periodo_bounds_dados_cartao())

    def test_periodo_bounds_dados_digital_sempre_none(self):
        self.assertIsNone(_periodo_bounds_dados_digital())

    def test_apply_answer_sheet_result_period_filter_sem_bounds_nao_altera_query(self):
        query = MagicMock()
        self.assertIs(_apply_answer_sheet_result_period_filter(query, None), query)
        query.filter.assert_not_called()

    def test_apply_answer_sheet_result_period_filter_com_bounds_filtra(self):
        query = MagicMock()
        filtered = MagicMock()
        query.filter.return_value = filtered
        bounds = _parse_cartao_periodo_bounds("2026-05")
        result = _apply_answer_sheet_result_period_filter(query, bounds)
        self.assertIs(result, filtered)
        query.filter.assert_called_once()

    def test_filtrar_alunos_mapa_digital_ignora_periodo(self):
        students = [
            SimpleNamespace(id="s1", class_id="c1"),
            SimpleNamespace(id="s2", class_id="c2"),
        ]
        bounds = _parse_periodo_bounds("2026-06")
        out = _filtrar_alunos_mapa_digital_por_periodo_aplicacao(students, "av-1", bounds)
        self.assertIs(out, students)
        self.assertEqual(len(out), 2)

    def test_parse_periodo_bounds_maio_junho_distintos(self):
        maio = _parse_cartao_periodo_bounds("2026-05")
        junho = _parse_cartao_periodo_bounds("2026-06")
        self.assertEqual(maio[0], datetime(2026, 5, 1))
        self.assertEqual(maio[1], datetime(2026, 5, 31))
        self.assertEqual(junho[0], datetime(2026, 6, 1))
        self.assertEqual(junho[1], datetime(2026, 6, 30))


if __name__ == "__main__":
    unittest.main()
