# -*- coding: utf-8 -*-
"""Layout e quebra de linha do nome do aluno na capa Afirme."""
import unittest

from app.utils.afirme_cover_layout import (
    load_afirme_cover_layout,
    student_name_overlay_lines,
    student_overlay_coords_pt,
)


class TestAfirmeCoverStudentName(unittest.TestCase):
    def test_student_left_shifted_10px(self):
        layout = load_afirme_cover_layout()
        self.assertAlmostEqual(layout["student"]["left_cm"], 4.04, places=2)
        x_pt, _, _ = student_overlay_coords_pt(layout)
        self.assertAlmostEqual(x_pt, 4.04 * (72.0 / 2.54), places=2)

    def test_short_name_single_line(self):
        layout = load_afirme_cover_layout()
        lines = student_name_overlay_lines("Ana Silva", layout)
        self.assertEqual(lines, ["ANA SILVA"])

    def test_long_name_wraps_instead_of_hard_truncate(self):
        layout = load_afirme_cover_layout()
        # Nome longo o bastante para ultrapassar width_cm a 9pt Helvetica-Bold
        name = (
            "Maria Eduarda dos Santos Oliveira Ferreira da Conceicao "
            "Albuquerque Rodrigues Pereira de Souza"
        )
        lines = student_name_overlay_lines(name, layout)
        self.assertGreaterEqual(len(lines), 2)
        joined = " ".join(lines)
        self.assertIn("MARIA", joined)
        # Antiga lógica truncava em 55 chars; wrap deve preservar além disso
        preserved = joined.replace("…", "")
        self.assertGreater(len(preserved), 55)
        self.assertTrue(
            any("OLIVEIRA" in line or "FERREIRA" in line for line in lines)
        )


if __name__ == "__main__":
    unittest.main()
