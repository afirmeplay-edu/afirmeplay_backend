# -*- coding: utf-8 -*-
import unittest

from app.services.evolution_points_service import resolve_request_points


class EvolutionPointsParseTest(unittest.TestCase):
    def test_test_ids_planos_viram_um_ponto_cada(self):
        points, flat = resolve_request_points({"test_ids": ["a", "b", "c"]})
        self.assertEqual(points, [["a"], ["b"], ["c"]])
        self.assertEqual(flat, ["a", "b", "c"])

    def test_grupos_mesclados(self):
        points, flat = resolve_request_points(
            {"grupos": [["id1", "id2"], ["id3", "id4"]]}
        )
        self.assertEqual(points, [["id1", "id2"], ["id3", "id4"]])
        self.assertEqual(flat, ["id1", "id2", "id3", "id4"])

    def test_recusa_id_repetido_no_mesmo_grupo(self):
        with self.assertRaises(ValueError):
            resolve_request_points({"grupos": [["id1", "id1"], ["id2"]]})

    def test_recusa_menos_de_dois_pontos(self):
        with self.assertRaises(ValueError):
            resolve_request_points({"grupos": [["id1", "id2"]]})

    def test_recusa_mais_de_dez_pontos(self):
        grupos = [[f"id-{index}"] for index in range(11)]
        with self.assertRaises(ValueError):
            resolve_request_points({"grupos": grupos})


if __name__ == "__main__":
    unittest.main()
