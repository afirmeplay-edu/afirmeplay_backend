import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services.student_enrollment_service import transfer_student_to_class
from app.services.student_password_log_service import (
    _normalize_person_name,
    apply_active_student_password_log_filter,
    delete_password_logs_for_student_at_school,
    ensure_password_log_for_student_placement,
    migrate_password_logs_to_new_school,
    sync_password_logs_for_class_school_relocation,
    sync_password_logs_with_student_placement,
)


class FakeField:
    def __init__(self, name):
        self.name = name

    def __eq__(self, other):
        return lambda item: str(getattr(item, self.name, None)) == str(other)


class FakePasswordLogModel:
    _test_model_label = "StudentPasswordLog"
    student_id = FakeField("student_id")
    school_id = FakeField("school_id")
    class_id = FakeField("class_id")
    user_id = FakeField("user_id")


class FakeSchoolModel:
    _test_model_label = "School"
    id = FakeField("id")
    city_id = FakeField("city_id")


class FakeUpdateQuery:
    def __init__(self, update_result=2):
        self._update_result = update_result
        self.updated_values = None

    def filter(self, *predicates):
        return self

    def update(self, values, synchronize_session=False):
        self.updated_values = values
        return self._update_result


class FakeDeleteQuery:
    def __init__(self, delete_result=1):
        self._delete_result = delete_result

    def filter(self, *predicates):
        return self

    def delete(self, synchronize_session=False):
        return self._delete_result


class FakeSchoolQuery:
    def __init__(self, schools):
        self._schools = list(schools)

    def filter(self, *predicates):
        filtered = self._schools
        for predicate in predicates:
            if callable(predicate):
                filtered = [s for s in filtered if predicate(s)]
        return FakeSchoolQuery(filtered)

    def first(self):
        return self._schools[0] if self._schools else None


class FakeSession:
    def __init__(self, schools=None, update_result=2, delete_result=1):
        self._schools = list(schools or [])
        self._update_result = update_result
        self._delete_result = delete_result
        self.last_update_query = None
        self.last_delete_query = None
        self._password_mode = "update"

    def query(self, model):
        name = getattr(model, "_test_model_label", type(model).__name__)
        if name == "School":
            return FakeSchoolQuery(self._schools)
        if name == "StudentPasswordLog":
            if self._password_mode == "delete":
                q = FakeDeleteQuery(self._delete_result)
                self.last_delete_query = q
                return q
            q = FakeUpdateQuery(self._update_result)
            self.last_update_query = q
            return q
        raise AssertionError(f"Unexpected model: {model} ({name})")


class TestPasswordLogSync(unittest.TestCase):
    def test_normalize_person_name_ignores_accents(self):
        self.assertEqual(
            _normalize_person_name("José Miguel Marques Silva"),
            _normalize_person_name("JOSE MIGUEL MARQUES SILVA"),
        )

    def test_sync_password_logs_with_student_placement_updates_fields(self):
        school = SimpleNamespace(id="school-1", city_id="city-1")
        session = FakeSession([school])
        student = SimpleNamespace(
            id="student-1",
            school_id="school-1",
            class_id="class-new",
            grade_id="grade-new",
        )

        with patch("app.models.school.School", FakeSchoolModel):
            with patch("app.models.studentPasswordLog.StudentPasswordLog", FakePasswordLogModel):
                n = sync_password_logs_with_student_placement(session, student)

        self.assertEqual(n, 2)
        self.assertEqual(
            session.last_update_query.updated_values,
            {
                "class_id": "class-new",
                "grade_id": "grade-new",
                "school_id": "school-1",
                "city_id": "city-1",
            },
        )

    def test_sync_password_logs_for_class_school_relocation(self):
        session = FakeSession()
        with patch("app.models.studentPasswordLog.StudentPasswordLog", FakePasswordLogModel):
            n = sync_password_logs_for_class_school_relocation(
                session,
                "class-1",
                "school-old",
                "school-new",
                city_id="city-1",
            )

        self.assertEqual(n, 2)
        self.assertEqual(
            session.last_update_query.updated_values,
            {"school_id": "school-new", "city_id": "city-1"},
        )

    def test_migrate_password_logs_to_new_school_updates_placement(self):
        session = FakeSession()
        with patch("app.models.studentPasswordLog.StudentPasswordLog", FakePasswordLogModel):
            n = migrate_password_logs_to_new_school(
                session,
                "student-1",
                "school-pedro",
                new_school_id="school-araci",
                class_id="class-araci-4a",
                grade_id="grade-4",
                city_id="city-1",
            )

        self.assertEqual(n, 2)
        self.assertEqual(
            session.last_update_query.updated_values,
            {
                "school_id": "school-araci",
                "class_id": "class-araci-4a",
                "grade_id": "grade-4",
                "city_id": "city-1",
            },
        )

    def test_migrate_password_logs_same_school_returns_zero(self):
        session = FakeSession()
        with patch("app.models.studentPasswordLog.StudentPasswordLog", FakePasswordLogModel):
            n = migrate_password_logs_to_new_school(
                session,
                "student-1",
                "school-1",
                new_school_id="school-1",
            )
        self.assertEqual(n, 0)

    def test_delete_password_logs_for_student_at_school(self):
        session = FakeSession()
        session._password_mode = "delete"

        with patch("app.models.studentPasswordLog.StudentPasswordLog", FakePasswordLogModel):
            n = delete_password_logs_for_student_at_school(session, "student-1", "school-old")

        self.assertEqual(n, 1)
        self.assertIsNotNone(session.last_delete_query)


