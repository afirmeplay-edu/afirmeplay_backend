# -*- coding: utf-8 -*-
"""
Tasks Celery para competições (Etapa 5).
Processa competições expiradas: grava snapshot em competition_results e paga moedas de ranking.
"""

import logging
from celery import Task

from app.report_analysis.celery_app import celery_app
from app import db
from app.services.competition_ranking_service import CompetitionRankingService

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name='competition_tasks.process_finished_competitions',
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
