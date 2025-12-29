# -*- coding: utf-8 -*-
"""
Store de progresso para correção em lote de provas físicas
Pode ser migrado para Redis posteriormente para escalabilidade

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

# Dicionário global de progresso
progress = {}
lock = Lock()

logger = logging.getLogger(__name__)


def create_job(job_id: str, total: int, test_id: str = None, gabarito_id: str = None) -> dict:
    """
    Cria um novo job de correção em lote
    
    Args:
        job_id: ID único do job
        total: Número total de imagens a processar
        test_id: ID da prova (opcional)
        gabarito_id: ID do gabarito (opcional)
    
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


def get_job(job_id: str) -> dict:
    """
    Retorna dados do job
    
    Args:
        job_id: ID do job
    
    Returns:
        dict: Dados do job ou None se não encontrado
    """
    with lock:
        return progress.get(job_id)


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