class TestTransferStudentPasswordLogs(unittest.TestCase):
    def test_transfer_same_school_syncs_password_logs(self):
        school = SimpleNamespace(id="school-1", city_id="city-1")
        session = FakeSession([school])
        student = SimpleNamespace(
            id="student-1",
            school_id="school-1",
            class_id="class-old",
            grade_id="grade-old",
            user=SimpleNamespace(city_id="city-1"),
        )
        new_class = SimpleNamespace(
            id="class-new",
            school_id="school-1",
            grade_id="grade-new",
        )

        with patch("app.models.school.School", FakeSchoolModel):
            with patch("app.services.student_enrollment_service.close_active_enrollment"):
                with patch("app.services.student_enrollment_service.open_enrollment"):
                    with patch(
                        "app.services.student_password_log_service.sync_password_logs_with_student_placement"
                    ) as sync_mock:
                        transfer_student_to_class(session, student, new_class, update_user_city=True)

        sync_mock.assert_called_once_with(session, student)
        self.assertEqual(student.class_id, "class-new")
        self.assertEqual(student.grade_id, "grade-new")

    def test_transfer_different_school_migrates_logs_not_sync(self):
        schools = [
            SimpleNamespace(id="school-pedro", city_id="city-1"),
            SimpleNamespace(id="school-araci", city_id="city-1"),
        ]
        session = FakeSession(schools)
        student = SimpleNamespace(
            id="student-1",
            school_id="school-pedro",
            class_id="class-old",
            grade_id="grade-old",
            user=SimpleNamespace(city_id="city-1"),
        )
        new_class = SimpleNamespace(
            id="class-araci-4a",
            school_id="school-araci",
            grade_id="grade-new",
        )

        with patch("app.models.school.School", FakeSchoolModel):
            with patch("app.services.student_enrollment_service.close_active_enrollment"):
                with patch("app.services.student_enrollment_service.open_enrollment"):
                    with patch(
                        "app.services.student_password_log_service.migrate_password_logs_to_new_school"
                    ) as migrate_mock:
                        with patch(
                            "app.services.student_password_log_service.ensure_password_log_for_student_placement"
                        ) as ensure_mock:
                            with patch(
                                "app.services.student_password_log_service.sync_password_logs_with_student_placement"
                            ) as sync_mock:
                                migrate_mock.return_value = 1
                                transfer_student_to_class(session, student, new_class, update_user_city=True)

        migrate_mock.assert_called_once_with(
            session,
            "student-1",
            "school-pedro",
            new_school_id="school-araci",
            class_id="class-araci-4a",
            grade_id="grade-new",
            city_id="city-1",
        )
        ensure_mock.assert_not_called()
        sync_mock.assert_not_called()
        self.assertEqual(student.school_id, "school-araci")


class TestPasswordReportQueryFilter(unittest.TestCase):
    def test_apply_active_filter_chains_join_and_filter(self):
        base_query = MagicMock()
        joined = MagicMock()
        base_query.join.return_value = joined

        result = apply_active_student_password_log_filter(base_query)

        base_query.join.assert_called_once()
        joined.filter.assert_called_once()
        self.assertIs(result, joined.filter.return_value)


if __name__ == "__main__":
    unittest.main()
