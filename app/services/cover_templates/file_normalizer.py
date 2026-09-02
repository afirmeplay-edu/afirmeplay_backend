# -*- coding: utf-8 -*-
"""Validação do arquivo original e geração do PDF normalizado (sem WeasyPrint)."""
from __future__ import annotations

import io
from typing import Any, Dict, Tuple

from PIL import Image, ImageOps
from pypdf import PdfReader
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas

from app.services.cover_templates.constants import (
    A4_HEIGHT_PT,
    A4_TOLERANCE_PT,
    A4_WIDTH_PT,
    MAX_COVER_FILE_BYTES,
)
from app.services.cover_templates.coordinates import pt_to_mm
from app.services.cover_templates.exceptions import CoverTemplateValidationError


def _assert_a4_portrait(width_pt: float, height_pt: float, source_label: str) -> None:
    portrait = (
        abs(width_pt - A4_WIDTH_PT) <= A4_TOLERANCE_PT
        and abs(height_pt - A4_HEIGHT_PT) <= A4_TOLERANCE_PT
    )
    landscape = (
        abs(width_pt - A4_HEIGHT_PT) <= A4_TOLERANCE_PT
        and abs(height_pt - A4_WIDTH_PT) <= A4_TOLERANCE_PT
    )
    if portrait:
        return
    width_mm = pt_to_mm(width_pt)
    height_mm = pt_to_mm(height_pt)
    if landscape:
        raise CoverTemplateValidationError(
            f"{source_label} está em paisagem ({width_mm:.1f}×{height_mm:.1f} mm). "
            "A capa de prova física precisa ser A4 retrato (210×297 mm). "
            "O arquivo original não é esticado nem recortado."
        )
    raise CoverTemplateValidationError(
        f"{source_label} mede {width_mm:.1f}×{height_mm:.1f} mm. "
        "A capa de prova física precisa ser A4 retrato (210×297 mm, tolerância de "
        f"{pt_to_mm(A4_TOLERANCE_PT):.0f} mm). "
        "O arquivo original não é esticado nem recortado."
    )


def detect_source(filename: str, data: bytes) -> Tuple[str, str]:
    """Retorna (source_kind, mime_type)."""
    if not data:
        raise CoverTemplateValidationError("Arquivo vazio")
    if len(data) > MAX_COVER_FILE_BYTES:
        limit_mb = MAX_COVER_FILE_BYTES // (1024 * 1024)
        raise CoverTemplateValidationError(
            f"Arquivo excede o limite de {limit_mb} MB"
        )

    name = (filename or "").lower()
    if data.startswith(b"%PDF"):
        return "pdf", "application/pdf"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png", "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpeg", "image/jpeg"

    if name.endswith(".pdf"):
        raise CoverTemplateValidationError("Arquivo não é um PDF válido")
    if name.endswith(".png"):
        raise CoverTemplateValidationError("Arquivo PNG inválido ou corrompido")
    if name.endswith(".jpg") or name.endswith(".jpeg"):
        raise CoverTemplateValidationError("Arquivo JPEG inválido ou corrompido")
    raise CoverTemplateValidationError(
        "Formato não suportado. Envie PDF, JPG/JPEG ou PNG."
    )


def inspect_pdf(data: bytes) -> Dict[str, Any]:
    if not data.startswith(b"%PDF"):
        raise CoverTemplateValidationError("Arquivo não é um PDF válido")
    try:
        reader = PdfReader(io.BytesIO(data))
    except Exception as exc:
        raise CoverTemplateValidationError(f"Não foi possível ler o PDF: {exc}") from exc

    page_count = len(reader.pages)
    if page_count < 1:
        raise CoverTemplateValidationError("PDF não possui páginas")
    if page_count > 1:
        raise CoverTemplateValidationError(
            f"A capa deve ter exatamente uma página. O PDF enviado tem {page_count} páginas."
        )

    page = reader.pages[0]
    box = page.mediabox
    width_pt = float(box.width)
    height_pt = float(box.height)
    rotation = int(page.get("/Rotate") or 0) % 360
    if rotation != 0:
        raise CoverTemplateValidationError(
            f"PDF com rotação de página ({rotation}°) não é suportado. "
            "Exporte a capa sem rotação."
        )
    _assert_a4_portrait(width_pt, height_pt, "O PDF")
    return {
        "page_count": 1,
        "page_width_pt": width_pt,
        "page_height_pt": height_pt,
        "rotation": 0,
    }


