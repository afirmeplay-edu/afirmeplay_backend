# -*- coding: utf-8 -*-
import unittest
from types import SimpleNamespace

from app.services.evolution_groups_service import (
    _build_grade_by_recorte,
    _resultados_para_geral_do_relatorio,
)

PORT = "portugues"
MAT = "matematica"


def _aluno(student_id, subjects, completo):
    stored = {
        key: {"subject_name": name, "grade": grade, "proficiency": prof}
        for key, name, grade, prof in subjects
    }
    return SimpleNamespace(
        student_id=student_id,
        subject_results=stored,
        completo=completo,
        grade=1,
        proficiency=1,
    )


class EvolutionGroupsGeralTest(unittest.TestCase):
    def test_so_uma_disciplina_entra_no_geral(self):
        parciais = [
            _aluno("a", [(PORT, "Português", 6.0, 200)], completo=False),
            _aluno("b", [(PORT, "Português", 7.0, 220)], completo=False),
        ]
        kept = _resultados_para_geral_do_relatorio(parciais)
        self.assertEqual([item.student_id for item in kept], ["a", "b"])

    def test_duas_disciplinas_so_quem_fez_as_duas(self):
        rows = [
            _aluno(
                "completo",
                [(PORT, "Português", 6.0, 200), (MAT, "Matemática", 8.0, 240)],
                completo=True,
            ),
            _aluno("so_lp", [(PORT, "Português", 5.0, 180)], completo=False),
            _aluno("so_mat", [(MAT, "Matemática", 9.0, 260)], completo=False),
        ]
        kept = _resultados_para_geral_do_relatorio(rows)
        self.assertEqual([item.student_id for item in kept], ["completo"])

    def test_resultado_sem_flag_de_par_nao_e_cortado(self):
        cru = SimpleNamespace(student_id="legado", subject_results={})
        self.assertEqual(_resultados_para_geral_do_relatorio([cru]), [cru])

    def test_recorte_so_traz_geral(self):
        points = [
            {"evaluation_id": "p1", "order": 1, "average_grade": 6.28},
            {"evaluation_id": "p2", "order": 2, "average_grade": 5.96},
        ]
        recortes = _build_grade_by_recorte(points)
        self.assertEqual(len(recortes), 1)
        self.assertEqual(recortes[0]["recorte"], "Geral")
        self.assertTrue(recortes[0]["is_geral"])
        self.assertIsNone(recortes[0]["subject_id"])
        self.assertEqual(
            [item["average_grade"] for item in recortes[0]["values"]],
            [6.28, 5.96],
        )
        self.assertEqual(recortes[0]["transitions"][0]["evolution"]["direction"], "decrease")


if __name__ == "__main__":
    unittest.main()
