# -*- coding: utf-8 -*-
"""Constantes físicas e fontes permitidas no overlay ReportLab."""

# A4 retrato em pontos PDF (1 pt = 1/72 in). Mesmo valor usado pelo ReportLab.
A4_WIDTH_PT = 595.2755905511812
A4_HEIGHT_PT = 841.8897637795276

# Provas físicas do pipeline atual (questões + OMR) são A4.
# Tolerância de 2 mm: aceita variação de exportação sem esticar a arte.
A4_TOLERANCE_MM = 2.0
A4_TOLERANCE_PT = A4_TOLERANCE_MM * 72.0 / 25.4

DEFAULT_IMAGE_DPI = 300.0
MAX_COVER_FILE_BYTES = 20 * 1024 * 1024

ALLOWED_FONTS = frozenset(
    {
        "Helvetica",
        "Helvetica-Bold",
        "Helvetica-Oblique",
        "Helvetica-BoldOblique",
        "Times-Roman",
        "Times-Bold",
        "Times-Italic",
        "Times-BoldItalic",
        "Courier",
        "Courier-Bold",
        "Courier-Oblique",
        "Courier-BoldOblique",
    }
)

ALLOWED_ALIGN = frozenset({"left", "center", "right"})
ALLOWED_VALIGN = frozenset({"top", "middle", "bottom"})
ALLOWED_OVERFLOW = frozenset({"ellipsis", "wrap", "clip"})
ALLOWED_STATUSES = frozenset({"draft", "active", "inactive"})
ALLOWED_SOURCE_KINDS = frozenset({"pdf", "jpeg", "png"})

MIN_FONT_SIZE_PT = 6.0
MAX_FONT_SIZE_PT = 72.0
