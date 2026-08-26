# -*- coding: utf-8 -*-
"""
Extrai contagens do MVP a partir da sessão persistida (Q1 / Q2 / Q3).

A classe de cálculo não conhece o JSON da sessão — só este adapter.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.afirme_ler.scoring.levels import normalize_status
from app.afirme_ler.scoring.student import StudentReadingInput

STATUS_SILABOU = "silabou"
STATUS_ACERTOU = "acertou"
STATUS_SOLETROU = "soletrou"

# Escala de aplicação 1–5 → boolean do MVP. 3+ = adequada.
PROSODY_ADEQUADA_MIN = 3


def _as_int(value: Any, default: int = 0) -> int:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_float(value: Any, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _part(fluency_data: Optional[dict], key: str) -> Dict[str, Any]:
    if not isinstance(fluency_data, dict):
        return {}
    raw = fluency_data.get(key)
    return raw if isinstance(raw, dict) else {}


def _part_skipped(part: dict) -> bool:
    if part.get("skipped") is True:
        return True
    reason = part.get("notReadReason")
    return bool(reason) and reason != "nao_se_aplica"


def _markings(part: dict) -> List[dict]:
    raw = part.get("markings")
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    return []


def _count_status(markings: List[dict], *statuses: str) -> int:
    wanted = {item.lower() for item in statuses}
    total = 0
    for item in markings:
        status = str(item.get("status") or "").strip().lower()
        if status in wanted:
            total += 1
    return total


def _corretas_da_lista(part: dict) -> int:
    if _part_skipped(part):
        return 0
    markings = _markings(part)
    if markings:
        return _count_status(markings, STATUS_ACERTOU)
    words_read = _as_int(part.get("wordsRead"))
    errors = _as_int(part.get("errorsCount"))
    return max(0, words_read - errors)


def _texto_lidas(part: dict) -> int:
    if _part_skipped(part):
        return 0
    if part.get("lastWordPosition") is not None:
        return _as_int(part.get("lastWordPosition"))
    return _as_int(part.get("wordsRead"))


def _prosodia_adequada(
    fluency_data: Optional[dict],
    prosody_level: Any,
) -> bool:
    extras = {}
    if isinstance(fluency_data, dict):
        raw = fluency_data.get("prosodiaAdequada")
        extras = fluency_data.get("extras") if isinstance(fluency_data.get("extras"), dict) else {}
        if raw is None:
            raw = extras.get("prosodiaAdequada")
        if isinstance(raw, bool):
            return raw
        if prosody_level is None:
            prosody_level = fluency_data.get("prosodyLevel")
    if prosody_level is None:
        return False
    try:
        return int(prosody_level) >= PROSODY_ADEQUADA_MIN
    except (TypeError, ValueError):
        return False


def input_from_fluency_payload(
    *,
    status: Optional[str],
    fluency_data: Optional[dict] = None,
    comprehension_correct: Optional[int] = None,
    comprehension_total: Optional[int] = None,
    prosody_level: Any = None,
) -> StudentReadingInput:
    """Monta o DTO do classificador a partir do JSON da sessão."""
    report_status = normalize_status(status)

    q1 = _part(fluency_data, "q1")
    q2 = _part(fluency_data, "q2")
    q3 = _part(fluency_data, "q3")
    q1_skipped = _part_skipped(q1)

    silabacoes = 0 if q1_skipped else _count_status(_markings(q1), STATUS_SILABOU)
    soletracoes = 0 if q1_skipped else _count_status(_markings(q1), STATUS_SOLETROU)

    return StudentReadingInput(
        status=report_status,
        palavras_corretas=_corretas_da_lista(q1),
        silabacoes=silabacoes,
        soletracoes=soletracoes,
        desconhecidas_corretas=_corretas_da_lista(q2),
        texto_palavras_lidas=_texto_lidas(q3),
        texto_erros=0 if _part_skipped(q3) else _as_int(q3.get("errorsCount")),
        tempo_segundos=0.0 if _part_skipped(q3) else _as_float(q3.get("readingTimeSeconds")),
        prosodia_adequada=_prosodia_adequada(fluency_data, prosody_level),
        compreensao_acertos=_as_int(comprehension_correct),
        compreensao_validas=_as_int(comprehension_total),
    )


def input_from_session(session: Any) -> StudentReadingInput:
    """Aceita ``ReadingFluencySession`` (ORM) ou dict ``to_dict()``."""
    if isinstance(session, dict):
        fluency = session.get("fluencyData") or session.get("fluency_data")
        return input_from_fluency_payload(
            status=session.get("status"),
            fluency_data=fluency if isinstance(fluency, dict) else None,
            comprehension_correct=session.get("comprehensionCorrectCount")
            if session.get("comprehensionCorrectCount") is not None
            else session.get("comprehension_correct_count"),
            comprehension_total=session.get("comprehensionTotal")
            if session.get("comprehensionTotal") is not None
            else session.get("comprehension_total"),
            prosody_level=session.get("prosodyLevel")
            if session.get("prosodyLevel") is not None
            else session.get("prosody_level"),
        )

    fluency = getattr(session, "fluency_data", None)
    return input_from_fluency_payload(
        status=getattr(session, "status", None),
        fluency_data=fluency if isinstance(fluency, dict) else None,
        comprehension_correct=getattr(session, "comprehension_correct_count", None),
        comprehension_total=getattr(session, "comprehension_total", None),
        prosody_level=getattr(session, "prosody_level", None),
    )
