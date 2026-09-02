# -*- coding: utf-8 -*-
"""Métricas oficiais Afirme Ler (Fluência Leitora / alinhamento de leitura)."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

from app.afirme_ler.services.auto_evaluation.align import (
    WINDOW_TEXT,
    WINDOW_WORD_LIST,
    AlignmentResult,
    align_tokens,
)
from app.afirme_ler.services.auto_evaluation.normalize import tokenize

ALGORITHM_VERSION = "1.0.0"
EVALUATION_VERSION = "1.0.0"


@dataclass
class ReadingPartMetrics:
    part: str
    words_read: int
    errors_count: int
    omitted_count: int
    extra_count: int
    correct_count: int
    accuracy: Optional[float]
    plcm: Optional[float]
    precision_level: Optional[str]
    fluency_level: Optional[str]
    duration_seconds: Optional[float]
    transcript: str
    alignment: List[Dict[str, Any]]


def calculate_plcm(words_read: int, errors_count: int, duration_seconds: float) -> Optional[float]:
    if duration_seconds is None or duration_seconds <= 0:
        return None
    correct = max(0, words_read - errors_count)
    return round(correct / (duration_seconds / 60.0), 2)


def calculate_accuracy(words_read: int, errors_count: int) -> Optional[float]:
    if words_read <= 0:
        return None
    correct = max(0, words_read - errors_count)
    return round(100.0 * correct / words_read, 2)


def precision_level(accuracy: Optional[float]) -> Optional[str]:
    if accuracy is None:
        return None
    if accuracy >= 95:
        return "Independente"
    if accuracy >= 90:
        return "Instrucional"
    return "Frustração"


def fluency_level_2nd_grade(plcm: Optional[float]) -> Optional[str]:
    if plcm is None:
        return None
    if plcm < 40:
        return "abaixo"
    if plcm <= 60:
        return "esperado"
    return "acima"


def fluency_score_for_ica(plcm: Optional[float]) -> Optional[float]:
    if plcm is None:
        return None
    return round(min(100.0, (plcm / 60.0) * 100.0), 2)


def calculate_comprehension(correct: int, total: int) -> Optional[float]:
    if total <= 0:
        return None
    return round(100.0 * correct / total, 2)


ICA_BASE_WEIGHTS = {
    "lista1": 0.25,
    "lista2": 0.15,
    "texto": 0.30,
    "compreensao": 0.20,
    "fluencia": 0.10,
}


def leiturimetro_level(ica_score: Optional[float]) -> Optional[int]:
    """Níveis 1–6 do Leiturômetro a partir do ICA (0–100)."""
    if ica_score is None:
        return None
    score = float(ica_score)
    if score < 0:
        return 1
    if score <= 20:
        return 1
    if score <= 40:
        return 2
    if score <= 55:
        return 3
    if score <= 70:
        return 4
    if score <= 85:
        return 5
    return 6


def calculate_ica(
    *,
    accuracy_lista1: Optional[float],
    accuracy_lista2: Optional[float],
    accuracy_texto: Optional[float],
    comprehension: Optional[float],
    plcm: Optional[float],
    skipped_components: Optional[List[str]] = None,
) -> Optional[Dict[str, Any]]:
    """
    ICA =
      0.25 * Precisão Lista 1
    + 0.15 * Precisão Lista 2
    + 0.30 * Precisão Texto
    + 0.20 * Compreensão
    + 0.10 * Fluência(min(100, PLCM/60*100))

    Partes em ``skipped_components`` são excluídas e os pesos restantes
    são renormalizados (soma = 1). Componentes não-skipped com valor
    ``None`` deixam o ICA incompleto (``null``), exceto quando há skip.
    """
    fluency = fluency_score_for_ica(plcm)
    skipped = {str(s).strip().lower() for s in (skipped_components or []) if s}
    raw = {
        "lista1": accuracy_lista1,
        "lista2": accuracy_lista2,
        "texto": accuracy_texto,
        "compreensao": comprehension,
        "fluencia": fluency,
    }

    active: Dict[str, tuple] = {}
    for key, base_weight in ICA_BASE_WEIGHTS.items():
        if key in skipped:
            continue
        value = raw[key]
        if value is None:
            # Sem skip: exige todos os componentes (compat).
            if not skipped:
                return None
            continue
        active[key] = (float(value), base_weight)

    if not active:
        return None

    weight_sum = sum(w for _, w in active.values())
    if weight_sum <= 0:
        return None

    weights_used = {
        key: round(weight / weight_sum, 4) for key, (_, weight) in active.items()
    }
    score = sum(value * weights_used[key] for key, (value, _) in active.items())

    return {
        "icaScore": round(score, 2),
        "weights": dict(ICA_BASE_WEIGHTS),
        "weightsUsed": weights_used,
        "skippedParts": sorted(skipped),
        "leiturimetroLevel": leiturimetro_level(score),
        "components": {
            "lista1Accuracy": accuracy_lista1,
            "lista2Accuracy": accuracy_lista2,
            "textoAccuracy": accuracy_texto,
            "comprehension": comprehension,
            "fluency": fluency,
            "plcm": plcm,
        },
    }


def evaluate_reading(
    expected_tokens: List[str],
    recognized_text: str,
    *,
    part: str,
    duration_seconds: Optional[float],
    content_kind: str = "text",
) -> ReadingPartMetrics:
    recognized_tokens = tokenize(recognized_text)
    window = WINDOW_WORD_LIST if content_kind == "word_list" else WINDOW_TEXT
    alignment: AlignmentResult = align_tokens(
        expected_tokens, recognized_tokens, window=window
    )
    accuracy = calculate_accuracy(alignment.words_read, alignment.errors_count)
    plcm = calculate_plcm(
        alignment.words_read,
        alignment.errors_count,
        float(duration_seconds or 0),
    )
    return ReadingPartMetrics(
        part=part,
        words_read=alignment.words_read,
        errors_count=alignment.errors_count,
        omitted_count=alignment.omitted_count,
        extra_count=alignment.extra_count,
        correct_count=alignment.correct_count,
        accuracy=accuracy,
        plcm=plcm,
        precision_level=precision_level(accuracy),
        fluency_level=fluency_level_2nd_grade(plcm),
        duration_seconds=duration_seconds,
        transcript=recognized_text,
        alignment=[asdict(item) for item in alignment.items],
    )
