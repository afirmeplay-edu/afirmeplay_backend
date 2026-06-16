# -*- coding: utf-8 -*-
"""
Layout da capa Afirme (capalimpa.png).

Fonte única de coordenadas para WeasyPrint (cm) e overlay ReportLab (aluno).
Arquivo: app/assets/afirme_cover_layout.json
"""

from __future__ import annotations

import copy
import json
import os
from typing import Any, Dict, Optional, Tuple

A4_HEIGHT_PT = 841.89
CM_TO_PT = 72.0 / 2.54

DEFAULT_LAYOUT: Dict[str, Any] = {
    "title": {"top_cm": 4.5, "left_cm": 1.4, "right_cm": 1.4, "font_pt": 21},
    "subtitle": {"top_cm": 7.1, "left_cm": 1.4, "right_cm": 1.4, "font_pt": 12.5},
    "institution": {"top_cm": 17.2, "left_cm": 8.0, "right_cm": 2.2, "font_pt": 10},
    "grade": {"top_cm": 19.3, "left_cm": 6.5, "width_cm": 4.5, "font_pt": 10},
    "class": {"top_cm": 19.3, "left_cm": 16.5, "width_cm": 4.5, "font_pt": 10},
    "student": {"top_cm": 21.8, "left_cm": 7.5, "font_pt": 10, "max_chars": 42},
}


def default_layout_path() -> str:
    return os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "assets",
        "afirme_cover_layout.json",
    )


def _deep_merge(base: Dict[str, Any], patch: Dict[str, Any]) -> Dict[str, Any]:
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def load_afirme_cover_layout(path: Optional[str] = None) -> Dict[str, Any]:
    """Carrega JSON de layout; defaults embutidos se arquivo ausente."""
    layout = copy.deepcopy(DEFAULT_LAYOUT)
    layout_path = path or default_layout_path()
    if os.path.exists(layout_path):
        with open(layout_path, encoding="utf-8") as fh:
            file_data = json.load(fh)
        if isinstance(file_data, dict):
            _deep_merge(layout, file_data)
    return layout


def student_overlay_coords_pt(layout: Dict[str, Any]) -> Tuple[float, float, int]:
    """Converte posição do aluno (cm do topo) para ReportLab (pt, origem inferior)."""
    student = layout.get("student") or {}
    left_cm = float(student.get("left_cm", 7.5))
    top_cm = float(student.get("top_cm", 21.8))
    font_pt = int(student.get("font_pt", 10))
    x_pt = left_cm * CM_TO_PT
    y_pt = A4_HEIGHT_PT - (top_cm * CM_TO_PT)
    return x_pt, y_pt, font_pt


def student_max_chars(layout: Dict[str, Any]) -> int:
    return int((layout.get("student") or {}).get("max_chars", 42))
