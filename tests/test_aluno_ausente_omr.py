# -*- coding: utf-8 -*-
"""Leitura da bolinha 'Aluno ausente' sem alterar o grid de questões."""
import unittest

import cv2
import numpy as np

from app.services.cartao_resposta.correction_new_grid import AnswerSheetCorrectionNewGrid


class TestAlunoAusenteOmr(unittest.TestCase):
    def setUp(self):
        self.omr = AnswerSheetCorrectionNewGrid(debug=False)

    def test_question_bubble_constants_unchanged(self):
        self.assertEqual(self.omr.ROW_HEIGHT_PX, 51.97)
        self.assertEqual(self.omr.BUBBLE_RADIUS_PX, 25)
        self.assertEqual(self.omr.BUBBLE_SPACING_PX, 61)
        self.assertEqual(self.omr.BLOCK_OFFSET_X, 115)
        self.assertEqual(self.omr.BLOCK_OFFSET_Y, 40)
        self.assertEqual(self.omr.FILL_THRESHOLD, 0.45)

    def test_fill_ratio_filled_vs_empty(self):
        img = np.full((200, 200, 3), 255, dtype=np.uint8)
        cv2.circle(img, (60, 60), 28, (0, 0, 0), 2)
        cv2.circle(img, (140, 60), 28, (0, 0, 0), -1)
        empty = self.omr._circle_fill_ratio(img, 60, 60, 28)
        filled = self.omr._circle_fill_ratio(img, 140, 60, 28)
        self.assertLess(empty, self.omr.FILL_THRESHOLD)
        self.assertGreater(filled, self.omr.FILL_THRESHOLD)

    def _synthetic_a4(self, fill_first: bool):
        h, w = self.omr.A4_HEIGHT_PX, self.omr.A4_WIDTH_PX
        img = np.full((h, w, 3), 255, dtype=np.uint8)
        blocks = [{"x": 200, "y": 1800, "w": 400, "h": 1200}]
        band = self.omr._applicator_search_band(img, blocks)
        self.assertIsNotNone(band)
        cx, cy, r = self.omr._fallback_ausente_center(band)
        # Três bolinhas empilhadas (ausente, deficiência, tempo extra)
        gap = int(0.45 * self.omr.PX_PER_CM_A4)
        for i in range(3):
            y = cy + i * gap
            filled = fill_first and i == 0
            cv2.circle(img, (cx, y), r, (0, 0, 0), -1 if filled else 2)
        return img, blocks

    def test_detects_marked_absent_bubble(self):
        img, blocks = self._synthetic_a4(fill_first=True)
        info = self.omr._detect_aluno_ausente(img, blocks)
        self.assertTrue(info["marked"])
        self.assertGreater(info["fill_ratio"], self.omr.FILL_THRESHOLD)
        self.assertIn(info["method"], ("hough", "fallback"))

    def test_empty_absent_bubble_not_marked(self):
        img, blocks = self._synthetic_a4(fill_first=False)
        info = self.omr._detect_aluno_ausente(img, blocks)
        self.assertFalse(info["marked"])
        self.assertLess(info["fill_ratio"], self.omr.FILL_THRESHOLD)

    def test_cartao_em_branco_conta_como_ausente(self):
        correction = {
            "total_questions": 40,
            "blank_answers": 40,
            "invalid_answers": 0,
        }
        self.assertTrue(self.omr._cartao_sem_nenhuma_resposta(correction))

    def test_uma_questao_marcada_nao_e_ausente_por_branco(self):
        correction = {
            "total_questions": 40,
            "blank_answers": 39,
            "invalid_answers": 0,
        }
        self.assertFalse(self.omr._cartao_sem_nenhuma_resposta(correction))

    def test_invalid_conta_como_marcada(self):
        correction = {
            "total_questions": 40,
            "blank_answers": 39,
            "invalid_answers": 1,
        }
        self.assertFalse(self.omr._cartao_sem_nenhuma_resposta(correction))


if __name__ == "__main__":
    unittest.main()
