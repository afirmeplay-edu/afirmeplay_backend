# -*- coding: utf-8 -*-
"""Filtro opcional × identidade detectada na Correção por foto."""
import unittest
from unittest.mock import patch

from app.services.cartao_resposta.photo_identity import resolve_identity_with_filter


class TestResolveIdentityWithFilter(unittest.TestCase):
    def test_detection_only(self):
        out = resolve_identity_with_filter(
            detected={
                "student_id": "stu-1",
                "gabarito_id": "gab-1",
                "test_id": None,
                "identity_source": "qr+idgrid",
                "identity_confidence": "high",
                "idgrid_checksum_ok": True,
                "identity_mismatch": False,
                "detected": True,
            }
        )
        self.assertEqual(out["student_id"], "stu-1")
        self.assertEqual(out["identity_source"], "qr+idgrid")
        self.assertFalse(out["filter_applied"])
        self.assertFalse(out["identity_mismatch"])

    def test_filter_fallback_when_no_detection(self):
        out = resolve_identity_with_filter(
            filter_student_id="stu-filter",
            expected_test_id="test-1",
            detected={"detected": False, "student_id": None},
        )
        self.assertEqual(out["student_id"], "stu-filter")
        self.assertEqual(out["identity_source"], "filter")
        self.assertTrue(out["filter_applied"])
        self.assertEqual(out["test_id"], "test-1")
        self.assertTrue(out["matches_selected_document"])

    def test_mismatch_prefers_filter(self):
        out = resolve_identity_with_filter(
            filter_student_id="stu-filter",
            detected={
                "student_id": "stu-detected",
                "identity_source": "qr",
                "identity_confidence": "medium",
                "detected": True,
            },
        )
        self.assertEqual(out["student_id"], "stu-filter")
        self.assertTrue(out["identity_mismatch"])
        self.assertTrue(out["student_mismatch"])
        self.assertEqual(out["identity_source"], "filter+conflict")

    def test_neither_yields_null_student(self):
        out = resolve_identity_with_filter(detected={"detected": False})
        self.assertIsNone(out["student_id"])
        self.assertIsNone(out["identity_source"])

    def test_cartao_gabarito_matches_selected_test(self):
        """QR traz gabarito_id; UI selecionou test_id da mesma prova → OK."""
        with patch(
            "app.services.cartao_resposta.photo_identity._gabarito_test_id",
            return_value="test-novo-novembro",
        ):
            out = resolve_identity_with_filter(
                expected_test_id="test-novo-novembro",
                detected={
                    "student_id": "stu-1",
                    "gabarito_id": "gab-da-prova",
                    "test_id": None,
                    "identity_source": "qr",
                    "detected": True,
                },
            )
        self.assertTrue(out["matches_selected_document"])
        self.assertFalse(out["document_mismatch"])
        self.assertFalse(out["identity_mismatch"])
        self.assertEqual(out["test_id"], "test-novo-novembro")
        self.assertEqual(out["gabarito_id"], "gab-da-prova")

    def test_gabarito_of_other_test_is_mismatch(self):
        with patch(
            "app.services.cartao_resposta.photo_identity._gabarito_test_id",
            return_value="outra-prova",
        ):
            out = resolve_identity_with_filter(
                expected_test_id="test-novo-novembro",
                detected={
                    "student_id": "stu-1",
                    "gabarito_id": "gab-outra",
                    "test_id": None,
                    "detected": True,
                },
            )
        self.assertFalse(out["matches_selected_document"])
        self.assertTrue(out["document_mismatch"])
        self.assertEqual(out["document_mismatch_reason"], "gabarito_other_test")


if __name__ == "__main__":
    unittest.main()
