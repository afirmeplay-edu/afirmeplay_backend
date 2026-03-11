# -*- coding: utf-8 -*-
"""
Store de progresso para correção em lote de provas físicas.
Progresso de jobs de geração de cartões resposta (answer_sheet) é espelhado em Redis
para que Flask e Celery worker vejam o mesmo estado (progresso gradual no GET /jobs/.../status).

Formato do progress:
{
    "job_id": {
        "total": 5,
        "completed": 0,
        "successful": 0,
        "failed": 0,
        "status": "processing",  # "processing", "completed", "error"
        "test_id": "uuid",
        "created_at": "2024-01-01T00:00:00",
        "items": {
            "0": {"status": "done", "student_id": "xxx", "student_name": "João", "correct": 8, "total": 10, "percentage": 80.0},
            "1": {"status": "processing"},
            "2": {"status": "pending"},
            "3": {"status": "error", "error": "QR Code não detectado"},
            "4": {"status": "pending"},
        },
        "results": []  # Lista com resultados completos
    }
}
"""

from threading import Lock
from datetime import datetime
import logging
import os
from typing import Optional

# Dicionário global de progresso (memória; progresso de answer_sheet também vai para Redis)
progress = {}
lock = Lock()

logger = logging.getLogger(__name__)

# Prefixo e TTL para chaves de progresso no Redis (compartilhado entre Flask e Celery)
REDIS_PROGRESS_KEY_PREFIX = "as_job_progress:"
REDIS_PROGRESS_TTL_SEC = 24 * 3600  # 24 horas


_redis_client = None


def _get_redis_client():
    """Cliente Redis singleton (mesma URL/senha que Celery). Retorna None se Redis indisponível."""
    global _redis_client
    try:
        import redis
    except ImportError:
        return None
    if _redis_client is not None:
        return _redis_client
    try:
        redis_url = os.getenv("REDIS_URL") or os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
        redis_password = os.getenv("REDIS_PASSWORD")
        if redis_password and "@" not in redis_url and redis_url.startswith("redis://"):
            parts = redis_url.replace("redis://", "").split("/")
            host_port = parts[0]
            db = parts[1] if len(parts) > 1 else "0"
            redis_url = f"redis://:{redis_password}@{host_port}/{db}"
        _redis_client = redis.from_url(redis_url, decode_responses=True)
        _redis_client.ping()
        logger.debug("Redis conectado para progress_store (answer_sheet job progress)")
    except Exception as e:
        logger.warning("Redis indisponível para progresso de job: %s", e)
        _redis_client = None
    return _redis_client


def update_job_progress_redis(job_id: str, updates: dict) -> None:
    """Grava progress_current e progress_percentage no Redis (para GET status ver progresso gradual)."""
    r = _get_redis_client()
    if not r:
        return
    key = REDIS_PROGRESS_KEY_PREFIX + job_id
    try:
        if "progress_current" in updates:
            r.hset(key, "progress_current", str(int(updates["progress_current"])))
        if "progress_percentage" in updates:
            r.hset(key, "progress_percentage", str(int(updates["progress_percentage"])))
        r.expire(key, REDIS_PROGRESS_TTL_SEC)
    except Exception as e:
        logger.debug("Falha ao escrever progresso no Redis: %s", e)


