# -*- coding: utf-8 -*-
"""Testes unitários do encode/decode do ID-Grid OMR (6 hex / checksum)."""
import unittest

from app.services.cartao_resposta.identity_grid import (
    BUBBLE_DIAMETER_MM_MIN,
    BUBBLE_PITCH_MM_MAX,
    BUBBLE_PITCH_MM_MIN,
    KIND_GABARITO,
    KIND_PHYSICAL,
    MARKER_BUBBLE_CLEARANCE_MM,
    N_BUBBLES,
    PT_PER_CM,
    bits_to_nibble,
    checksum_nibble,
    code_to_column_bits,
    code_to_flat_bits,
    decode,
    decode_legacy_12,
    decode_token,
    encode,
    _grid_geometry_pt,
    nibble_bits,
    uuid_hex_prefix,
)


class TestIdentityGridEncodeDecode(unittest.TestCase):
    def test_roundtrip_gabarito(self):
        doc = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        student = "f0e1d2c3-b4a5-9687-6543-210fedcba987"
        code = encode(KIND_GABARITO, doc, student)
        self.assertEqual(len(code), 6)
        self.assertEqual(code, code.upper())
        decoded = decode(code)
        self.assertIsNotNone(decoded)
        self.assertEqual(decoded["kind"], KIND_GABARITO)
        self.assertEqual(decoded["document_prefix"], uuid_hex_prefix(doc, 2))
        self.assertEqual(decoded["student_prefix"], uuid_hex_prefix(student, 2))
        self.assertEqual(decoded["raw"], code)

    def test_roundtrip_physical(self):
        code = encode(
            KIND_PHYSICAL,
            "01234567-89ab-cdef-0123-456789abcdef",
            "fedcba98-7654-3210-fedc-ba9876543210",
        )
        self.assertEqual(code[0], KIND_PHYSICAL)
        self.assertEqual(len(code), 6)
        self.assertEqual(decode(code)["raw"], code)

    def test_nibble_0_and_f(self):
        self.assertEqual(nibble_bits(0), [False, False, False, False])
        self.assertEqual(nibble_bits(0xF), [True, True, True, True])
        self.assertEqual(bits_to_nibble([False, False, False, False]), 0)
        self.assertEqual(bits_to_nibble([True, True, True, True]), 0xF)
        self.assertEqual(bits_to_nibble(nibble_bits(9)), 9)

    def test_checksum_detects_swapped_nibble(self):
        code = encode(
            KIND_GABARITO,
            "aabbccddeeff00112233445566778899",
            "11223344556677889900aabbccddeeff",
        )
        # Troca D e S (índices 1-2 vs 3-4) parcialmente: índices 2 e 3
        chars = list(code)
        self.assertNotEqual(chars[2], chars[3])
        chars[2], chars[3] = chars[3], chars[2]
        swapped = "".join(chars)
        self.assertIsNone(decode(swapped))
        self.assertNotEqual(
            checksum_nibble(swapped[:5]),
            int(swapped[5], 16),
        )

    def test_checksum_detects_single_bit_flip(self):
        code = encode(
            KIND_GABARITO,
            "deadbeef-0000-1111-2222-333344445555",
            "cafebabe-9999-8888-7777-666655554444",
        )
        chars = list(code)
        n = int(chars[2], 16) ^ 0x1
        chars[2] = f"{n:X}"
        flipped = "".join(chars)
        self.assertIsNone(decode(flipped))

    def test_code_to_column_and_flat_bits(self):
        code = encode(
            KIND_PHYSICAL,
            "12345678-90ab-cdef-1234-567890abcdef",
            "abcdef01-2345-6789-abcd-ef0123456789",
        )
        cols = code_to_column_bits(code)
        self.assertEqual(len(cols), 6)
        rebuilt = "".join(f"{bits_to_nibble(b):X}" for b in cols)
        self.assertEqual(rebuilt, code)
        flat = code_to_flat_bits(code)
        self.assertEqual(len(flat), 24)
        rebuilt2 = "".join(
            f"{bits_to_nibble(flat[i : i + 4]):X}" for i in range(0, 24, 4)
        )
        self.assertEqual(rebuilt2, code)

    def test_decode_rejects_short_and_bad_hex(self):
        self.assertIsNone(decode("123"))
        self.assertIsNone(decode("GGGGGG"))
        self.assertIsNone(decode(""))
        self.assertIsNone(decode(None))
        # 12 hex legado não passa no decode novo
        self.assertIsNone(decode("1A1B2CF0E1D6"))

    def test_decode_legacy_12_still_works(self):
        # Monta manualmente payload legado válido
        payload11 = "1A1B2CF0E1D"
        c = checksum_nibble(payload11)
        raw = f"{payload11}{c:X}"
        decoded = decode_legacy_12(raw)
        self.assertIsNotNone(decoded)
        self.assertEqual(decoded["document_prefix"], "A1B2C")
        self.assertEqual(decoded["student_prefix"], "F0E1D")

    def test_geometry_clears_markers_and_caps_pitch(self):
        """Bolhas não invadem marcadores; passo limitado (faixa compacta)."""
        geo = _grid_geometry_pt()
        self.assertEqual(len(geo["centers_x"]), N_BUBBLES)
        pitch_mm = geo["pitch"] / PT_PER_CM * 10.0
        diam_mm = geo["diameter"] / PT_PER_CM * 10.0
        self.assertGreaterEqual(pitch_mm, BUBBLE_PITCH_MM_MIN - 1e-6)
        self.assertLessEqual(pitch_mm, BUBBLE_PITCH_MM_MAX + 1e-6)
        self.assertGreaterEqual(diam_mm, BUBBLE_DIAMETER_MM_MIN - 1e-6)

        r = geo["radius"]
        lm, rm = geo["left_marker"], geo["right_marker"]
        lm_right = lm["x"] + lm["size"] / 2.0
        rm_left = rm["x"] - rm["size"] / 2.0
        bubble_left = geo["centers_x"][0] - r
        bubble_right = geo["centers_x"][-1] + r
        clear_pt = MARKER_BUBBLE_CLEARANCE_MM * PT_PER_CM / 10.0
        self.assertGreaterEqual(bubble_left - lm_right, clear_pt - 0.05)
        self.assertGreaterEqual(rm_left - bubble_right, clear_pt - 0.05)


