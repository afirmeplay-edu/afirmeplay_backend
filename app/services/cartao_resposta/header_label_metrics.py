# -*- coding: utf-8 -*-
"""Métricas do cabeçalho do cartão/prova física (rótulo HTML ↔ overlay ReportLab).

WeasyPrint e ReportLab precisam medir o rótulo com o MESMO arquivo TTF.
Os templates usam @font-face AfirmeHeaderSans → app/static/fonts/LiberationSans-*.ttf.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Dict, Tuple

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfbase.ttfonts import TTFont

# Mesmos números do CSS/layout OMR (não alterar sem recalibrar overlay Y/QR).
X_BASE = 60.44
# 8pt: 5pt ficava opticamente colado no "O:" de NOME COMPLETO (negrito 7pt).
LABEL_VALUE_GAP = 8.0  # = margin-right do .header-info-line .label
LABEL_FONT_SIZE = 7.0  # = font-size: 7pt do .header-info-line
VALUE_MIN_SIZE = 5.5

# Rótulo mais largo do cabeçalho — coluna segura para todos os valores do overlay.
LONGEST_OVERLAY_LABEL = "NOME COMPLETO:"

_LABEL_FONT_REG = "AfirmeHeaderSans-Bold"
_VALUE_FONT_REG = "AfirmeHeaderSans"
_FALLBACK_LABEL = "Helvetica-Bold"
_FALLBACK_VALUE = "Helvetica"

_STATIC_FONTS_DIR = os.path.normpath(
    os.path.join(
        os.path.dirname(__file__),  # .../services/cartao_resposta
        "..",
        "..",
        "static",
        "fonts",
    )
)

_BOLD_TTF = os.path.join(_STATIC_FONTS_DIR, "LiberationSans-Bold.ttf")
_REGULAR_TTF = os.path.join(_STATIC_FONTS_DIR, "LiberationSans-Regular.ttf")


def weasyprint_base_url() -> str:
    """base_url para o WeasyPrint resolver url('fonts/...') dos @font-face."""
    static_dir = os.path.normpath(os.path.join(_STATIC_FONTS_DIR, ".."))
    return os.path.abspath(static_dir) + os.sep


def header_font_template_vars() -> Dict[str, str]:
    """URLs file:// dos TTFs para @font-face nos templates Jinja."""
    bold = Path(_BOLD_TTF).resolve()
    regular = Path(_REGULAR_TTF).resolve()
    return {
        "header_font_bold_url": bold.as_uri() if bold.is_file() else "",
        "header_font_regular_url": regular.as_uri() if regular.is_file() else "",
    }


@lru_cache(maxsize=1)
def ensure_header_fonts_registered() -> Tuple[str, str]:
    """Registra Liberation Sans no ReportLab. Retorna (label_font, value_font)."""
    label_font = _FALLBACK_LABEL
    value_font = _FALLBACK_VALUE
    try:
        if os.path.isfile(_BOLD_TTF):
            if _LABEL_FONT_REG not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(_LABEL_FONT_REG, _BOLD_TTF))
            label_font = _LABEL_FONT_REG
        else:
            logging.warning(
                "[HEADER-METRICS] TTF bold ausente (%s); fallback %s",
                _BOLD_TTF,
                _FALLBACK_LABEL,
            )
        if os.path.isfile(_REGULAR_TTF):
            if _VALUE_FONT_REG not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(_VALUE_FONT_REG, _REGULAR_TTF))
            value_font = _VALUE_FONT_REG
        else:
            logging.warning(
                "[HEADER-METRICS] TTF regular ausente (%s); fallback %s",
                _REGULAR_TTF,
                _FALLBACK_VALUE,
            )
    except Exception as exc:
        logging.error("[HEADER-METRICS] Falha ao registrar fontes: %s", exc, exc_info=True)
    return label_font, value_font


def x_after_label(label: str) -> float:
    """X do valor = X_BASE + largura real do rótulo (bold 7pt) + 5pt."""
    label_font, _ = ensure_header_fonts_registered()
    return X_BASE + stringWidth(label, label_font, LABEL_FONT_SIZE) + LABEL_VALUE_GAP


def overlay_value_x_positions() -> dict:
    """X de cada valor do overlay = largura real do respectivo rótulo + gap.

    Medição na mesma TTF Liberation Sans Bold do @font-face HTML (7pt) +
    LABEL_VALUE_GAP (8pt). NOME COMPLETO usa o rótulo mais longo.
    """
    return {
        "nome": x_after_label(LONGEST_OVERLAY_LABEL),
        "escola": x_after_label("ESCOLA:"),
        "turma": x_after_label("TURMA:"),
        "turno": x_after_label("TURNO:"),
    }
