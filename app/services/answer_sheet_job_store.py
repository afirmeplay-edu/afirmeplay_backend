# -*- coding: utf-8 -*-
"""
Store de jobs de geração de cartões resposta persistido em public.answer_sheet_generation_jobs.
Usado para que todas as instâncias da API e Celery vejam o mesmo estado (evita "job não encontrado").
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Any

from app import db
from app.models.answerSheetGenerationJob import AnswerSheetGenerationJob
from app.services.progress_store import (
    get_job_progress_redis,
    update_job_progress_redis,
)

logger = logging.getLogger(__name__)


def create_answer_sheet_job(
    job_id: str,
    total: int,
    gabarito_id: str,
    user_id: str,
    task_ids: list,
    city_id: str,
    scope_type: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Cria um job de geração de cartões na tabela public.answer_sheet_generation_jobs.
    """
    job = AnswerSheetGenerationJob(
        job_id=job_id,
        city_id=city_id,
        gabarito_id=gabarito_id,
        user_id=user_id,
        task_ids=task_ids or [],
        total=total,
        completed=0,
        successful=0,
        failed=0,
        status='processing',
        progress_current=0,
        progress_percentage=0,
        scope_type=scope_type,
    )
    db.session.add(job)
    db.session.commit()
    logger.info("📋 Job de cartões criado (DB): %s com %s turmas", job_id, total)
    return job.to_dict()


def get_answer_sheet_job(job_id: str) -> Optional[Dict[str, Any]]:
    """
    Retorna o job da tabela public.answer_sheet_generation_jobs.
    Mescla progress_current e progress_percentage do Redis se existirem.
    """
    job = AnswerSheetGenerationJob.query.filter_by(job_id=job_id).first()
    if job is None:
        return None
    data = job.to_dict()
    redis_progress = get_job_progress_redis(job_id)
    if redis_progress:
        if "progress_current" in redis_progress:
            data["progress_current"] = redis_progress["progress_current"]
        if "progress_percentage" in redis_progress:
            data["progress_percentage"] = redis_progress["progress_percentage"]
    return data


def update_answer_sheet_job(job_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Atualiza o job na tabela e, se houver progress_current/progress_percentage, no Redis.
    """
    job = AnswerSheetGenerationJob.query.filter_by(job_id=job_id).first()
    if job is None:
        return None
    if "progress_current" in updates:
        job.progress_current = int(updates["progress_current"])
    if "progress_percentage" in updates:
        job.progress_percentage = int(updates["progress_percentage"])
    if "completed" in updates:
        job.completed = int(updates["completed"])
    if "successful" in updates:
        job.successful = int(updates["successful"])
    if "failed" in updates:
        job.failed = int(updates["failed"])
    if "status" in updates:
        job.status = str(updates["status"])
    if "completed_at" in updates:
        val = updates["completed_at"]
        if isinstance(val, str):
            try:
                job.completed_at = datetime.fromisoformat(val.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                job.completed_at = None
        else:
            job.completed_at = val
    if "total_students_generated" in updates:
        job.total_students_generated = updates["total_students_generated"]
    if "classes_generated" in updates:
        job.classes_generated = updates["classes_generated"]
    if "scope_type" in updates:
        job.scope_type = updates["scope_type"]
    db.session.commit()
    logger.debug("📝 Job %s atualizado (DB): %s", job_id, list(updates.keys()))
    if "progress_current" in updates or "progress_percentage" in updates:
        progress_updates = {
            k: updates[k]
            for k in ("progress_current", "progress_percentage")
            if k in updates
        }
        if progress_updates:
            update_job_progress_redis(job_id, progress_updates)
    return job.to_dict()
