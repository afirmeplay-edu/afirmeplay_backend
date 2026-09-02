# -*- coding: utf-8 -*-
"""Engine de avaliação automática de leitura falada (Leitura Guiada Automática)."""

from app.afirme_ler.services.auto_evaluation.metrics import (
    ALGORITHM_VERSION,
    EVALUATION_VERSION,
    evaluate_reading,
)
from app.afirme_ler.services.auto_evaluation.normalize import normalize_text, tokenize

__all__ = [
    "ALGORITHM_VERSION",
    "EVALUATION_VERSION",
    "evaluate_reading",
    "normalize_text",
    "tokenize",
]
