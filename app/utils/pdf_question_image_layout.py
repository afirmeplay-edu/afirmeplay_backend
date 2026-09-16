# -*- coding: utf-8 -*-
"""
Dimensionamento visual de imagens do conteúdo das questões (PDF Arch4 / hybrid).

Calcula S = min(Wmax/W, Hmax/H, 1) e grava width/height em cm no <img>.
Não altera rasters (isso é pdf_question_image_optimizer). Não usar em capa/OMR.
"""

from __future__ import annotations

import base64
import io
import logging
import re
from dataclasses import dataclass
from html import unescape
from typing import Any, Dict, List, Optional, Tuple

from markupsafe import Markup
from PIL import Image, ImageOps

logger = logging.getLogger(__name__)

# Área útil A4 portrait com margens 2 cm / 1,5 cm
PAGE_USEFUL_WIDTH_CM = 17.0
PAGE_USEFUL_HEIGHT_CM = 26.7
WMAX_CM = 16.5
HMAX_SINGLE_CM = 10.0
MULTI_IMAGE_BUDGET_FRACTION = 0.42  # ~40–45% da altura útil
CSS_DPI = 96.0
CM_PER_INCH = 2.54

# Heurística de texto / estrutura (pré-layout WeasyPrint)
CHARS_PER_LINE = 85
LINE_HEIGHT_CM = 0.55  # ~12 pt × 1.5
HEADER_RESERVE_CM = 1.2
SPACING_RESERVE_CM = 1.0
ALT_ROW_CM = 0.55
MIN_H_AVAILABLE_CM = 2.0

_IMG_TAG_RE = re.compile(r"<img\b[^>]*>", flags=re.IGNORECASE)
_SRC_RE = re.compile(
    r"""\bsrc\s*=\s*(["'])(data:image/[^"']+)\1""",
    flags=re.IGNORECASE,
)
_CLASS_RE = re.compile(
    r"""\bclass\s*=\s*(["'])(.*?)\1""",
    flags=re.IGNORECASE | re.DOTALL,
)
_STYLE_RE = re.compile(
    r"""\s+style\s*=\s*(["'])(.*?)\1""",
    flags=re.IGNORECASE | re.DOTALL,
)
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")

_MATH_CLASSES = frozenset({"math-inline-img", "math-display-img"})


@dataclass(frozen=True)
class FittedImageSize:
    width_cm: float
    height_cm: float
    scale: float
    natural_width_cm: float
    natural_height_cm: float


def px_to_cm(px: float, dpi: float = CSS_DPI) -> float:
    if dpi <= 0:
        dpi = CSS_DPI
    return float(px) * CM_PER_INCH / dpi


def compute_scale(w_cm: float, h_cm: float, w_max: float, h_max: float) -> float:
    """S = min(Wmax/W, Hmax/H, 1). Não amplia além do tamanho original."""
    if w_cm <= 0 or h_cm <= 0:
        return 0.0
    return min(w_max / w_cm, h_max / h_cm, 1.0)


def multi_image_budget_cap_cm(page_height_cm: float = PAGE_USEFUL_HEIGHT_CM) -> float:
    return MULTI_IMAGE_BUDGET_FRACTION * page_height_cm


