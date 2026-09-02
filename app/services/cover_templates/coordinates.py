# -*- coding: utf-8 -*-
"""Conversão entre coordenadas normalizadas (origem no topo) e pontos PDF (origem inferior)."""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from app.services.cover_templates.exceptions import CoverTemplateValidationError


def pt_to_mm(pt: float) -> float:
    return float(pt) * 25.4 / 72.0


def mm_to_pt(mm: float) -> float:
    return float(mm) * 72.0 / 25.4


def norm_to_pt(
    x_norm: float,
    y_norm_from_top: float,
    w_norm: float,
    h_norm: float,
    page_width_pt: float,
    page_height_pt: float,
) -> Tuple[float, float, float, float]:
    """
    Converte caixa normalizada (0–1, origem no topo-esquerda) para
    pontos PDF (origem no canto inferior esquerdo).

    y_pt retornado é a borda inferior da caixa.
    """
    width_pt = float(w_norm) * float(page_width_pt)
    height_pt = float(h_norm) * float(page_height_pt)
    x_pt = float(x_norm) * float(page_width_pt)
    top_from_top_pt = float(y_norm_from_top) * float(page_height_pt)
    y_pt = float(page_height_pt) - top_from_top_pt - height_pt
    return x_pt, y_pt, width_pt, height_pt


def pt_to_norm(
    x_pt: float,
    y_pt: float,
    width_pt: float,
    height_pt: float,
    page_width_pt: float,
    page_height_pt: float,
) -> Tuple[float, float, float, float]:
    """Inverso de norm_to_pt. y_norm_from_top é o topo da caixa."""
    x_norm = float(x_pt) / float(page_width_pt) if page_width_pt else 0.0
    w_norm = float(width_pt) / float(page_width_pt) if page_width_pt else 0.0
    h_norm = float(height_pt) / float(page_height_pt) if page_height_pt else 0.0
    top_from_top_pt = float(page_height_pt) - float(y_pt) - float(height_pt)
    y_norm_from_top = top_from_top_pt / float(page_height_pt) if page_height_pt else 0.0
    return x_norm, y_norm_from_top, w_norm, h_norm


def _as_float(value: Any, name: str) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise CoverTemplateValidationError(f"Campo {name} deve ser numérico") from exc


def canonicalize_field_box(
    field: Dict[str, Any],
    page_width_pt: float,
    page_height_pt: float,
) -> Dict[str, float]:
    """
    Aceita coordenadas normalizadas (preferidas pelo editor) ou pt.
    Devolve as quatro medidas em ambos os sistemas.
    """
    has_norm = all(
        field.get(k) is not None
        for k in ("x_norm", "y_norm_from_top", "w_norm", "h_norm")
    )
    has_pt = all(
        field.get(k) is not None for k in ("x_pt", "y_pt", "width_pt", "height_pt")
    )
    if not has_norm and not has_pt:
        raise CoverTemplateValidationError(
            "Cada campo precisa de coordenadas normalizadas "
            "(x_norm, y_norm_from_top, w_norm, h_norm) ou em pontos "
            "(x_pt, y_pt, width_pt, height_pt)"
        )

    if has_norm:
        x_norm = _as_float(field.get("x_norm"), "x_norm")
        y_norm = _as_float(field.get("y_norm_from_top"), "y_norm_from_top")
        w_norm = _as_float(field.get("w_norm"), "w_norm")
        h_norm = _as_float(field.get("h_norm"), "h_norm")
        for name, value in (
            ("x_norm", x_norm),
            ("y_norm_from_top", y_norm),
            ("w_norm", w_norm),
            ("h_norm", h_norm),
        ):
            if value < -0.01 or value > 1.01:
                raise CoverTemplateValidationError(
                    f"{name} deve estar entre 0 e 1 (recebido: {value})"
                )
        x_pt, y_pt, width_pt, height_pt = norm_to_pt(
            x_norm, y_norm, w_norm, h_norm, page_width_pt, page_height_pt
        )
    else:
        x_pt = _as_float(field.get("x_pt"), "x_pt")
        y_pt = _as_float(field.get("y_pt"), "y_pt")
        width_pt = _as_float(field.get("width_pt"), "width_pt")
        height_pt = _as_float(field.get("height_pt"), "height_pt")
        x_norm, y_norm, w_norm, h_norm = pt_to_norm(
            x_pt, y_pt, width_pt, height_pt, page_width_pt, page_height_pt
        )

    if width_pt <= 0 or height_pt <= 0:
        raise CoverTemplateValidationError("width_pt e height_pt devem ser positivos")

    # Folga mínima: centro da caixa precisa cair dentro da página.
    if x_pt + width_pt < 0 or y_pt + height_pt < 0:
        raise CoverTemplateValidationError("Campo está fora da página")
    if x_pt > page_width_pt or y_pt > page_height_pt:
        raise CoverTemplateValidationError("Campo está fora da página")

    return {
        "x_pt": round(x_pt, 4),
        "y_pt": round(y_pt, 4),
        "width_pt": round(width_pt, 4),
        "height_pt": round(height_pt, 4),
        "x_norm": round(x_norm, 6),
        "y_norm_from_top": round(y_norm, 6),
        "w_norm": round(w_norm, 6),
        "h_norm": round(h_norm, 6),
    }
