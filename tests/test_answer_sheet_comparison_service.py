import unittest
from unittest.mock import MagicMock, patch

from app.routes.answer_sheet_routes import _parse_gabarito_ids_from_body
from app.services.answer_sheet_comparison_service import AnswerSheetComparisonService


class TestParseGabaritoIds(unittest.TestCase):
    def test_rejects_missing_field(self):
        ids, err = _parse_gabarito_ids_from_body({})
        self.assertIsNone(ids)
        self.assertIsNotNone(err)

    def test_rejects_single_id(self):
        ids, err = _parse_gabarito_ids_from_body({"gabarito_ids": ["a"]})
        self.assertIsNone(ids)

    def test_accepts_valid_list(self):
        ids, err = _parse_gabarito_ids_from_body({"gabarito_ids": ["a", "b"]})
        self.assertEqual(ids, ["a", "b"])
        self.assertIsNone(err)


class TestAnswerSheetGeneralComparison(unittest.TestCase):
    def test_general_comparison_averages(self):
        r1 = MagicMock(grade=6.0, proficiency=200.0, classification="Básico")
        r2 = MagicMock(grade=8.0, proficiency=250.0, classification="Adequado")
        r3 = MagicMock(grade=4.0, proficiency=150.0, classification="Abaixo do Básico")
        r4 = MagicMock(grade=6.0, proficiency=200.0, classification="Básico")

        out = AnswerSheetComparisonService._get_general_comparison([r1, r2], [r3, r4])

        self.assertEqual(out["average_grade"]["evaluation_1"], 7.0)
        self.assertEqual(out["average_grade"]["evaluation_2"], 5.0)
        self.assertEqual(out["average_proficiency"]["evaluation_1"], 225.0)
        self.assertEqual(out["total_students"]["evaluation_1"], 2)
        self.assertIn("evolution", out["average_grade"])
        self.assertEqual(out["classification_distribution"]["evaluation_1"]["Básico"], 1)


class TestAnswerSheetSubjectComparison(unittest.TestCase):
    def test_subject_comparison_from_proficiency_by_subject(self):
        gab_1 = MagicMock(blocks_config={"blocks": [{"subject_id": "mat", "subject_name": "Matemática", "start_question": 1, "end_question": 2}]})
        gab_2 = MagicMock(blocks_config={"blocks": [{"subject_id": "mat", "subject_name": "Matemática", "start_question": 1, "end_question": 2}]})

        res_1 = MagicMock(
            student_id="s1",
            proficiency_by_subject={
                "mat": {"grade": 6.0, "proficiency": 200.0, "classification": "Básico"}
            },
        )
        res_2 = MagicMock(
            student_id="s2",
            proficiency_by_subject={
                "mat": {"grade": 8.0, "proficiency": 260.0, "classification": "Adequado"}
            },
        )
        res_3 = MagicMock(
            student_id="s3",
            proficiency_by_subject={
                "mat": {"grade": 4.0, "proficiency": 150.0, "classification": "Abaixo do Básico"}
            },
        )

        with patch.object(
            AnswerSheetComparisonService,
            "_extract_subjects_from_gabarito",
            side_effect=[{"mat": "Matemática"}, {"mat": "Matemática"}],
        ):
            out = AnswerSheetComparisonService._get_subject_comparison(
                gab_1, gab_2, [res_1, res_2], [res_3]
            )

        self.assertIn("Matemática", out)
        self.assertEqual(out["Matemática"]["average_grade"]["evaluation_1"], 7.0)
        self.assertEqual(out["Matemática"]["average_grade"]["evaluation_2"], 4.0)


if __name__ == "__main__":
    unittest.main()