def estimate_text_height_cm(plain_text: str) -> float:
    text = (plain_text or "").strip()
    if not text:
        return 0.0
    chars = len(text)
    lines = max(1, (chars + CHARS_PER_LINE - 1) // CHARS_PER_LINE)
    return lines * LINE_HEIGHT_CM


def strip_html_to_text(html: str) -> str:
    if not html:
        return ""
    # Remover imgs para não contar lixo do data URI no comprimento
    without_imgs = _IMG_TAG_RE.sub(" ", str(html))
    text = _TAG_RE.sub(" ", without_imgs)
    text = unescape(text)
    return _WS_RE.sub(" ", text).strip()


def estimate_h_available_cm(
    *,
    content_html: str = "",
    prompt_html: str = "",
    instruction: str = "",
    title: str = "",
    alternatives_count: int = 0,
    alternatives_text: str = "",
) -> float:
    text_parts = [
        strip_html_to_text(instruction),
        strip_html_to_text(title),
        strip_html_to_text(content_html),
        strip_html_to_text(prompt_html),
        strip_html_to_text(alternatives_text),
    ]
    text_height = estimate_text_height_cm(" ".join(p for p in text_parts if p))
    structure = (
        HEADER_RESERVE_CM
        + SPACING_RESERVE_CM
        + max(0, int(alternatives_count)) * ALT_ROW_CM
    )
    available = PAGE_USEFUL_HEIGHT_CM - text_height - structure
    return max(MIN_H_AVAILABLE_CM, available)


def _is_math_img(tag: str) -> bool:
    m = _CLASS_RE.search(tag or "")
    if not m:
        return False
    classes = {c.lower() for c in m.group(2).split()}
    return bool(classes & _MATH_CLASSES)


def _decode_data_uri_size(data_uri: str) -> Optional[Tuple[int, int]]:
    if not data_uri or not data_uri.lower().startswith("data:image/"):
        return None
    try:
        _header, _, payload = data_uri.partition(",")
        raw = base64.b64decode(payload, validate=False)
        if not raw:
            return None
        img = Image.open(io.BytesIO(raw))
        img = ImageOps.exif_transpose(img)
        w, h = img.size
        if w <= 0 or h <= 0:
            return None
        return int(w), int(h)
    except Exception as exc:
        logger.debug("[PDF-IMG-LAYOUT] falha ao ler dimensões: %s", exc)
        return None


def fit_single_image_cm(
    width_px: int,
    height_px: int,
    *,
    w_max: float = WMAX_CM,
    h_max: float = HMAX_SINGLE_CM,
    dpi: float = CSS_DPI,
) -> FittedImageSize:
    w_cm = px_to_cm(width_px, dpi)
    h_cm = px_to_cm(height_px, dpi)
    s = compute_scale(w_cm, h_cm, w_max, h_max)
    return FittedImageSize(
        width_cm=w_cm * s,
        height_cm=h_cm * s,
        scale=s,
        natural_width_cm=w_cm,
        natural_height_cm=h_cm,
    )


def apply_multi_image_budget(
    sizes: List[FittedImageSize],
    budget_cm: float,
) -> List[FittedImageSize]:
    """Se Σ Hfinal > budget e N≥2, aplica fator B uniforme."""
    if len(sizes) < 2 or budget_cm <= 0:
        return sizes
    total_h = sum(s.height_cm for s in sizes)
    if total_h <= budget_cm or total_h <= 0:
        return sizes
    b = budget_cm / total_h
    out: List[FittedImageSize] = []
    for s in sizes:
        new_s = s.scale * b
        out.append(
            FittedImageSize(
                width_cm=s.natural_width_cm * new_s,
                height_cm=s.natural_height_cm * new_s,
                scale=new_s,
                natural_width_cm=s.natural_width_cm,
                natural_height_cm=s.natural_height_cm,
            )
        )
    return out


def _merge_fit_style(existing_style: str, width_cm: float, height_cm: float) -> str:
    style = existing_style or ""
    style = re.sub(
        r"(?:^|(?<=;))\s*(?:width|height|max-width|max-height)\s*:[^;]+",
        "",
        style,
        flags=re.IGNORECASE,
    )
    style = re.sub(r";\s*;", ";", style).strip().strip(";").strip()
    fit = f"width: {width_cm:.2f}cm; height: {height_cm:.2f}cm"
    if style:
        return f"{style}; {fit}"
    return fit


def _apply_size_to_img_tag(tag: str, width_cm: float, height_cm: float) -> str:
    style_m = _STYLE_RE.search(tag)
    if style_m:
        quote = style_m.group(1)
        new_style = _merge_fit_style(style_m.group(2), width_cm, height_cm)
        tag = tag[: style_m.start()] + f' style={quote}{new_style}{quote}' + tag[style_m.end() :]
    else:
        # Inserir style antes do fechamento
        insert = f' style="width: {width_cm:.2f}cm; height: {height_cm:.2f}cm"'
        if tag.endswith("/>"):
            tag = tag[:-2] + insert + " />"
        elif tag.endswith(">"):
            tag = tag[:-1] + insert + ">"
        else:
            tag = tag + insert

    # Garantir classe question-fit-img
    class_m = _CLASS_RE.search(tag)
    if class_m:
        quote = class_m.group(1)
        classes = class_m.group(2).split()
        if "question-fit-img" not in classes:
            classes.append("question-fit-img")
            new_class = f' class={quote}{" ".join(classes)}{quote}'
            tag = tag[: class_m.start()] + new_class + tag[class_m.end() :]
    else:
        insert = ' class="question-fit-img"'
        if tag.endswith("/>"):
            tag = tag[:-2] + insert + " />"
        elif tag.endswith(">"):
            tag = tag[:-1] + insert + ">"
    return tag


def fit_images_in_html_fragments(
    fragments: List[str],
    *,
    h_available_cm: float,
    w_max: float = WMAX_CM,
    h_max_single: float = HMAX_SINGLE_CM,
) -> List[str]:
    """
    Dimensiona todas as imagens de conteúdo nos fragmentos com orçamento compartilhado.
    Retorna a lista de HTML atualizada (mesma ordem/tamanho).
    """
    if not fragments:
        return fragments

    # Coletar candidatos: (frag_idx, tag_match, natural_w_cm, natural_h_cm)
    candidates: List[Tuple[int, re.Match, float, float]] = []
    for frag_idx, html in enumerate(fragments):
        if not html or "<img" not in str(html).lower():
            continue
        for m in _IMG_TAG_RE.finditer(str(html)):
            tag = m.group(0)
            if _is_math_img(tag):
                continue
            src_m = _SRC_RE.search(tag)
            if not src_m:
                continue
            size = _decode_data_uri_size(src_m.group(2))
            if not size:
                continue
            w_px, h_px = size
            candidates.append(
                (frag_idx, m, px_to_cm(w_px), px_to_cm(h_px))
            )

    if not candidates:
        return [str(f) if f is not None else f for f in fragments]

    h_max = min(max(h_available_cm, MIN_H_AVAILABLE_CM), h_max_single)
    budget = min(max(h_available_cm, MIN_H_AVAILABLE_CM), multi_image_budget_cap_cm())

    fitted: List[FittedImageSize] = []
    for _fi, _m, w_cm, h_cm in candidates:
        s = compute_scale(w_cm, h_cm, w_max, h_max)
        fitted.append(
            FittedImageSize(
                width_cm=w_cm * s,
                height_cm=h_cm * s,
                scale=s,
                natural_width_cm=w_cm,
                natural_height_cm=h_cm,
            )
        )

    fitted = apply_multi_image_budget(fitted, budget)

    # Reescrever de trás para frente por fragmento
    by_frag: Dict[int, List[Tuple[re.Match, FittedImageSize]]] = {}
    for (frag_idx, match, _w, _h), size in zip(candidates, fitted):
        by_frag.setdefault(frag_idx, []).append((match, size))

    out = [str(f) if f is not None else "" for f in fragments]
    for frag_idx, items in by_frag.items():
        html = out[frag_idx]
        # Ordem inversa para preservar offsets
        for match, size in sorted(items, key=lambda x: x[0].start(), reverse=True):
            new_tag = _apply_size_to_img_tag(match.group(0), size.width_cm, size.height_cm)
            html = html[: match.start()] + new_tag + html[match.end() :]
        out[frag_idx] = html

    return out


def fit_question_dict_images(question: Dict[str, Any]) -> None:
    """Ajusta imagens em content/prompt/alternatives[].content in-place."""
    if not isinstance(question, dict):
        return

    content = str(question.get("content") or "")
    prompt = str(question.get("prompt") or "") if question.get("prompt") else ""
    instruction = str(question.get("instruction") or "")
    title = str(question.get("title") or "")

    alts = question.get("alternatives") or []
    alt_contents: List[str] = []
    alt_indices: List[int] = []
    if isinstance(alts, list):
        for i, alt in enumerate(alts):
            if isinstance(alt, dict) and alt.get("content"):
                alt_indices.append(i)
                alt_contents.append(str(alt["content"]))

    alternatives_text = " ".join(alt_contents)
    h_available = estimate_h_available_cm(
        content_html=content,
        prompt_html=prompt,
        instruction=instruction,
        title=title,
        alternatives_count=len(alt_contents) if alt_contents else (
            len(alts) if isinstance(alts, list) else 0
        ),
        alternatives_text=alternatives_text,
    )

    fragments = [content, prompt] + alt_contents
    fitted = fit_images_in_html_fragments(fragments, h_available_cm=h_available)

    question["content"] = Markup(fitted[0])
    if question.get("prompt"):
        question["prompt"] = Markup(fitted[1]) if fitted[1] else question.get("prompt")

    if alt_indices and isinstance(alts, list):
        for offset, alt_i in enumerate(alt_indices):
            alts[alt_i]["content"] = Markup(fitted[2 + offset])


def fit_questions_collection(
    questions_by_subject: Optional[Dict] = None,
    questions_by_block: Optional[List] = None,
) -> None:
    """Aplica fit em todas as questões organizadas (subject ou block)."""
    seen: set = set()

    def _walk(q: Any) -> None:
        if not isinstance(q, dict):
            return
        # Evitar processar o mesmo dict duas vezes se block e subject compartilham refs
        key = id(q)
        if key in seen:
            return
        seen.add(key)
        fit_question_dict_images(q)

    if questions_by_block:
        for block in questions_by_block:
            for q in (block.get("questions") or []):
                _walk(q)
    elif questions_by_subject:
        for subject_questions in (questions_by_subject or {}).values():
            for q in subject_questions or []:
                _walk(q)
