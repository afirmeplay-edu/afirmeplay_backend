#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Teste simples de conexão Celery + Redis
Testa se o Celery consegue executar uma task e retornar resultado
"""

from app.report_analysis.celery_app import celery_app

@celery_app.task
def ping():
    return "pong"

if __name__ == "__main__":
    print("Enviando task ping()...")
    result = ping.delay()
    print(f"Task ID: {result.id}")
    print("Aguardando resultado (timeout: 10s)...")
    try:
        response = result.get(timeout=10)
        print(f"✅ Sucesso! Resposta: {response}")
    except Exception as e:
        print(f"❌ Erro: {type(e).__name__}: {str(e)}")
        print("\nCertifique-se de que o worker está rodando:")
        print("  celery -A app.report_analysis.celery_app worker --loglevel=info --pool=solo")
