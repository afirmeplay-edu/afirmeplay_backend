# -*- coding: utf-8 -*-
"""Participação do cartão: matrícula no denominador, corrigidos no numerador."""
import unittest

from app.routes.answer_sheet_routes import (
    _aluno_ausente_cartao,
    _build_disciplina_rows_from_cartao_results,
    _calcular_dados_gerais_alunos_cartao,
    _montar_lista_ausentes_cartao,
    _participacao_matricula_cartao,
)


class TestParticipacaoMatriculaCartao(unittest.TestCase):
    def test_separa_quem_fez_e_quem_nao_fez(self):
        campos = _participacao_matricula_cartao(499, 584)

        self.assertEqual(campos["alunos_participantes"], 499)
        self.assertEqual(campos["total_alunos"], 584)
        self.assertEqual(campos["alunos_ausentes"], 85)
        self.assertEqual(campos["alunos_pendentes"], 85)
        self.assertEqual(campos["percentual_comparecimento"], 85.45)

    def test_matricula_menor_que_participantes_nao_vira_negativo(self):
        campos = _participacao_matricula_cartao(10, 8)

        self.assertEqual(campos["total_alunos"], 10)
        self.assertEqual(campos["alunos_ausentes"], 0)
        self.assertEqual(campos["percentual_comparecimento"], 100.0)

    def test_disciplina_nao_forca_cem_por_cento(self):
        from types import SimpleNamespace
        from unittest.mock import patch

        gabarito = SimpleNamespace(
            blocks_config=None,
            grades=[{"id": "g1", "name": "1º Ano"}],
            grade_id="g1",
            grade_name="1º Ano",
        )
        result = SimpleNamespace(
            student_id="a1",
            proficiency_by_subject={
                "mat": {
                    "subject_name": "Matemática",
                    "grade": 7.0,
                    "proficiency": 250.0,
                    "classification": "Adequado",
                    "absent": False,
                }
            },
            detected_answers={},
            class_id_snapshot=None,
            school_id_snapshot=None,
            grade_id_snapshot=None,
        )

        with patch(
            "app.services.cartao_resposta.gabarito_grades.course_meta_for_gabarito_serie",
            return_value=("Anos Iniciais", "1º Ano", "g1"),
        ), patch(
            "app.utils.school_equal_weight_means.hierarchical_mean_from_subject_rows",
            return_value=(7.0, 250.0, 0.0),
        ):
            rows = _build_disciplina_rows_from_cartao_results(
                [result],
                total_alunos=10,
                gabarito=gabarito,
                aggregation_level="municipio",
            )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["alunos_participantes"], 1)
        self.assertEqual(rows[0]["total_alunos"], 10)
        self.assertEqual(rows[0]["alunos_ausentes"], 9)
        self.assertEqual(rows[0]["percentual_comparecimento"], 10.0)

    def test_tabela_geral_marca_faltoso_como_pendente(self):
        disciplinas = [
            {
                "nome": "Matemática",
                "alunos": [
                    {
                        "id": "fez",
                        "nome": "Fez",
                        "escola": "E1",
                        "serie": "1º",
                        "turma": "A",
                        "nota": 7.0,
                        "proficiencia": 250.0,
                        "status": "concluida",
                        "total_acertos": 5,
                        "total_questoes_disciplina": 10,
                        "total_respondidas": 10,
                        "respostas_por_questao": [],
                    },
                    {
                        "id": "faltou",
                        "nome": "Faltou",
                        "escola": "E1",
                        "serie": "1º",
                        "turma": "A",
                        "nota": None,
                        "proficiencia": None,
                        "status": "pendente",
                        "total_acertos": 0,
                        "total_questoes_disciplina": 10,
                        "total_respondidas": 0,
                        "respostas_por_questao": [],
                    },
                ],
            }
        ]

        gerais = _calcular_dados_gerais_alunos_cartao(
            disciplinas, "1º Ano", student_ids_com_resultado={"fez"}
        )
        por_id = {a["id"]: a for a in gerais["alunos"]}

        self.assertEqual(por_id["fez"]["status_geral"], "concluida")
        self.assertEqual(por_id["faltou"]["status_geral"], "pendente")
        self.assertEqual(por_id["faltou"]["nome"], "Faltou")

    def test_aluno_sem_resultado_e_ausente(self):
        self.assertTrue(_aluno_ausente_cartao(False, [False, False]))

    def test_aluno_ausente_em_todas_disciplinas_e_ausente(self):
        self.assertTrue(_aluno_ausente_cartao(True, [True, True]))

    def test_aluno_ausente_so_em_uma_disciplina_continua_na_tabela(self):
        self.assertFalse(_aluno_ausente_cartao(True, [True, False]))

    def test_aluno_presente_nao_e_ausente(self):
        self.assertFalse(_aluno_ausente_cartao(True, [False]))

    def test_lista_ausentes_ordenada_por_escola_turma_nome(self):
        lista = _montar_lista_ausentes_cartao(
            [
                {"nome": "Bia", "turma": "B", "escola": "Escola Z"},
                {"nome": "Ana", "turma": "B", "escola": "Escola A"},
                {"nome": "Caio", "turma": "A", "escola": "Escola A"},
            ]
        )
        self.assertEqual([a["nome"] for a in lista], ["Caio", "Ana", "Bia"])


class TestResultadoAusenteEmTodasDisciplinas(unittest.TestCase):
    BLOCKS = {
        "blocks": [
            {"block_id": 1, "subject_id": "mat", "subject_name": "Matemática",
             "start_question": 1, "end_question": 2},
            {"block_id": 2, "subject_id": "port", "subject_name": "Português",
             "start_question": 3, "end_question": 4},
        ]
    }

    def _ausente(self, pbs, detected, blocks=None, fallback=None):
        from app.services.cartao_resposta.proficiency_by_subject import (
            result_absent_in_all_subjects,
        )

        return result_absent_in_all_subjects(
            pbs, detected, self.BLOCKS if blocks is None else blocks, fallback
        )

    def test_tudo_em_branco_e_ausente(self):
        detected = {"1": None, "2": None, "3": None, "4": None}
        self.assertTrue(self._ausente({}, detected))

    def test_ausente_marcado_nas_duas_disciplinas_e_ausente(self):
        pbs = {"mat": {"absent": True}, "port": {"status": "ausente"}}
        self.assertTrue(self._ausente(pbs, {"1": "A", "3": "B"}))

    def test_so_uma_disciplina_em_branco_nao_e_ausente(self):
        detected = {"1": None, "2": None, "3": "A", "4": None}
        self.assertFalse(self._ausente({}, detected))

    def test_aluno_com_respostas_nao_e_ausente(self):
        self.assertFalse(self._ausente({}, {"1": "A", "2": "B", "3": "C", "4": "D"}))

    def test_gabarito_sem_blocos_usa_questoes_do_gabarito(self):
        self.assertTrue(self._ausente({}, {"1": None, "2": None}, blocks={}, fallback=[1, 2]))
        self.assertFalse(self._ausente({}, {"1": "A", "2": None}, blocks={}, fallback=[1, 2]))

    def test_sem_nenhuma_informacao_nao_assume_ausente(self):
        self.assertFalse(self._ausente({}, None, blocks={}))

    def test_sem_respostas_gravadas_so_vale_ausente_marcado(self):
        self.assertFalse(self._ausente({"mat": {"proficiency": 200.0}}, None))
        pbs = {"mat": {"absent": True}, "port": {"absent": True}}
        self.assertTrue(self._ausente(pbs, None))


if __name__ == "__main__":
    unittest.main()
