#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para preparar contexto Flask para o Celery Worker
O worker deve ser iniciado via CLI: celery -A app.report_analysis.celery_app worker --loglevel=info
"""

import os
import sys
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv("app/.env")

# Adicionar o diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.report_analysis.celery_app import init_celery

def main():
    """
    Prepara o contexto Flask para o Celery Worker.
    O worker deve ser iniciado via comando CLI separado.
    """
    app = create_app()
    init_celery(app)
    
    print("=" * 60)
    print("Celery worker pronto para iniciar via CLI")
    print("=" * 60)
    print()
    print("Para iniciar o worker, execute:")
    print()
    if sys.platform == 'win32':
        print("  celery -A app.report_analysis.celery_app worker --loglevel=info --pool=solo")
    else:
        print("  celery -A app.report_analysis.celery_app worker --loglevel=info")
    print()
    print("=" * 60)

if __name__ == "__main__":
    main()

