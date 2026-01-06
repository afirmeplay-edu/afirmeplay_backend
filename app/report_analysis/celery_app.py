# -*- coding: utf-8 -*-
"""
Configuração do Celery para processamento assíncrono de relatórios
Integração com Flask usando padrão flask-celery
"""

import os
from celery import Celery
from flask import Flask
from dotenv import load_dotenv

load_dotenv('app/.env')

# Configuração do Celery
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')

# Criar instância do Celery
celery_app = Celery(
    'report_analysis',
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=['app.report_analysis.tasks']
)

# Configurações do Celery
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='America/Sao_Paulo',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5 minutos máximo por task
    task_soft_time_limit=240,  # 4 minutos soft limit
    worker_prefetch_multiplier=1,  # Processar uma task por vez
    task_acks_late=True,  # Ack apenas após conclusão
    worker_max_tasks_per_child=50,  # Reiniciar worker após 50 tasks
    task_always_eager=False,  # Executar de forma assíncrona
    task_eager_propagates=True,
)

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

