import unittest
from unittest.mock import MagicMock, patch

from app.services.folha_rascunho_service import (
    FolhaRascunhoService,
    FolhaRascunhoValidationError,
    _count_covers,
    _count_totals,
    _parse_filters,
    _tree_to_response,
)


class TestFolhaRascunhoService(unittest.TestCase):
    def test_parse_filters_rejects_invalid_modo(self):
        with self.assertRaises(FolhaRascunhoValidationError) as ctx:
            _parse_filters({"modo": "invalido", "municipio": "city-1"})
        self.assertIn("modo", ctx.exception.message)

    def test_parse_filters_requires_municipio(self):
        with self.assertRaises(FolhaRascunhoValidationError) as ctx:
            _parse_filters({"modo": "personalizada"})
        self.assertIn("município", ctx.exception.message.lower())

    def test_parse_filters_personalizada_requires_escola(self):
        with self.assertRaises(FolhaRascunhoValidationError) as ctx:
            _parse_filters({"modo": "personalizada", "municipio": "city-1"})
        self.assertIn("escola", ctx.exception.message.lower())

    def test_parse_filters_avaliacao_requires_evaluation_id(self):
        with self.assertRaises(FolhaRascunhoValidationError) as ctx:
            _parse_filters({"modo": "avaliacao", "municipio": "city-1"})
        self.assertIn("avaliação", ctx.exception.message.lower())

    def test_parse_filters_cartao_requires_answer_sheet_id(self):
        with self.assertRaises(FolhaRascunhoValidationError) as ctx:
            _parse_filters({"modo": "cartao_resposta", "municipio": "city-1"})
        self.assertIn("cartão", ctx.exception.message.lower())

    def test_parse_filters_accepts_valid_personalizada(self):
        parsed = _parse_filters(
            {
                "modo": "personalizada",
                "municipio": "city-1",
                "escola": "school-1",
                "serie": "grade-1",
                "turma": "class-1",
            }
        )
        self.assertEqual(parsed["modo"], "personalizada")
        self.assertEqual(parsed["municipio"], "city-1")
        self.assertEqual(parsed["escola"], "school-1")
        self.assertEqual(parsed["serie"], "grade-1")
        self.assertEqual(parsed["turma"], "class-1")

    def test_tree_to_response_sorts_hierarchy(self):
        tree = {
            "s2": {
                "id": "s2",
                "name": "Escola B",
                "_series": {
                    "g1": {
                        "id": "g1",
                        "name": "2º Ano",
                        "_classes": {
                            "c1": {
                                "id": "c1",
                                "name": "Turma A",
                                "turno": "Manhã",
                                "students": [{"id": "1", "name": "Ana"}],
                            }
                        },
                    }
                },
            },
            "s1": {
                "id": "s1",
                "name": "Escola A",
                "_series": {
                    "g1": {
                        "id": "g1",
                        "name": "1º Ano",
                        "_classes": {
                            "c2": {
                                "id": "c2",
                                "name": "Turma B",
                                "turno": "",
                                "students": [{"id": "2", "name": "Bruno"}],
                            }
                        },
                    }
                },
            },
        }
        escolas = _tree_to_response(tree)
        self.assertEqual([e["name"] for e in escolas], ["Escola A", "Escola B"])
        self.assertEqual(escolas[0]["series"][0]["classes"][0]["name"], "Turma B")

    def test_count_covers_multiple_levels(self):
        escolas = [
            {
                "series": [
                    {
                        "classes": [
                            {"students": [{"id": "1", "name": "A"}]},
                            {"students": [{"id": "2", "name": "B"}]},
                        ]
                    },
                    {
                        "classes": [
                            {"students": [{"id": "3", "name": "C"}]},
                        ]
                    },
                ]
            },
            {
                "series": [
                    {
                        "classes": [
                            {"students": [{"id": "4", "name": "D"}]},
                        ]
                    }
                ]
            },
        ]
        self.assertEqual(_count_covers(escolas), 6)

    def test_count_totals_includes_pages(self):
        escolas = [
            {
                "series": [
                    {
                        "classes": [
                            {"students": [{"id": "1", "name": "A"}, {"id": "2", "name": "B"}]},
                        ]
                    }
                ]
            }
        ]
        totals = _count_totals(escolas)
        self.assertEqual(totals["students"], 2)
        self.assertEqual(totals["pages"], totals["covers"] + 2)

    @patch("app.services.folha_rascunho_service.City")
    @patch("app.services.folha_rascunho_service._collect_personalizada")
    def test_get_dados_personalizada(self, collect_mock, city_mock):
        city = MagicMock()
        city.id = "city-1"
        city.name = "Cidade Teste"
        city.state = "SP"
        city_mock.query.get.return_value = city

        collect_mock.return_value = {
            "school-1": {
                "id": "school-1",
                "name": "Escola 1",
                "_series": {
                    "g1": {
                        "id": "g1",
                        "name": "1º Ano",
                        "_classes": {
                            "c1": {
                                "id": "c1",
                                "name": "Turma A",
                                "turno": "Manhã",
                                "students": [{"id": "st1", "name": "Aluno Um"}],
                            }
                        },
                    }
                },
            }
        }

        payload = FolhaRascunhoService.get_dados(
            {"id": "u1", "role": "admin"},
            {"modo": "personalizada", "municipio": "city-1", "escola": "school-1"},
        )
        self.assertEqual(payload["modo"], "personalizada")
        self.assertEqual(payload["municipio"]["prefeitura_label"], "PREFEITURA MUNICIPAL DE CIDADE TESTE")
        self.assertEqual(len(payload["escolas"]), 1)
        self.assertEqual(payload["totals"]["students"], 1)

    @patch("app.services.folha_rascunho_service.City")
    @patch("app.services.folha_rascunho_service._collect_personalizada")
    def test_get_dados_empty_raises(self, collect_mock, city_mock):
        city_mock.query.get.return_value = MagicMock(id="city-1", name="X", state="SP")
        collect_mock.return_value = {}
        with self.assertRaises(FolhaRascunhoValidationError) as ctx:
            FolhaRascunhoService.get_dados(
                {"id": "u1", "role": "admin"},
                {"modo": "personalizada", "municipio": "city-1", "escola": "school-1"},
            )
        self.assertIn("Nenhum aluno", ctx.exception.message)


if __name__ == "__main__":
    unittest.main()
