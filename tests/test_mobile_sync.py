"""
Testes do módulo mobile (sync, device_id, DDL, idempotência).
Execução: python -m unittest tests.test_mobile_sync
Requer variável DATABASE_URL para testes de integração com DB.
"""
import os
import unittest
import uuid

from app.services.mobile.ddl import get_mobile_tables_ddl
from app.services.mobile.device_service import is_valid_uuid_v4
from app.services.mobile.content_hash import compute_test_content_version
from app.services.mobile.student_registration_pin_core import (
    allocate_unique_pin,
    is_valid_pin_format,
)
from app.services.mobile.student_registration_pin import (
    assign_registration_pin,
    collect_used_student_registrations,
)


class TestMobileDDL(unittest.TestCase):
    def test_ddl_idempotent_markers(self):
        sql = get_mobile_tables_ddl("city_test123")
        self.assertIn('CREATE TABLE IF NOT EXISTS "city_test123".mobile_device', sql)
        self.assertIn("mobile_sync_submission", sql)
        self.assertIn("test_content_version", sql)
        self.assertIn("ADD COLUMN IF NOT EXISTS test_content_version", sql)
        self.assertIn("mobile_sync_bundle_generation", sql)
        self.assertIn("mobile_offline_pack_code", sql)
        self.assertIn("activation_code", sql)
        self.assertIn("mobile_offline_pack_redeem_device", sql)

    def test_ddl_rejects_bad_schema(self):
        with self.assertRaises(ValueError):
            get_mobile_tables_ddl("public")

    def test_ddl_multiple_schemas_no_cross_reference_issue(self):
        a = get_mobile_tables_ddl("city_a")
        b = get_mobile_tables_ddl("city_b")
        self.assertIn("city_a", a)
        self.assertIn("city_b", b)


class TestDeviceId(unittest.TestCase):
    def test_uuid_v4_valid(self):
        u = str(uuid.uuid4())
        self.assertTrue(is_valid_uuid_v4(u))

    def test_uuid_v4_invalid(self):
        self.assertFalse(is_valid_uuid_v4("not-a-uuid"))
        self.assertFalse(is_valid_uuid_v4(""))


class TestStudentRegistrationPin(unittest.TestCase):
    def test_pin_format(self):
        pin = allocate_unique_pin(set())
        self.assertTrue(is_valid_pin_format(pin))
        self.assertEqual(len(pin), 4)

    def test_pin_unique_in_memory(self):
        used = {allocate_unique_pin(set()) for _ in range(50)}
        self.assertEqual(len(used), 50)

    @unittest.skipUnless(os.getenv("DATABASE_URL"), "DATABASE_URL não definido")
    def test_assign_pin_on_student(self):
        from app import create_app, db
        from app.models.student import Student

        app = create_app()
        with app.app_context():
            used = collect_used_student_registrations(db.session)
            before = len(used)
            student = Student(name="Teste PIN", user_id=None)
            db.session.add(student)
            db.session.flush()
            pin = assign_registration_pin(student, db.session, used)
            self.assertTrue(is_valid_pin_format(pin))
            self.assertEqual(student.registration, pin)
            self.assertEqual(len(used), before + 1)
            db.session.rollback()


