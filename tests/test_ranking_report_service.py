import unittest
from unittest.mock import patch

from app.services.ranking_report_service import RankingReportService
from app.routes.ranking_routes import parse_ranking_request_args, validate_ranking_filters


class FakeArgs(dict):
    def get(self, key, default=None):
        return super().get(key, default)


class TestRankingReportService(unittest.TestCase):
    def test_build_request_rejects_invalid_ranking_type(self):
        with self.assertRaisesRegex(ValueError, "ranking_type inválido"):
            RankingReportService.build_request("foo")

    def test_build_request_accepts_valid_types(self):
        for rt in ("general", "specific_evaluation", "specific_answer_sheet", "teachers"):
            req = RankingReportService.build_request(rt, page=1, per_page=10, filters={})
            self.assertEqual(req.ranking_type, rt)

    def test_specific_evaluation_requires_evaluation_id(self):
        req = RankingReportService.build_request("specific_evaluation", filters={})
        with patch.object(RankingReportService, "_resolve_scope", return_value={"scope": "municipio"}):
            with self.assertRaisesRegex(ValueError, "evaluation_id"):
                RankingReportService.get_report({"role": "admin"}, req)

    def test_specific_answer_sheet_requires_answer_sheet_id(self):
        req = RankingReportService.build_request("specific_answer_sheet", filters={})
        with patch.object(RankingReportService, "_resolve_scope", return_value={"scope": "municipio"}):
            with self.assertRaisesRegex(ValueError, "answer_sheet_id"):
                RankingReportService.get_report({"role": "admin"}, req)

    def test_dispatches_general(self):
        req = RankingReportService.build_request("general", filters={})
        fake_payload = {"ranking_type": "general", "items": []}
        with patch.object(RankingReportService, "_resolve_scope", return_value={"scope": "municipio"}):
            with patch.object(RankingReportService, "_general_ranking", return_value=fake_payload) as general_mock:
                payload = RankingReportService.get_report({"role": "admin"}, req)
        general_mock.assert_called_once()
        self.assertEqual(payload, fake_payload)

    def test_dispatches_teachers(self):
        req = RankingReportService.build_request("teachers", filters={})
        fake_payload = {"ranking_type": "teachers", "items": []}
        with patch.object(RankingReportService, "_resolve_scope", return_value={"scope": "escola"}):
            with patch.object(RankingReportService, "_teacher_ranking", return_value=fake_payload) as teacher_mock:
                payload = RankingReportService.get_report({"role": "diretor"}, req)
        teacher_mock.assert_called_once()
        self.assertEqual(payload, fake_payload)

    def test_general_ranking_uses_page_offset(self):
        req = RankingReportService.build_request("general", page=2, per_page=10, filters={})
        with patch.object(RankingReportService, "_resolve_scope", return_value={"scope": "municipio"}):
            with patch.object(
                RankingReportService,
                "_build_school_general_rows",
                return_value=[
                    {
                        "school_id": "s1",
                        "school_name": "Escola 1",
                        "average_score": 7.1,
                        "average_proficiency": 260.4,
                        "classification": "Básico",
                        "students_count": 20,
                        "total_students": 25,
                        "participating_students": 15,
                        "participation_rate": 60.0,
                        "series": [
                            {
                                "grade_id": "g1",
                                "grade_name": "1º Ano",
                                "average_score": 7.1,
                                "average_proficiency": 260.4,
                                "classification": "Básico",
                                "students_count": 20,
                                "total_students": 25,
                                "participating_students": 15,
                            }
                        ],
                    }
                ],
            ):
                with patch("app.services.ranking_report_service.DashboardService.get_school_ranking_card") as school_card_mock:
                    with patch("app.services.ranking_report_service.DashboardService.get_class_ranking_card") as class_mock:
                        with patch("app.services.ranking_report_service.DashboardService.get_ranking_alunos") as ranking_mock:
                            school_card_mock.return_value = {"ranking": [], "total": 0}
                            class_mock.return_value = {"ranking": [], "total": 0}
                            ranking_mock.return_value = {"ranking": [], "total": 123}
                            payload = RankingReportService.get_report({"role": "admin"}, req)
        ranking_mock.assert_called_once_with({"scope": "municipio"}, limit=500, offset=0, filters={})
        self.assertEqual(payload["totals"]["count"], 1)
        self.assertIn("general_rankings", payload)
        self.assertIn("visibility", payload["general_rankings"])
        self.assertEqual(payload["general_rankings"]["visibility"]["schools_by_course"], True)
        self.assertEqual(payload["general_rankings"]["visibility"]["students_by_course"], True)
        self.assertEqual(payload["students_totals"]["count"], 123)


