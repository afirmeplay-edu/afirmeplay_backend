# -*- coding: utf-8 -*-
"""Aproximação fonética leve para português brasileiro (MVP)."""
from __future__ import annotations

import re

from app.afirme_ler.services.auto_evaluation.normalize import normalize_text


def to_phonetic(token: str) -> str:
    """
    Aproximação fonética leve (não é IPA).
    Espelha tratamentos comuns do MVP front: ç→ss, qu→k, etc.
    """
    if token is None:
        return ""
    # Aplicar ç→ss antes de remover acentos (senão ç vira c)
    text = str(token).lower().strip()
    text = text.replace("ç", "ss").replace("Ç", "ss")
    text = normalize_text(text)
    if not text:
        return ""

    # Digrafos / padrões comuns em pt-BR (ordem importa)
    replacements = (
        (r"ch", "x"),
        (r"lh", "li"),
        (r"nh", "ni"),
        (r"qu", "k"),
        (r"gu(?=[ei])", "g"),
        (r"rr", "r"),
        (r"ss", "s"),
        (r"sc(?=[ei])", "s"),
        (r"xc(?=[ei])", "s"),
        (r"ph", "f"),
        (r"th", "t"),
        (r"w", "v"),
        (r"y", "i"),
        (r"h", ""),
    )
    for pattern, repl in replacements:
        text = re.sub(pattern, repl, text)

    # Colapsar letras repetidas residualmente
    text = re.sub(r"(.)\1+", r"\1", text)
    return text