def _assert_a4_aspect(width: float, height: float, source_label: str) -> None:
    if width <= 0 or height <= 0:
        raise CoverTemplateValidationError(f"{source_label} sem dimensões válidas")
    ratio = width / height
    a4_ratio = A4_WIDTH_PT / A4_HEIGHT_PT
    landscape_ratio = A4_HEIGHT_PT / A4_WIDTH_PT
    # 2 mm em A4 ≈ 0.67% na largura; usamos 2% para arte digital com DPI irregular.
    tolerance = 0.02
    if abs(ratio - a4_ratio) / a4_ratio <= tolerance:
        return
    if abs(ratio - landscape_ratio) / landscape_ratio <= tolerance:
        raise CoverTemplateValidationError(
            f"{source_label} está em paisagem. "
            "A capa de prova física precisa ser A4 retrato (210×297 mm). "
            "O arquivo original não é esticado nem recortado."
        )
    raise CoverTemplateValidationError(
        f"{source_label} não tem proporção A4 retrato (210×297 mm). "
        f"Proporção recebida: {width:.0f}×{height:.0f}. "
        "O arquivo original não é esticado nem recortado."
    )


def inspect_and_normalize_image(data: bytes, source_kind: str) -> Tuple[Dict[str, Any], bytes]:
    """
    Preserva o original (quem chama armazena `data`).
    Gera um PDF A4 com a imagem em contain (sem distorcer).
    A proporção precisa ser A4 retrato; DPI do arquivo não é confiável.
    """
    try:
        image = Image.open(io.BytesIO(data))
        image = ImageOps.exif_transpose(image)
        image.load()
    except Exception as exc:
        raise CoverTemplateValidationError(f"Imagem inválida ou corrompida: {exc}") from exc

    if image.width < 1 or image.height < 1:
        raise CoverTemplateValidationError("Imagem sem dimensões válidas")

    _assert_a4_aspect(float(image.width), float(image.height), "A imagem")

    if image.mode not in ("RGB", "RGBA"):
        image = image.convert("RGBA" if "A" in image.getbands() else "RGB")

    page_w, page_h = A4_WIDTH_PT, A4_HEIGHT_PT
    img_aspect = image.width / float(image.height)
    page_aspect = page_w / page_h
    if img_aspect > page_aspect:
        draw_w = page_w
        draw_h = page_w / img_aspect
    else:
        draw_h = page_h
        draw_w = page_h * img_aspect
    x = (page_w - draw_w) / 2.0
    y = (page_h - draw_h) / 2.0

    buffer = io.BytesIO()
    canvas = Canvas(buffer, pagesize=(page_w, page_h))
    canvas.setPageSize((page_w, page_h))
    canvas.setFillColorRGB(1, 1, 1)
    canvas.rect(0, 0, page_w, page_h, stroke=0, fill=1)
    img_buffer = io.BytesIO()
    save_format = "PNG" if source_kind == "png" or "A" in image.getbands() else "JPEG"
    if save_format == "JPEG" and image.mode != "RGB":
        image = image.convert("RGB")
    image.save(img_buffer, format=save_format)
    img_buffer.seek(0)
    canvas.drawImage(
        ImageReader(img_buffer),
        x,
        y,
        width=draw_w,
        height=draw_h,
        preserveAspectRatio=True,
        mask="auto",
        anchor="sw",
    )
    canvas.save()
    normalized_pdf = buffer.getvalue()

    meta = inspect_pdf(normalized_pdf)
    meta["source_kind"] = source_kind
    return meta, normalized_pdf


def normalize_upload(filename: str, data: bytes) -> Dict[str, Any]:
    """
    Valida o upload e devolve metadados + PDF normalizado.

    Para PDF: o normalizado é uma cópia dos bytes originais (sem rasterizar).
    Para imagem: gera um PDF A4 com contain, sem distorcer.
    """
    source_kind, mime_type = detect_source(filename, data)
    if source_kind == "pdf":
        meta = inspect_pdf(data)
        return {
            **meta,
            "source_kind": source_kind,
            "mime_type": mime_type,
            "normalized_pdf": data,
        }

    meta, normalized_pdf = inspect_and_normalize_image(data, source_kind)
    return {
        **meta,
        "source_kind": source_kind,
        "mime_type": mime_type,
        "normalized_pdf": normalized_pdf,
    }
