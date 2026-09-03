# -*- coding: utf-8 -*-
"""
Otimização de rasters das PÁGINAS DE QUESTÕES (Architecture 4).

Reduz resolução/bytes das imagens embutidas no PDF de questões.
Não altera tamanho visual no HTML/CSS (apenas os bytes do bitmap).

NÃO usar este módulo no render do cartão-resposta OMR, no overlay
ReportLab, nem em correction_new_grid.py.
"""

from __future__ import annotations

import base64
import hashlib
import io
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

from PIL import Image, ImageOps

logger = logging.getLogger(__name__)


def _positive_int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
        return value if value > 0 else default
    except ValueError:
        return default


# Questões: ~A4 @ 300 DPI. Não usar estes limites em capa/timbrado/logo.
MAX_IMAGE_WIDTH = _positive_int_env("PDF_QUESTION_IMAGE_MAX_WIDTH", 2480)
MAX_IMAGE_HEIGHT = _positive_int_env("PDF_QUESTION_IMAGE_MAX_HEIGHT", 2480)
JPEG_QUALITY = _positive_int_env("PDF_QUESTION_IMAGE_JPEG_QUALITY", 90)

# Marca A4 @ 300 DPI (21×29,7 cm). Não usar no OMR nem no CoverTemplate.
LETTERHEAD_MAX_WIDTH = _positive_int_env("PDF_LETTERHEAD_MAX_WIDTH", 2480)
LETTERHEAD_MAX_HEIGHT = _positive_int_env("PDF_LETTERHEAD_MAX_HEIGHT", 3508)
COVER_JPEG_QUALITY = _positive_int_env("PDF_COVER_JPEG_QUALITY", 90)
LOGO_MAX_EDGE = _positive_int_env("PDF_LOGO_MAX_EDGE", 2480)
_DIAGRAM_MAX_UNIQUE_COLORS = 4096
_ILLUSTRATION_MAX_UNIQUE_COLORS = 8192

_SRC_DATA_URI_RE = re.compile(
    r"""(src\s*=\s*["'])(data:(image/[a-zA-Z0-9.+-]+);base64,([A-Za-z0-9+/=\s]+))(["'])""",
    flags=re.IGNORECASE,
)


@dataclass
class ImageOptimizationResult:
    data: bytes
    mime: str
    original_width: int
    original_height: int
    optimized_width: int
    optimized_height: int
    original_bytes: int
    optimized_bytes: int
    changed: bool
    reason: str


@dataclass
class ImageOptimizationStats:
    images: int = 0
    original_bytes: int = 0
    optimized_bytes: int = 0
    resized: int = 0
    converted_to_jpeg: int = 0
    kept_original: int = 0
    failed: int = 0
    details: list = field(default_factory=list)

    def add(self, result: ImageOptimizationResult, original_mime: str = "") -> None:
        self.images += 1
        self.original_bytes += result.original_bytes
        self.optimized_bytes += result.optimized_bytes
        if not result.changed:
            self.kept_original += 1
        if (
            result.optimized_width < result.original_width
            or result.optimized_height < result.original_height
        ):
            self.resized += 1
        if result.changed and result.mime == "image/jpeg" and original_mime != "image/jpeg":
            self.converted_to_jpeg += 1
        self.details.append(result)

    @property
    def reduction_percent(self) -> float:
        if self.original_bytes <= 0:
            return 0.0
        return (1.0 - (self.optimized_bytes / self.original_bytes)) * 100.0


def _normalize_mime(mime: Optional[str]) -> str:
    mime = (mime or "").split(";")[0].strip().lower()
    if mime in ("image/jpg", "image/jpeg"):
        return "image/jpeg"
    if mime == "image/png":
        return "image/png"
    if mime in ("image/webp", "image/gif", "image/bmp", "image/tiff"):
        return mime
    return mime or "image/png"


def _has_useful_transparency(img: Image.Image) -> bool:
    if img.mode in ("RGBA", "LA"):
        extrema = img.getchannel("A").getextrema()
        return bool(extrema and extrema[0] < 255)
    if img.mode == "P":
        return "transparency" in img.info
    if img.mode == "PA":
        return True
    return False