class TestIdGridScoreThreshold(unittest.TestCase):
    """Limiar do ID-Grid: gap dominante vs baseline elevada (pós-warp)."""

    def test_gap_threshold_ignores_elevated_empty_baseline(self):
        import numpy as np
        from app.services.cartao_resposta.correction_new_grid import (
            AnswerSheetCorrectionNewGrid,
        )

        # Perfil típico pós-warp: vazias ~40–64, preenchidas ~235–255.
        # Otsu puro cortava ~63 e marcava FP no checksum (1DAF0D vs 1DAF05).
        empties = [57.7, 52.1, 55.1, 60.6, 44.6, 37.9, 56.1, 58.7, 61.2, 61.6, 63.9, 52.5]
        filled = [249.8, 248.9, 251.3, 254.4, 255.0, 255.0, 255.0, 255.0, 255.0, 255.0, 243.5, 234.9]
        scores = np.asarray(empties + filled, dtype=np.float64)
        omr = AnswerSheetCorrectionNewGrid(debug=False)
        thr = omr._otsu_threshold_scores(scores)
        self.assertIsNotNone(thr)
        self.assertGreater(thr, 70.0)
        self.assertLess(thr, 220.0)
        n_on = int((scores >= thr).sum())
        self.assertEqual(n_on, len(filled))


class TestDecodeToken(unittest.TestCase):
    def test_decode_token_accepts_opaque_payload(self):
        payload5 = "A9F30"
        code = f"{payload5}{checksum_nibble(payload5):X}"
        got = decode_token(code)
        self.assertIsNotNone(got)
        self.assertEqual(got["raw"], code)
        self.assertEqual(got["token"], payload5)
        # Prefix legado exige kind 1/2 — token opaco tipicamente falha
        if code[0] not in (KIND_GABARITO, KIND_PHYSICAL):
            self.assertIsNone(decode(code))

    def test_decode_token_rejects_bad_checksum(self):
        self.assertIsNone(decode_token("A9F306"))  # checksum correto seria 5


class TestAllocateCodeIdempotent(unittest.TestCase):
    def test_allocate_reuses_same_pair(self):
        from unittest.mock import MagicMock, patch
        from app.services.cartao_resposta import identity_code_service as svc

        existing = MagicMock()
        existing.code = "BEEF15"
        q = MagicMock()
        q.filter_by.return_value.first.return_value = existing

        with patch.object(svc, "AnswerSheetIdentityCode") as model:
            model.query = q
            code = svc.allocate_code(
                KIND_GABARITO,
                "f053ea39-0d1a-4d9f-b256-027499399221",
                gabarito_id="dabe8fe9-1fd8-4d0a-90ab-8cb5d7af3e99",
            )
        self.assertEqual(code, "BEEF15")
        q.filter_by.assert_called()


if __name__ == "__main__":
    unittest.main()
