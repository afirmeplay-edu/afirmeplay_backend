"""
Configuração de logging estruturado para a aplicação Flask.
Logs são enviados para o terminal (stdout) para facilitar debug em desenvolvimento.
"""

import logging
import sys
from flask import current_app


def setup_logging(app=None):
    """
    Configura o sistema de logging para a aplicação Flask.
    
    Usa StreamHandler (stdout) para exibir logs no terminal do servidor.
    Formato estruturado com timestamp, nível, módulo e mensagem.
    
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
    
    # Um único handler para terminal (stdout), compartilhado entre app e root logger
    handler = logging.StreamHandler(sys.stdout)
    
    # Formato estruturado de log
    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s in %(module)s [%(funcName)s:%(lineno)d]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)
    
    # Configurar logger da aplicação
    app.logger.setLevel(logging.INFO)
    
    # Remover handlers duplicados (evitar múltiplos logs)
    if not any(isinstance(h, logging.StreamHandler) for h in app.logger.handlers):
        app.logger.addHandler(handler)
    
    # Também configurar root logger para capturar logs de outros módulos (mesmo handler)
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    if not any(isinstance(h, logging.StreamHandler) for h in root_logger.handlers):
        root_logger.addHandler(handler)
    
    app.logger.info("Logging configurado com sucesso (saída no terminal)")


def _setup_basic_logging():
    """Configuração básica de logging quando não há contexto Flask (saída no terminal)."""
    handler = logging.StreamHandler(sys.stdout)
    
    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s in %(module)s [%(funcName)s:%(lineno)d]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)
    
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
