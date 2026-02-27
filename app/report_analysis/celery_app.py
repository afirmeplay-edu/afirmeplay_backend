# -*- coding: utf-8 -*-
"""
Configuração do Celery para processamento assíncrono de relatórios
Integração com Flask usando padrão flask-celery

==============================================================
RELATÓRIOS QUE USAM ESTE ARQUIVO:
  - Análise das Avaliações  (frontend: AnaliseAvaliacoes / analise-avaliacoes)
  - Relatório Escolar       (frontend: RelatorioEscolar)

RESPONSABILIDADE:
  Inicialização e configuração da instância Celery usada por
  app/report_analysis/tasks.py para processar relatórios em background.

ARQUIVOS RELACIONADOS AO SISTEMA DE RELATÓRIOS:
  app/report_analysis/routes.py       → rotas Flask
  app/report_analysis/tasks.py        → tasks Celery (usa esta instância)
  app/report_analysis/services.py     → ReportAggregateService (cache no banco)
  app/report_analysis/calculations.py → re-exporta funções de cálculo
  app/report_analysis/debounce.py     → debounce Redis
  app/report_analysis/celery_app.py   ← este arquivo (configuração do Celery)
  app/routes/report_routes.py         → funções de cálculo + _determinar_escopo_por_role
  app/routes/evaluation_results_routes.py → dados tabulares (/avaliacoes e /opcoes-filtros)
==============================================================
"""

import os
import sys
from pathlib import Path
from celery import Celery
from flask import Flask
from dotenv import load_dotenv

# Carregar .env pelo caminho absoluto (funciona mesmo quando Celery é iniciado de outro diretório)
_project_root = Path(__file__).resolve().parent.parent.parent
_env_path = _project_root / 'app' / '.env'
load_dotenv(_env_path)

# Detectar se está rodando no Windows
IS_WINDOWS = sys.platform == 'win32'

# Carregar variáveis de ambiente — APENAS Redis local via .env (sem fallback para VPS)
REDIS_PASSWORD = os.getenv('REDIS_PASSWORD')
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
# Garantir que broker e backend vêm só do .env; default único é localhost:6379

# Se Redis exige senha e a URL não contém senha, inserir (evita "Connection closed by server")
def _ensure_redis_auth(url: str, password: str | None) -> str:
    if not password or ':@' in url or url.startswith('redis://:'):
        return url
    # redis://localhost:6379/0 -> redis://:senha@localhost:6379/0
    if url.startswith('redis://'):
        return url.replace('redis://', f'redis://:{password}@', 1)
    return url

CELERY_BROKER_URL = _ensure_redis_auth(CELERY_BROKER_URL, REDIS_PASSWORD)
CELERY_RESULT_BACKEND = _ensure_redis_auth(CELERY_RESULT_BACKEND, REDIS_PASSWORD)

# Criar instância do Celery com URLs SEM senha
# A senha será configurada separadamente via redis_password
celery_app = Celery(
    'report_analysis',
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=[
        'app.report_analysis.tasks',
        'app.services.celery_tasks.physical_test_tasks',  # Tasks de geração de formulários físicos
        'app.services.celery_tasks.answer_sheet_tasks',  # Tasks de geração de cartões de resposta
        'app.services.celery_tasks.evaluation_recalculation_tasks',  # Tasks de recálculo de resultados
        'app.socioeconomic_forms.services.results_tasks',  # Tasks de resultados socioeconômicos
        'app.socioeconomic_forms.services.results_migration_tasks',  # Tasks de migração/população inicial
        'app.services.celery_tasks.competition_tasks',  # Tasks de finalização de competições
    ]
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
    task_acks_late=True,  # Ack apenas após conclusão
    task_always_eager=False,  # Executar de forma assíncrona
    task_eager_propagates=True,
)

# 🔥 ÚNICA FORMA CORRETA DE PASSAR SENHA PARA REDIS NO CELERY
# O Celery espera redis_password, não senha na URL nem transport_options
if REDIS_PASSWORD:
    celery_app.conf.redis_password = REDIS_PASSWORD

# Configurações específicas por plataforma
if IS_WINDOWS:
    celery_app.conf.worker_pool = 'solo'
    celery_app.conf.worker_concurrency = 1  # Apenas 1 worker no Windows
else:
    # Linux/Unix: usar prefork (padrão)
    celery_app.conf.worker_prefetch_multiplier = 1  # Processar uma task por vez
    celery_app.conf.worker_max_tasks_per_child = 50  # Reiniciar worker após 50 tasks

# Configuração de retry
celery_app.conf.task_default_retry_delay = 60  # 1 minuto
celery_app.conf.task_max_retries = 3

# Celery Beat: processar competições expiradas a cada hora
from celery.schedules import crontab
celery_app.conf.beat_schedule = {
    # Finalização de competições expiradas (ranking, snapshot e pagamentos)
    "process-finished-competitions": {
        "task": "competition_tasks.process_finished_competitions",
        "schedule": crontab(minute=0, hour="*"),  # a cada hora
    },
}

# 🔥 CRÍTICO: Criar app Flask automaticamente quando o módulo é importado pelo worker
# Isso garante que o contexto Flask esteja disponível mesmo quando iniciado via CLI
_flask_app = None

def _get_flask_app():
    """Obtém ou cria a instância Flask (singleton)"""
    global _flask_app
    if _flask_app is None:
        from app import create_app
        _flask_app = create_app()
    return _flask_app

# Configurar FlaskTask que cria contexto automaticamente
class FlaskTask(celery_app.Task):
    """Task com contexto Flask automático"""
    def __call__(self, *args, **kwargs):
        app = _get_flask_app()
        with app.app_context():
            return self.run(*args, **kwargs)

# Substituir classe base de Task ANTES de qualquer task ser registrada
celery_app.Task = FlaskTask


def init_celery(app: Flask) -> Celery:
    """
    Inicializa Celery com contexto Flask (padrão flask-celery).
    Deve ser chamado após criar a app Flask.
    
    Args:
        app: Instância da aplicação Flask
    
    Returns:
        Instância do Celery configurada
    
    Nota: O FlaskTask já está configurado globalmente, mas esta função
    permite atualizar configurações específicas da app.
    """
    global _flask_app
    # Armazenar a app Flask fornecida (pode ser diferente da criada automaticamente)
    _flask_app = app
    
    # Atualizar configuração com app context
    celery_app.conf.update(
        task_always_eager=app.config.get('CELERY_ALWAYS_EAGER', False),
        task_eager_propagates=app.config.get('CELERY_EAGER_PROPAGATES', True),
    )
    
    return celery_app