def increment_answer_sheet_progress(job_id: str, total_classes: int) -> Optional[tuple]:
    """
    Incrementa progress_current em 1 no Redis (atômico) e calcula progress_percentage.
    Retorna (new_current, new_percentage) ou None se Redis indisponível.
    Usado pelas tasks por turma para progresso gradual no GET /jobs/.../status.
    """
    r = _get_redis_client()
    if not r:
        return None
    key = REDIS_PROGRESS_KEY_PREFIX + job_id
    try:
        new_current = r.hincrby(key, "progress_current", 1)
        pct = min(100, (100 * new_current) // total_classes) if total_classes > 0 else 0
        r.hset(key, "progress_percentage", str(pct))
        r.expire(key, REDIS_PROGRESS_TTL_SEC)
        return (new_current, pct)
    except Exception as e:
        logger.debug("Falha ao incrementar progresso no Redis: %s", e)
        return None


def get_job_progress_redis(job_id: str) -> Optional[dict]:
    """Lê progress_current e progress_percentage do Redis. Retorna None se não houver ou Redis indisponível."""
    r = _get_redis_client()
    if not r:
        return None
    key = REDIS_PROGRESS_KEY_PREFIX + job_id
    try:
        raw = r.hgetall(key)
        if not raw:
            return None
        out = {}
        if "progress_current" in raw:
            try:
                out["progress_current"] = int(raw["progress_current"])
            except (ValueError, TypeError):
                pass
        if "progress_percentage" in raw:
            try:
                out["progress_percentage"] = int(raw["progress_percentage"])
            except (ValueError, TypeError):
                pass
        return out if out else None
    except Exception as e:
        logger.debug("Falha ao ler progresso do Redis: %s", e)
        return None


def create_job(job_id: str, total: int, test_id: str = None, gabarito_id: str = None, user_id: str = None, task_ids: list = None) -> dict:
    """
    Cria um novo job de correção em lote
    
    Args:
        job_id: ID único do job
        total: Número total de imagens a processar
        test_id: ID da prova (opcional)
        gabarito_id: ID do gabarito (opcional)
        user_id: ID do usuário que criou o job (opcional, para validação de acesso)
        task_ids: Lista de IDs de tasks Celery associadas ao job (opcional)
    
    Returns:
        dict: Dados do job criado
    """
    with lock:
        progress[job_id] = {
            "total": total,
            "completed": 0,
            "successful": 0,
            "failed": 0,
            "status": "processing",
            "test_id": test_id,
            "gabarito_id": gabarito_id,
            "user_id": user_id,
            "task_ids": task_ids or [],
            "warnings": [],
            "created_at": datetime.utcnow().isoformat(),
            "items": {str(i): {"status": "pending"} for i in range(total)},
            "results": []
        }
        logger.info(f"📋 Job criado: {job_id} com {total} imagens")
        return progress[job_id]


def update_item_processing(job_id: str, index: int):
    """
    Marca item como em processamento
    
    Args:
        job_id: ID do job
        index: Índice do item (0-based)
    """
    with lock:
        if job_id in progress:
            progress[job_id]["items"][str(index)] = {"status": "processing"}
            logger.debug(f"🔄 Job {job_id}: Item {index} em processamento")


def update_item_done(job_id: str, index: int, result: dict):
    """
    Marca item como concluído com sucesso
    
    Args:
        job_id: ID do job
        index: Índice do item (0-based)
        result: Resultado da correção
    """
    with lock:
        if job_id in progress:
            progress[job_id]["items"][str(index)] = {
                "status": "done",
                "student_id": result.get("student_id"),
                "student_name": result.get("student_name"),
                "correct": result.get("correct"),
                "total": result.get("total"),
                "percentage": result.get("percentage"),
                "grade": result.get("grade"),
                "classification": result.get("classification"),
                "proficiency": result.get("proficiency")
            }
            progress[job_id]["completed"] += 1
            progress[job_id]["successful"] += 1
            progress[job_id]["results"].append(result)
            logger.info(f"✅ Job {job_id}: Item {index} concluído - {result.get('student_name', 'N/A')}")


def update_item_error(job_id: str, index: int, error: str):
    """
    Marca item como erro
    
    Args:
        job_id: ID do job
        index: Índice do item (0-based)
        error: Mensagem de erro
    """
    with lock:
        if job_id in progress:
            progress[job_id]["items"][str(index)] = {
                "status": "error",
                "error": error
            }
            progress[job_id]["completed"] += 1
            progress[job_id]["failed"] += 1
            logger.warning(f"❌ Job {job_id}: Item {index} falhou - {error}")


def complete_job(job_id: str):
    """
    Marca job como concluído
    
    Args:
        job_id: ID do job
    """
    with lock:
        if job_id in progress:
            progress[job_id]["status"] = "completed"
            progress[job_id]["completed_at"] = datetime.utcnow().isoformat()
            logger.info(f"🏁 Job {job_id} concluído: {progress[job_id]['successful']} sucesso, {progress[job_id]['failed']} falhas")


def get_job(job_id: str) -> Optional[dict]:
    """
    Retorna dados do job. Para jobs de answer_sheet, mescla progress_current e progress_percentage
    vindos do Redis (atualizados pelo Celery) para que o progresso seja gradual no status.
    """
    with lock:
        job = progress.get(job_id)
    if job is None:
        return None
    redis_progress = get_job_progress_redis(job_id)
    if redis_progress:
        job = dict(job)
        if "progress_current" in redis_progress:
            job["progress_current"] = redis_progress["progress_current"]
        if "progress_percentage" in redis_progress:
            job["progress_percentage"] = redis_progress["progress_percentage"]
    return job


def update_job(job_id: str, updates: dict) -> dict:
    """
    Atualiza campos específicos de um job.
    Se updates contiver progress_current ou progress_percentage, também grava no Redis
    para que o Flask (GET /jobs/.../status) veja o progresso gradual atualizado pelo Celery.
    """
    with lock:
        if job_id in progress:
            progress[job_id].update(updates)
            logger.debug(f"📝 Job {job_id} atualizado: {list(updates.keys())}")
            result = progress[job_id]
        else:
            result = None
    if result and ("progress_current" in updates or "progress_percentage" in updates):
        progress_updates = {k: updates[k] for k in ("progress_current", "progress_percentage") if k in updates}
        if progress_updates:
            update_job_progress_redis(job_id, progress_updates)
    return result


def get_all_active_jobs() -> list:
    """
    Retorna todos os jobs ativos no sistema
    
    Returns:
        Lista com todos os jobs e suas informações
    """
    with lock:
        jobs = []
        for job_id, job_data in progress.items():
            job_copy = job_data.copy()
            job_copy['id'] = job_id
            jobs.append(job_copy)
        return jobs


def delete_job(job_id: str) -> bool:
    """
    Remove job do store (limpeza)
    
    Args:
        job_id: ID do job
    
    Returns:
        bool: True se removido, False se não encontrado
    """
    with lock:
        if job_id in progress:
            del progress[job_id]
            logger.info(f"🗑️ Job {job_id} removido do store")
            return True
        return False


def cleanup_old_jobs(max_age_hours: int = 24):
    """
    Remove jobs antigos do store
    
    Args:
        max_age_hours: Idade máxima em horas para manter jobs
    """
    from datetime import timedelta
    
    cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)
    
    with lock:
        jobs_to_delete = []
        for job_id, job_data in progress.items():
            created_at_str = job_data.get("created_at")
            if created_at_str:
                try:
                    created_at = datetime.fromisoformat(created_at_str)
                    if created_at < cutoff:
                        jobs_to_delete.append(job_id)
                except:
                    pass
        
        for job_id in jobs_to_delete:
            del progress[job_id]
        
        if jobs_to_delete:
            logger.info(f"🧹 Limpeza: {len(jobs_to_delete)} jobs antigos removidos")


def get_all_jobs() -> dict:
    """
    Retorna todos os jobs (para debug/admin)
    
    Returns:
        dict: Todos os jobs
    """
    with lock:
        return dict(progress)








