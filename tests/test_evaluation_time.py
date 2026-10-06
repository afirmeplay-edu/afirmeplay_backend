# -*- coding: utf-8 -*-
"""Métricas de tempo de prova (estimativa por série e tempo real da sessão)."""

from app.report_analysis.evaluation_time import (
    DEFAULT_ESTIMATED_TIME_MINUTES,
    ESTIMATED_TIME_YEARS_1_2_MINUTES,
    ESTIMATED_TIME_YEARS_3_9_MINUTES,
    ORIGEM_ESTIMADA_FALLBACK,
    ORIGEM_ESTIMADA_MOBILE,
    ORIGEM_MEDIDA,
    classify_session_origin,
    compute_session_time_metrics,
    estimated_time_minutes_for_grade,
    is_mobile_session,
    is_physical_session,
    resolve_estimated_time_minutes,
    seconds_per_question,
    session_elapsed_seconds,
)
from types import SimpleNamespace
from datetime import datetime, timedelta


def test_estimated_time_years_1_and_2():
    assert estimated_time_minutes_for_grade("1º Ano") == ESTIMATED_TIME_YEARS_1_2_MINUTES
    assert estimated_time_minutes_for_grade("2º Ano") == ESTIMATED_TIME_YEARS_1_2_MINUTES
    assert estimated_time_minutes_for_grade("1o ano") == ESTIMATED_TIME_YEARS_1_2_MINUTES


def test_estimated_time_years_3_to_9():
    assert estimated_time_minutes_for_grade("3º Ano") == ESTIMATED_TIME_YEARS_3_9_MINUTES
    assert estimated_time_minutes_for_grade("9º Ano") == ESTIMATED_TIME_YEARS_3_9_MINUTES
    assert estimated_time_minutes_for_grade("5º Ano") == ESTIMATED_TIME_YEARS_3_9_MINUTES


def test_estimated_time_ensino_medio_is_not_year_1():
    assert estimated_time_minutes_for_grade("1º Médio") == ESTIMATED_TIME_YEARS_3_9_MINUTES
    assert estimated_time_minutes_for_grade("1º Ano EM") == ESTIMATED_TIME_YEARS_3_9_MINUTES
    assert estimated_time_minutes_for_grade("3º Ano EM") == ESTIMATED_TIME_YEARS_3_9_MINUTES


def test_estimated_time_default_when_unknown():
    assert estimated_time_minutes_for_grade(None) == DEFAULT_ESTIMATED_TIME_MINUTES
    assert estimated_time_minutes_for_grade("") == DEFAULT_ESTIMATED_TIME_MINUTES


def test_stored_estimated_time_wins():
    test = SimpleNamespace(estimated_time=90, grade=SimpleNamespace(name="9º Ano"))
    assert resolve_estimated_time_minutes(test=test) == 90


def test_seconds_per_question():
    assert seconds_per_question(3600, 20) == 180.0
    assert seconds_per_question(90 * 60, 30) == 180.0
    assert seconds_per_question(100, 0) is None


def test_online_session_uses_elapsed_time():
    started = datetime(2026, 5, 1, 8, 0, 0)
    session = SimpleNamespace(
        started_at=started,
        submitted_at=started + timedelta(minutes=40),
        user_agent="Mozilla/5.0",
        status="finalizada",
        total_questions=20,
    )
    test = SimpleNamespace(estimated_time=150, test_questions=[None] * 20)
    out = compute_session_time_metrics(session, test=test, question_count=20)
    assert out is not None
    assert out["origem"] == ORIGEM_MEDIDA
    assert out["tempo_total_segundos"] == 40 * 60
    assert out["tempo_por_questao_segundos"] == 120.0


def test_mobile_session_uses_estimate():
    started = datetime(2026, 5, 1, 8, 0, 0)
    session = SimpleNamespace(
        started_at=started,
        submitted_at=started + timedelta(days=2),
        user_agent="mobile-sync",
        status="finalizada",
        total_questions=30,
    )
    test = SimpleNamespace(estimated_time=90, grade=SimpleNamespace(name="1º Ano"))
    out = compute_session_time_metrics(session, test=test, question_count=30)
    assert out is not None
    assert out["origem"] == ORIGEM_ESTIMADA_MOBILE
    assert out["tempo_total_segundos"] == 90 * 60
    assert out["tempo_por_questao_segundos"] == 180.0


def test_physical_session_is_ignored():
    session = SimpleNamespace(
        started_at=datetime.utcnow(),
        submitted_at=datetime.utcnow(),
        user_agent="Physical Test Correction (NewGrid)",
        status="corrigida",
        total_questions=20,
    )
    assert classify_session_origin(session) is None
    assert is_physical_session(session) is True
    assert is_mobile_session(session) is False
    assert compute_session_time_metrics(session, question_count=20) is None


def test_elapsed_seconds_none_without_timestamps():
    session = SimpleNamespace(started_at=None, submitted_at=None)
    assert session_elapsed_seconds(session) is None
    assert classify_session_origin(
        SimpleNamespace(
            started_at=None,
            submitted_at=None,
            user_agent="Chrome",
            status="finalizada",
        )
    ) == ORIGEM_ESTIMADA_FALLBACK
