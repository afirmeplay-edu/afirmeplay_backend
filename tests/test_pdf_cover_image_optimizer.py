# -*- coding: utf-8 -*-
"""Otimização de timbrado/capa — isolada do OMR."""
import base64
import io
import unittest

from PIL import Image, ImageDraw

from app.exams.services.institutional_test_weasyprint_generator import (
    InstitutionalTestWeasyPrintGenerator,
)
from app.utils.pdf_question_image_optimizer import (
    COVER_JPEG_QUALITY,
    LETTERHEAD_MAX_HEIGHT,
    LETTERHEAD_MAX_WIDTH,
    LOGO_MAX_EDGE,
    ImageOptimizationStats,
    optimize_base64_asset,
    optimize_cover_photo,
    optimize_letterhead_image,
    optimize_logo_image,
)


def _png_bytes(width: int, height: int, color=(255, 255, 255), extra=None) -> bytes:
    img = Image.new("RGB", (width, height), color)
    draw = ImageDraw.Draw(img)
    draw.rectangle([2, 2, max(4, width // 4), max(4, height // 8)], fill=(20, 40, 120))
    if extra:
        extra(draw, width, height)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _png_transparent_a4() -> bytes:
    img = Image.new("RGBA", (2480, 3508), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rectangle([80, 80, 900, 400], fill=(20, 60, 140, 200))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _jpeg_cover(width: int, height: int) -> bytes:
    import numpy as np

    rng = np.random.default_rng(3)
    arr = rng.integers(0, 256, size=(height, width, 3), dtype="uint8")
    img = Image.fromarray(arr, "RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    return buf.getvalue()


class TestPdfCoverImageOptimizer(unittest.TestCase):
    def test_letterhead_a4_300dpi_is_not_downscaled(self):
        original = _png_bytes(2480, 3508)
        result = optimize_letterhead_image(original, "image/png")
        self.assertEqual(result.mime, "image/png")
        self.assertEqual(result.optimized_width, 2480)
        self.assertEqual(result.optimized_height, 3508)

    def test_letterhead_above_300dpi_is_downscaled_and_stays_png(self):
        original = _png_bytes(3508, 4961)
        result = optimize_letterhead_image(original, "image/png")
        self.assertEqual(result.mime, "image/png")
        self.assertLessEqual(result.optimized_width, LETTERHEAD_MAX_WIDTH)
        self.assertLessEqual(result.optimized_height, LETTERHEAD_MAX_HEIGHT)
        self.assertLess(result.optimized_bytes, result.original_bytes)
        ratio = 3508 / 4961
        self.assertLess(abs(result.optimized_width / result.optimized_height - ratio), 0.02)

    def test_transparent_letterhead_keeps_alpha(self):
        original = _png_transparent_a4()
        result = optimize_letterhead_image(original, "image/png")
        self.assertEqual(result.mime, "image/png")
        out = Image.open(io.BytesIO(result.data))
        self.assertIn(out.mode, ("RGBA", "LA", "P", "PA"))
        if out.mode in ("RGBA", "LA"):
            self.assertLess(out.getchannel("A").getextrema()[0], 255)

    def test_cover_photo_above_300dpi_is_downscaled(self):
        original = _jpeg_cover(3508, 4961)
        result = optimize_cover_photo(original, "image/jpeg")
        self.assertLessEqual(result.optimized_width, LETTERHEAD_MAX_WIDTH)
        self.assertLessEqual(result.optimized_height, LETTERHEAD_MAX_HEIGHT)
        self.assertLess(result.optimized_bytes, result.original_bytes)

    def test_logo_is_capped_and_stays_png(self):
        original = _png_bytes(4000, 1600, color=(255, 255, 255))
        result = optimize_logo_image(original, "image/png")
        self.assertEqual(result.mime, "image/png")
        self.assertLessEqual(max(result.optimized_width, result.optimized_height), LOGO_MAX_EDGE)

    def test_small_logo_not_upscaled(self):
        original = _png_bytes(120, 80)
        result = optimize_logo_image(original, "image/png")
        self.assertEqual(result.optimized_width, 120)
        self.assertEqual(result.optimized_height, 80)

    def test_optimize_base64_roundtrip(self):
        raw = _png_bytes(3508, 4961)
        b64 = base64.b64encode(raw).decode("ascii")
        stats = ImageOptimizationStats()
        out_b64, mime = optimize_base64_asset(b64, "image/png", optimize_letterhead_image, stats=stats)
        self.assertEqual(mime, "image/png")
        self.assertLess(len(out_b64), len(b64))
        self.assertEqual(stats.images, 1)

    def test_print_branding_copy_does_not_mutate_original(self):
        raw = _png_bytes(3508, 4961)
        original_b64 = base64.b64encode(raw).decode("ascii")
        test_data = {
            "title": "Prova",
            "letterhead_image_base64": original_b64,
            "municipality_logo": original_b64,
        }
        gen = InstitutionalTestWeasyPrintGenerator()
        stats = ImageOptimizationStats()
        copied = gen._optimize_print_branding_copy(test_data, stats)
        self.assertEqual(test_data["letterhead_image_base64"], original_b64)
        self.assertEqual(test_data["municipality_logo"], original_b64)
        self.assertNotEqual(copied["letterhead_image_base64"], original_b64)
        self.assertLess(len(copied["letterhead_image_base64"]), len(original_b64))
        self.assertIsNot(copied, test_data)

    def test_omr_html_keeps_original_letterhead_when_print_copy_exists(self):
        raw = _png_bytes(3508, 4961)
        original_b64 = base64.b64encode(raw).decode("ascii")
        test_data = {"title": "Prova OMR", "state": "ALAGOAS", "letterhead_image_base64": original_b64}
        gen = InstitutionalTestWeasyPrintGenerator()
        copied = gen._optimize_print_branding_copy(test_data, ImageOptimizationStats())

        omr_data = {
            "test_data": test_data,
            "student": {
                "name": "",
                "school_name": "",
                "class_name": "",
                "qr_code": gen._get_omr_placeholder_qr_base64(),
            },
            "questions_by_subject": {},
            "questions_by_block": None,
            "blocks_config": {},
            "questions_map": {1: ["A", "B", "C", "D"]},
            "answer_sheet_image": "",
            "total_questions": 1,
            "generated_date": "01/01/2026 00:00",
            "default_logo": None,
            "include_cover": False,
            "include_questions": False,
            "include_answer_sheet": True,
        }
        html_omr = gen._render_template("institutional_test_hybrid.html", omr_data)
        self.assertIn(original_b64, html_omr)
        self.assertNotIn(copied["letterhead_image_base64"], html_omr)
        self.assertIn("answer-sheet", html_omr)

        omr_data_if_mutated = dict(omr_data)
        omr_data_if_mutated["test_data"] = copied
        html_if_print = gen._render_template("institutional_test_hybrid.html", omr_data_if_mutated)
        self.assertNotEqual(html_omr, html_if_print)

    def test_omr_pdf_geometry_unchanged_after_print_copy(self):
        try:
            from weasyprint import HTML  # noqa: F401
        except ImportError:
            self.skipTest("weasyprint não disponível")

        from pypdf import PdfReader

        raw = _png_bytes(2480, 3508)
        original_b64 = base64.b64encode(raw).decode("ascii")
        test_data = {"title": "Prova OMR", "state": "ALAGOAS", "letterhead_image_base64": original_b64}
        gen = InstitutionalTestWeasyPrintGenerator()

        def _omr_pdf(data):
            payload = {
                "test_data": data,
                "student": {
                    "name": "",
                    "school_name": "",
                    "class_name": "",
                    "qr_code": gen._get_omr_placeholder_qr_base64(),
                },
                "questions_by_subject": {},
                "questions_by_block": None,
                "blocks_config": {},
                "questions_map": {1: ["A", "B", "C", "D"]},
                "answer_sheet_image": "",
                "total_questions": 1,
                "generated_date": "01/01/2026 00:00",
                "default_logo": None,
                "include_cover": False,
                "include_questions": False,
                "include_answer_sheet": True,
            }
            return gen._html_to_pdf_bytes(
                gen._render_template("institutional_test_hybrid.html", payload)
            )

        pdf_before = _omr_pdf(test_data)
        gen._optimize_print_branding_copy(test_data, ImageOptimizationStats())
        pdf_after = _omr_pdf(test_data)

        before = PdfReader(io.BytesIO(pdf_before)).pages[0]
        after = PdfReader(io.BytesIO(pdf_after)).pages[0]
        self.assertEqual([float(x) for x in before.mediabox], [float(x) for x in after.mediabox])
        self.assertEqual([float(x) for x in before.cropbox], [float(x) for x in after.cropbox])
        self.assertEqual(int(before.get("/Rotate", 0) or 0), 0)
        width = float(after.mediabox[2]) - float(after.mediabox[0])
        height = float(after.mediabox[3]) - float(after.mediabox[1])
        self.assertLess(abs(width - 595.27), 1.0)
        self.assertLess(abs(height - 841.89), 1.0)
        self.assertEqual(pdf_before, pdf_after)

    def test_cover_constants(self):
        self.assertEqual(LETTERHEAD_MAX_WIDTH, 2480)
        self.assertEqual(LETTERHEAD_MAX_HEIGHT, 3508)
        self.assertEqual(COVER_JPEG_QUALITY, 90)
        self.assertEqual(LOGO_MAX_EDGE, 2480)


if __name__ == "__main__":
    unittest.main()
