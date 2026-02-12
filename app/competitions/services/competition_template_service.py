# -*- coding: utf-8 -*-
"""
Serviços auxiliares para CompetitionTemplate (Etapa 6).

Responsabilidades principais:
- Calcular datas de inscrição/aplicação/expiração por recorrência.
- Selecionar questões aleatórias por disciplina/nível com limite seguro.
- Definir reward_config padrão por tipo de recorrência.
- Calcular numeração e nome da edição (série) das competições automáticas.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from sqlalchemy import func

from app import db
from app.competitions.models import Competition
from app.competitions.services.question_selection_service import (
    QuestionSelectionService,
)
from app.models.question import Question


# -----------------------------
# Configuração de recorrência
# -----------------------------


@dataclass(frozen=True)
class RecurrenceConfig:
    enrollment_days: int
    application_days: int


# Regra dada pelo usuário:
# - semanal   → 1 dia de inscrição, 5 dias de aplicação
# - quinzenal → 2 dias de inscrição, 5 dias de aplicação
# - mensal    → 7 dias de inscrição, 5 dias de aplicação
RECURRENCE_CONFIG: Dict[str, RecurrenceConfig] = {
    "weekly": RecurrenceConfig(enrollment_days=1, application_days=5),
    "biweekly": RecurrenceConfig(enrollment_days=2, application_days=5),
    "monthly": RecurrenceConfig(enrollment_days=7, application_days=5),
}


def normalize_recurrence(value: Optional[str]) -> Optional[str]:
    """Normaliza a string de recorrência para os valores esperados."""
    if not value:
        return None
    v = value.strip().lower()
    if v in ("weekly", "semanal"):
        return "weekly"
    if v in ("biweekly", "quinzenal", "quizenal"):
        return "biweekly"
    if v in ("monthly", "mensal"):
        return "monthly"
    return v


def compute_period_for_recurrence(
    recurrence: str,
    cycle_start: datetime,
) -> Dict[str, datetime]:
    """
    Calcula enrollment_start, enrollment_end, application e expiration
    a partir da recorrência e de uma data base (cycle_start).

    cycle_start deve ser o início do ciclo:
    - semanal  → segunda-feira 00:00 da semana
    - quinzenal → início do bloco de 14 dias
    - mensal   → primeiro dia do mês 00:00
    """
    rec = normalize_recurrence(recurrence)
    if rec not in RECURRENCE_CONFIG:
        raise ValueError(f"Recorrência inválida para template: {recurrence}")

    cfg = RECURRENCE_CONFIG[rec]

    start = cycle_start.replace(hour=0, minute=0, second=0, microsecond=0)
    enrollment_start = start
    enrollment_end = enrollment_start + timedelta(days=cfg.enrollment_days)

    application = enrollment_end
    expiration = application + timedelta(days=cfg.application_days)

    return {
        "enrollment_start": enrollment_start,
        "enrollment_end": enrollment_end,
        "application": application,
        "expiration": expiration,
    }


# -----------------------------
# Seleção de questões
# -----------------------------


def select_questions_for_template(
    subject_id: str,
    level: Optional[int],
    max_questions: int = 20,
) -> List[Question]:
    """
    Seleciona questões aleatórias para uma competição automática.

    Diferente do fluxo geral de Competitions, aqui NÃO falhamos se houver
    menos questões que o desejado. Usamos sempre o máximo disponível até
    o limite de max_questions, como pedido para evitar erros.
    """
    if max_questions <= 0:
        return []

    # Reaproveitar a lógica de filtros do QuestionSelectionService,
    # mas sem impor num_questions obrigatório.
    base_query = QuestionSelectionService.build_query(
        subject_id=subject_id,
        level=level,
        rules={},
    )

    total = base_query.count()
    if total == 0:
        return []

    limit = min(total, max_questions)

    # Selecionar aleatoriamente usando ORDER BY random() (PostgreSQL)
    random_query = base_query.order_by(func.random()).limit(limit)
    return list(random_query.all())


# -----------------------------
# Recompensas padrão
# -----------------------------


def get_default_reward_config_for_recurrence(recurrence: str) -> Dict:
    """
    Retorna reward_config padrão para a recorrência informada.

    Valores definidos pelo usuário:
    - semanal:
        1º: 100, 2º: 50, 3º: 30, participação: 25
    - quinzenal:
        1º: 200, 2º: 100, 3º: 50, participação: 50
    - mensal:
        1º: 300, 2º: 200, 3º: 100, participação: 70
    """
    rec = normalize_recurrence(recurrence)

    if rec == "weekly":
        participation = 25
        top = [(1, 100), (2, 50), (3, 30)]
    elif rec == "biweekly":
        participation = 50
        top = [(1, 200), (2, 100), (3, 50)]
    elif rec == "monthly":
        participation = 70
        top = [(1, 300), (2, 200), (3, 100)]
    else:
        # Fallback seguro: sem moedas
        participation = 0
        top = []

    return {
        "participation_coins": participation,
        "ranking_rewards": [
            {"position": pos, "coins": coins} for pos, coins in top
        ],
    }


# -----------------------------
# Série / numeração das edições
# -----------------------------


@dataclass(frozen=True)
class SeriesConfig:
    key: str
    name_template: str


SERIES_BY_RECURRENCE: Dict[str, SeriesConfig] = {
    # N(numero da edição)° Copinha Afirmeplay  → sugerido para semanal
    "weekly": SeriesConfig(
        key="copinha_afirmeplay",
        name_template="{n}° Copinha Afirmeplay",
    ),
    # N(numero da edição)° Copa Prata Afirmeplay → sugerido para quinzenal
    "biweekly": SeriesConfig(
        key="copa_prata_afirmeplay",
        name_template="{n}° Copa Prata Afirmeplay",
    ),
    # N(numero da edição)° Torneio Mestre Afirmeplay → sugerido para mensal
    "monthly": SeriesConfig(
        key="mestre_afirmeplay",
        name_template="{n}° Torneio Mestre Afirmeplay",
    ),
}


def get_series_config_for_recurrence(recurrence: str) -> Optional[SeriesConfig]:
    rec = normalize_recurrence(recurrence)
    return SERIES_BY_RECURRENCE.get(rec)


def compute_next_edition(
    subject_id: str,
    recurrence: str,
) -> Tuple[Optional[int], Optional[str], Optional[str]]:
    """
    Calcula próximo número de edição e nome base para determinada combinação
    (série + disciplina + recorrência).

    Numeração é separada por:
    - série (edition_series)
    - subject_id (disciplina)
    - recurrence (semanal/quinzenal/mensal)
    """
    series_cfg = get_series_config_for_recurrence(recurrence)
    if not series_cfg:
        return None, None, None

    rec = normalize_recurrence(recurrence)

    max_number = (
        db.session.query(func.max(Competition.edition_number))
        .filter(
            Competition.subject_id == subject_id,
            Competition.recurrence == rec,
            Competition.edition_series == series_cfg.key,
        )
        .scalar()
    )
    next_number = int(max_number or 0) + 1
    name = series_cfg.name_template.format(n=next_number)
    return next_number, series_cfg.key, name


__all__ = [
    "compute_period_for_recurrence",
    "select_questions_for_template",
    "get_default_reward_config_for_recurrence",
    "compute_next_edition",
    "normalize_recurrence",
]

