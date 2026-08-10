# -*- coding: utf-8 -*-
"""
Normalização e cálculo oficial da Avaliação de Fluência Leitora (CAEd / ICA).

O frontend (wizard/protótipo) envia contagens por questão (Q1/Q2/Q3) e extras;
o backend calcula PLCM, precisão, níveis e ICA.
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from app.afirme_ler.services.auto_evaluation.metrics import (
    ALGORITHM_VERSION,
    EVALUATION_VERSION,
    calculate_accuracy,
    calculate_ica,
    calculate_plcm,
    fluency_level_2nd_grade,
    precision_level,
)
from app.afirme_ler.services.parsing import get_field

PART_KEYS = ("q1", "q2", "q3")
PART_ALIASES = {
    "q1": ("q1", "lista1", "words", "wordsList"),
    "q2": ("q2", "lista2", "uncommon", "uncommonWords"),
    "q3": ("q3", "texto", "text", "narrative"),
}


def _as_non_negative_int(value: Any, field_name: str) -> Optional[int]:
    if value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} deve ser um inteiro.") from exc
    if parsed < 0:
        raise ValueError(f"{field_name} não pode ser negativo.")
    return parsed


def _as_non_negative_float(value: Any, field_name: str) -> Optional[float]:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} deve ser numérico.") from exc
    if parsed < 0:
        raise ValueError(f"{field_name} não pode ser negativo.")
    return parsed


def _extract_part_raw(payload: dict, part_key: str) -> Optional[dict]:
    for alias in PART_ALIASES[part_key]:
        raw = get_field(payload, alias)
        if isinstance(raw, dict):
            return raw
    return None


def _normalize_part(part_key: str, raw: Optional[dict]) -> Optional[dict]:
    if not raw:
        return None

    words_read = _as_non_negative_int(
        get_field(raw, "wordsRead", "words_read", "wordsTotal", "words_total"),
        f"{part_key}.wordsRead",
    )
    errors_raw = get_field(raw, "errorsCount", "errors_count")
    errors_count = _as_non_negative_int(
        errors_raw if errors_raw is not None else 0,
        f"{part_key}.errorsCount",
    )
    if errors_count is None:
        errors_count = 0

    # errors pode vir como lista de marcações (sem errorsCount)
    if isinstance(get_field(raw, "errors"), list) and errors_raw is None:
        errors_count = len(get_field(raw, "errors"))

    time_seconds = _as_non_negative_float(
        get_field(
            raw,
            "readingTimeSeconds",
            "reading_time_seconds",
            "timeSeconds",
            "time_seconds",
            "durationSeconds",
            "duration_seconds",
        ),
        f"{part_key}.readingTimeSeconds",
    )

    if words_read is None:
        raise ValueError(f"{part_key}.wordsRead é obrigatório quando a parte é enviada.")

    if errors_count > words_read:
        raise ValueError(f"{part_key}.errorsCount não pode ser maior que wordsRead.")

    accuracy = calculate_accuracy(words_read, errors_count)
    plcm = calculate_plcm(words_read, errors_count, float(time_seconds or 0))

    part = {
        "wordsRead": words_read,
        "errorsCount": errors_count,
        "readingTimeSeconds": time_seconds,
        "accuracy": accuracy,
        "plcm": plcm,
        "precisionLevel": precision_level(accuracy),
        "fluencyLevel": fluency_level_2nd_grade(plcm),
    }

    transcript = get_field(raw, "transcript", "transcription", "recognizedText")
    if transcript is not None:
        part["transcript"] = transcript

    markings = get_field(raw, "markings", "errorItems", "error_items")
    if markings is None and isinstance(get_field(raw, "errors"), list):
        markings = get_field(raw, "errors")
    if markings is not None:
        part["markings"] = markings

    overrides = get_field(raw, "overrides", "teacherOverrides", "teacher_overrides")
    if overrides is not None:
        part["overrides"] = overrides

    # Preserva campos extras da parte sem sobrescrever calculados
    reserved = {
        "wordsRead",
        "words_read",
        "wordsTotal",
        "words_total",
        "errorsCount",
        "errors_count",
        "errors",
        "readingTimeSeconds",
        "reading_time_seconds",
        "timeSeconds",
        "time_seconds",
        "durationSeconds",
        "duration_seconds",
        "accuracy",
        "plcm",
        "precisionLevel",
        "fluencyLevel",
        "transcript",
        "transcription",
        "recognizedText",
        "markings",
        "errorItems",
        "error_items",
        "overrides",
        "teacherOverrides",
        "teacher_overrides",
    }
    extras_part = {k: v for k, v in raw.items() if k not in reserved}
    if extras_part:
        part["extras"] = extras_part

    return part


def build_fluency_record(
    payload: dict,
    *,
    comprehension_score: Optional[float] = None,
) -> Tuple[dict, dict]:
    """
    Retorna (fluency_data persistido, metrics_flat para colunas da sessão).
    """
    if not isinstance(payload, dict):
        raise ValueError("fluencyData deve ser um objeto JSON.")

    # Aceita wrapper acidental
    inner = get_field(payload, "fluencyData", "fluency_data")
    if isinstance(inner, dict) and not any(
        get_field(payload, *PART_ALIASES[k]) for k in PART_KEYS
    ):
        payload = inner

    q1 = _normalize_part("q1", _extract_part_raw(payload, "q1"))
    q2 = _normalize_part("q2", _extract_part_raw(payload, "q2"))
    q3 = _normalize_part("q3", _extract_part_raw(payload, "q3"))

    # Compat protótipo flat → assume Q3 (texto narrativo)
    if q3 is None and get_field(payload, "wordsRead", "words_read") is not None:
        q3 = _normalize_part(
            "q3",
            {
                "wordsRead": get_field(payload, "wordsRead", "words_read"),
                "errorsCount": get_field(
                    payload, "errorsCount", "errors_count", default=0
                ),
                "readingTimeSeconds": get_field(
                    payload,
                    "readingTimeSeconds",
                    "reading_time_seconds",
                    "timeSeconds",
                    "time_seconds",
                ),
                "transcript": get_field(payload, "transcript", "transcription"),
                "markings": get_field(payload, "markings", "errors"),
                "overrides": get_field(payload, "overrides"),
            },
        )

    if not any((q1, q2, q3)):
        raise ValueError(
            "Informe ao menos q1, q2 ou q3 (ou wordsRead/errorsCount/readingTimeSeconds)."
        )

    prosody = get_field(payload, "prosodyLevel", "prosody_level")
    if prosody is not None:
        try:
            prosody = int(prosody)
        except (TypeError, ValueError) as exc:
            raise ValueError("prosodyLevel deve ser um inteiro entre 1 e 5.") from exc
        if prosody < 1 or prosody > 5:
            raise ValueError("prosodyLevel deve ser um inteiro entre 1 e 5.")

    kind = get_field(payload, "kind", "assessmentKind", default="FLUENCY")
    if isinstance(kind, str):
        kind = kind.strip().upper() or "FLUENCY"

    lista1_acc = (q1 or {}).get("accuracy")
    lista2_acc = (q2 or {}).get("accuracy")
    texto_acc = (q3 or {}).get("accuracy")
    plcm_for_ica = (q3 or {}).get("plcm")
    if plcm_for_ica is None:
        plcm_for_ica = (q1 or {}).get("plcm")

    ica = calculate_ica(
        accuracy_lista1=lista1_acc,
        accuracy_lista2=lista2_acc,
        accuracy_texto=texto_acc,
        comprehension=comprehension_score,
        plcm=plcm_for_ica,
    )

    # Métricas “principais” do relatório: preferem Q3 (texto)
    primary = q3 or q1 or q2 or {}
    metrics = {
        "calculatedPlcm": primary.get("plcm"),
        "calculatedAccuracy": primary.get("accuracy"),
        "precisionLevel": primary.get("precisionLevel"),
        "fluencyLevel": primary.get("fluencyLevel"),
        "icaScore": (ica or {}).get("icaScore"),
        "icaBreakdown": ica,
        "algorithmVersion": ALGORITHM_VERSION,
        "evaluationVersion": EVALUATION_VERSION,
    }

    extras = get_field(payload, "extras", default={})
    if extras is None:
        extras = {}
    if not isinstance(extras, dict):
        raise ValueError("extras deve ser um objeto JSON.")

    fluency_data: Dict[str, Any] = {
        "kind": kind,
        "caderno": get_field(payload, "caderno"),
        "notReadReason": get_field(payload, "notReadReason", "not_read_reason"),
        "prosodyLevel": prosody,
        "q1": q1,
        "q2": q2,
        "q3": q3,
        "extras": extras,
        "metrics": metrics,
    }

    # Compat: espelha totais flat do protótipo no root (derivados)
    if primary:
        fluency_data["wordsRead"] = primary.get("wordsRead")
        fluency_data["errorsCount"] = primary.get("errorsCount")
        fluency_data["readingTimeSeconds"] = primary.get("readingTimeSeconds")
        fluency_data["calculatedPlcm"] = metrics["calculatedPlcm"]
        fluency_data["calculatedAccuracy"] = metrics["calculatedAccuracy"]
        fluency_data["icaScore"] = metrics["icaScore"]

    flat_columns = {
        "calculated_plcm": metrics["calculatedPlcm"],
        "calculated_accuracy": metrics["calculatedAccuracy"],
        "precision_level": metrics["precisionLevel"],
        "fluency_level": metrics["fluencyLevel"],
        "ica_score": metrics["icaScore"],
        "ica_breakdown": ica,
        "prosody_level": prosody,
    }
    return fluency_data, flat_columns


def refresh_ica_in_fluency_data(
    fluency_data: Optional[dict],
    *,
    comprehension_score: Optional[float],
) -> Tuple[Optional[dict], dict]:
    """Recalcula ICA quando a compreensão muda, preservando q1/q2/q3."""
    if not isinstance(fluency_data, dict):
        return fluency_data, {}

    q1 = fluency_data.get("q1") if isinstance(fluency_data.get("q1"), dict) else None
    q2 = fluency_data.get("q2") if isinstance(fluency_data.get("q2"), dict) else None
    q3 = fluency_data.get("q3") if isinstance(fluency_data.get("q3"), dict) else None

    lista1_acc = (q1 or {}).get("accuracy")
    lista2_acc = (q2 or {}).get("accuracy")
    texto_acc = (q3 or {}).get("accuracy")
    plcm_for_ica = (q3 or {}).get("plcm")
    if plcm_for_ica is None:
        plcm_for_ica = (q1 or {}).get("plcm")

    ica = calculate_ica(
        accuracy_lista1=lista1_acc,
        accuracy_lista2=lista2_acc,
        accuracy_texto=texto_acc,
        comprehension=comprehension_score,
        plcm=plcm_for_ica,
    )

    primary = q3 or q1 or q2 or {}
    metrics = dict(fluency_data.get("metrics") or {})
    metrics.update(
        {
            "calculatedPlcm": primary.get("plcm"),
            "calculatedAccuracy": primary.get("accuracy"),
            "precisionLevel": primary.get("precisionLevel"),
            "fluencyLevel": primary.get("fluencyLevel"),
            "icaScore": (ica or {}).get("icaScore"),
            "icaBreakdown": ica,
            "algorithmVersion": ALGORITHM_VERSION,
            "evaluationVersion": EVALUATION_VERSION,
        }
    )
    updated = dict(fluency_data)
    updated["metrics"] = metrics
    updated["icaScore"] = metrics["icaScore"]
    updated["calculatedPlcm"] = metrics["calculatedPlcm"]
    updated["calculatedAccuracy"] = metrics["calculatedAccuracy"]

    flat_columns = {
        "calculated_plcm": metrics["calculatedPlcm"],
        "calculated_accuracy": metrics["calculatedAccuracy"],
        "precision_level": metrics["precisionLevel"],
        "fluency_level": metrics["fluencyLevel"],
        "ica_score": metrics["icaScore"],
        "ica_breakdown": ica,
        "prosody_level": updated.get("prosodyLevel"),
    }
    return updated, flat_columns
