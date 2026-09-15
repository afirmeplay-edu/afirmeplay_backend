# -*- coding: utf-8 -*-
"""Validação de cartão manual 100% em branco (entrada)."""

import unittest

from app.services.cartao_resposta.manual_answer_sheet_service import (
    ManualAnswerSheetError,
    _is_manual_answer_filled,
    assert_at_least_one_manual_answer,
    normalize_manual_answers,
)


class ManualBlankValidationTests(unittest.TestCase):
    def test_filled_detection(self):
        self.assertFalse(_is_manual_answer_filled(None))
        self.assertFalse(_is_manual_answer_filled(""))
        self.assertFalse(_is_manual_answer_filled("   "))
        self.assertFalse(_is_manual_answer_filled("INVALID"))
        self.assertFalse(_is_manual_answer_filled("invalid"))
        self.assertTrue(_is_manual_answer_filled("A"))
        self.assertTrue(_is_manual_answer_filled("b"))

    def test_assert_rejects_all_null(self):
        with self.assertRaises(ManualAnswerSheetError) as ctx:
            assert_at_least_one_manual_answer({1: None, 2: None, 3: None})
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("pelo menos uma questão", ctx.exception.message)

    def test_assert_rejects_only_invalid(self):
        with self.assertRaises(ManualAnswerSheetError) as ctx:
            assert_at_least_one_manual_answer({1: "INVALID", 2: None})
        self.assertEqual(ctx.exception.status_code, 400)

    def test_assert_accepts_partial(self):
        assert_at_least_one_manual_answer({1: "A", 2: None, 3: None})

    def test_assert_accepts_complete(self):
        assert_at_least_one_manual_answer({1: "A", 2: "B", 3: "C"})

    def test_normalize_then_assert_all_blank_payload(self):
        gabarito = {1: "A", 2: "B", 3: "C"}
        alternatives = {1: ["A", "B", "C", "D"], 2: ["A", "B", "C", "D"], 3: ["A", "B", "C", "D"]}
        normalized = normalize_manual_answers({}, gabarito, alternatives)
        self.assertEqual(normalized, {1: None, 2: None, 3: None})
        with self.assertRaises(ManualAnswerSheetError):
            assert_at_least_one_manual_answer(normalized)

    def test_normalize_partial_passes_assert(self):
        gabarito = {1: "A", 2: "B", 3: "C"}
        alternatives = {1: ["A", "B", "C", "D"], 2: ["A", "B", "C", "D"], 3: ["A", "B", "C", "D"]}
        normalized = normalize_manual_answers({"1": "A", "2": None}, gabarito, alternatives)
        assert_at_least_one_manual_answer(normalized)
        self.assertEqual(normalized[1], "A")
        self.assertIsNone(normalized[2])
        self.assertIsNone(normalized[3])


if __name__ == "__main__":
    unittest.main()
