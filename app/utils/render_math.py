# -*- coding: utf-8 -*-
"""
Renderização de LaTeX para PDF (WeasyPrint).

Espelha o comportamento do frontend (renderMath.ts + KaTeX):
  - $...$       → inline  (displayMode: false)
  - $$...$$     → bloco   (displayMode: true)
  - throwOnError: false   → em falha, mantém o delimitador original

WeasyPrint não executa JavaScript; fórmulas viram <img> PNG (matplotlib mathtext).
"""

from __future__ import annotations

import base64
import io
import logging
import re
from typing import Optional

import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt

logger = logging.getLogger(__name__)

# Mesma ordem do frontend: bloco ($$) antes de inline ($)
MATH_PATTERN = re.compile(r'\$\$([\s\S]+?)\$\$|\$([^$\n]+?)\$')
HTML_TAG_OR_TEXT = re.compile(r'(<[^>]+>)|([^<]+)', re.DOTALL)

_MATH_FONT_SIZE = 12
_MATH_DPI = 200


def _latex_to_png_bytes(latex: str, fontsize: float = _MATH_FONT_SIZE, dpi: int = _MATH_DPI) -> Optional[bytes]:
    latex = (latex or '').strip()
    if not latex:
        return None

    fig = None
    try:
        fig = plt.figure()
        fig.patch.set_alpha(0.0)
        text = fig.text(0, 0, f'${latex}$', fontsize=fontsize)
        fig.canvas.draw()
        bbox = text.get_window_extent(fig.canvas.get_renderer())
        width_in = max(bbox.width / fig.dpi, 0.05)
        height_in = max(bbox.height / fig.dpi, 0.05)
        fig.set_size_inches(width_in * 1.08, height_in * 1.25)
        text.set_position((0.02, 0.5))
        text.set_verticalalignment('center')

        buf = io.BytesIO()
        fig.savefig(
            buf,
            format='png',
            dpi=dpi,
            transparent=True,
            bbox_inches='tight',
            pad_inches=0.02,
        )
        buf.seek(0)
        return buf.read()
    except Exception as exc:
        logger.debug('Falha ao renderizar LaTeX %r: %s', latex, exc)
        return None
    finally:
        if fig is not None:
            plt.close(fig)


def _escape_html_attr(value: str) -> str:
    return (
        value.replace('&', '&amp;')
        .replace('"', '&quot;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
    )


def _build_math_img_tag(latex: str, display_mode: bool) -> str:
    png = _latex_to_png_bytes(latex)
    if not png:
        return f'$${latex}$$' if display_mode else f'${latex}$'

    b64 = base64.b64encode(png).decode('ascii')
    alt = _escape_html_attr(latex)
    if display_mode:
        return (
            '<span class="math-display">'
            f'<img src="data:image/png;base64,{b64}" '
            'class="math-rendered math-display-img" '
            'style="display:block;margin:6px 0;" '
            f'alt="{alt}" />'
            '</span>'
        )
    return (
        f'<img src="data:image/png;base64,{b64}" '
        'class="math-rendered math-inline-img" '
        'style="display:inline;vertical-align:middle;height:1.15em;" '
        f'alt="{alt}" />'
    )


def render_math_in_text(text: str) -> str:
    """Substitui $...$ / $$...$$ em texto plano por imagens renderizadas."""
    if not text:
        return text or ''

    def _replace(match: re.Match) -> str:
        if match.group(1) is not None:
            return _build_math_img_tag(match.group(1), display_mode=True)
        return _build_math_img_tag(match.group(2), display_mode=False)

    return MATH_PATTERN.sub(_replace, text)


def render_math_in_html(html: str) -> str:
    """
    Processa nós de texto em HTML (TipTap), preservando tags.
    Equivalente ao renderMathInHtml do frontend.
    """
    if not html:
        return html or ''

    parts = []
    for match in HTML_TAG_OR_TEXT.finditer(html):
        tag = match.group(1)
        text = match.group(2)
        if tag:
            parts.append(tag)
        elif text:
            parts.append(render_math_in_text(text))
    return ''.join(parts)
