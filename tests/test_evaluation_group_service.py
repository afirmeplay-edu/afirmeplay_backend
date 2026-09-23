import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.services.evaluation_group_service import (
    GroupTestInfo,
    apply_test_id_filter,
    build_participacao,
    is_group_request,
    merge_student_group_results,
    parse_avaliacao_ids,
    validate_group_tests,
)


class TestEvaluationGroupParse(unittest.TestCase):
    def test_group_flag_accepts_common_truthy_values(self):
        for value in ("1", "true", "TRUE", "yes", "on"):
            self.assertTrue(is_group_request(value), value)
        for value in (None, "", "0", "false", "no"):
            self.assertFalse(is_group_request(value), value)

    def test_parse_avaliacao_ids(self):
        self.assertEqual(parse_avaliacao_ids("id-a,id-b,id-c"), ["id-a", "id-b", "id-c"])
        self.assertEqual(parse_avaliacao_ids("id-a"), ["id-a"])
        self.assertEqual(parse_avaliacao_ids("all"), [])
        self.assertEqual(parse_avaliacao_ids(None), [])
        self.assertEqual(parse_avaliacao_ids(" id-a , , id-b "), ["id-a", "id-b"])

    def test_apply_test_id_filter_single_and_many(self):
        calls = []

        class Query:
            def filter(self, expr):
                calls.append(expr)
                return self

        column = SimpleNamespace(in_=lambda ids: ("in", tuple(ids)))
        apply_test_id_filter(Query(), column, "somente-um")
        apply_test_id_filter(Query(), column, "a,b")
        apply_test_id_filter(Query(), column, ["x", "y"])
        self.assertEqual(len(calls), 3)


class TestEvaluationGroupValidation(unittest.TestCase):
    def test_requires_same_grade(self):
        infos = [
            GroupTestInfo("t1", "PT", "g1", "1º Ano", [{"id": "pt", "name": "Português"}]),
            GroupTestInfo("t2", "MAT", "g2", "2º Ano", [{"id": "mat", "name": "Matemática"}]),
        ]
        self.assertIn("mesma série", validate_group_tests(infos))

    def test_accepts_same_grade_two_or_more(self):
        infos = [
            GroupTestInfo("t1", "PT", "g1", "1º Ano", [{"id": "pt", "name": "Português"}]),
            GroupTestInfo("t2", "MAT", "g1", "1º Ano", [{"id": "mat", "name": "Matemática"}]),
            GroupTestInfo("t3", "CIE", "g1", "1º Ano", [{"id": "cie", "name": "Ciências"}]),
        ]
        self.assertIsNone(validate_group_tests(infos))

    def test_rejects_duplicate_subject(self):
        infos = [
            GroupTestInfo("t1", "PT A", "g1", "1º Ano", [{"id": "pt", "name": "Português"}]),
            GroupTestInfo("t2", "PT B", "g1", "1º Ano", [{"id": "pt", "name": "Português"}]),
        ]
        self.assertIn("repetir a disciplina", validate_group_tests(infos))

    def test_rejects_missing_grade(self):
        infos = [
            GroupTestInfo("t1", "PT", None, "", [{"id": "pt", "name": "Português"}]),
            GroupTestInfo("t2", "MAT", None, "", [{"id": "mat", "name": "Matemática"}]),
        ]
        self.assertIn("série cadastrada", validate_group_tests(infos))


