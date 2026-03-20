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
import json
import logging
import os
import copy
from typing import Optional

# Dicionário global de progresso (memória; progresso de answer_sheet também vai para Redis)
progress = {}
lock = Lock()

logger = logging.getLogger(__name__)

# Prefixo e TTL para chaves de progresso no Redis (compartilhado entre Flask e Celery)
REDIS_PROGRESS_KEY_PREFIX = "as_job_progress:"
REDIS_JOB_FULL_KEY_PREFIX = "as_job_full:"  # Job completo (JSON) para Flask ver progresso quando worker está em outro processo
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


def _persist_job_to_redis(job_id: str, job_dict: dict) -> None:
    """Persiste o job completo no Redis para o Flask (GET /task/.../status) ver progresso atualizado pelo Celery."""
    r = _get_redis_client()
    if not r:
        return
    key = REDIS_JOB_FULL_KEY_PREFIX + job_id
    try:
        r.set(key, json.dumps(job_dict, default=str), ex=REDIS_PROGRESS_TTL_SEC)
    except Exception as e:
        logger.debug("Falha ao persistir job no Redis: %s", e)


def _get_job_from_redis(job_id: str) -> Optional[dict]:
    """Lê o job completo do Redis. Usado pelo Flask quando o job foi criado/atualizado pelo worker (outro processo)."""
    r = _get_redis_client()
    if not r:
        return None
    key = REDIS_JOB_FULL_KEY_PREFIX + job_id
    try:
        raw = r.get(key)
        if not raw:
            return None
        return json.loads(raw)
    except Exception as e:
        logger.debug("Falha ao ler job do Redis: %s", e)
        return None


def _ensure_job_in_memory(job_id: str) -> bool:
    """
    Garante progress[job_id] preenchido (carrega do Redis se o job foi criado em outro processo,
    ex.: API Flask semeia items e o worker Celery atualiza item a item).
    """
    with lock:
        if job_id in progress:
            return True
        loaded = _get_job_from_redis(job_id)
        if loaded:
            progress[job_id] = loaded
            logger.debug("Job %s carregado do Redis para memória local", job_id)
            return True
        return False


def create_job(
    job_id: str,
    total: int,
    test_id: str = None,
    gabarito_id: str = None,
    user_id: str = None,
    task_ids: list = None,
    items_meta: list = None,
    stage_message: str = None,
) -> dict:
    """
    Cria um novo job de correção em lote.
    
    items_meta: Lista opcional de dicts (um por índice), com chaves opcionais:
        class_id, class_name, school_name, student_id, student_name.
        Se fornecida e len(items_meta)==total, cada item nasce com esses campos
        para o status mostrar turmas corretas desde o início.
    """
    meta_keys = ("class_id", "class_name", "school_name", "student_id", "student_name")
    if items_meta is not None and len(items_meta) == total:
        items = {}
        for i in range(total):
            meta = items_meta[i] or {}
            item = {"status": "pending"}
            for k in meta_keys:
                if k in meta and meta[k] is not None and meta[k] != "":
                    item[k] = meta[k]
            items[str(i)] = item
    else:
        items = {str(i): {"status": "pending"} for i in range(total)}

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
            "items": items,
            "results": [],
            "phase": "generating",
            "stage_message": stage_message or "Gerando formulários PDF...",
        }
        job_snapshot = copy.deepcopy(progress[job_id])
        logger.info(f"📋 Job criado: {job_id} com {total} itens")
    _persist_job_to_redis(job_id, job_snapshot)
    return progress[job_id]


def update_item_processing(job_id: str, index: int, extra: dict = None):
    """
    Marca item como em processamento.
    extra: dict opcional (class_id, class_name, school_name, student_id, student_name) para progresso detalhado.
    """
    if not _ensure_job_in_memory(job_id):
        logger.warning("update_item_processing: job %s não encontrado (memória nem Redis)", job_id)
        return
    with lock:
        if job_id in progress:
            item = {"status": "processing"}
            if extra:
                for key in ("student_id", "student_name", "class_id", "class_name", "school_name"):
                    if key in extra and extra[key] is not None:
                        item[key] = extra[key]
            progress[job_id]["items"][str(index)] = item
            job_snapshot = copy.deepcopy(progress[job_id])
            logger.debug(f"🔄 Job {job_id}: Item {index} em processamento")
        else:
            job_snapshot = None
    if job_snapshot is not None:
        _persist_job_to_redis(job_id, job_snapshot)


