# -*- coding: utf-8 -*-
"""Composição: capa original (PDF) + overlay ReportLab + merge pypdf."""
from __future__ import annotations

import io
import logging
from typing import Any, Dict, List, Optional, Union

from pypdf import PdfReader, PdfWriter
from reportlab.lib.colors import HexColor, black
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen.canvas import Canvas

from app.services.cover_templates.constants import ALLOWED_FONTS
from app.services.cover_templates.coordinates import canonicalize_field_box
from app.services.cover_templates.field_catalog import resolve_field_value

logger = logging.getLogger(__name__)


def _parse_color(value: Any):
    if not value:
        return HexColor("#1a1a1a")
    text = str(value).strip()
    if not text.startswith("#"):
        text = f"#{text}"
    try:
        return HexColor(text)
    except Exception:
        return black


def _fit_text(
    text: str,
    font_name: str,
    font_size: float,
    max_width: float,
    overflow: str,
    max_chars: Optional[int],
) -> List[str]:
    if max_chars and len(text) > max_chars:
        if overflow == "ellipsis":
            text = text[: max(1, max_chars - 1)] + "…"
        else:
            text = text[:max_chars]

    if overflow == "clip":
        while text and stringWidth(text, font_name, font_size) > max_width:
            text = text[:-1]
        return [text] if text else []

    if overflow != "wrap":
        if stringWidth(text, font_name, font_size) > max_width:
            while text and stringWidth(text + "…", font_name, font_size) > max_width:
                text = text[:-1]
            text = (text + "…") if text else ""
        return [text] if text else []

    words = text.split()
    if not words:
        return []
    lines: List[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if stringWidth(candidate, font_name, font_size) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _baseline_y(box_y: float, box_h: float, font_size: float, valign: str, line_count: int) -> float:
    block_h = font_size * 1.2 * max(line_count, 1)
    if valign == "top":
        return box_y + box_h - font_size
    if valign == "bottom":
        return box_y + font_size * 0.15 + (block_h - font_size)
    return box_y + (box_h - block_h) / 2.0 + (block_h - font_size)


def _draw_lines(
    canvas: Canvas,
    lines: List[str],
    x: float,
    y_top_baseline: float,
    width: float,
    font_name: str,
    font_size: float,
    align: str,
) -> None:
    leading = font_size * 1.2
    for index, line in enumerate(lines):
        baseline = y_top_baseline - index * leading
        if align == "center":
            canvas.drawCentredString(x + width / 2.0, baseline, line)
        elif align == "right":
            canvas.drawRightString(x + width, baseline, line)
        else:
            canvas.drawString(x, baseline, line)


class CoverComposer:
    """Gera overlay transparente e mescla na capa original sem rasterizar o PDF-base."""

    @staticmethod
    def build_overlay_pdf(
        template: Any,
        student: Optional[Dict[str, Any]] = None,
        test_data: Optional[Dict[str, Any]] = None,
        sample: bool = False,
        fields_override: Optional[Dict[str, Any]] = None,
    ) -> bytes:
        from app.services.cover_templates.field_catalog import SAMPLE_VALUES

        page_w = float(getattr(template, "page_width_pt", 0) or 0)
        page_h = float(getattr(template, "page_height_pt", 0) or 0)
        if page_w <= 0 or page_h <= 0:
            raise ValueError("Template sem dimensões de página")

        config = fields_override if fields_override is not None else (getattr(template, "fields", None) or {})
        raw_fields = config.get("fields") if isinstance(config, dict) else config
        if not isinstance(raw_fields, list):
            raw_fields = []

        buffer = io.BytesIO()
        canvas = Canvas(buffer, pagesize=(page_w, page_h))
        canvas.setPageSize((page_w, page_h))

        for raw in raw_fields:
            if not isinstance(raw, dict):
                continue
            key = (raw.get("key") or "").strip()
            if not key:
                continue
            try:
                box = canonicalize_field_box(raw, page_w, page_h)
            except Exception:
                logger.warning("Campo de capa ignorado (coordenadas inválidas): %s", raw)
                continue

            if sample:
                value = SAMPLE_VALUES.get(key, "")
            else:
                value = resolve_field_value(key, student, test_data)
            if raw.get("uppercase"):
                value = value.upper()
            if not value:
                continue

            font_name = raw.get("font_name") or "Helvetica"
            if font_name not in ALLOWED_FONTS:
                font_name = "Helvetica"
            try:
                font_size = float(raw.get("font_size_pt") or 12)
            except (TypeError, ValueError):
                font_size = 12.0
            align = raw.get("align") or "left"
            valign = raw.get("valign") or "middle"
            overflow = raw.get("overflow") or "ellipsis"
            max_chars = raw.get("max_chars")
            try:
                max_chars = int(max_chars) if max_chars is not None else None
            except (TypeError, ValueError):
                max_chars = None

            lines = _fit_text(
                value,
                font_name,
                font_size,
                box["width_pt"],
                overflow,
                max_chars,
            )
            if not lines:
                continue

            canvas.setFont(font_name, font_size)
            canvas.setFillColor(_parse_color(raw.get("color")))
            baseline = _baseline_y(
                box["y_pt"], box["height_pt"], font_size, valign, len(lines)
            )
            _draw_lines(
                canvas,
                lines,
                box["x_pt"],
                baseline,
                box["width_pt"],
                font_name,
                font_size,
                align,
            )

        canvas.save()
        return buffer.getvalue()

    @staticmethod
    def merge_overlay(cover_base_pdf: bytes, overlay_pdf: bytes) -> bytes:
        base_reader = PdfReader(io.BytesIO(cover_base_pdf))
        if not base_reader.pages:
            raise ValueError("PDF da capa não possui páginas")
        overlay_reader = PdfReader(io.BytesIO(overlay_pdf))
        if not overlay_reader.pages:
            return cover_base_pdf
        page = base_reader.pages[0]
        page.merge_page(overlay_reader.pages[0])
        writer = PdfWriter()
        writer.add_page(page)
        for extra in base_reader.pages[1:]:
            writer.add_page(extra)
        out = io.BytesIO()
        writer.write(out)
        return out.getvalue()

    @classmethod
    def compose(
        cls,
        cover_base_pdf: bytes,
        template: Any,
        student: Optional[Dict[str, Any]] = None,
        test_data: Optional[Dict[str, Any]] = None,
        sample: bool = False,
        fields_override: Optional[Dict[str, Any]] = None,
    ) -> bytes:
        overlay = cls.build_overlay_pdf(
            template,
            student=student,
            test_data=test_data,
            sample=sample,
            fields_override=fields_override,
        )
        return cls.merge_overlay(cover_base_pdf, overlay)
