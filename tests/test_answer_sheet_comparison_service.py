import unittest
from unittest.mock import MagicMock, patch

from app.routes.answer_sheet_routes import _parse_gabarito_ids_from_body
from app.services.answer_sheet_comparison_service import AnswerSheetComparisonService
from app.services.evaluation_comparison_service import EvaluationComparisonService


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
    def test_general_comparison_uses_hierarchical_mean(self):
        r1 = MagicMock(grade=6.0, proficiency=200.0, classification="Básico")
        r2 = MagicMock(grade=8.0, proficiency=250.0, classification="Adequado")
        r3 = MagicMock(grade=4.0, proficiency=150.0, classification="Abaixo do Básico")
        r4 = MagicMock(grade=6.0, proficiency=200.0, classification="Básico")
        gab_1 = MagicMock(id="g1")
        gab_2 = MagicMock(id="g2")

        with patch(
            "app.services.answer_sheet_comparison_service.AnswerSheetComparisonService._course_meta_for_gabarito",
            side_effect=[("Anos Iniciais", True), ("Anos Iniciais", True)],
        ), patch(
            "app.utils.school_equal_weight_means.hierarchical_mean_grade_and_proficiency",
            side_effect=[(7.4, 252.0), (5.1, 180.0)],
        ) as mock_hier:
            out = AnswerSheetComparisonService._get_general_comparison(
                [r1, r2], [r3, r4], gab_1, gab_2
            )

        self.assertEqual(mock_hier.call_count, 2)
        self.assertEqual(mock_hier.call_args_list[0].args[1], "municipio")
        self.assertEqual(out["average_grade"]["evaluation_1"], 7.4)
        self.assertEqual(out["average_grade"]["evaluation_2"], 5.1)
        self.assertEqual(out["average_proficiency"]["evaluation_1"], 252.0)
        self.assertEqual(out["total_students"]["evaluation_1"], 2)
        self.assertIn("evolution", out["average_grade"])
        self.assertEqual(out["classification_distribution"]["evaluation_1"]["Básico"], 1)


class TestAnswerSheetSubjectComparison(unittest.TestCase):
    def test_subject_comparison_uses_hierarchical_mean(self):
        gab_1 = MagicMock(
            id="g1",
            blocks_config={
                "blocks": [
                    {
                        "subject_id": "mat",
                        "subject_name": "Matemática",
                        "start_question": 1,
                        "end_question": 2,
                    }
                ]
            },
        )
        gab_2 = MagicMock(
            id="g2",
            blocks_config={
                "blocks": [
                    {
                        "subject_id": "mat",
                        "subject_name": "Matemática",
                        "start_question": 1,
                        "end_question": 2,
                    }
                ]
            },
        )

        res_1 = MagicMock(
            student_id="s1",
            class_id_snapshot=None,
            school_id_snapshot=None,
            grade_id_snapshot=None,
            proficiency_by_subject={
                "mat": {"grade": 6.0, "proficiency": 200.0, "classification": "Básico"}
            },
        )
        res_2 = MagicMock(
            student_id="s2",
            class_id_snapshot=None,
            school_id_snapshot=None,
            grade_id_snapshot=None,
            proficiency_by_subject={
                "mat": {"grade": 8.0, "proficiency": 260.0, "classification": "Adequado"}
            },
        )
        res_3 = MagicMock(
            student_id="s3",
            class_id_snapshot=None,
            school_id_snapshot=None,
            grade_id_snapshot=None,
            proficiency_by_subject={
                "mat": {
                    "grade": 4.0,
                    "proficiency": 150.0,
                    "classification": "Abaixo do Básico",
                }
            },
        )

        with patch.object(
            AnswerSheetComparisonService,
            "_extract_subjects_from_gabarito",
            side_effect=[{"mat": "Matemática"}, {"mat": "Matemática"}],
        ), patch(
            "app.services.answer_sheet_comparison_service.AnswerSheetComparisonService._course_meta_for_gabarito",
            side_effect=[("Anos Iniciais", True), ("Anos Iniciais", True)],
        ), patch(
            "app.utils.school_equal_weight_means.hierarchical_mean_from_subject_rows",
            side_effect=[(7.4, 252.0, 0.0), (4.0, 150.0, 0.0)],
        ) as mock_hier:
            out = AnswerSheetComparisonService._get_subject_comparison(
                gab_1, gab_2, [res_1, res_2], [res_3]
            )

        self.assertIn("Matemática", out)
        self.assertEqual(mock_hier.call_count, 2)
        self.assertEqual(mock_hier.call_args_list[0].args[1], "municipio")
        self.assertEqual(out["Matemática"]["average_grade"]["evaluation_1"], 7.4)
        self.assertEqual(out["Matemática"]["average_grade"]["evaluation_2"], 4.0)


class TestEvaluationGeneralComparison(unittest.TestCase):
    def test_general_comparison_uses_hierarchical_mean(self):
        r1 = MagicMock(grade=6.0, proficiency=200.0, classification="Básico")
        r2 = MagicMock(grade=8.0, proficiency=250.0, classification="Adequado")
        test_1 = MagicMock(id="t1", course=None)
        test_2 = MagicMock(id="t2", course=None)

        with patch(
            "app.utils.school_equal_weight_means.hierarchical_mean_grade_and_proficiency",
            side_effect=[(6.5, 220.0), (7.9, 270.0)],
        ) as mock_hier:
            out = EvaluationComparisonService._get_general_comparison(
                [r1, r2], [r1], test_1, test_2
            )

        self.assertEqual(mock_hier.call_count, 2)
        self.assertEqual(mock_hier.call_args_list[0].args[1], "municipio")
        self.assertEqual(out["average_grade"]["evaluation_1"], 6.5)
        self.assertEqual(out["average_grade"]["evaluation_2"], 7.9)
        self.assertEqual(out["average_proficiency"]["evaluation_2"], 270.0)


class TestGradeInfoResolution(unittest.TestCase):
    def test_resolve_test_grade_info_from_class_test(self):
        test = MagicMock(
            id="test-1",
            grade_id=None,
            grade=None,
            title="Prova",
        )
        class_obj = MagicMock(grade_id="grade-uuid-1", id="class-uuid-1", name="Turma A")
        grade_obj = MagicMock(name="5º Ano")

        with patch("app.models.classTest.ClassTest") as mock_ct, patch(
            "app.models.studentClass.Class"
        ) as mock_class, patch("app.models.grades.Grade") as mock_grade:
            mock_ct.query.filter_by.return_value.all.return_value = [
                MagicMock(class_id="class-uuid-1")
            ]
            mock_class.query.filter.return_value.all.return_value = [class_obj]
            mock_grade.query.get.return_value = grade_obj

            info = EvaluationComparisonService._resolve_test_grade_info(test)

        self.assertEqual(info["grade_id"], "grade-uuid-1")
        self.assertEqual(info["grade_name"], "5º Ano")
        self.assertEqual(info["grade_names"], ["5º Ano"])
        self.assertEqual(
            info["classes"],
            [{"id": "class-uuid-1", "name": "Turma A"}],
        )


if __name__ == "__main__":
    unittest.main()
