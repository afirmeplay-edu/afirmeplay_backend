# -*- coding: utf-8 -*-
# Exec: python -m unittest tests.test_distribution_form_scope
import importlib.util
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_FILTER_UTILS = _ROOT / "app" / "socioeconomic_forms" / "services" / "filter_utils.py"


def _load_filter_utils():
    spec = importlib.util.spec_from_file_location("socio_filter_utils", _FILTER_UTILS)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


_fu = _load_filter_utils()
student_matches_form_scope = _fu.student_matches_form_scope


class TestStudentMatchesFormScope(unittest.TestCase):
    def test_matches_school_and_grade_without_selected_classes(self):
        self.assertTrue(
            student_matches_form_scope(
                "aluno-jovem",
                "school-1",
                "grade-1",
                "class-new",
                selected_schools=["school-1"],
                selected_grades=["grade-1"],
            )
        )

    def test_rejects_other_grade_when_form_is_grade_scoped(self):
        self.assertFalse(
            student_matches_form_scope(
                "aluno-jovem",
                "school-1",
                "grade-old",
                "class-new",
                selected_schools=["school-1"],
                selected_grades=["grade-1"],
            )
        )

    def test_matches_selected_class_with_matching_grade(self):
        self.assertTrue(
            student_matches_form_scope(
                "aluno-jovem",
                "school-1",
                "grade-1",
                "class-new",
                selected_schools=["school-1"],
                selected_grades=["grade-1"],
                selected_classes=["class-new"],
            )
        )

    def test_matches_class_only_form_without_selected_grades(self):
        self.assertTrue(
            student_matches_form_scope(
                "aluno-jovem",
                "school-1",
                "grade-old",
                "class-new",
                selected_schools=["school-1"],
                selected_grades=None,
                selected_classes=["class-new"],
            )
        )

    def test_matches_filters_turma_without_selected_grades_or_classes(self):
        self.assertTrue(
            student_matches_form_scope(
                "aluno-jovem",
                "school-1",
                "grade-1",
                "class-new",
                filters={"turma": "class-new", "escola": "school-1"},
            )
        )

    def test_rejects_other_class_when_filters_turma_is_set(self):
        self.assertFalse(
            student_matches_form_scope(
                "aluno-jovem",
                "school-1",
                "grade-1",
                "class-other",
                filters={"turma": "class-new", "escola": "school-1"},
            )
        )

    def test_rejects_other_school(self):
        self.assertFalse(
            student_matches_form_scope(
                "aluno-jovem",
                "school-2",
                "grade-1",
                "class-new",
                selected_schools=["school-1"],
                selected_grades=["grade-1"],
            )
        )


if __name__ == "__main__":
    unittest.main()
