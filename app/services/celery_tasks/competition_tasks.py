# -*- coding: utf-8 -*-
"""
Tasks Celery para competições.

Etapa 5:
- process_finished_competitions → finaliza competições expiradas, grava snapshot em
  competition_results e paga moedas de ranking.

Etapa 6:
- create_competitions_from_templates → cria competições recorrentes a partir de
  CompetitionTemplate (weekly, biweekly, monthly).
"""

import logging
from datetime import datetime, timedelta, timezone

from celery import Task

from app import db
from app.competitions.models import CompetitionTemplate, Competition
from app.report_analysis.celery_app import celery_app
from app.services.competition_ranking_service import CompetitionRankingService

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="competition_tasks.process_finished_competitions",
    max_retries=2,
    default_retry_delay=60,
    time_limit=300,
    soft_time_limit=240,
)
def process_finished_competitions(self: Task) -> dict:
    """
    Job que roda periodicamente (ex: a cada hora) via Celery Beat.
    Delega para CompetitionRankingService.finalize_all_expired_competitions().
    """
    try:
        return CompetitionRankingService.finalize_all_expired_competitions()
    except Exception as e:
        logger.exception("process_finished_competitions falhou: %s", str(e))
        db.session.rollback()
        raise self.retry(exc=e)


def _start_of_week_utc_today(now: datetime) -> datetime:
    """Calcula a segunda-feira da semana corrente (00:00) em UTC naive."""
    monday = now - timedelta(days=now.weekday())
    return datetime(monday.year, monday.month, monday.day, tzinfo=timezone.utc).replace(
        tzinfo=None
    )


def _start_of_biweekly_period(now: datetime) -> datetime:
    """
    Define o início do período quinzenal atual.
    Regra simples:
    - dias 1-15 → período inicia no dia 1
    - dias 16-fim → período inicia no dia 16
    """
    if now.day <= 15:
        base_day = 1
    else:
        base_day = 16
    dt = datetime(now.year, now.month, base_day, tzinfo=timezone.utc).replace(
        tzinfo=None
    )
    return dt


def _start_of_month(now: datetime) -> datetime:
    """Primeiro dia do mês (00:00)."""
    dt = datetime(now.year, now.month, 1, tzinfo=timezone.utc).replace(tzinfo=None)
    return dt


@celery_app.task(
    bind=True,
    name="competition_tasks.create_competitions_from_templates",
    max_retries=2,
    default_retry_delay=60,
    time_limit=300,
    soft_time_limit=240,
)
def create_competitions_from_templates(self: Task) -> dict:
    """
    Job diário (ex.: todo dia às 00:00) que cria competições
    semanais/quinzenais/mensais a partir de CompetitionTemplate.

    Regras principais:
    - Considera apenas templates ativos.
    - Para cada template + recorrência, verifica se já existe competição
      na janela do ciclo corrente (para aquele template + nível).
    - Se não existir, gera 2 competições por disciplina usando os dois níveis
      possíveis (1 e 2), desde que haja questões suficientes para cada nível.
    """
    from app.competitions.constants import COMPETITION_LEVEL_VALID
    from app.competitions.models.competition_template import CompetitionTemplate as CT

    created = 0
    skipped_no_questions = 0
    skipped_existing = 0

    now_utc = datetime.utcnow()
    # Data base em UTC naive para comparações
    now = now_utc.replace(tzinfo=timezone.utc).replace(tzinfo=None)

    templates = CT.query.filter_by(active=True).all()

    for template in templates:
        rec = (template.recurrence or "").strip().lower()

        if rec == "weekly":
            cycle_start = _start_of_week_utc_today(now)
            cycle_end = cycle_start + timedelta(days=7)
        elif rec in ("biweekly", "quinzenal", "biweekly"):
            cycle_start = _start_of_biweekly_period(now)
            cycle_end = cycle_start + timedelta(days=14)
        elif rec in ("monthly", "mensal"):
            cycle_start = _start_of_month(now)
            # Próximo mês
            if cycle_start.month == 12:
                next_month = datetime(cycle_start.year + 1, 1, 1)
            else:
                next_month = datetime(cycle_start.year, cycle_start.month + 1, 1)
            cycle_end = next_month
        else:
            logger.warning(
                "Recorrência desconhecida em template %s: %s",
                template.id,
                template.recurrence,
            )
            continue

        # Para cada nível permitido, gerar uma competição se ainda não existir
        for level in COMPETITION_LEVEL_VALID:
            # Verifica se já existe competição deste template + nível no ciclo
            existing = (
                Competition.query.filter(
                    Competition.template_id == template.id,
                    Competition.level == level,
                    Competition.enrollment_start >= cycle_start,
                    Competition.enrollment_start < cycle_end,
                )
                .first()
            )
            if existing:
                skipped_existing += 1
                continue

            try:
                # Usa o método do próprio template, que já:
                # - seleciona questões (até 20, máximo possível)
                # - define reward_config
                # - calcula datas pelo recurrence
                # - gera edição e nome
                competition = template.generate_competition_for_period(
                    start_date=cycle_start,
                    level_override=level,
                )
                db.session.add(competition)
                created += 1
                logger.info(
                    "Competição criada automaticamente do template %s (level=%s): %s",
                    template.id,
                    level,
                    competition.name,
                )
            except Exception as e:
                # Se for falha por falta de questões, apenas contabiliza e segue
                msg = str(e)
                if "Nenhuma questão disponível" in msg:
                    skipped_no_questions += 1
                    logger.warning(
                        "Template %s (level=%s) ignorado por falta de questões: %s",
                        template.id,
                        level,
                        msg,
                    )
                    db.session.rollback()
                    continue
                logger.exception(
                    "Erro ao gerar competição automática do template %s (level=%s): %s",
                    template.id,
                    level,
                    msg,
                )
                db.session.rollback()

    try:
        db.session.commit()
    except Exception as e:
        logger.exception("Commit de create_competitions_from_templates falhou: %s", str(e))
        db.session.rollback()
        raise self.retry(exc=e)

    summary = {
        "created": created,
        "skipped_existing": skipped_existing,
        "skipped_no_questions": skipped_no_questions,
        "templates_processed": len(templates),
    }
    logger.info("create_competitions_from_templates resumo: %s", summary)
    return summary

