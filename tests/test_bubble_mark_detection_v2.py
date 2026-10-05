# -*- coding: utf-8 -*-
"""Testes da detecção de marcação OMR V2 (ink-agnostic + decisão relativa)."""
import unittest

import cv2
import numpy as np

from app.services.cartao_resposta.correction_new_grid import AnswerSheetCorrectionNewGrid


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

    def test_decide_winner_without_enough_margin_is_blank(self):
        scored = [
            {"letter": "A", "score": 30},
            {"letter": "B", "score": 20},
            {"letter": "C", "score": 10},
            {"letter": "D", "score": 10},
        ]
        # top>=floor, second<floor, margin=10 < 14 → None
        self.assertIsNone(self.omr._decide_question_mark_v2(scored))

    def test_ink_map_blue_darker_than_paper(self):
        """Caneta azul (BGR) deve gerar ink_strength > papel branco — sem regra de cor."""
        img = np.full((80, 80, 3), 240, dtype=np.uint8)  # papel
        # Bolha azul (B alto, R/G baixos) no centro
        cv2.circle(img, (40, 40), 12, (180, 40, 20), -1)
        ink = self.omr._build_ink_strength_map(img)
        center = float(np.mean(ink[35:45, 35:45]))
        corner = float(np.mean(ink[0:10, 0:10]))
        self.assertGreater(center, corner + 10)

    def test_ink_map_black_and_red_also_detected(self):
        img = np.full((80, 160, 3), 240, dtype=np.uint8)
        cv2.circle(img, (40, 40), 12, (20, 20, 20), -1)  # preto
        cv2.circle(img, (120, 40), 12, (20, 20, 200), -1)  # vermelho BGR
        ink = self.omr._build_ink_strength_map(img)
        black_s = float(np.mean(ink[35:45, 35:45]))
        red_s = float(np.mean(ink[35:45, 115:125]))
        paper_s = float(np.mean(ink[0:10, 70:80]))
        self.assertGreater(black_s, paper_s + 10)
        self.assertGreater(red_s, paper_s + 10)

    def test_v2_detects_blue_mark_legacy_may_miss(self):
        """Bloco sintético: uma bolha azul marcada; V2 deve marcar A."""
        # ROI claro com 4 círculos roxos vazios; A preenchida de azul
        h, w = 120, 280
        roi = np.full((h, w, 3), 245, dtype=np.uint8)
        centers = [(50, 60), (110, 60), (170, 60), (230, 60)]
        letters = ["A", "B", "C", "D"]
        r = 20
        for (cx, cy) in centers:
            cv2.circle(roi, (cx, cy), r, (200, 120, 180), 2)  # borda roxa
        # Marca azul em A
        cv2.circle(roi, centers[0], r - 3, (200, 60, 30), -1)

        bubbles = [
            {"q_num": 1, "alternative": let, "cx": cx, "cy": cy, "r": r}
            for let, (cx, cy) in zip(letters, centers)
        ]
        v2 = self.omr._detect_marked_bubbles_v2(roi, bubbles, block_id=1)
        self.assertEqual(v2.get(1), "A")

    def test_v2_empty_block_is_blank(self):
        h, w = 120, 280
        roi = np.full((h, w, 3), 245, dtype=np.uint8)
        centers = [(50, 60), (110, 60), (170, 60), (230, 60)]
        r = 20
        for (cx, cy) in centers:
            cv2.circle(roi, (cx, cy), r, (200, 120, 180), 2)
        bubbles = [
            {"q_num": 1, "alternative": let, "cx": cx, "cy": cy, "r": r}
            for let, (cx, cy) in zip(["A", "B", "C", "D"], centers)
        ]
        v2 = self.omr._detect_marked_bubbles_v2(roi, bubbles, block_id=1)
        self.assertIsNone(v2.get(1))

    def test_v2_double_mark_invalid(self):
        h, w = 120, 280
        roi = np.full((h, w, 3), 245, dtype=np.uint8)
        centers = [(50, 60), (110, 60), (170, 60), (230, 60)]
        r = 20
        for (cx, cy) in centers:
            cv2.circle(roi, (cx, cy), r, (200, 120, 180), 2)
        cv2.circle(roi, centers[0], r - 3, (30, 30, 30), -1)
        cv2.circle(roi, centers[1], r - 3, (30, 30, 30), -1)
        bubbles = [
            {"q_num": 1, "alternative": let, "cx": cx, "cy": cy, "r": r}
            for let, (cx, cy) in zip(["A", "B", "C", "D"], centers)
        ]
        v2 = self.omr._detect_marked_bubbles_v2(roi, bubbles, block_id=1)
        self.assertEqual(v2.get(1), "INVALID")


if __name__ == "__main__":
    unittest.main()
