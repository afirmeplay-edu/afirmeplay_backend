import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.services.student_enrollment_service import (
    assert_same_municipality_two_schools,
    transfer_student_to_class,
)


class FakeField:
    def __init__(self, name):
        self.name = name

    def __eq__(self, other):
        return lambda item: str(getattr(item, self.name, None)) == str(other)


class FakeSchoolModel:
    id = FakeField("id")
    city_id = FakeField("city_id")


class FakeQuery:
    def __init__(self, items):
        self._items = list(items)

    def filter(self, *predicates):
        filtered = self._items
        for predicate in predicates:
            if callable(predicate):
                filtered = [item for item in filtered if predicate(item)]
        return FakeQuery(filtered)

    def first(self):
        return self._items[0] if self._items else None


class FakeSession:
    def __init__(self, schools):
        self._schools = list(schools)

    def query(self, _model):
        return FakeQuery(self._schools)


class TestStudentEnrollmentService(unittest.TestCase):
    def test_transfer_same_school_different_class_does_not_validate_distinct_school(self):
        school = SimpleNamespace(id="school-1", city_id="city-1")
        session = FakeSession([school])
        student = SimpleNamespace(
            id="student-1",
            school_id="school-1",
            class_id="class-old",
            grade_id="grade-old",
            user=SimpleNamespace(city_id="city-1"),
        )
        new_class = SimpleNamespace(id="class-new", school_id="school-1", grade_id="grade-new")

        with patch("app.models.school.School", FakeSchoolModel):
            with patch("app.services.student_enrollment_service.assert_same_municipality_two_schools") as assert_mock:
                with patch("app.services.student_enrollment_service.close_active_enrollment") as close_mock:
                    with patch("app.services.student_enrollment_service.open_enrollment") as open_mock:
                        with patch(
                            "app.services.student_password_log_service.sync_password_logs_with_student_placement"
                        ):
                            transfer_student_to_class(session, student, new_class, update_user_city=True)

        assert_mock.assert_not_called()
        close_mock.assert_called_once_with(session, "student-1")
        open_mock.assert_called_once_with(session, "student-1", school_id="school-1", class_id="class-new")
        self.assertEqual(student.class_id, "class-new")
        self.assertEqual(student.school_id, "school-1")

    def test_transfer_different_school_same_city_still_allows(self):
        schools = [
            SimpleNamespace(id="school-1", city_id="city-1"),
            SimpleNamespace(id="school-2", city_id="city-1"),
        ]
        session = FakeSession(schools)
        student = SimpleNamespace(
            id="student-1",
            school_id="school-1",
            class_id="class-old",
            grade_id="grade-old",
            user=SimpleNamespace(city_id="city-1"),
        )
        new_class = SimpleNamespace(id="class-new", school_id="school-2", grade_id="grade-new")

        with patch("app.models.school.School", FakeSchoolModel):
            with patch("app.services.student_enrollment_service.close_active_enrollment"):
                with patch("app.services.student_enrollment_service.open_enrollment"):
                    with patch(
                        "app.services.student_password_log_service.migrate_password_logs_to_new_school"
                    ):
                        transfer_student_to_class(session, student, new_class, update_user_city=True)

        self.assertEqual(student.class_id, "class-new")
        self.assertEqual(student.school_id, "school-2")

    def test_assert_same_municipality_raises_for_different_city(self):
        schools = [
            SimpleNamespace(id="school-1", city_id="city-1"),
            SimpleNamespace(id="school-2", city_id="city-2"),
        ]
        session = FakeSession(schools)

        with patch("app.models.school.School", FakeSchoolModel):
            with self.assertRaisesRegex(ValueError, "mesmo município"):
                assert_same_municipality_two_schools(session, "school-1", "school-2")


if __name__ == "__main__":
    unittest.main()
