# -*- coding: utf-8 -*-
"""Testes da detecção de marcação OMR V2 (multi-feature + decisão adaptativa)."""
import unittest

import cv2
import numpy as np

from app.services.cartao_resposta.correction_new_grid import AnswerSheetCorrectionNewGrid


def _blank_roi(h=120, w=280, r=20):
    roi = np.full((h, w, 3), 245, dtype=np.uint8)
    centers = [(50, 60), (110, 60), (170, 60), (230, 60)]
    for (cx, cy) in centers:
        cv2.circle(roi, (cx, cy), r, (200, 120, 180), 2)
    return roi, centers, r


def _bubbles(centers, r, q_num=1):
    return [
        {"q_num": q_num, "alternative": let, "cx": cx, "cy": cy, "r": r}
        for let, (cx, cy) in zip(["A", "B", "C", "D"], centers)
    ]


class TestBubbleMarkDetectionV2(unittest.TestCase):
    def setUp(self):
        self.omr = AnswerSheetCorrectionNewGrid(debug=False)

    def test_fill_threshold_legado_inalterado(self):
        self.assertEqual(self.omr.FILL_THRESHOLD, 0.45)

    def test_v2_enabled_by_default(self):
        self.assertTrue(self.omr.USE_BUBBLE_DETECTION_V2)

    def test_decide_clear_winner(self):
        scored = [
            {"letter": "A", "score": 5},
            {"letter": "B", "score": 7},
            {"letter": "C", "score": 62},
            {"letter": "D", "score": 6},
        ]
        self.assertEqual(self.omr._decide_question_mark_v2(scored), "C")
        _d, meta = self.omr._decide_question_mark_v2_with_meta(scored)
        self.assertEqual(meta["confidence"], "high")

    def test_decide_all_low_is_blank(self):
        scored = [
            {"letter": "A", "score": 5},
            {"letter": "B", "score": 7},
            {"letter": "C", "score": 6},
            {"letter": "D", "score": 5},
        ]
        self.assertIsNone(self.omr._decide_question_mark_v2(scored))

    def test_decide_ambiguous_mid_is_blank(self):
        scored = [
            {"letter": "A", "score": 31},
            {"letter": "B", "score": 33},
            {"letter": "C", "score": 35},
            {"letter": "D", "score": 32},
        ]
        self.assertIsNone(self.omr._decide_question_mark_v2(scored))

    def test_decide_two_strong_is_invalid(self):
        scored = [
            {"letter": "A", "score": 61},
            {"letter": "B", "score": 57},
            {"letter": "C", "score": 8},
            {"letter": "D", "score": 7},
        ]
        self.assertEqual(self.omr._decide_question_mark_v2(scored), "INVALID")

    def test_decide_partial_with_margin(self):
        scored = [
            {"letter": "A", "score": 12},
            {"letter": "B", "score": 9},
            {"letter": "C", "score": 45},
            {"letter": "D", "score": 10},
        ]
        self.assertEqual(self.omr._decide_question_mark_v2(scored), "C")

    def test_decide_medium_confidence_weak_but_dominant(self):
        """Marca fraca acima de floor_lo com margem/evidência relativa → aceita medium."""
        scored = [
            {"letter": "A", "score": 24},
            {"letter": "B", "score": 12},
            {"letter": "C", "score": 11},
            {"letter": "D", "score": 10},
        ]
        decision, meta = self.omr._decide_question_mark_v2_with_meta(scored)
        self.assertEqual(decision, "A")
        self.assertEqual(meta["confidence"], "medium")

    def test_decide_high_score_small_margin_still_medium_if_relative_ok(self):
        """top=30 second=20: antes era None (margin<14); agora medium se evidência relativa ok."""
        scored = [
            {"letter": "A", "score": 30},
            {"letter": "B", "score": 20},
            {"letter": "C", "score": 10},
            {"letter": "D", "score": 10},
        ]
        decision, meta = self.omr._decide_question_mark_v2_with_meta(scored)
        self.assertEqual(decision, "A")
        self.assertIn(meta["confidence"], ("medium", "high"))

    def test_ink_map_blue_darker_than_paper(self):
        img = np.full((80, 80, 3), 240, dtype=np.uint8)
        cv2.circle(img, (40, 40), 12, (180, 40, 20), -1)
        ink = self.omr._build_ink_strength_map(img)
        center = float(np.mean(ink[35:45, 35:45]))
        corner = float(np.mean(ink[0:10, 0:10]))
        self.assertGreater(center, corner + 10)

    def test_ink_map_black_and_red_also_detected(self):
        img = np.full((80, 160, 3), 240, dtype=np.uint8)
        cv2.circle(img, (40, 40), 12, (20, 20, 20), -1)
        cv2.circle(img, (120, 40), 12, (20, 20, 200), -1)
        ink = self.omr._build_ink_strength_map(img)
        black_s = float(np.mean(ink[35:45, 35:45]))
        red_s = float(np.mean(ink[35:45, 115:125]))
        paper_s = float(np.mean(ink[0:10, 70:80]))
        self.assertGreater(black_s, paper_s + 10)
        self.assertGreater(red_s, paper_s + 10)

    def test_v2_detects_blue_mark(self):
        roi, centers, r = _blank_roi()
        cv2.circle(roi, centers[0], r - 3, (200, 60, 30), -1)
        v2 = self.omr._detect_marked_bubbles_v2(roi, _bubbles(centers, r), block_id=1)
        self.assertEqual(v2.get(1), "A")

    def test_v2_empty_block_is_blank(self):
        roi, centers, r = _blank_roi()
        v2 = self.omr._detect_marked_bubbles_v2(roi, _bubbles(centers, r), block_id=1)
        self.assertIsNone(v2.get(1))

    def test_v2_double_mark_invalid(self):
        roi, centers, r = _blank_roi()
        cv2.circle(roi, centers[0], r - 3, (30, 30, 30), -1)
        cv2.circle(roi, centers[1], r - 3, (30, 30, 30), -1)
        v2 = self.omr._detect_marked_bubbles_v2(roi, _bubbles(centers, r), block_id=1)
        self.assertEqual(v2.get(1), "INVALID")

    def test_v2_light_graphite_detected(self):
        """Grafite claro (gray~140) que falhava no floor=28 médio-only."""
        roi, centers, r = _blank_roi()
        cv2.circle(roi, centers[2], r - 3, (140, 140, 140), -1)
        v2 = self.omr._detect_marked_bubbles_v2(roi, _bubbles(centers, r), block_id=1)
        self.assertEqual(v2.get(1), "C")
        self.assertIn(self.omr.last_bubble_diagnostics[1]["confidence"], ("medium", "high"))

    def test_v2_sparse_scribble_or_ring_inside_disk(self):
        roi, centers, r = _blank_roi()
        cx, cy = centers[1]
        # anel interno (dentro do disco de análise 0.78*r)
        cv2.circle(roi, (cx, cy), max(6, r - 8), (50, 50, 50), 3)
        v2 = self.omr._detect_marked_bubbles_v2(roi, _bubbles(centers, r), block_id=1)
        self.assertEqual(v2.get(1), "B")

    def test_v2_center_scribble_lines_detected(self):
        roi, centers, r = _blank_roi()
        cx, cy = centers[0]
        for i in range(-8, 9, 4):
            cv2.line(roi, (cx - 10, cy + i), (cx + 10, cy + i), (90, 90, 90), 1)
        v2 = self.omr._detect_marked_bubbles_v2(roi, _bubbles(centers, r), block_id=1)
        self.assertEqual(v2.get(1), "A")

    def test_v2_diagnostics_cover_high_question_numbers(self):
        """Debug/diagnóstico não fica limitado a q_num<=13."""
        roi, centers, r = _blank_roi()
        cv2.circle(roi, centers[0], r - 3, (25, 25, 25), -1)
        bubbles = _bubbles(centers, r, q_num=28)
        v2 = self.omr._detect_marked_bubbles_v2(roi, bubbles, block_id=3)
        self.assertEqual(v2.get(28), "A")
        self.assertIn(28, self.omr.last_bubble_diagnostics)
        diag = self.omr.last_bubble_diagnostics[28]
        self.assertIn("A", diag["alternatives"])
        self.assertIn("density", diag["alternatives"]["A"])
        self.assertIn("reason", diag)

    def test_v2_shadow_noise_empty_stays_blank(self):
        """Sombra/ruído sem marcação dominante não vira resposta."""
        np.random.seed(1)
        roi, centers, r = _blank_roi()
        noise = np.random.normal(0, 10, roi.shape)
        roi = np.clip(roi.astype(np.float32) + noise, 0, 255).astype(np.uint8)
        for cx, cy in centers:
            cv2.circle(roi, (cx, cy), r, (200, 120, 180), 2)
        v2 = self.omr._detect_marked_bubbles_v2(roi, _bubbles(centers, r), block_id=1)
        self.assertIsNone(v2.get(1))


if __name__ == "__main__":
    unittest.main()