class TestRankingRoutesParse(unittest.TestCase):
    def test_parse_defaults(self):
        ranking_type, page, per_page, filters = parse_ranking_request_args(FakeArgs())
        self.assertEqual(ranking_type, "general")
        self.assertEqual(page, 1)
        self.assertEqual(per_page, 20)
        self.assertIsNone(filters["evaluation_id"])
        self.assertIsNone(filters["avaliacao"])

    def test_parse_explicit_values(self):
        args = FakeArgs(
            ranking_type="specific_evaluation",
            page="2",
            per_page="30",
            municipio="city-1",
            avaliacao="eval-1",
        )
        ranking_type, page, per_page, filters = parse_ranking_request_args(args)
        self.assertEqual(ranking_type, "specific_evaluation")
        self.assertEqual(page, 2)
        self.assertEqual(per_page, 30)
        self.assertEqual(filters["municipio"], "city-1")
        self.assertEqual(filters["evaluation_id"], "eval-1")

    def test_parse_preserves_legacy_evaluation_id(self):
        args = FakeArgs(ranking_type="specific_evaluation", evaluation_id="eval-legacy")
        _, _, _, filters = parse_ranking_request_args(args)
        self.assertEqual(filters["evaluation_id"], "eval-legacy")

    def test_parse_answer_sheet_uses_avaliacao_or_gabarito(self):
        args = FakeArgs(ranking_type="specific_answer_sheet", avaliacao="gab-1")
        _, _, _, filters = parse_ranking_request_args(args)
        self.assertEqual(filters["answer_sheet_id"], "gab-1")

        args = FakeArgs(ranking_type="specific_answer_sheet", gabarito_id="gab-2")
        _, _, _, filters = parse_ranking_request_args(args)
        self.assertEqual(filters["answer_sheet_id"], "gab-2")

    def test_parse_ignores_all_values(self):
        args = FakeArgs(estado="all", municipio="all", escola="all", avaliacao="all")
        _, _, _, filters = parse_ranking_request_args(args)
        self.assertIsNone(filters["estado"])
        self.assertIsNone(filters["municipio"])
        self.assertIsNone(filters["escola"])
        self.assertIsNone(filters["avaliacao"])


class TestRankingRoutesValidation(unittest.TestCase):
    def test_requires_estado(self):
        with self.assertRaisesRegex(ValueError, "Estado é obrigatório"):
            validate_ranking_filters("general", {"municipio": "city-1"})

    def test_requires_municipio(self):
        with self.assertRaisesRegex(ValueError, "Município é obrigatório"):
            validate_ranking_filters("general", {"estado": "AL"})

    def test_specific_evaluation_requires_selected_avaliacao(self):
        with self.assertRaisesRegex(ValueError, "Selecione uma avaliação"):
            validate_ranking_filters(
                "specific_evaluation",
                {"estado": "AL", "municipio": "city-1", "evaluation_id": None},
            )

    def test_specific_answer_sheet_requires_selected_avaliacao(self):
        with self.assertRaisesRegex(ValueError, "Selecione um cartão resposta"):
            validate_ranking_filters(
                "specific_answer_sheet",
                {"estado": "AL", "municipio": "city-1", "answer_sheet_id": None},
            )


if __name__ == "__main__":
    unittest.main()