def _unique_colors_within(img: Image.Image, max_colors: int) -> bool:
    sample = img.convert("RGB")
    if max(sample.size) > 400:
        sample = sample.copy()
        sample.thumbnail((400, 400), Image.Resampling.NEAREST)
    return sample.getcolors(maxcolors=max_colors) is not None


def _looks_like_diagram(img: Image.Image) -> bool:
    """Diagrama/gráfico/screenshot: paleta limitada — manter PNG."""
    if img.mode in ("P", "1"):
        return True
    return _unique_colors_within(img, _DIAGRAM_MAX_UNIQUE_COLORS)


def _looks_like_illustration(img: Image.Image, original_mime: str) -> bool:
    """PNG ilustrado (texto, ícones, arte) — não converter para JPEG de foto."""
    if original_mime != "image/png":
        return False
    if img.mode in ("P", "1", "L"):
        return True
    return _unique_colors_within(img, _ILLUSTRATION_MAX_UNIQUE_COLORS)


def _resize_if_needed(
    img: Image.Image,
    max_width: int = MAX_IMAGE_WIDTH,
    max_height: int = MAX_IMAGE_HEIGHT,
) -> Image.Image:
    width, height = img.size
    if width <= max_width and height <= max_height:
        return img
    img = img.copy()
    img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
    return img


def _encode_jpeg(img: Image.Image, quality: int = JPEG_QUALITY) -> bytes:
    if img.mode == "RGBA":
        background = Image.new("RGB", img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[-1])
        img = background
    elif img.mode != "RGB":
        img = img.convert("RGB")
    buf = io.BytesIO()
    img.save(
        buf,
        format="JPEG",
        quality=quality,
        optimize=True,
        progressive=False,
    )
    return buf.getvalue()