def update_item_done(job_id: str, index: int, result: dict):
    """
    Marca item como concluído com sucesso.
    Aceita campos de correção (correct, total, percentage) e/ou de formulários físicos (class_id, class_name, school_name).
    """
    if not _ensure_job_in_memory(job_id):
        logger.warning("update_item_done: job %s não encontrado (memória nem Redis)", job_id)
        return
    with lock:
        if job_id in progress:
            item = {
                "status": "done",
                "student_id": result.get("student_id"),
                "student_name": result.get("student_name"),
                "correct": result.get("correct"),
                "total": result.get("total"),
                "percentage": result.get("percentage"),
                "grade": result.get("grade"),
                "classification": result.get("classification"),
                "proficiency": result.get("proficiency"),
                "class_id": result.get("class_id"),
                "class_name": result.get("class_name"),
                "school_name": result.get("school_name"),
            }
            progress[job_id]["items"][str(index)] = {"status": "done", **{k: v for k, v in item.items() if k != "status" and v is not None}}
            progress[job_id]["completed"] += 1
            progress[job_id]["successful"] += 1
            progress[job_id]["results"].append(result)
            job_snapshot = copy.deepcopy(progress[job_id])
            logger.info(f"✅ Job {job_id}: Item {index} concluído - {result.get('student_name', 'N/A')}")
        else:
            job_snapshot = None
    if job_snapshot is not None:
        _persist_job_to_redis(job_id, job_snapshot)


def update_item_error(job_id: str, index: int, error: str, extra: dict = None):
    """
    Marca item como erro.
    extra: dict opcional com student_id, student_name, class_id, class_name, school_name para status detalhado.
    """
    if not _ensure_job_in_memory(job_id):
        logger.warning("update_item_error: job %s não encontrado (memória nem Redis)", job_id)
        return
    with lock:
        if job_id in progress:
            item = {"status": "error", "error": error}
            if extra:
                for key in ("student_id", "student_name", "class_id", "class_name", "school_name"):
                    if key in extra and extra[key] is not None:
                        item[key] = extra[key]
            progress[job_id]["items"][str(index)] = item
            progress[job_id]["completed"] += 1
            progress[job_id]["failed"] += 1
            job_snapshot = copy.deepcopy(progress[job_id])
            logger.warning(f"❌ Job {job_id}: Item {index} falhou - {error}")
        else:
            job_snapshot = None
    if job_snapshot is not None:
        _persist_job_to_redis(job_id, job_snapshot)


def complete_job(job_id: str):
    """
    Marca job como concluído (phase=done para o frontend saber que terminou).
    """
    if not _ensure_job_in_memory(job_id):
        logger.warning("complete_job: job %s não encontrado (memória nem Redis)", job_id)
        return
    with lock:
        if job_id in progress:
            progress[job_id]["status"] = "completed"
            progress[job_id]["completed_at"] = datetime.utcnow().isoformat()
            progress[job_id]["phase"] = "done"
            progress[job_id]["stage_message"] = "Concluído"
            job_snapshot = copy.deepcopy(progress[job_id])
            logger.info(f"🏁 Job {job_id} concluído: {progress[job_id]['successful']} sucesso, {progress[job_id]['failed']} falhas")
        else:
            job_snapshot = None
    if job_snapshot is not None:
        _persist_job_to_redis(job_id, job_snapshot)


def get_job(job_id: str) -> Optional[dict]:
    """
    Retorna dados do job.

    Se o job existir só no Redis (ex.: Celery), carrega o JSON completo e mescla o hash
    as_job_progress (progress_current / progress_percentage).

    Se existir em memória no processo (ex.: após seed na API), a memória pode estar **obsoleta**
    para items/contadores — o worker atualiza apenas Redis. Nesse caso mesclamos do snapshot
    completo em Redis (items, completed, successful, failed, phase, etc.), sem sobrescrever
    ``total`` (pode ser turmas no DB vs alunos no job de progresso).

    Após mesclar, atualizamos ``progress[job_id]`` para o próximo GET não repetir o problema.
    """
    with lock:
        job_local = progress.get(job_id)
    redis_full = _get_job_from_redis(job_id)

    if job_local is None:
        job = redis_full
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

    job = dict(job_local)
    if redis_full:
        for key in (
            "items",
            "completed",
            "successful",
            "failed",
            "results",
            "phase",
            "stage_message",
            "status",
            "completed_at",
            "warnings",
        ):
            if key in redis_full:
                job[key] = redis_full[key]

    redis_progress = get_job_progress_redis(job_id)
    if redis_progress:
        if "progress_current" in redis_progress:
            job["progress_current"] = redis_progress["progress_current"]
        if "progress_percentage" in redis_progress:
            job["progress_percentage"] = redis_progress["progress_percentage"]

    with lock:
        if job_id in progress:
            progress[job_id] = job

    return job


def update_job(job_id: str, updates: dict) -> dict:
    """
    Atualiza campos específicos de um job.
    Se updates contiver progress_current ou progress_percentage, também grava no Redis
    para que o Flask (GET /jobs/.../status) veja o progresso gradual atualizado pelo Celery.
    """
    if not _ensure_job_in_memory(job_id):
        return None
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


def purge_answer_sheet_job_keys(job_id: str) -> None:
    """
    Remove job da memória local e das chaves Redis usadas pelo progresso de cartões
    (as_job_progress / as_job_full).
    """
    delete_job(job_id)
    r = _get_redis_client()
    if not r:
        return
    try:
        r.delete(REDIS_PROGRESS_KEY_PREFIX + job_id)
        r.delete(REDIS_JOB_FULL_KEY_PREFIX + job_id)
        logger.debug("Redis purgado para job %s", job_id)
    except Exception as e:
        logger.debug("Falha ao purgar Redis do job %s: %s", job_id, e)


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








