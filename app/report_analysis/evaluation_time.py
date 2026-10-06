# -*- coding: utf-8 -*-
"""
Métricas de tempo de prova para relatórios.

Regras (convenção operacional da plataforma):
  - 1º e 2º anos: 1h30 (90 min) — estimativa
  - 3º ao 9º (e demais séries, incl. EM): 2h30 (150 min) — estimativa

Uso:
  - Provas **mobile** (`user_agent` mobile-sync): sempre a estimativa
    (sessão offline não tem `submitted_at` confiável no servidor).
  - Provas **online** (web): tempo real da sessão (`started_at` → `submitted_at`)
    dividido pelo número de questões da avaliação.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
import re

from app.services.cartao_resposta.course_name_resolver import _extract_grade_number

ESTIMATED_TIME_YEARS_1_2_MINUTES = 90
ESTIMATED_TIME_YEARS_3_9_MINUTES = 150
DEFAULT_ESTIMATED_TIME_MINUTES = ESTIMATED_TIME_YEARS_3_9_MINUTES

MOBILE_USER_AGENT_MARKER = "mobile-sync"
PHYSICAL_USER_AGENT_MARKERS = ("physical test", "physical test correction")

ORIGEM_MEDIDA = "medida"
ORIGEM_ESTIMADA_MOBILE = "estimada_mobile"
ORIGEM_ESTIMADA_FALLBACK = "estimada_fallback"

EXCLUDED_SESSION_STATUSES = frozenset({"em_andamento", "expirada"})


def estimated_time_minutes_for_grade(grade_name: Optional[str]) -> int:
    """Retorna o tempo estimado de prova (minutos) a partir do nome da série."""
    if not grade_name or not str(grade_name).strip():
        return DEFAULT_ESTIMATED_TIME_MINUTES

    grade_lower = str(grade_name).strip().lower()

    if "médio" in grade_lower or "medio" in grade_lower:
        return ESTIMATED_TIME_YEARS_3_9_MINUTES
    if re.search(r"(?:^|[\s\-])em(?:$|[\s\-])", grade_lower):
        return ESTIMATED_TIME_YEARS_3_9_MINUTES

    if "infantil" in grade_lower or "grupo" in grade_lower or "pré" in grade_lower:
        return ESTIMATED_TIME_YEARS_1_2_MINUTES

    year = _extract_grade_number(grade_lower)
    if year is None:
        return DEFAULT_ESTIMATED_TIME_MINUTES
    if year in (1, 2):
        return ESTIMATED_TIME_YEARS_1_2_MINUTES
    return ESTIMATED_TIME_YEARS_3_9_MINUTES


def resolve_estimated_time_minutes(
    test: Any = None,
    grade_name: Optional[str] = None,
) -> int:
    """
    Tempo estimado persistido em ``test.estimated_time``, com fallback pela série.
    """
    stored = getattr(test, "estimated_time", None) if test is not None else None
    if stored is not None:
        try:
            value = int(stored)
            if value > 0:
                return value
        except (TypeError, ValueError):
            pass

    if not grade_name and test is not None:
        grade = getattr(test, "grade", None)
        grade_name = getattr(grade, "name", None) if grade is not None else None

    return estimated_time_minutes_for_grade(grade_name)


def is_mobile_session(session: Any) -> bool:
    ua = (getattr(session, "user_agent", None) or "").strip().lower()
    return MOBILE_USER_AGENT_MARKER in ua


def is_physical_session(session: Any) -> bool:
    ua = (getattr(session, "user_agent", None) or "").strip().lower()
    return any(marker in ua for marker in PHYSICAL_USER_AGENT_MARKERS)


def _as_aware_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def session_elapsed_seconds(session: Any) -> Optional[int]:
    """Tempo real da sessão em segundos. None se não for mensurável."""
    started = getattr(session, "started_at", None)
    submitted = getattr(session, "submitted_at", None)
    if started is None or submitted is None:
        return None
    try:
        delta = _as_aware_utc(submitted) - _as_aware_utc(started)
        seconds = int(delta.total_seconds())
    except (TypeError, AttributeError, OverflowError):
        return None
    if seconds <= 0:
        return None
    return seconds


def seconds_per_question(total_seconds: Optional[int], question_count: Optional[int]) -> Optional[float]:
    if total_seconds is None or not question_count or question_count <= 0:
        return None
    return round(float(total_seconds) / float(question_count), 2)


def resolve_question_count(session: Any = None, test: Any = None, fallback: Optional[int] = None) -> int:
    """Número de questões da prova (test_questions, sessão ou fallback)."""
    if fallback is not None:
        try:
            n = int(fallback)
            if n > 0:
                return n
        except (TypeError, ValueError):
            pass

    if test is not None:
        tqs = getattr(test, "test_questions", None)
        if tqs is not None:
            try:
                n = len(tqs)
                if n > 0:
                    return n
            except TypeError:
                pass

    session_total = getattr(session, "total_questions", None) if session is not None else None
    if session_total:
        try:
            n = int(session_total)
            if n > 0:
                return n
        except (TypeError, ValueError):
            pass

    return 0


def classify_session_origin(session: Any) -> Optional[str]:
    """
    Retorna a origem da métrica ou None se a sessão deve ser ignorada
    (prova física / OMR ou status incompleto).
    """
    status = (getattr(session, "status", None) or "").strip().lower()
    if status in EXCLUDED_SESSION_STATUSES:
        return None
    if is_physical_session(session):
        return None
    if is_mobile_session(session):
        return ORIGEM_ESTIMADA_MOBILE
    if session_elapsed_seconds(session) is not None:
        return ORIGEM_MEDIDA
    return ORIGEM_ESTIMADA_FALLBACK


def compute_session_time_metrics(
    session: Any,
    test: Any = None,
    grade_name: Optional[str] = None,
    question_count: Optional[int] = None,
) -> Optional[dict]:
    """
    Calcula tempo total e tempo médio por questão de uma sessão.

    Retorna dict com origem, segundos e nº de questões, ou None se ignorada.
    """
    origin = classify_session_origin(session)
    if origin is None:
        return None

    n_questions = resolve_question_count(session=session, test=test, fallback=question_count)
    estimated_minutes = resolve_estimated_time_minutes(test=test, grade_name=grade_name)

    if origin == ORIGEM_MEDIDA:
        total_seconds = session_elapsed_seconds(session)
    else:
        total_seconds = int(estimated_minutes) * 60

    if total_seconds is None or total_seconds <= 0:
        return None

    return {
        "origem": origin,
        "tempo_total_segundos": int(total_seconds),
        "estimated_time_minutos": int(estimated_minutes),
        "total_questions": n_questions,
        "tempo_por_questao_segundos": seconds_per_question(total_seconds, n_questions),
        "medida": origin == ORIGEM_MEDIDA,
    }
