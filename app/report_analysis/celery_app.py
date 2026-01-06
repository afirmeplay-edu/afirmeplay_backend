# -*- coding: utf-8 -*-
"""
Configuração do Celery para processamento assíncrono de relatórios
Integração com Flask usando padrão flask-celery
"""

import os
import sys
from celery import Celery
from flask import Flask
from dotenv import load_dotenv

load_dotenv('app/.env')

# Detectar se está rodando no Windows
IS_WINDOWS = sys.platform == 'win32'

# Configuração do Celery
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')

# Se houver senha do Redis separada, adicionar à URL
REDIS_PASSWORD = os.getenv('REDIS_PASSWORD')
if REDIS_PASSWORD and '@' not in CELERY_BROKER_URL:
    # Adicionar senha à URL do Redis
    # Formato: redis://:password@host:port/db
    if CELERY_BROKER_URL.startswith('redis://'):
        parts = CELERY_BROKER_URL.replace('redis://', '').split('/')
        host_port = parts[0]
        db = parts[1] if len(parts) > 1 else '0'
        CELERY_BROKER_URL = f'redis://:{REDIS_PASSWORD}@{host_port}/{db}'
        CELERY_RESULT_BACKEND = f'redis://:{REDIS_PASSWORD}@{host_port}/{db}'
        # Log para debug (apenas em desenvolvimento)
        import logging
        logger = logging.getLogger(__name__)
        logger.debug(f"Senha Redis aplicada. Broker: redis://:***@{host_port}/{db}")

# Criar instância do Celery
# IMPORTANTE: Usar as variáveis já modificadas (com senha se aplicável)
celery_app = Celery(
    'report_analysis',
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=['app.report_analysis.tasks']
)

# Garantir que as URLs com senha sejam usadas (atualizar explicitamente)
# IMPORTANTE: Atualizar antes de qualquer uso do Celery
# Usar setdefault para garantir que as URLs sejam definidas
celery_app.conf.broker_url = CELERY_BROKER_URL
celery_app.conf.result_backend = CELERY_RESULT_BACKEND

# Forçar atualização das conexões
try:
    # Limpar conexões existentes para forçar recriação com novas URLs
    if hasattr(celery_app, '_connection_cache'):
        celery_app._connection_cache.clear()
    if hasattr(celery_app.backend, 'client'):
        # Fechar conexão existente se houver
        try:
            celery_app.backend.client.connection_pool.disconnect()
        except:
            pass
except:
    pass  # Ignorar erros ao limpar cache

# Configurações do Celery
celery_config = {
    'task_serializer': 'json',
    'accept_content': ['json'],
    'result_serializer': 'json',
    'timezone': 'America/Sao_Paulo',
    'enable_utc': True,
    'task_track_started': True,
    'task_time_limit': 300,  # 5 minutos máximo por task
    'task_soft_time_limit': 240,  # 4 minutos soft limit
    'task_acks_late': True,  # Ack apenas após conclusão
    'task_always_eager': False,  # Executar de forma assíncrona
    'task_eager_propagates': True,
}

# Configurações específicas por plataforma
if IS_WINDOWS:
    # Windows: usar pool 'solo' (não suporta prefork)
    celery_config['worker_pool'] = 'solo'
    celery_config['worker_concurrency'] = 1  # Apenas 1 worker no Windows
else:
    # Linux/Unix: usar prefork (padrão)
    celery_config['worker_prefetch_multiplier'] = 1  # Processar uma task por vez
    celery_config['worker_max_tasks_per_child'] = 50  # Reiniciar worker após 50 tasks

celery_app.conf.update(celery_config)

# Configuração de retry
celery_app.conf.task_default_retry_delay = 60  # 1 minuto
celery_app.conf.task_max_retries = 3


def init_celery(app: Flask) -> Celery:
    """
    Inicializa Celery com contexto Flask (padrão flask-celery).
    Deve ser chamado após criar a app Flask.
    
    Args:
        app: Instância da aplicação Flask
    
    Returns:
        Instância do Celery configurada
    """
    class FlaskTask(celery_app.Task):
        """Task com contexto Flask automático"""
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)
    
    # Substituir classe base de Task
    celery_app.Task = FlaskTask
    
    # Atualizar configuração com app context
    celery_app.conf.update(
        task_always_eager=app.config.get('CELERY_ALWAYS_EAGER', False),
        task_eager_propagates=app.config.get('CELERY_EAGER_PROPAGATES', True),
    )
    
    return celery_app

