# -*- coding: utf-8 -*-
"""
Normalização e cálculo oficial da Avaliação de Fluência Leitora (CAEd / ICA).

O frontend (wizard/protótipo) envia contagens por questão (Q1/Q2/Q3) e extras;
o backend calcula PLCM, precisão, níveis e ICA.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from app.afirme_ler.services.auto_evaluation.metrics import (
    ALGORITHM_VERSION,
    EVALUATION_VERSION,
    calculate_accuracy,
    calculate_ica,
    calculate_plcm,
    fluency_level_2nd_grade,
    leiturimetro_level,
    precision_level,
)
from app.afirme_ler.services.parsing import get_field

PART_KEYS = ("q1", "q2", "q3")
PART_ALIASES = {
    "q1": ("q1", "lista1", "words", "wordsList"),
    "q2": ("q2", "lista2", "uncommon", "uncommonWords"),
    "q3": ("q3", "texto", "text", "narrative"),
}

WORD_STATUSES = frozenset(
    {"nao_leu", "acertou", "inventou", "silabou", "soletrou", "errou"}
)
NOT_READ_REASONS = frozenset(
    {"nao_se_aplica", "recusou", "nao_consegue", "nao_sabe"}
)
MARKING_SOURCES = frozenset({"ia", "manual", "timeout"})
PART_TO_ICA_COMPONENT = {
    "q1": "lista1",
    "q2": "lista2",
    "q3": "texto",
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


def _as_bool(value: Any, field_name: str) -> Optional[bool]:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in ("true", "1", "sim", "yes"):
            return True
        if lowered in ("false", "0", "nao", "não", "no"):
            return False
    raise ValueError(f"{field_name} deve ser booleano.")


def _normalize_not_read_reason(value: Any, field_name: str) -> Optional[str]:
    if value is None or value == "":
        return None
    reason = str(value).strip().lower()
    if reason not in NOT_READ_REASONS:
        raise ValueError(
            f"{field_name} inválido. Use: {', '.join(sorted(NOT_READ_REASONS))}."
        )
    return reason


def _normalize_markings(raw: Any, field_name: str) -> List[dict]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError(f"{field_name} deve ser uma lista.")
    result: List[dict] = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"{field_name}[{i}] deve ser um objeto.")
        index = _as_non_negative_int(
            get_field(item, "index", "position", default=i),
            f"{field_name}[{i}].index",
        )
        word = get_field(item, "word", "token", default="")
        status_raw = get_field(item, "status")
        status = None
        if status_raw is not None and status_raw != "":
            status = str(status_raw).strip().lower()
            if status not in WORD_STATUSES:
                raise ValueError(
                    f"{field_name}[{i}].status inválido. "
                    f"Use: {', '.join(sorted(WORD_STATUSES))}."
                )
        marking: Dict[str, Any] = {
            "index": index if index is not None else i,
            "word": str(word) if word is not None else "",
            "status": status,
        }
        source = get_field(item, "source")
        if source is not None and source != "":
            source_norm = str(source).strip().lower()
            if source_norm not in MARKING_SOURCES:
                raise ValueError(
                    f"{field_name}[{i}].source inválido. "
                    f"Use: {', '.join(sorted(MARKING_SOURCES))}."
                )
            marking["source"] = source_norm
        result.append(marking)
    return result


def _normalize_lines(raw: Any, field_name: str) -> List[dict]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError(f"{field_name} deve ser uma lista.")
    lines: List[dict] = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            raise ValueError(f"{field_name}[{i}] deve ser um objeto.")
        line_index = _as_non_negative_int(
            get_field(item, "lineIndex", "line_index", default=i),
            f"{field_name}[{i}].lineIndex",
        )
        text = get_field(item, "text", default="")
        wrong = _as_non_negative_int(
            get_field(item, "wrongWordsCount", "wrong_words_count", default=0),
            f"{field_name}[{i}].wrongWordsCount",
        )
        lines.append(
            {
                "lineIndex": line_index if line_index is not None else i,
                "text": str(text) if text is not None else "",
                "wrongWordsCount": wrong if wrong is not None else 0,
            }
        )
    return lines


def _extract_part_raw(payload: dict, part_key: str) -> Any:
    """Retorna o valor bruto da parte (dict, None se chave explícita, ou sentinel)."""
    for alias in PART_ALIASES[part_key]:
        if alias in payload:
            return payload[alias]
        snake = "".join(
            f"_{c.lower()}" if c.isupper() else c for c in alias
        ).lstrip("_")
        if snake in payload:
            return payload[snake]
    # camelCase variants via get_field only if present
    raw = get_field(payload, *PART_ALIASES[part_key])
    if isinstance(raw, dict):
        return raw
    return _MISSING


_MISSING = object()


def _part_is_skipped(part: Optional[dict]) -> bool:
    if not isinstance(part, dict):
        return False
    if part.get("skipped") is True:
        return True
    reason = part.get("notReadReason")
    return bool(reason) and reason != "nao_se_aplica"


def collect_skipped_ica_components(
    q1: Optional[dict],
    q2: Optional[dict],
    q3: Optional[dict],
) -> List[str]:
    skipped: List[str] = []
    for part_key, part in (("q1", q1), ("q2", q2), ("q3", q3)):
        if _part_is_skipped(part):
            skipped.append(PART_TO_ICA_COMPONENT[part_key])
    # Fluência ICA usa PLCM do texto; se Q3 skipped, fluência também sai
    if "texto" in skipped:
        skipped.append("fluencia")
    return skipped


def _default_last_word_position(
    part_key: str,
    words_read: Optional[int],
    part: Dict[str, Any],
) -> int:
    """Posição 1-based da última palavra avaliada. 0 se não leu."""
    if words_read:
        return words_read
    markings = part.get("markings") if isinstance(part.get("markings"), list) else []
    evaluated = [
        item.get("index")
        for item in markings
        if isinstance(item, dict) and item.get("status")
    ]
    evaluated = [idx for idx in evaluated if isinstance(idx, int)]
    if evaluated:
        return max(evaluated) + 1
    if part_key == "q3":
        total = part.get("totalWords")
        unread = part.get("unreadAfterEnd")
        if total is not None and unread is not None:
            return max(0, int(total) - int(unread))
    return 0


def _normalize_part(part_key: str, raw: Optional[dict]) -> Optional[dict]:
    if not raw:
        return None
    if not isinstance(raw, dict):
        raise ValueError(f"{part_key} deve ser um objeto JSON.")

    skipped = _as_bool(get_field(raw, "skipped"), f"{part_key}.skipped") or False
    not_read_reason = _normalize_not_read_reason(
        get_field(raw, "notReadReason", "not_read_reason"),
        f"{part_key}.notReadReason",
    )
    if not_read_reason and not_read_reason != "nao_se_aplica":
        skipped = True

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

    if skipped:
        words_read = words_read if words_read is not None else 0
        errors_count = errors_count if errors_count is not None else 0
        time_seconds = time_seconds if time_seconds is not None else 0.0
    elif words_read is None:
        raise ValueError(f"{part_key}.wordsRead é obrigatório quando a parte é enviada.")

    if errors_count > words_read:
        raise ValueError(f"{part_key}.errorsCount não pode ser maior que wordsRead.")

    accuracy = None if skipped else calculate_accuracy(words_read, errors_count)
    plcm = None if skipped else calculate_plcm(
        words_read, errors_count, float(time_seconds or 0)
    )

    part: Dict[str, Any] = {
        "wordsRead": words_read,
        "errorsCount": errors_count,
        "readingTimeSeconds": time_seconds,
        "skipped": skipped,
        "notReadReason": not_read_reason,
        "accuracy": accuracy,
        "plcm": plcm,
        "precisionLevel": None if skipped else precision_level(accuracy),
        "fluencyLevel": None if skipped else fluency_level_2nd_grade(plcm),
    }

    last_pos = get_field(raw, "lastWordPosition", "last_word_position")
    if last_pos is not None:
        part["lastWordPosition"] = _as_non_negative_int(
            last_pos, f"{part_key}.lastWordPosition"
        )

    transcript = get_field(raw, "transcript", "transcription", "recognizedText")
    if transcript is not None:
        part["transcript"] = transcript
    elif skipped:
        part["transcript"] = None

    markings = get_field(raw, "markings", "errorItems", "error_items")
    if markings is None and isinstance(get_field(raw, "errors"), list):
        markings = get_field(raw, "errors")
    if markings is not None:
        part["markings"] = _normalize_markings(markings, f"{part_key}.markings")
    elif skipped:
        part["markings"] = []
    elif part_key in ("q1", "q2") and markings is None:
        # Q1/Q2: markings obrigatório no contrato novo — aceita vazio se enviado;
        # se omitido e não skipped, persiste lista vazia para compat.
        part["markings"] = []

    overrides = get_field(raw, "overrides", "teacherOverrides", "teacher_overrides")
    if overrides is not None:
        part["overrides"] = overrides

    stt_provider = get_field(raw, "sttProvider", "stt_provider")
    if stt_provider is not None:
        part["sttProvider"] = stt_provider

    if part_key == "q3":
        total_words = get_field(raw, "totalWords", "total_words")
        if total_words is not None:
            part["totalWords"] = _as_non_negative_int(
                total_words, f"{part_key}.totalWords"
            )
        unread = get_field(raw, "unreadAfterEnd", "unread_after_end")
        if unread is not None:
            part["unreadAfterEnd"] = _as_non_negative_int(
                unread, f"{part_key}.unreadAfterEnd"
            )
        elif skipped:
            part["unreadAfterEnd"] = 0
        obeyed = get_field(raw, "obeyedSensePauses", "obeyed_sense_pauses")
        if obeyed is not None:
            part["obeyedSensePauses"] = _as_bool(
                obeyed, f"{part_key}.obeyedSensePauses"
            )
        elif skipped:
            part["obeyedSensePauses"] = None
        lines = get_field(raw, "lines")
        if lines is not None:
            part["lines"] = _normalize_lines(lines, f"{part_key}.lines")
        elif skipped:
            part["lines"] = []

    if "lastWordPosition" not in part:
        # 1-based; 0 se não leu. Q3 também persiste (enviado ou derivado).
        if skipped:
            part["lastWordPosition"] = 0
        else:
            part["lastWordPosition"] = _default_last_word_position(
                part_key, words_read, part
            )

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
        "skipped",
        "notReadReason",
        "not_read_reason",
        "lastWordPosition",
        "last_word_position",
        "sttProvider",
        "stt_provider",
        "totalWords",
        "total_words",
        "unreadAfterEnd",
        "unread_after_end",
        "obeyedSensePauses",
        "obeyed_sense_pauses",
        "lines",
        "extras",
    }
    extras_part = {k: v for k, v in raw.items() if k not in reserved}
    nested_extras = get_field(raw, "extras")
    if isinstance(nested_extras, dict):
        extras_part = {**extras_part, **nested_extras}
    if extras_part:
        part["extras"] = extras_part

    return part


def merge_fluency_payload(
    existing: Optional[dict],
    incoming: dict,
) -> dict:
    """
    Merge incremental: partes omitidas no incoming são preservadas do existing.
    Parte enviada como null remove a parte.
    """
    if not isinstance(incoming, dict):
        raise ValueError("fluencyData deve ser um objeto JSON.")

    base = dict(existing) if isinstance(existing, dict) else {}
    inner = get_field(incoming, "fluencyData", "fluency_data")
    if isinstance(inner, dict) and not any(
        alias in incoming for k in PART_KEYS for alias in PART_ALIASES[k]
    ):
        incoming = inner

    merged: Dict[str, Any] = {
        "kind": base.get("kind") or "FLUENCY",
        "caderno": base.get("caderno"),
        "prosodyLevel": base.get("prosodyLevel"),
        "notReadReason": base.get("notReadReason"),
        "q1": base.get("q1"),
        "q2": base.get("q2"),
        "q3": base.get("q3"),
        "extras": dict(base.get("extras") or {})
        if isinstance(base.get("extras"), dict)
        else {},
    }

    if "kind" in incoming or "assessmentKind" in incoming:
        merged["kind"] = get_field(incoming, "kind", "assessmentKind") or "FLUENCY"
    if "caderno" in incoming:
        merged["caderno"] = incoming.get("caderno")
    if "prosodyLevel" in incoming or "prosody_level" in incoming:
        merged["prosodyLevel"] = get_field(incoming, "prosodyLevel", "prosody_level")
    if "notReadReason" in incoming or "not_read_reason" in incoming:
        merged["notReadReason"] = get_field(
            incoming, "notReadReason", "not_read_reason"
        )

    for part_key in PART_KEYS:
        raw = _extract_part_raw(incoming, part_key)
        if raw is _MISSING:
            continue
        if raw is None:
            merged[part_key] = None
        elif isinstance(raw, dict):
            merged[part_key] = raw
        else:
            raise ValueError(f"{part_key} deve ser um objeto JSON ou null.")

    extras_in = get_field(incoming, "extras")
    if isinstance(extras_in, dict):
        merged["extras"] = {**merged["extras"], **extras_in}

    # Flat prototype → q3 se wordsRead no root e q3 não veio
    if merged.get("q3") is None and get_field(
        incoming, "wordsRead", "words_read"
    ) is not None:
        if _extract_part_raw(incoming, "q3") is _MISSING and not isinstance(
            base.get("q3"), dict
        ):
            merged["q3"] = {
                "wordsRead": get_field(incoming, "wordsRead", "words_read"),
                "errorsCount": get_field(
                    incoming, "errorsCount", "errors_count", default=0
                ),
                "readingTimeSeconds": get_field(
                    incoming,
                    "readingTimeSeconds",
                    "reading_time_seconds",
                    "timeSeconds",
                    "time_seconds",
                ),
                "transcript": get_field(incoming, "transcript", "transcription"),
                "markings": get_field(incoming, "markings", "errors"),
                "overrides": get_field(incoming, "overrides"),
            }

    return merged


def build_fluency_record(
    payload: dict,
    *,
    comprehension_score: Optional[float] = None,
    existing: Optional[dict] = None,
) -> Tuple[dict, dict]:
    """
    Retorna (fluency_data persistido, metrics_flat para colunas da sessão).

    Se ``existing`` for passado, faz merge incremental antes de normalizar.
    """
    if not isinstance(payload, dict):
        raise ValueError("fluencyData deve ser um objeto JSON.")

    merged_payload = merge_fluency_payload(existing, payload)

    q1 = _normalize_part(
        "q1",
        merged_payload.get("q1")
        if isinstance(merged_payload.get("q1"), dict)
        else None,
    )
    q2 = _normalize_part(
        "q2",
        merged_payload.get("q2")
        if isinstance(merged_payload.get("q2"), dict)
        else None,
    )
    q3 = _normalize_part(
        "q3",
        merged_payload.get("q3")
        if isinstance(merged_payload.get("q3"), dict)
        else None,
    )

    if not any((q1, q2, q3)) and existing is None:
        raise ValueError(
            "Informe ao menos q1, q2 ou q3 (ou wordsRead/errorsCount/readingTimeSeconds)."
        )
    if not any((q1, q2, q3)) and isinstance(existing, dict):
        # Merge sem partes novas e existing sem partes — ainda inválido
        if not any(
            isinstance(existing.get(k), dict) for k in PART_KEYS
        ):
            raise ValueError(
                "Informe ao menos q1, q2 ou q3 (ou wordsRead/errorsCount/readingTimeSeconds)."
            )

    prosody = merged_payload.get("prosodyLevel")
    if prosody is not None:
        try:
            prosody = int(prosody)
        except (TypeError, ValueError) as exc:
            raise ValueError("prosodyLevel deve ser um inteiro entre 1 e 5.") from exc
        if prosody < 1 or prosody > 5:
            raise ValueError("prosodyLevel deve ser um inteiro entre 1 e 5.")

    kind = merged_payload.get("kind") or "FLUENCY"
    if isinstance(kind, str):
        kind = kind.strip().upper() or "FLUENCY"

    lista1_acc = None if _part_is_skipped(q1) else (q1 or {}).get("accuracy")
    lista2_acc = None if _part_is_skipped(q2) else (q2 or {}).get("accuracy")
    texto_acc = None if _part_is_skipped(q3) else (q3 or {}).get("accuracy")
    plcm_for_ica = None if _part_is_skipped(q3) else (q3 or {}).get("plcm")
    if plcm_for_ica is None and not _part_is_skipped(q1):
        plcm_for_ica = (q1 or {}).get("plcm")

    skipped_components = collect_skipped_ica_components(q1, q2, q3)
    ica = calculate_ica(
        accuracy_lista1=lista1_acc,
        accuracy_lista2=lista2_acc,
        accuracy_texto=texto_acc,
        comprehension=comprehension_score,
        plcm=plcm_for_ica,
        skipped_components=skipped_components or None,
    )

    primary = None
    for candidate in (q3, q1, q2):
        if candidate and not _part_is_skipped(candidate):
            primary = candidate
            break
    if primary is None:
        primary = q3 or q1 or q2 or {}

    metrics = {
        "calculatedPlcm": primary.get("plcm"),
        "calculatedAccuracy": primary.get("accuracy"),
        "precisionLevel": primary.get("precisionLevel"),
        "fluencyLevel": primary.get("fluencyLevel"),
        "icaScore": (ica or {}).get("icaScore"),
        "icaBreakdown": ica,
        "leiturimetroLevel": (ica or {}).get("leiturimetroLevel")
        or leiturimetro_level((ica or {}).get("icaScore")),
        "algorithmVersion": ALGORITHM_VERSION,
        "evaluationVersion": EVALUATION_VERSION,
        "skippedParts": skipped_components,
    }

    extras = merged_payload.get("extras") or {}
    if not isinstance(extras, dict):
        raise ValueError("extras deve ser um objeto JSON.")

    root_not_read = _normalize_not_read_reason(
        merged_payload.get("notReadReason"),
        "notReadReason",
    )

    fluency_data: Dict[str, Any] = {
        "kind": kind,
        "caderno": merged_payload.get("caderno"),
        "notReadReason": root_not_read,
        "prosodyLevel": prosody,
        "q1": q1,
        "q2": q2,
        "q3": q3,
        "extras": extras,
        "metrics": metrics,
    }

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
        "leiturimetro_level": metrics["leiturimetroLevel"],
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

    lista1_acc = None if _part_is_skipped(q1) else (q1 or {}).get("accuracy")
    lista2_acc = None if _part_is_skipped(q2) else (q2 or {}).get("accuracy")
    texto_acc = None if _part_is_skipped(q3) else (q3 or {}).get("accuracy")
    plcm_for_ica = None if _part_is_skipped(q3) else (q3 or {}).get("plcm")
    if plcm_for_ica is None and not _part_is_skipped(q1):
        plcm_for_ica = (q1 or {}).get("plcm")

    skipped_components = collect_skipped_ica_components(q1, q2, q3)
    ica = calculate_ica(
        accuracy_lista1=lista1_acc,
        accuracy_lista2=lista2_acc,
        accuracy_texto=texto_acc,
        comprehension=comprehension_score,
        plcm=plcm_for_ica,
        skipped_components=skipped_components or None,
    )

    primary = None
    for candidate in (q3, q1, q2):
        if candidate and not _part_is_skipped(candidate):
            primary = candidate
            break
    if primary is None:
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
            "leiturimetroLevel": (ica or {}).get("leiturimetroLevel")
            or leiturimetro_level((ica or {}).get("icaScore")),
            "algorithmVersion": ALGORITHM_VERSION,
            "evaluationVersion": EVALUATION_VERSION,
            "skippedParts": skipped_components,
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
        "leiturimetro_level": metrics["leiturimetroLevel"],
    }
    return updated, flat_columns