def _encode_png(img: Image.Image) -> bytes:
    if img.mode not in ("RGB", "RGBA", "L", "LA", "P"):
        img = img.convert("RGBA" if "A" in img.mode else "RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _log_result(result: ImageOptimizationResult) -> None:
    logger.info(
        "[PDF-IMAGE-OPT] original=%sx%s optimized=%sx%s "
        "original_bytes=%s optimized_bytes=%s mime=%s changed=%s reason=%s",
        result.original_width,
        result.original_height,
        result.optimized_width,
        result.optimized_height,
        result.original_bytes,
        result.optimized_bytes,
        result.mime,
        result.changed,
        result.reason,
    )


def optimize_question_image(
    image_bytes: bytes,
    mime_type: Optional[str] = None,
    *,
    max_width: Optional[int] = None,
    max_height: Optional[int] = None,
    jpeg_quality: Optional[int] = None,
    force_format: Optional[str] = None,
) -> ImageOptimizationResult:
    """
    Redimensiona/recomprime um raster para impressão A4.

    Não amplia imagens pequenas. Se a versão otimizada for maior que a
    original (e não houve resize), devolve os bytes originais.
    """
    original_bytes = len(image_bytes or b"")
    original_mime = _normalize_mime(mime_type)
    max_width = max_width or MAX_IMAGE_WIDTH
    max_height = max_height or MAX_IMAGE_HEIGHT
    jpeg_quality = jpeg_quality or JPEG_QUALITY

    def _unchanged(width: int = 0, height: int = 0, reason: str = "keep_original") -> ImageOptimizationResult:
        result = ImageOptimizationResult(
            data=image_bytes,
            mime=original_mime,
            original_width=width,
            original_height=height,
            optimized_width=width,
            optimized_height=height,
            original_bytes=original_bytes,
            optimized_bytes=original_bytes,
            changed=False,
            reason=reason,
        )
        _log_result(result)
        return result

    if not image_bytes:
        return _unchanged(reason="empty")

    try:
        img = Image.open(io.BytesIO(image_bytes))
        img.load()
        img = ImageOps.exif_transpose(img)
    except Exception as exc:
        logger.warning("[PDF-IMAGE-OPT] falha ao abrir imagem: %s", exc)
        return _unchanged(reason="unreadable")

    original_width, original_height = img.size
    has_alpha = _has_useful_transparency(img)
    keep_png = has_alpha or _looks_like_diagram(img) or _looks_like_illustration(img, original_mime)
    resized = _resize_if_needed(img, max_width=max_width, max_height=max_height)
    optimized_width, optimized_height = resized.size

    candidates: list[Tuple[bytes, str, str]] = []
    forced = (force_format or "").strip().lower()

    if forced in ("png", "image/png"):
        candidates.append((_encode_png(resized), "image/png", "png_forced"))
    elif forced in ("jpeg", "jpg", "image/jpeg"):
        candidates.append((_encode_jpeg(resized, quality=jpeg_quality), "image/jpeg", "jpeg_forced"))
    elif keep_png:
        candidates.append((_encode_png(resized), "image/png", "png_preserved"))
    else:
        candidates.append((_encode_jpeg(resized, quality=jpeg_quality), "image/jpeg", "jpeg_recompress"))
        if original_mime == "image/png":
            candidates.append((_encode_png(resized), "image/png", "png_resized"))

    if original_mime == "image/jpeg" and not has_alpha and not forced:
        if not any(mime == "image/jpeg" for _, mime, _ in candidates):
            candidates.append((_encode_jpeg(resized, quality=jpeg_quality), "image/jpeg", "jpeg_recompress"))

    if not candidates:
        candidates.append((_encode_jpeg(resized, quality=jpeg_quality), "image/jpeg", "jpeg_recompress"))

    best_data, best_mime, best_reason = min(candidates, key=lambda item: len(item[0]))

    resized_happened = optimized_width < original_width or optimized_height < original_height

    if not resized_happened and len(best_data) >= original_bytes:
        return _unchanged(original_width, original_height, reason="optimized_larger")

    # Sem resize e mesmo formato: só troca se a economia for material (~5%).
    # Evita oscilação em uma segunda passagem (JPEG q80 → q80).
    if not resized_happened and best_mime == original_mime:
        if len(best_data) >= int(original_bytes * 0.95):
            return _unchanged(original_width, original_height, reason="optimized_larger")

    result = ImageOptimizationResult(
        data=best_data,
        mime=best_mime,
        original_width=original_width,
        original_height=original_height,
        optimized_width=optimized_width,
        optimized_height=optimized_height,
        original_bytes=original_bytes,
        optimized_bytes=len(best_data),
        changed=best_data != image_bytes,
        reason=best_reason,
    )
    _log_result(result)
    return result


def optimize_data_uri(
    data_uri: str,
    cache: Optional[Dict[str, str]] = None,
    stats: Optional[ImageOptimizationStats] = None,
) -> str:
    """Otimiza um data URI `data:image/...;base64,...`. Em falha, devolve o original."""
    if not data_uri or not data_uri.lower().startswith("data:image/"):
        return data_uri
    try:
        header, _, payload = data_uri.partition(",")
        mime = header.split(";")[0].split(":", 1)[1].strip()
        raw = base64.b64decode(payload, validate=False)
        if not raw:
            return data_uri
    except Exception:
        return data_uri

    cache_key = None
    if cache is not None:
        cache_key = "opt:" + hashlib.sha256(raw).hexdigest()
        cached = cache.get(cache_key)
        if cached:
            if stats is not None:
                # Já contabilizado na primeira ocorrência
                pass
            return cached

    result = optimize_question_image(raw, mime)
    if stats is not None:
        stats.add(result, original_mime=_normalize_mime(mime))

    out_uri = f"data:{result.mime};base64,{base64.b64encode(result.data).decode('ascii')}"
    if cache is not None and cache_key:
        cache[cache_key] = out_uri
    return out_uri


def optimize_html_data_uris(
    html: str,
    cache: Optional[Dict[str, str]] = None,
    stats: Optional[ImageOptimizationStats] = None,
) -> str:
    """
    Substitui data URIs em atributos src= de <img> pela versão otimizada.

    Não altera width/height/style das tags — só o payload do raster.
    """
    if not html or "data:image/" not in html:
        return html

    def _replace(match: re.Match) -> str:
        prefix, _full_uri, mime, b64, suffix = match.groups()
        data_uri = f"data:{mime};base64,{b64}"
        optimized = optimize_data_uri(data_uri, cache=cache, stats=stats)
        return f"{prefix}{optimized}{suffix}"

    return _SRC_DATA_URI_RE.sub(_replace, html)


def log_optimization_summary(stats: ImageOptimizationStats, questions_pdf_bytes=0) -> None:
    orig_mb = stats.original_bytes / (1024 * 1024)
    opt_mb = stats.optimized_bytes / (1024 * 1024)
    logger.info(
        "[ARCH4] Questões imagens: antes=%.2f MB depois=%.2f MB redução=%.1f%% "
        "(imagens=%s redimensionadas=%s jpeg=%s originais_mantidos=%s falhas=%s)",
        orig_mb,
        opt_mb,
        stats.reduction_percent,
        stats.images,
        stats.resized,
        stats.converted_to_jpeg,
        stats.kept_original,
        stats.failed,
    )
    size = len(questions_pdf_bytes) if isinstance(questions_pdf_bytes, (bytes, bytearray)) else int(questions_pdf_bytes or 0)
    if size:
        logger.info(
            "[ARCH4] Questões PDF: %.2f MB",
            size / (1024 * 1024),
        )


def optimize_letterhead_image(
    image_bytes: bytes,
    mime_type: Optional[str] = "image/png",
) -> ImageOptimizationResult:
    """Timbrado A4 @ 300 DPI, PNG. Não usar em CoverTemplate nem no OMR."""
    return optimize_question_image(
        image_bytes,
        mime_type,
        max_width=LETTERHEAD_MAX_WIDTH,
        max_height=LETTERHEAD_MAX_HEIGHT,
        force_format="png",
    )


def optimize_cover_photo(
    image_bytes: bytes,
    mime_type: Optional[str] = "image/jpeg",
) -> ImageOptimizationResult:
    """Foto de capa Afirme A4 @ 300 DPI. Não usar em CoverTemplate nem no OMR."""
    return optimize_question_image(
        image_bytes,
        mime_type,
        max_width=LETTERHEAD_MAX_WIDTH,
        max_height=LETTERHEAD_MAX_HEIGHT,
        jpeg_quality=COVER_JPEG_QUALITY,
    )


def optimize_logo_image(
    image_bytes: bytes,
    mime_type: Optional[str] = "image/png",
) -> ImageOptimizationResult:
    """Logo de município/empresa. Mantém PNG; não esmaga abaixo de ~300 DPI A4."""
    return optimize_question_image(
        image_bytes,
        mime_type,
        max_width=LOGO_MAX_EDGE,
        max_height=LOGO_MAX_EDGE,
        force_format="png",
    )


def optimize_base64_asset(
    b64_payload: str,
    mime_type: str,
    optimizer,
    stats: Optional[ImageOptimizationStats] = None,
) -> Tuple[str, str]:
    """
    Decodifica base64, otimiza e devolve (base64, mime).
    Em falha, devolve o payload original.
    """
    if not b64_payload:
        return b64_payload, mime_type
    try:
        raw = base64.b64decode(b64_payload, validate=False)
        if not raw:
            return b64_payload, mime_type
    except Exception:
        return b64_payload, mime_type

    result = optimizer(raw, mime_type)
    if stats is not None:
        stats.add(result, original_mime=_normalize_mime(mime_type))
    if not result.changed:
        return b64_payload, result.mime
    return base64.b64encode(result.data).decode("ascii"), result.mime


def log_cover_optimization_summary(stats: ImageOptimizationStats) -> None:
    if stats.images <= 0:
        return
    logger.info(
        "[ARCH4] Capa/timbrado: antes=%.2f MB depois=%.2f MB redução=%.1f%% "
        "(imagens=%s redimensionadas=%s originais_mantidos=%s)",
        stats.original_bytes / (1024 * 1024),
        stats.optimized_bytes / (1024 * 1024),
        stats.reduction_percent,
        stats.images,
        stats.resized,
        stats.kept_original,
    )
