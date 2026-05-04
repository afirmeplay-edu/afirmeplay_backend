# -*- coding: utf-8 -*-
"""
Tasks Celery para gerar análise de IA em background e armazenar em Redis.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict

from app.report_analysis.celery_app import celery_app
from app.services.ai_analysis_service import AIAnalysisService
from app.services.ai_redis_cache import set_ready, set_error

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=1, default_retry_delay=30)
def generate_ai_analysis_json_to_redis(
    self,
    *,
    cache_key: str,
    prompt: str,
    ttl_sec: int = 3600,
) -> Dict[str, Any]:
    """
    Gera análise (JSON) via IA a partir do prompt e salva no Redis.
    """
    try:
        ai_service = AIAnalysisService()
        result = ai_service.analyze_intervention_plan_json(prompt)
        set_ready(cache_key, result=result, ttl_sec=ttl_sec)
        return {"success": True, "cache_key": cache_key}
    except Exception as e:
        logger.error("Erro ao gerar IA (cache_key=%s): %s", cache_key, e, exc_info=True)
        set_error(cache_key, error="Falha ao gerar análise de IA", details=str(e), ttl_sec=min(int(ttl_sec), 900))
        try:
            raise self.retry(exc=e)
        except Exception:
            return {"success": False, "cache_key": cache_key, "error": str(e)}

