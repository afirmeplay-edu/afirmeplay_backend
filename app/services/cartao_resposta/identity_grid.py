# -*- coding: utf-8 -*-
"""
ID-Grid OMR — identificador de 6 hex em 1 linha × 24 bolhas.

Encode/decode + desenho ReportLab (overlay). Geometria compartilhada com a
leitura em correction_new_grid.py.

Payload impresso (token v2): TTTTT C
  5 hex opacos + checksum; IDs completos vêm de answer_sheet_identity_codes.
  C = checksum: sum((i+1)*nibble_i for i in 0..4) % 16

Legado prefix (cartões antigos): K DD SS C (decode) — só leitura.
Legado 4×12 / 12 hex: decode_legacy_12 + IDGRID_ACCEPT_LEGACY_4ROW.

Layout: 6 grupos × 4 bits (8-4-2-1 L→R dentro do grupo).
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Constantes de payload (6 hex)
# ---------------------------------------------------------------------------
KIND_GABARITO = "1"
KIND_PHYSICAL = "2"
ID_GRID_LEN = 6
DOC_PREFIX_LEN = 2
STUDENT_PREFIX_LEN = 2
# Legado impresso na fase de testes (4 linhas × 12 colunas)
ID_GRID_LEN_LEGACY = 12
DOC_PREFIX_LEN_LEGACY = 5
STUDENT_PREFIX_LEN_LEGACY = 5

# ---------------------------------------------------------------------------
# Geometria da faixa (layout CSS + overlay + leitura A4@300DPI)
# ---------------------------------------------------------------------------
# Folha: padding-top 1.2cm + header 6.4cm → faixa começa a 7.6cm do topo.
# Faixa baixa (~1.15cm); instruções condensadas 1.95cm. Soma ≤ 3.8cm legado
# (aplicador / grade / QR não sobem — folga branca fica na faixa).
HEADER_END_CM = 1.2 + 6.4  # 7.6
ID_GRID_HEIGHT_CM = 1.15
INSTRUCTIONS_HEIGHT_CM_WITH_GRID = 1.95
INSTRUCTIONS_HEIGHT_CM_LEGACY = 3.8

PT_PER_CM = 72.0 / 2.54
PX_PER_CM_A4 = 118.11  # 300 DPI
A4_HEIGHT_PT = 841.89
A4_WIDTH_PT = 595.28
PAGE_PAD_X_CM = 2.0

# 1 linha × 24 bolhas = 6 grupos × 4 bits (8-4-2-1)
N_GROUPS = 6
BITS_PER_GROUP = 4
N_BUBBLES = N_GROUPS * BITS_PER_GROUP  # 24
GROUP_GAP_MM = 0.8
# Diâmetro/passo: NÃO esticar até a borda do slot (sobrepunha os marcadores).
# Passo teto mantém a faixa compacta e centrada; diâmetro ~72% do passo.
BUBBLE_DIAMETER_MM_MIN = 2.8
BUBBLE_PITCH_MM_MIN = 3.3
BUBBLE_PITCH_MM_MAX = 5.0
BUBBLE_DIAM_FACTOR = 0.72
MARKER_SIZE_MM = 4.0
MARKER_INSET_PT = 3.0
# Folga mínima entre borda do marcador e borda da bolha extrema
MARKER_BUBBLE_CLEARANCE_MM = 1.5

# Legado 4×12 (só leitura)
N_COLS_LEGACY = 12
N_ROWS_LEGACY = 4
BUBBLE_DIAMETER_MM_LEGACY = 3.0
BUBBLE_PITCH_MM_LEGACY = 3.8
ID_GRID_HEIGHT_CM_LEGACY = 1.85

BIT_WEIGHTS = (8, 4, 2, 1)

LABEL_TEXT = "USO DO SISTEMA — NÃO PREENCHER"


def _mm_to_pt(mm: float) -> float:
    return mm * PT_PER_CM / 10.0


def _cm_to_pt(cm: float) -> float:
    return cm * PT_PER_CM


def _cm_to_px(cm: float) -> float:
    return cm * PX_PER_CM_A4


def _mm_to_px(mm: float) -> float:
    return (mm / 10.0) * PX_PER_CM_A4


def uuid_hex_prefix(raw: str, n: int = DOC_PREFIX_LEN) -> str:
    """Primeiros n hex do UUID, sem hífen, maiúsculos."""
    hex_only = re.sub(r"[^0-9a-fA-F]", "", str(raw or ""))
    if len(hex_only) < n:
        raise ValueError(f"UUID sem hex suficiente para prefixo de {n}: {raw!r}")
    return hex_only[:n].upper()


def checksum_nibble(payload: str) -> int:
    """
    Checksum de 1 nibble.
    Payload novo: 5 hex (K+DD+SS). Legado: 11 hex (K+DDDDD+SSSSS).
    """
    text = (payload or "").strip().upper()
    n = len(text)
    if n not in (5, 11):
        raise ValueError("payload checksum exige 5 (novo) ou 11 (legado) hex")
    total = 0
    for i, ch in enumerate(text[:n]):
        total += (i + 1) * int(ch, 16)
    return total % 16


def encode(kind: str, document_id: str, student_id: str) -> str:
    """
    Legado: monta K DD SS C a partir de prefixos de UUID.

    Novos cartões usam identity_code_service.allocate_code (token no banco).
    Mantido para testes e fallback de leitura de folhas antigas.
    """
    k = str(kind or "").strip()[:1]
    if k not in (KIND_GABARITO, KIND_PHYSICAL):
        raise ValueError(f"kind inválido: {kind!r}")
    d = uuid_hex_prefix(document_id, DOC_PREFIX_LEN)
    s = uuid_hex_prefix(student_id, STUDENT_PREFIX_LEN)
    payload5 = f"{k}{d}{s}"
    c = checksum_nibble(payload5)
    return f"{payload5}{c:X}"


def decode_token(code: str) -> Optional[Dict[str, str]]:
    """
    Valida token v2 (5 hex + checksum). Não resolve IDs — só checksum/raw.
    Aceita qualquer nibble inicial (token opaco).
    """
    text = (code or "").strip().upper()
    if len(text) != ID_GRID_LEN:
        return None
    if any(ch not in "0123456789ABCDEF" for ch in text):
        return None
    try:
        expected = checksum_nibble(text[:5])
    except ValueError:
        return None
    if expected != int(text[5], 16):
        return None
    return {
        "token": text[:5],
        "checksum": text[5],
        "raw": text,
    }


def decode(code: str) -> Optional[Dict[str, str]]:
    """
    Legado prefix: valida e decompõe K DD SS C. None se inválido.
    Nunca "adivinha". Tokens v2 aleatórios tipicamente falham aqui (kind).
    """
    text = (code or "").strip().upper()
    if len(text) != ID_GRID_LEN:
        return None
    if any(ch not in "0123456789ABCDEF" for ch in text):
        return None
    if text[0] not in (KIND_GABARITO, KIND_PHYSICAL):
        return None
    try:
        expected = checksum_nibble(text[:5])
    except ValueError:
        return None
    if expected != int(text[5], 16):
        return None
    return {
        "kind": text[0],
        "document_prefix": text[1:3],
        "student_prefix": text[3:5],
        "checksum": text[5],
        "raw": text,
    }


def decode_legacy_12(code: str) -> Optional[Dict[str, str]]:
    """Decode do payload legado de 12 hex (K DDDDD SSSSS C). Removível com o fallback 4×12."""
    text = (code or "").strip().upper()
    if len(text) != ID_GRID_LEN_LEGACY:
        return None
    if any(ch not in "0123456789ABCDEF" for ch in text):
        return None
    if text[0] not in (KIND_GABARITO, KIND_PHYSICAL):
        return None
    try:
        expected = checksum_nibble(text[:11])
    except ValueError:
        return None
    if expected != int(text[11], 16):
        return None
    return {
        "kind": text[0],
        "document_prefix": text[1:6],
        "student_prefix": text[6:11],
        "checksum": text[11],
        "raw": text,
    }


def nibble_bits(nibble: int) -> List[bool]:
    """Bits 8, 4, 2, 1 (ordem L→R no grupo / top→bottom no legado)."""
    n = int(nibble) & 0xF
    return [bool(n & w) for w in BIT_WEIGHTS]


def bits_to_nibble(bits: List[bool]) -> int:
    value = 0
    for on, w in zip(bits, BIT_WEIGHTS):
        if on:
            value |= w
    return value


def code_to_column_bits(code: str) -> List[List[bool]]:
    """6 grupos × 4 bits (compatível com testes; ordem 8-4-2-1)."""
    text = (code or "").strip().upper()
    if len(text) != ID_GRID_LEN:
        raise ValueError(f"código deve ter {ID_GRID_LEN} hex")
    return [nibble_bits(int(ch, 16)) for ch in text]


def code_to_flat_bits(code: str) -> List[bool]:
    """48→24 bits planos: grupos L→R, dentro do grupo 8-4-2-1."""
    flat: List[bool] = []
    for bits in code_to_column_bits(code):
        flat.extend(bits)
    return flat


# ---------------------------------------------------------------------------
# Geometria em pontos (ReportLab) e pixels A4 (leitura)
# ---------------------------------------------------------------------------

def slot_rect_pt(height_cm: float = None) -> Dict[str, float]:
    """Retângulo da faixa no PDF (origem inferior-esquerda)."""
    h_cm = ID_GRID_HEIGHT_CM if height_cm is None else height_cm
    top_from_page_top = _cm_to_pt(HEADER_END_CM)
    height = _cm_to_pt(h_cm)
    left = _cm_to_pt(PAGE_PAD_X_CM)
    right = A4_WIDTH_PT - left
    top_y = A4_HEIGHT_PT - top_from_page_top
    bottom_y = top_y - height
    return {
        "left": left,
        "right": right,
        "top": top_y,
        "bottom": bottom_y,
        "width": right - left,
        "height": height,
    }


def slot_rect_px(height_cm: float = None) -> Dict[str, float]:
    """Retângulo da faixa na imagem A4 lógica (origem superior-esquerda)."""
    h_cm = ID_GRID_HEIGHT_CM if height_cm is None else height_cm
    top = _cm_to_px(HEADER_END_CM)
    height = _cm_to_px(h_cm)
    left = _cm_to_px(PAGE_PAD_X_CM)
    page_w = 21.0 * PX_PER_CM_A4
    right = page_w - left
    return {
        "left": left,
        "right": right,
        "top": top,
        "bottom": top + height,
        "width": right - left,
        "height": height,
    }


def _pt_x_to_px(x_pt: float) -> float:
    return (x_pt / A4_WIDTH_PT) * (21.0 * PX_PER_CM_A4)


def _pt_y_to_px(y_pt: float) -> float:
    y_from_top_pt = A4_HEIGHT_PT - y_pt
    return (y_from_top_pt / A4_HEIGHT_PT) * (29.7 * PX_PER_CM_A4)


def _grid_geometry_pt() -> Dict[str, Any]:
    """
    Centros das 24 bolhas em 1 linha + marcadores (pontos PDF).

    A faixa de bolhas é compacta (passo ≤ BUBBLE_PITCH_MM_MAX) e centrada,
    com folga explícita aos marcadores sólidos — não estica até a borda do slot.
    """
    slot = slot_rect_pt()
    marker = _mm_to_pt(MARKER_SIZE_MM)
    gap = _mm_to_pt(GROUP_GAP_MM)
    clear = _mm_to_pt(MARKER_BUBBLE_CLEARANCE_MM)
    pitch_min = _mm_to_pt(BUBBLE_PITCH_MM_MIN)
    pitch_max = _mm_to_pt(BUBBLE_PITCH_MM_MAX)
    diam_min = _mm_to_pt(BUBBLE_DIAMETER_MM_MIN)

    # Marcadores fixos nas extremidades do slot
    left_marker_x = slot["left"] + MARKER_INSET_PT + marker / 2.0
    right_marker_x = slot["right"] - MARKER_INSET_PT - marker / 2.0
    marker_right_edge = left_marker_x + marker / 2.0
    marker_left_edge = right_marker_x - marker / 2.0

    # Banda onde a BORDA das bolhas pode existir
    band_left = marker_right_edge + clear
    band_right = marker_left_edge - clear
    band_width = band_right - band_left

    n_gaps = N_GROUPS - 1  # 5
    n_spans = N_BUBBLES - 1  # 23
    # Passo: cabe na banda (descontando diâmetro ≈ factor*pitch) e respeita teto.
    # Iteração 1: pitch pelo espaço de centros assumindo diam = factor*pitch
    # centros_avail ≈ band_width - diam  →  n_spans*p + n_gaps*gap ≤ band - factor*p
    # → p*(n_spans + factor) ≤ band - n_gaps*gap
    pitch = (band_width - n_gaps * gap) / (n_spans + BUBBLE_DIAM_FACTOR)
    pitch = min(max(pitch, pitch_min), pitch_max)
    diam = max(min(BUBBLE_DIAM_FACTOR * pitch, pitch * 0.92), diam_min)
    # Se diam mínimo forçou valor alto, revalida
    if diam > pitch * 0.92:
        diam = pitch * 0.92
    radius = diam / 2.0

    centers_avail = band_width - 2.0 * radius
    span_needed = n_spans * pitch + n_gaps * gap
    if span_needed > centers_avail and centers_avail > 0:
        pitch = (centers_avail - n_gaps * gap) / n_spans
        pitch = max(pitch, pitch_min)
        diam = max(min(BUBBLE_DIAM_FACTOR * pitch, pitch * 0.92), diam_min)
        if diam > pitch * 0.92:
            diam = pitch * 0.92
        radius = diam / 2.0
        span_needed = n_spans * pitch + n_gaps * gap

    # Centra o bloco de bolhas na banda entre marcadores
    centers_left = band_left + radius
    centers_right = band_right - radius
    x0 = centers_left + max(0.0, (centers_right - centers_left - span_needed) / 2.0)

    centers_x: List[float] = []
    group_centers_x: List[float] = []
    for g in range(N_GROUPS):
        start = x0 + g * (BITS_PER_GROUP * pitch + gap)
        xs = [start + b * pitch for b in range(BITS_PER_GROUP)]
        centers_x.extend(xs)
        group_centers_x.append((xs[0] + xs[-1]) / 2.0)

    # Bandas: só rótulo genérico no topo; bolhas no restante (sem hex impresso)
    label_band = 8.0
    edge_pad = 1.5
    y_bubble = slot["bottom"] + edge_pad + radius
    y_max = slot["top"] - label_band - radius - edge_pad
    if y_max > y_bubble:
        y_bubble = (y_bubble + y_max) / 2.0

    return {
        "layout": "1x24",
        "slot": slot,
        "radius": radius,
        "diameter": diam,
        "pitch": pitch,
        "gap": gap,
        "centers_x": centers_x,
        "center_y": y_bubble,
        "group_centers_x": group_centers_x,
        "left_marker": {
            "x": left_marker_x,
            "y": y_bubble,
            "size": marker,
        },
        "right_marker": {
            "x": right_marker_x,
            "y": y_bubble,
            "size": marker,
        },
        "label_y": slot["top"] - 6.0,
    }


def _grid_geometry_pt_legacy_4row() -> Dict[str, Any]:
    """Geometria legada 12×4 (só para leitura de cartões já impressos)."""
    slot = slot_rect_pt(ID_GRID_HEIGHT_CM_LEGACY)
    diam = _mm_to_pt(BUBBLE_DIAMETER_MM_LEGACY)
    pitch = _mm_to_pt(BUBBLE_PITCH_MM_LEGACY)
    radius = diam / 2.0
    marker = _mm_to_pt(MARKER_SIZE_MM)
    label_band = 5.0
    hex_band = 4.5
    edge_pad = 1.0
    side_pad = marker + 6.0
    usable_left = slot["left"] + side_pad
    usable_right = slot["right"] - side_pad
    usable_width = usable_right - usable_left
    col_span = pitch * (N_COLS_LEGACY - 1)
    if col_span > usable_width - diam:
        pitch_h = max(pitch * 0.95, (usable_width - diam) / max(N_COLS_LEGACY - 1, 1))
    else:
        pitch_h = pitch
    col_span = pitch_h * (N_COLS_LEGACY - 1)
    x0 = usable_left + (usable_width - col_span) / 2.0
    y_max = slot["top"] - label_band - hex_band - radius - edge_pad
    y_min = slot["bottom"] + radius + edge_pad
    avail = y_max - y_min
    row_span_needed = pitch * (N_ROWS_LEGACY - 1)
    if row_span_needed > avail:
        pitch_v = avail / max(N_ROWS_LEGACY - 1, 1)
    else:
        pitch_v = pitch
        extra = avail - pitch_v * (N_ROWS_LEGACY - 1)
        y_max -= extra / 2.0
    cols_x = [x0 + i * pitch_h for i in range(N_COLS_LEGACY)]
    rows_y = [y_max - j * pitch_v for j in range(N_ROWS_LEGACY)]
    marker_cy = (rows_y[0] + rows_y[-1]) / 2.0
    return {
        "layout": "4x12",
        "slot": slot,
        "radius": radius,
        "diameter": diam,
        "pitch_h": pitch_h,
        "pitch_v": pitch_v,
        "cols_x": cols_x,
        "rows_y": rows_y,
        "left_marker": {
            "x": slot["left"] + 3.0 + marker / 2.0,
            "y": marker_cy,
            "size": marker,
        },
        "right_marker": {
            "x": slot["right"] - 3.0 - marker / 2.0,
            "y": marker_cy,
            "size": marker,
        },
    }


def grid_geometry_px() -> Dict[str, Any]:
    """Centros 1×24 na imagem A4 (y cresce para baixo)."""
    geo_pt = _grid_geometry_pt()
    slot_px = slot_rect_px()
    centers_x = [_pt_x_to_px(x) for x in geo_pt["centers_x"]]
    center_y = _pt_y_to_px(geo_pt["center_y"])
    radius_px = (geo_pt["radius"] / PT_PER_CM) * PX_PER_CM_A4

    def marker_px(m: Dict[str, float]) -> Dict[str, float]:
        size_px = (m["size"] / PT_PER_CM) * PX_PER_CM_A4
        return {
            "cx": _pt_x_to_px(m["x"]),
            "cy": _pt_y_to_px(m["y"]),
            "size": size_px,
        }

    return {
        "layout": "1x24",
        "slot": slot_px,
        "radius": radius_px,
        "centers_x": centers_x,
        "center_y": center_y,
        "group_centers_x": [_pt_x_to_px(x) for x in geo_pt["group_centers_x"]],
        "left_marker": marker_px(geo_pt["left_marker"]),
        "right_marker": marker_px(geo_pt["right_marker"]),
        "pitch": abs(centers_x[1] - centers_x[0]) if len(centers_x) > 1 else _mm_to_px(BUBBLE_PITCH_MM_MIN),
    }


def grid_geometry_px_legacy_4row() -> Dict[str, Any]:
    """Centros legados 4×12 — pode ser removido com IDGRID_ACCEPT_LEGACY_4ROW."""
    geo_pt = _grid_geometry_pt_legacy_4row()
    slot_px = slot_rect_px(ID_GRID_HEIGHT_CM_LEGACY)
    cols_x = [_pt_x_to_px(x) for x in geo_pt["cols_x"]]
    rows_y = [_pt_y_to_px(y) for y in geo_pt["rows_y"]]
    radius_px = (geo_pt["radius"] / PT_PER_CM) * PX_PER_CM_A4

    def marker_px(m: Dict[str, float]) -> Dict[str, float]:
        size_px = (m["size"] / PT_PER_CM) * PX_PER_CM_A4
        return {
            "cx": _pt_x_to_px(m["x"]),
            "cy": _pt_y_to_px(m["y"]),
            "size": size_px,
        }

    return {
        "layout": "4x12",
        "slot": slot_px,
        "radius": radius_px,
        "cols_x": cols_x,
        "rows_y": rows_y,
        "left_marker": marker_px(geo_pt["left_marker"]),
        "right_marker": marker_px(geo_pt["right_marker"]),
    }


def draw_identity_grid(canvas, code: str) -> None:
    """
    Desenha a faixa OMR 1×24 no canvas ReportLab (página A4 atual).

    Não imprime os dígitos hex — só bolhas (preenchidas/vazias), rótulo
    genérico e marcadores. A leitura reconstrói o código a partir das bolhas.
    """
    from reportlab.lib.colors import black, white, HexColor

    text = (code or "").strip().upper()
    if len(text) != ID_GRID_LEN:
        raise ValueError(f"draw_identity_grid exige código de {ID_GRID_LEN} hex, veio {text!r}")

    geo = _grid_geometry_pt()
    slot = geo["slot"]
    radius = geo["radius"]
    flat = code_to_flat_bits(text)

    canvas.setStrokeColor(black)
    canvas.setFillColor(white)
    canvas.setLineWidth(0.8)
    canvas.rect(slot["left"], slot["bottom"], slot["width"], slot["height"], stroke=1, fill=1)

    # Rótulo genérico (sem revelar o código)
    canvas.setFillColor(black)
    canvas.setFont("Helvetica-Bold", 5)
    canvas.drawCentredString(
        (slot["left"] + slot["right"]) / 2.0,
        geo["label_y"],
        LABEL_TEXT,
    )

    # 24 bolhas em 1 linha
    canvas.setLineWidth(0.9)
    cy = geo["center_y"]
    for i, filled in enumerate(flat):
        cx = geo["centers_x"][i]
        if filled:
            canvas.setFillColor(black)
            canvas.circle(cx, cy, radius, stroke=1, fill=1)
        else:
            canvas.setFillColor(white)
            canvas.setStrokeColor(black)
            canvas.circle(cx, cy, radius, stroke=1, fill=1)

    # Marcadores sólidos
    canvas.setFillColor(black)
    for m in (geo["left_marker"], geo["right_marker"]):
        half = m["size"] / 2.0
        canvas.rect(m["x"] - half, m["y"] - half, m["size"], m["size"], stroke=0, fill=1)

    # Moldura leve por grupo
    canvas.setStrokeColor(HexColor("#555555"))
    canvas.setLineWidth(0.35)
    pad = radius + 1.0
    for g in range(N_GROUPS):
        xs = geo["centers_x"][g * BITS_PER_GROUP : (g + 1) * BITS_PER_GROUP]
        left = xs[0] - pad
        right = xs[-1] + pad
        canvas.rect(left, cy - pad, right - left, 2 * pad, stroke=1, fill=0)
