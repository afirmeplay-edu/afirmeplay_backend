"""
Configuração de logging estruturado para a aplicação Flask.
Inclui RotatingFileHandler para logs rotativos em arquivo.
"""

import logging
from logging.handlers import RotatingFileHandler
import os
from flask import current_app


def setup_logging(app=None):
    """
    Configura o sistema de logging para a aplicação Flask.
    
    Cria:
    - Diretório logs/ se não existir
    - RotatingFileHandler com rotação automática (5MB, 5 backups)
    - Formato estruturado de logs com timestamp, nível, módulo e mensagem
    
    Args:
        app: Instância da aplicação Flask (opcional se usado com current_app)
    """
    if app is None:
        # Se não passar app, tenta usar current_app (precisa estar em contexto)
        try:
            app = current_app
        except RuntimeError:
            # Se não estiver em contexto, cria configuração básica
            _setup_basic_logging()
            return
    
    # Criar diretório de logs se não existir
    logs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs")
    os.makedirs(logs_dir, exist_ok=True)
    
    # Configurar arquivo de log
    log_file = os.path.join(logs_dir, "app.log")
    
    # Criar handler com rotação automática
    # maxBytes: 5MB por arquivo
    # backupCount: manter 5 arquivos de backup
    handler = RotatingFileHandler(
        log_file,
        maxBytes=5_000_000,  # 5MB
        backupCount=5,
        encoding='utf-8'
    )
    
    # Formato estruturado de log
    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s in %(module)s [%(funcName)s:%(lineno)d]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)
    
    # Configurar logger da aplicação
    app.logger.setLevel(logging.INFO)
    
    # Remover handlers duplicados (evitar múltiplos logs)
    if not any(isinstance(h, RotatingFileHandler) for h in app.logger.handlers):
        app.logger.addHandler(handler)
    
    # Também configurar root logger para capturar logs de outros módulos
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    if not any(isinstance(h, RotatingFileHandler) for h in root_logger.handlers):
        root_logger.addHandler(handler)
    
    app.logger.info("Logging configurado com sucesso")


def _setup_basic_logging():
    """Configuração básica de logging quando não há contexto Flask"""
    logs_dir = os.path.join(os.getcwd(), "logs")
    os.makedirs(logs_dir, exist_ok=True)
    
    log_file = os.path.join(logs_dir, "app.log")
    
    handler = RotatingFileHandler(
        log_file,
        maxBytes=5_000_000,
        backupCount=5,
        encoding='utf-8'
    )
    
    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s in %(module)s [%(funcName)s:%(lineno)d]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)
    
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
