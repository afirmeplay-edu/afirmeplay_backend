# -*- coding: utf-8 -*-
"""Testes do otimizador de imagens das páginas de questões (não OMR)."""
import base64
import io
import unittest

import numpy as np
from PIL import Image, ImageDraw

from app.utils import pdf_question_image_optimizer as opt
from app.utils.pdf_question_image_optimizer import (
    MAX_IMAGE_HEIGHT,
    MAX_IMAGE_WIDTH,
    ImageOptimizationStats,
    optimize_data_uri,
    optimize_html_data_uris,
    optimize_question_image,
)


def _jpeg_bytes(width: int, height: int, quality: int = 95, seed: int = 1) -> bytes:
    rng = np.random.default_rng(seed)
    arr = rng.integers(0, 256, size=(height, width, 3), dtype="uint8")
    img = Image.fromarray(arr, "RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


def _png_photo_bytes(width: int, height: int, seed: int = 2) -> bytes:
    rng = np.random.default_rng(seed)
    arr = rng.integers(0, 256, size=(height, width, 3), dtype="uint8")
    img = Image.fromarray(arr, "RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _png_diagram_bytes(width: int, height: int) -> bytes:
    img = Image.new("RGB", (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.rectangle([20, 20, width // 3, height // 3], fill=(0, 0, 220))
    draw.rectangle([width // 2, height // 2, width - 20, height - 20], fill=(220, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _png_transparent_bytes(width: int, height: int) -> bytes:
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([40, 40, width - 40, height - 40], fill=(30, 180, 80, 160))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _open(data: bytes) -> Image.Image:
    img = Image.open(io.BytesIO(data))
    img.load()
    return img


class TestPdfQuestionImageOptimizer(unittest.TestCase):
    def test_large_jpeg_is_downscaled_and_smaller(self):
        original = _jpeg_bytes(3600, 3000, quality=95)
        result = optimize_question_image(original, "image/jpeg")
        self.assertEqual(result.original_width, 3600)
        self.assertEqual(result.original_height, 3000)
        self.assertLessEqual(result.optimized_width, MAX_IMAGE_WIDTH)
        self.assertLessEqual(result.optimized_height, MAX_IMAGE_HEIGHT)
        self.assertLess(result.optimized_bytes, result.original_bytes)
        self.assertTrue(result.changed)
        out = _open(result.data)
        self.assertEqual(out.size, (result.optimized_width, result.optimized_height))

    def test_large_opaque_png_is_optimized(self):
        original = _png_photo_bytes(2000, 2000)
        result = optimize_question_image(original, "image/png")
        self.assertLessEqual(result.optimized_width, MAX_IMAGE_WIDTH)
        self.assertLessEqual(result.optimized_height, MAX_IMAGE_HEIGHT)
        self.assertLess(result.optimized_bytes, result.original_bytes)
        self.assertTrue(result.changed)

    def test_transparent_png_keeps_alpha(self):
        original = _png_transparent_bytes(1800, 1400)
        result = optimize_question_image(original, "image/png")
        self.assertEqual(result.mime, "image/png")
        out = _open(result.data)
        self.assertIn(out.mode, ("RGBA", "LA", "P", "PA"))
        if out.mode in ("RGBA", "LA"):
            self.assertLess(out.getchannel("A").getextrema()[0], 255)
        else:
            self.assertIn("transparency", out.info)
        self.assertLessEqual(result.optimized_width, MAX_IMAGE_WIDTH)
        self.assertLessEqual(result.optimized_height, MAX_IMAGE_HEIGHT)

    def test_diagram_png_stays_png(self):
        original = _png_diagram_bytes(2000, 1600)
        result = optimize_question_image(original, "image/png")
        self.assertEqual(result.mime, "image/png")
        self.assertLessEqual(result.optimized_width, MAX_IMAGE_WIDTH)

    def test_illustration_png_is_not_treated_as_photo(self):
        img = Image.new("RGB", (1800, 1400), (245, 248, 252))
        draw = ImageDraw.Draw(img)
        for i in range(24):
            color = (20 + i * 8, 70, 160)
            draw.rectangle([40 + i * 60, 40, 90 + i * 60, 400], fill=color)
            draw.ellipse([80, 500 + i * 20, 700, 620 + i * 20], outline=(30, 30, 30), width=2)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        result = optimize_question_image(buf.getvalue(), "image/png")
        self.assertEqual(result.mime, "image/png")

    def test_small_image_is_not_upscaled(self):
        original = _jpeg_bytes(240, 180, quality=70)
        result = optimize_question_image(original, "image/jpeg")
        self.assertEqual(result.optimized_width, 240)
        self.assertEqual(result.optimized_height, 180)
        self.assertLessEqual(result.optimized_width, result.original_width)

    def test_keep_original_when_optimized_would_be_larger(self):
        # PNG transparente minúsculo já com optimize=True: reencode não reduz.
        img = Image.new("RGBA", (32, 32), (255, 0, 0, 128))
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        original = buf.getvalue()
        result = optimize_question_image(original, "image/png")
        self.assertEqual(result.optimized_width, 32)
        self.assertEqual(result.optimized_height, 32)
        self.assertEqual(result.data, original)
        self.assertFalse(result.changed)

    def test_aspect_ratio_preserved(self):
        original = _jpeg_bytes(3600, 1800, quality=95)
        result = optimize_question_image(original, "image/jpeg")
        orig_ratio = 3600 / 1800
        opt_ratio = result.optimized_width / result.optimized_height
        self.assertLessEqual(result.optimized_width, MAX_IMAGE_WIDTH)
        self.assertLess(abs(orig_ratio - opt_ratio), 0.02)

    def test_twice_processing_is_stable(self):
        original = _jpeg_bytes(3600, 2800, quality=95)
        first = optimize_question_image(original, "image/jpeg")
        second = optimize_question_image(first.data, first.mime)
        self.assertEqual(second.data, first.data)
        self.assertEqual(second.optimized_width, first.optimized_width)
        self.assertEqual(second.optimized_height, first.optimized_height)

    def test_html_data_uri_rewrites_src_not_layout(self):
        raw = _jpeg_bytes(3000, 3000, quality=95)
        uri = f"data:image/jpeg;base64,{base64.b64encode(raw).decode('ascii')}"
        html = (
            f'<p>Questão</p><img class="keep-me" src="{uri}" alt="fig" />'
            '<img width="999" style="margin:12px auto" src="/not-a-data-uri.png" />'
        )
        out = optimize_html_data_uris(html)
        self.assertIn('class="keep-me"', out)
        self.assertIn('alt="fig"', out)
        self.assertIn('width="999"', out)
        self.assertIn('style="margin:12px auto"', out)
        self.assertIn("/not-a-data-uri.png", out)
        self.assertIn("data:image/", out)
        self.assertNotIn(uri, out)

    def test_same_image_reused_via_cache(self):
        raw = _jpeg_bytes(3000, 2000, quality=95)
        uri = f"data:image/jpeg;base64,{base64.b64encode(raw).decode('ascii')}"
        html = f'<img src="{uri}" /><img src="{uri}" />'
        cache = {}
        stats = ImageOptimizationStats()
        optimize_html_data_uris(html, cache=cache, stats=stats)
        self.assertEqual(stats.images, 1)
        self.assertEqual(len(cache), 1)

    def test_optimize_data_uri_invalid_keeps_input(self):
        self.assertEqual(optimize_data_uri("not-a-data-uri"), "not-a-data-uri")
        broken = "data:image/png;base64,@@@"
        self.assertEqual(optimize_data_uri(broken), broken)

    def test_questions_pdf_with_optimized_image_is_smaller(self):
        try:
            from weasyprint import HTML
        except ImportError:
            self.skipTest("weasyprint não disponível")
        raw = _jpeg_bytes(3600, 3000, quality=95)
        optimized = optimize_question_image(raw, "image/jpeg")

        def _pdf(data: bytes, mime: str) -> bytes:
            b64 = base64.b64encode(data).decode("ascii")
            html = (
                "<html><body>"
                f'<img src="data:{mime};base64,{b64}" style="max-width:100%;height:auto;" />'
                "</body></html>"
            )
            return HTML(string=html).write_pdf()

        pdf_before = _pdf(raw, "image/jpeg")
        pdf_after = _pdf(optimized.data, optimized.mime)
        self.assertLess(len(pdf_after), len(pdf_before))
        self.assertLess(len(pdf_after), int(len(pdf_before) * 0.7))

    def test_constants_are_print_quality(self):
        self.assertEqual(MAX_IMAGE_WIDTH, 2480)
        self.assertEqual(MAX_IMAGE_HEIGHT, 2480)
        self.assertEqual(opt.JPEG_QUALITY, 90)


if __name__ == "__main__":
    unittest.main()