class TestEvaluationGroupMerge(unittest.TestCase):
    def _infos(self):
        return [
            GroupTestInfo("t-pt", "1º Ano - Português", "g1", "1º Ano", [{"id": "pt", "name": "Português"}]),
            GroupTestInfo("t-mat", "1º Ano - Matemática", "g1", "1º Ano", [{"id": "mat", "name": "Matemática"}]),
        ]

    def test_complete_student_averages_subjects(self):
        results = [
            SimpleNamespace(
                student_id="aluno-1",
                test_id="t-pt",
                grade=6.0,
                proficiency=200.0,
                classification="Básico",
                correct_answers=10,
                total_questions=20,
                subject_results={
                    "pt": {
                        "subject_name": "Português",
                        "grade": 6.0,
                        "proficiency": 200.0,
                        "classification": "Básico",
                    }
                },
                school_id_snapshot="esc-1",
                class_id_snapshot=None,
                grade_id_snapshot=None,
                enrollment_id_snapshot=None,
            ),
            SimpleNamespace(
                student_id="aluno-1",
                test_id="t-mat",
                grade=8.0,
                proficiency=260.0,
                classification="Adequado",
                correct_answers=16,
                total_questions=20,
                subject_results={
                    "mat": {
                        "subject_name": "Matemática",
                        "grade": 8.0,
                        "proficiency": 260.0,
                        "classification": "Adequado",
                    }
                },
                school_id_snapshot="esc-1",
                class_id_snapshot=None,
                grade_id_snapshot=None,
                enrollment_id_snapshot=None,
            ),
        ]
        merged = merge_student_group_results(results, self._infos(), "Anos Iniciais")
        self.assertEqual(len(merged), 1)
        aluno = merged[0]
        self.assertTrue(aluno.completo)
        self.assertEqual(aluno.grade, 7.0)
        self.assertEqual(aluno.proficiency, 230.0)
        self.assertEqual(aluno.correct_answers, 26)
        self.assertEqual(aluno.participacao["provas_realizadas"], 2)
        self.assertTrue(aluno.participacao["completo"])

    def test_partial_student_stays_in_payload(self):
        results = [
            SimpleNamespace(
                student_id="aluno-2",
                test_id="t-pt",
                grade=5.0,
                proficiency=180.0,
                classification="Básico",
                correct_answers=8,
                total_questions=20,
                subject_results=None,
                school_id_snapshot="esc-1",
                class_id_snapshot=None,
                grade_id_snapshot=None,
                enrollment_id_snapshot=None,
            ),
        ]
        merged = merge_student_group_results(results, self._infos(), "Anos Iniciais")
        self.assertEqual(len(merged), 1)
        aluno = merged[0]
        self.assertFalse(aluno.completo)
        self.assertEqual(aluno.participacao["provas_realizadas"], 1)
        self.assertEqual(aluno.participacao["provas_grupo"], 2)
        self.assertEqual(aluno.grade, 5.0)
        provas = {p["test_id"]: p["realizou"] for p in aluno.participacao["provas"]}
        self.assertTrue(provas["t-pt"])
        self.assertFalse(provas["t-mat"])

    def test_build_participacao_lists_missing_tests(self):
        part = build_participacao(self._infos(), ["t-pt"])
        self.assertFalse(part["completo"])
        self.assertEqual(part["provas_realizadas"], 1)
        self.assertEqual(part["provas"][1]["disciplina"], "Matemática")
        self.assertFalse(part["provas"][1]["realizou"])


class TestDetalheHelpers(unittest.TestCase):
    def test_titulo_e_disciplina_do_grupo(self):
        from app.routes.evaluation_results_routes import (
            _disciplina_avaliacao_detalhe,
            _titulo_avaliacao_detalhe,
        )

        evaluation = SimpleNamespace(title="1º Ano - Português", subject_rel=SimpleNamespace(name="Português"))
        scope = {"grupo": {"disciplinas": ["Português", "Matemática"]}}
        self.assertEqual(_titulo_avaliacao_detalhe(evaluation, scope), "Português + Matemática")
        self.assertEqual(_disciplina_avaliacao_detalhe(evaluation, scope), "Português + Matemática")
        self.assertEqual(_titulo_avaliacao_detalhe(evaluation, {}), "1º Ano - Português")
        self.assertEqual(_disciplina_avaliacao_detalhe(evaluation, {}), "Português")

    def test_aluno_ausente_no_grupo_usa_contrato_multidisciplinar(self):
        from app.routes.evaluation_results_routes import _aluno_pendente_disciplina_grupo

        aluno = _aluno_pendente_disciplina_grupo(
            {"id": "a1", "nome": "Maria", "escola": "E", "serie": "1º Ano", "turma": "A"},
            {"questoes": [{"numero": 1}, {"numero": 2}]},
        )
        self.assertEqual(aluno["status"], "pendente")
        self.assertEqual(aluno["nota"], 0.0)
        self.assertEqual(aluno["proficiencia"], 0.0)
        self.assertEqual(len(aluno["respostas_por_questao"]), 2)
        self.assertFalse(aluno["respostas_por_questao"][0]["respondeu"])


class TestResolveEvaluationGroup(unittest.TestCase):
    @patch("app.services.evaluation_group_service.is_group_request", return_value=False)
    def test_without_flag_does_not_group(self, _flag):
        from app.services.evaluation_group_service import resolve_evaluation_group

        ctx, err = resolve_evaluation_group("a,b", None)
        self.assertIsNone(ctx)
        self.assertIsNone(err)


if __name__ == "__main__":
    unittest.main()
