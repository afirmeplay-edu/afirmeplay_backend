# -*- coding: utf-8 -*-
"""Tasks Celery da Leitura Guiada Automática."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from celery import Task

from app.reports.report_analysis.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="afirme_ler.process_guided_auto_session",
    max_retries=2,
    default_retry_delay=30,
    time_limit=600,
    soft_time_limit=540,
)
def process_guided_auto_session(
    self: Task,
    session_id: str,
    part: str,
    city_id: str,
    duration_hint_seconds: Optional[float] = None,
) -> Dict[str, Any]:
    from app import db
    from app.afirme_ler.services.guided_auto_session_service import (
        GuidedAutoSessionService,
    )
    from app.utils.tenant_middleware import city_id_to_schema_name, set_search_path

    if not city_id:
        raise ValueError("city_id é obrigatório para processar leitura automática.")

    schema = city_id_to_schema_name(str(city_id))
    set_search_path(schema)

    try:
        session = GuidedAutoSessionService.process_part(
            session_id,
            part=part,
            duration_hint_seconds=duration_hint_seconds,
        )
        return {
            "success": True,
            "sessionId": session.id,
            "status": session.status,
            "part": part,
        }
    except Exception as exc:
        logger.exception(
            "Erro na task process_guided_auto_session session=%s part=%s",
            session_id,
            part,
        )
        try:
            db.session.rollback()
        except Exception:
            pass
        raise self.retry(exc=exc)
