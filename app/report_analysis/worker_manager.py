# -*- coding: utf-8 -*-
"""
Gerenciador do Celery Worker para iniciar/parar automaticamente com Flask
"""

import sys
import threading
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Variável global para armazenar o worker thread
_worker_thread: Optional[threading.Thread] = None
_worker_process = None


def start_celery_worker(app=None):
    """
    Inicia o Celery worker em uma thread separada.
    
    Args:
        app: Instância da aplicação Flask (opcional, será criada se não fornecida)
    """
    global _worker_thread, _worker_process
    
    if _worker_thread and _worker_thread.is_alive():
        logger.warning("Celery worker já está rodando")
        print("[CELERY WORKER] ⚠️ Worker já está rodando")
        return
    
    try:
        from app.report_analysis.celery_app import celery_app
        
        # Detectar se está no Windows
        is_windows = sys.platform == 'win32'
        
        def run_worker():
            """Função que roda o worker em uma thread separada"""
            try:
                # Importar aqui para garantir que o contexto Flask está disponível
                from app.report_analysis.celery_app import celery_app
                
                # Preparar argumentos do worker
                worker_args = [
                    'worker',
                    '--loglevel=info',
                    '--without-gossip',
                    '--without-mingle',
                    '--without-heartbeat',
                ]
                
                if is_windows:
                    worker_args.append('--pool=solo')
                
                logger.info("Iniciando Celery worker...")
                print("[CELERY WORKER] 🚀 Iniciando worker do Celery...")
                print(f"[CELERY WORKER] 📋 Argumentos: {' '.join(worker_args)}")
                
                # Executar worker
                celery_app.worker_main(worker_args)
                
            except Exception as e:
                logger.error(f"Erro ao executar Celery worker: {str(e)}", exc_info=True)
                print(f"[CELERY WORKER] ❌ Erro ao executar worker: {type(e).__name__}: {str(e)}")
                import traceback
                traceback.print_exc()
        
        # Criar e iniciar thread
        _worker_thread = threading.Thread(
            target=run_worker,
            daemon=True,  # Thread daemon morre quando o processo principal morre
            name="CeleryWorker"
        )
        _worker_thread.start()
        
        logger.info("Celery worker iniciado em thread separada")
        print("[CELERY WORKER] ✅ Worker iniciado com sucesso em thread separada!")
        
    except Exception as e:
        logger.error(f"Erro ao iniciar Celery worker: {str(e)}", exc_info=True)
        print(f"[CELERY WORKER] ❌ Erro ao iniciar worker: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()


def stop_celery_worker():
    """
    Para o Celery worker (se estiver rodando).
    Nota: Como o worker roda em thread daemon, ele será encerrado automaticamente
    quando o processo principal terminar.
    """
    global _worker_thread
    
    if _worker_thread and _worker_thread.is_alive():
        logger.info("Parando Celery worker...")
        print("[CELERY WORKER] 🛑 Parando worker...")
        # Thread daemon será encerrada automaticamente
        _worker_thread = None
    else:
        logger.info("Celery worker não está rodando")
        print("[CELERY WORKER] ℹ️ Worker não está rodando")

