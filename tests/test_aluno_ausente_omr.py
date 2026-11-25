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

    def _synthetic_a4(self, filled_index=None, dx: int = 0, dy: int = 0):
        """A4 com as três bolinhas do aplicador (ausente, deficiência, tempo)."""
        h, w = self.omr.A4_HEIGHT_PX, self.omr.A4_WIDTH_PX
        img = np.full((h, w, 3), 255, dtype=np.uint8)
        cx = self.omr.APPLICATOR_AUSENTE_CX_PX + dx
        cy = self.omr.APPLICATOR_AUSENTE_CY_PX + dy
        r = self.omr.APPLICATOR_AUSENTE_RADIUS_PX - 4
        pitch = int(round(self.omr.APPLICATOR_BUBBLE_PITCH_PX))
        for i in range(3):
            filled = filled_index == i
            cv2.circle(img, (cx, cy + i * pitch), r, (0, 0, 0), -1 if filled else 3)
        return img, [], (cx, cy, pitch)

    def test_detects_marked_absent_bubble(self):
        img, blocks, _ = self._synthetic_a4(filled_index=0)
        info = self.omr._detect_aluno_ausente(img, blocks)
        self.assertTrue(info["marked"])
        self.assertGreater(info["fill_ratio"], self.omr.FILL_THRESHOLD)

    def test_empty_absent_bubble_not_marked(self):
        img, blocks, (cx, cy, _p) = self._synthetic_a4()
        info = self.omr._detect_aluno_ausente(img, blocks)
        self.assertFalse(info["marked"])
        self.assertLess(info["fill_ratio"], self.omr.FILL_THRESHOLD)
        self.assertEqual(info["method"], "column")
        self.assertLessEqual(abs(info["cy"] - cy), 3)

    def test_deficiencia_marcada_nao_e_ausente(self):
        """Regressão 25/11: bolinha 2 ("deficiência") era lida como ausente."""
        img, blocks, _ = self._synthetic_a4(filled_index=1)
        info = self.omr._detect_aluno_ausente(img, blocks)
        self.assertFalse(info["marked"])

    def test_coluna_deslocada_ainda_le_bolinha_1(self):
        """Pequeno desvio de scan: segue a coluna, não a bolinha mais próxima."""
        img, blocks, (cx, cy, pitch) = self._synthetic_a4(filled_index=0, dx=10, dy=-30)
        info = self.omr._detect_aluno_ausente(img, blocks)
        self.assertTrue(info["marked"])
        self.assertLessEqual(abs(info["cy"] - cy), 3)

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

    def test_header_false_circle_is_not_aluno_ausente(self):
        """Faixa cinza do título + círculo escuro acima da coluna não contam."""
        img, blocks, (cx, cy, pitch) = self._synthetic_a4()
        cv2.rectangle(img, (cx - 60, cy - 100), (cx + 60, cy - 55), (60, 60, 60), -1)
        cv2.circle(img, (cx, cy - pitch), 24, (0, 0, 0), -1)
        info = self.omr._detect_aluno_ausente(img, blocks)
        self.assertFalse(info["marked"])
        self.assertLess(info["fill_ratio"], self.omr.FILL_THRESHOLD)
        self.assertLessEqual(abs(info["cy"] - cy), 3)


if __name__ == "__main__":
    unittest.main()
