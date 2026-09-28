# -*- coding: utf-8 -*-
"""Testes do dimensionamento visual de imagens das questões (layout cm)."""
import base64
import io
import re
import unittest

from PIL import Image

from app.utils import pdf_question_image_layout as layout
from app.utils.pdf_question_image_layout import (
    HMAX_SINGLE_CM,
    WMAX_CM,
    apply_multi_image_budget,
    compute_scale,
    fit_images_in_html_fragments,
    fit_question_dict_images,
    fit_single_image_cm,
    multi_image_budget_cap_cm,
    px_to_cm,
)


def _png_data_uri(width: int, height: int) -> str:
    img = Image.new("RGB", (width, height), (40, 120, 200))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"


def _img_tag(width: int, height: int, css_class: str = "") -> str:
    src = _png_data_uri(width, height)
    cls = f' class="{css_class}"' if css_class else ""
    return f'<img{cls} src="{src}" />'


def _parse_cm_size(html: str):
    m = re.search(
        r'style="[^"]*width:\s*([0-9.]+)cm;\s*height:\s*([0-9.]+)cm',
        html,
    )
    if not m:
        return None
    return float(m.group(1)), float(m.group(2))


class TestScaleMath(unittest.TestCase):
    def test_horizontal_limited_by_width(self):
        # ~20 cm × 5 cm @ 96dpi → width limited
        w_px = int(20 * 96 / 2.54)
        h_px = int(5 * 96 / 2.54)
        fitted = fit_single_image_cm(w_px, h_px)
        self.assertLessEqual(fitted.width_cm, WMAX_CM + 1e-6)
        self.assertAlmostEqual(
            fitted.width_cm / fitted.height_cm,
            fitted.natural_width_cm / fitted.natural_height_cm,
            places=4,
        )
        self.assertLess(fitted.scale, 1.0)

    def test_vertical_limited_by_height(self):
        w_px = int(5 * 96 / 2.54)
        h_px = int(20 * 96 / 2.54)
        fitted = fit_single_image_cm(w_px, h_px)
        self.assertLessEqual(fitted.height_cm, HMAX_SINGLE_CM + 1e-6)
        self.assertAlmostEqual(
            fitted.width_cm / fitted.height_cm,
            fitted.natural_width_cm / fitted.natural_height_cm,
            places=4,
        )

    def test_square_near_10cm(self):
        w_px = int(25 * 96 / 2.54)
        h_px = w_px
        fitted = fit_single_image_cm(w_px, h_px)
        self.assertLessEqual(fitted.width_cm, WMAX_CM + 1e-6)
        self.assertLessEqual(fitted.height_cm, HMAX_SINGLE_CM + 1e-6)
        self.assertAlmostEqual(fitted.width_cm, fitted.height_cm, places=3)

    def test_small_image_not_upscaled(self):
        # ~2 cm square — S must be 1
        w_px = int(2 * 96 / 2.54)
        h_px = w_px
        fitted = fit_single_image_cm(w_px, h_px)
        self.assertAlmostEqual(fitted.scale, 1.0, places=5)
        self.assertAlmostEqual(fitted.width_cm, px_to_cm(w_px), places=4)

    def test_compute_scale_formula(self):
        s = compute_scale(33.0, 10.0, WMAX_CM, HMAX_SINGLE_CM)
        self.assertAlmostEqual(s, WMAX_CM / 33.0, places=6)


class TestMultiImageBudget(unittest.TestCase):
    def test_budget_reduces_sum_of_heights(self):
        # Two tall-ish fitted sizes whose heights sum above budget
        a = fit_single_image_cm(800, 1200)  # vertical
        b = fit_single_image_cm(800, 1200)
        budget = multi_image_budget_cap_cm()
        total_before = a.height_cm + b.height_cm
        self.assertGreater(total_before, budget)

        out = apply_multi_image_budget([a, b], budget)
        total_after = out[0].height_cm + out[1].height_cm
        self.assertLessEqual(total_after, budget + 1e-6)
        # Proportions preserved per image
        for src, dst in zip([a, b], out):
            self.assertAlmostEqual(
                dst.width_cm / dst.height_cm,
                src.natural_width_cm / src.natural_height_cm,
                places=4,
            )

    def test_single_image_skips_budget(self):
        a = fit_single_image_cm(800, 1200)
        out = apply_multi_image_budget([a], 3.0)
        self.assertEqual(len(out), 1)
        self.assertAlmostEqual(out[0].height_cm, a.height_cm, places=5)


class TestHtmlFit(unittest.TestCase):
    def test_writes_cm_style_and_skips_math(self):
        content = (
            f"<p>Texto</p>{_img_tag(1200, 400)}"
            f'{_img_tag(40, 40, "math-inline-img")}'
        )
        out = fit_images_in_html_fragments([content], h_available_cm=12.0)[0]
        self.assertIn("width:", out)
        self.assertIn("height:", out)
        self.assertIn("question-fit-img", out)
        # Math tag must not get question-fit-img from content fit on that tag alone
        math_part = re.search(
            r'<img[^>]*class="[^"]*math-inline-img[^"]*"[^>]*>',
            out,
        )
        self.assertIsNotNone(math_part)
        self.assertNotIn("question-fit-img", math_part.group(0))
        size = _parse_cm_size(out)
        self.assertIsNotNone(size)
        w, h = size
        self.assertLessEqual(w, WMAX_CM + 0.05)
        self.assertLessEqual(h, HMAX_SINGLE_CM + 0.05)

    def test_question_dict_shared_budget(self):
        q = {
            "content": f"<p>Enunciado curto.</p>{_img_tag(900, 1400)}",
            "prompt": f"<p>Comando</p>{_img_tag(900, 1400)}",
            "alternatives": [
                {"letter": "A", "content": "Alt A"},
                {"letter": "B", "content": "Alt B"},
            ],
        }
        fit_question_dict_images(q)
        sizes = []
        for html in (str(q["content"]), str(q["prompt"])):
            size = _parse_cm_size(html)
            self.assertIsNotNone(size)
            sizes.append(size)
        total_h = sizes[0][1] + sizes[1][1]
        self.assertLessEqual(total_h, multi_image_budget_cap_cm() + 0.05)


if __name__ == "__main__":
    unittest.main()
