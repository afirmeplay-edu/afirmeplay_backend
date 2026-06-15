import unittest
from unittest.mock import MagicMock, patch

from app.routes.evaluation_results_routes import (
    _calcular_dados_gerais_alunos,
    _collect_participating_student_ids,
)


class TestEvaluationResultsParticipation(unittest.TestCase):
    def test_collect_participants_uses_only_evaluation_results(self):
        participants = _collect_participating_student_ids(
            test_id="test-1",
            student_ids=["s1", "s2"],
            results_dict={"s1": {"grade": 8.0}},
            respostas_por_aluno={"s2": {"q1": {"answer": "A"}}},
        )

        self.assertEqual(participants, {"s1"})

    def test_collect_participants_fallbacks_to_persisted_results_query(self):
        mock_all = MagicMock(return_value=[("s9",), ("s10",)])
        mock_distinct = MagicMock(return_value=MagicMock(all=mock_all))
        mock_filter = MagicMock(return_value=MagicMock(distinct=mock_distinct))
        mock_query = MagicMock(return_value=MagicMock(filter=mock_filter))

        with patch("app.routes.evaluation_results_routes.db.session.query", mock_query):
            participants = _collect_participating_student_ids(
                test_id="test-2",
                student_ids=["s9", "s10", "s11"],
                results_dict=None,
                respostas_por_aluno={"s11": {"q1": {"answer": "B"}}},
            )

        self.assertEqual(participants, {"s9", "s10"})

    def test_calcular_dados_gerais_preserva_escola_id(self):
        questoes_por_disciplina = {
            "matematica": {
                "alunos": [
                    {
                        "id": "aluno-1",
                        "nome": "Aluno 1",
                        "escola_id": "escola-a",
                        "escola": "Escola A",
                        "serie": "5º Ano",
                        "turma": "Turma 1",
                        "nota": 8.5,
                        "proficiencia": 245.0,
                        "total_acertos": 17,
                        "total_respondidas": 20,
                        "total_questoes_disciplina": 20,
                    }
                ]
            }
        }

        result = _calcular_dados_gerais_alunos(questoes_por_disciplina, "Anos Iniciais")
        self.assertEqual(len(result["alunos"]), 1)
        self.assertEqual(result["alunos"][0]["escola_id"], "escola-a")
        self.assertEqual(result["alunos"][0]["escola"], "Escola A")

    def test_calcular_dados_gerais_usa_evaluation_result_grade(self):
        questoes_por_disciplina = {
            "matematica": {
                "alunos": [
                    {
                        "id": "aluno-1",
                        "nome": "Aluno 1",
                        "escola_id": "escola-a",
                        "escola": "Escola A",
                        "serie": "9º Ano",
                        "turma": "A",
                        "nota": 2.66,
                        "proficiencia": 179.81,
                        "total_acertos": 11,
                        "total_respondidas": 26,
                        "total_questoes_disciplina": 26,
                    }
                ]
            },
            "portugues": {
                "alunos": [
                    {
                        "id": "aluno-1",
                        "nome": "Aluno 1",
                        "escola_id": "escola-a",
                        "escola": "Escola A",
                        "serie": "9º Ano",
                        "turma": "A",
                        "nota": 5.90,
                        "proficiencia": 276.93,
                        "total_acertos": 18,
                        "total_respondidas": 26,
                        "total_questoes_disciplina": 26,
                    }
                ]
            },
        }
        evaluation_result = MagicMock(
            grade=4.28,
            proficiency=228.37,
            classification="Básico",
        )
        results_dict = {"aluno-1": evaluation_result}

        result = _calcular_dados_gerais_alunos(
            questoes_por_disciplina, "Anos Finais", results_dict
        )

        aluno = result["alunos"][0]
        self.assertEqual(aluno["nota_geral"], 4.28)
        self.assertEqual(aluno["proficiencia_geral"], 228.37)
        self.assertEqual(aluno["nivel_proficiencia_geral"], "Básico")
        self.assertEqual(aluno["total_acertos_geral"], 29)
        self.assertEqual(aluno["total_questoes_geral"], 52)


if __name__ == "__main__":
    unittest.main()