class TestSubmissionContentReplay(unittest.TestCase):
    def test_same_hash_is_replay(self):
        from app.services.mobile.upload_service import _is_same_content_replay

        self.assertTrue(_is_same_content_replay("abc", "abc"))

    def test_legacy_null_is_not_replay(self):
        from app.services.mobile.upload_service import _is_same_content_replay

        self.assertFalse(_is_same_content_replay(None, "abc"))
        self.assertFalse(_is_same_content_replay("", "abc"))

    def test_different_hash_is_not_replay(self):
        from app.services.mobile.upload_service import _is_same_content_replay

        self.assertFalse(_is_same_content_replay("hash-antigo", "hash-novo"))

    def test_removed_question_is_ignored_when_current_are_answered(self):
        from app.services.mobile.upload_service import select_answers_for_current_test

        err, selected = select_answers_for_current_test(
            [
                {"question_id": "removida", "answer": "A"},
                {"question_id": "q1", "answer": "B"},
                {"question_id": "q2", "answer": "C"},
            ],
            {"q1", "q2"},
        )
        self.assertIsNone(err)
        self.assertEqual({item["question_id"] for item in selected}, {"q1", "q2"})

    def test_missing_current_question_is_error(self):
        from app.services.mobile.upload_service import select_answers_for_current_test

        err, selected = select_answers_for_current_test(
            [
                {"question_id": "q1", "answer": "B"},
                {"question_id": "removida", "answer": "A"},
            ],
            {"q1", "q2"},
        )
        self.assertEqual(err, "resposta ausente para questão da prova")
        self.assertEqual(selected, [])


class TestProcessOneSubmissionReplay(unittest.TestCase):
    def test_same_stored_hash_returns_duplicate_ignored(self):
        import uuid
        from unittest.mock import MagicMock, patch

        from app.services.mobile.upload_service import process_one_submission

        existing = MagicMock()
        existing.test_content_version = "hash-atual"
        with patch("app.services.mobile.upload_service.MobileSyncSubmission") as model:
            model.query.filter_by.return_value.first.return_value = existing
            result = process_one_submission(
                item={
                    "submission_id": str(uuid.uuid4()),
                    "student_id": "stu",
                    "test_id": "test",
                    "test_content_version": "hash-atual",
                    "sync_bundle_version": 3,
                    "answers": [],
                },
                user_id="user",
                school_id="school",
            )
        self.assertEqual(result["status"], "duplicate_ignored")
        self.assertTrue(result["already_processed"])

    def test_legacy_submission_without_hash_is_not_duplicate(self):
        import uuid
        from unittest.mock import MagicMock, patch

        from app.services.mobile.upload_service import process_one_submission

        existing = MagicMock()
        existing.test_content_version = None
        with patch("app.services.mobile.upload_service.MobileSyncSubmission") as model, patch(
            "app.services.mobile.upload_service.get_bundle_generation", return_value=None
        ), patch("app.services.mobile.upload_service.MobileSyncBundleGeneration") as generations:
            model.query.filter_by.return_value.first.return_value = existing
            generations.query.filter_by.return_value.order_by.return_value.all.return_value = []
            result = process_one_submission(
                item={
                    "submission_id": str(uuid.uuid4()),
                    "student_id": "stu",
                    "test_id": "test",
                    "test_content_version": "hash-novo",
                    "sync_bundle_version": 4,
                    "answers": [],
                },
                user_id="user",
                school_id="school",
            )
        self.assertEqual(result["status"], "error")
        self.assertNotEqual(result["status"], "duplicate_ignored")
        self.assertIn("sync_bundle_version", result["message"])


class TestContentHash(unittest.TestCase):
    def test_stable_hash(self):
        t = {"id": "t1", "title": "Prova"}
        qs = [{"id": "q1", "order": 1, "text": "?" }]
        h1 = compute_test_content_version(t, qs)
        h2 = compute_test_content_version(t, qs)
        self.assertEqual(h1, h2)
        self.assertEqual(len(h1), 64)


@unittest.skipUnless(os.getenv("DATABASE_URL"), "DATABASE_URL não definido")
class TestMobileIdempotencyIntegration(unittest.TestCase):
    """Duplicar upload: segundo retorna duplicate_ignored (exige DB e dados)."""

    def setUp(self):
        from app import create_app, db
        self.app = create_app()
        self.ctx = self.app.app_context()
        self.ctx.push()
        self.client = self.app.test_client()

    def tearDown(self):
        from app import db
        db.session.remove()
        self.ctx.pop()

    def test_duplicate_submission_returns_duplicate_status(self):
        # Placeholder: ambiente real precisa de tenant, tabelas mobile e usuário —
        # mantém estrutura para evolução com fixtures.
        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
