"""
Testes de bundle: questões compartilhadas entre provas (ids globais de public.question).
Execução: python -m unittest tests.test_bundle_shared_questions
"""
import unittest
from unittest.mock import MagicMock, patch

from app.services.mobile import bundle_service as svc


class TestBundleSharedQuestions(unittest.TestCase):
    @patch.object(svc, "Question")
    @patch.object(svc, "TestQuestion")
    @patch.object(svc, "_get_all_subjects_from_test")
    def test_two_tests_share_question_id_in_payload(
        self, mock_subjects, mock_tq, mock_question
    ):
        mock_subjects.return_value = []

        shared_q = MagicMock()
        shared_q.id = "q-shared-uuid"
        shared_q.number = 1
        shared_q.text = "Enunciado"
        shared_q.formatted_text = None
        shared_q.secondstatement = None
        shared_q.images = None
        shared_q.alternatives = []
        shared_q.command = None
        shared_q.subtitle = None
        shared_q.question_type = "multiple_choice"
        shared_q.correct_answer = "A"
        shared_q.value = 1
        shared_q.topics = None
        shared_q.version = 1

        q_a_only = MagicMock()
        q_a_only.id = "q-a-only"
        for attr in (
            "number",
            "text",
            "formatted_text",
            "secondstatement",
            "images",
            "alternatives",
            "command",
            "subtitle",
            "question_type",
            "correct_answer",
            "value",
            "topics",
            "version",
        ):
            setattr(q_a_only, attr, getattr(shared_q, attr))
        q_a_only.number = 2

        q_b_only = MagicMock()
        q_b_only.id = "q-b-only"
        for attr in (
            "number",
            "text",
            "formatted_text",
            "secondstatement",
            "images",
            "alternatives",
            "command",
            "subtitle",
            "question_type",
            "correct_answer",
            "value",
            "topics",
            "version",
        ):
            setattr(q_b_only, attr, getattr(shared_q, attr))
        q_b_only.number = 2

        test_a = MagicMock()
        test_a.id = "test-a"
        test_a.title = "Prova A"
        test_a.description = None
        test_a.intructions = None
        test_a.type = "exam"
        test_a.max_score = 10
        test_a.duration = 60
        test_a.evaluation_mode = None
        test_a.subject = None
        test_a.grade_id = None
        test_a.status = "active"

        test_b = MagicMock()
        test_b.id = "test-b"
        test_b.title = "Prova B"
        for attr in (
            "description",
            "intructions",
            "type",
            "max_score",
            "duration",
            "evaluation_mode",
            "subject",
            "grade_id",
            "status",
        ):
            setattr(test_b, attr, getattr(test_a, attr))

        row_a1 = MagicMock(question_id="q-shared-uuid", order=1)
        row_a2 = MagicMock(question_id="q-a-only", order=2)
        row_b1 = MagicMock(question_id="q-shared-uuid", order=1)
        row_b2 = MagicMock(question_id="q-b-only", order=2)

        def tq_filter(test_id=None, **kwargs):
            q = MagicMock()
            if test_id == "test-a":
                q.order_by.return_value.all.return_value = [row_a1, row_a2]
            else:
                q.order_by.return_value.all.return_value = [row_b1, row_b2]
            return q

        mock_tq.query.filter_by.side_effect = tq_filter
        mock_tq.query.filter_by.return_value.order_by.return_value.all.side_effect = (
            lambda: [row_a1, row_a2]
        )

        def question_filter(*args, **kwargs):
            q = MagicMock()
            q.all.return_value = [shared_q, q_a_only, q_b_only]
            return q

        mock_question.query.filter.side_effect = question_filter

        with patch.object(svc, "compute_test_content_version", return_value="hash"):
            tests_payload, versions, q_by_test = svc.build_tests_questions_payload(
                {"test-a": test_a, "test-b": test_b}
            )

        self.assertEqual(len(q_by_test["test-a"]), 2)
        self.assertEqual(len(q_by_test["test-b"]), 2)
        ids_a = {item["id"] for item in q_by_test["test-a"]}
        ids_b = {item["id"] for item in q_by_test["test-b"]}
        self.assertIn("q-shared-uuid", ids_a)
        self.assertIn("q-shared-uuid", ids_b)
        self.assertEqual(ids_a & ids_b, {"q-shared-uuid"})
        for item in q_by_test["test-a"] + q_by_test["test-b"]:
            self.assertEqual(item.get("question_id"), item["id"])


if __name__ == "__main__":
    unittest.main()
