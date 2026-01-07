#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Teste rápido para verificar URLs do Celery"""

import sys
import os
from dotenv import load_dotenv

load_dotenv('app/.env')

# Limpar cache do módulo se já foi importado
if 'app.report_analysis.celery_app' in sys.modules:
    del sys.modules['app.report_analysis.celery_app']

from app.report_analysis.celery_app import celery_app, CELERY_BROKER_URL, CELERY_RESULT_BACKEND

print("=" * 60)
print("TESTE DE URLs DO CELERY")
print("=" * 60)
print(f"\nVariáveis do módulo:")
print(f"  CELERY_BROKER_URL: {CELERY_BROKER_URL}")
print(f"  CELERY_RESULT_BACKEND: {CELERY_RESULT_BACKEND}")

print(f"\nConfigurações do Celery:")
print(f"  celery_app.conf.broker_url: {celery_app.conf.broker_url}")
print(f"  celery_app.conf.result_backend: {celery_app.conf.result_backend}")

print(f"\nVerificação:")
if '@' in CELERY_BROKER_URL:
    print("  [OK] CELERY_BROKER_URL tem senha")
else:
    print("  [ERRO] CELERY_BROKER_URL NÃO tem senha")

if '@' in CELERY_RESULT_BACKEND:
    print("  [OK] CELERY_RESULT_BACKEND tem senha")
else:
    print("  [ERRO] CELERY_RESULT_BACKEND NÃO tem senha")

if '@' in celery_app.conf.broker_url:
    print("  [OK] celery_app.conf.broker_url tem senha")
else:
    print("  [ERRO] celery_app.conf.broker_url NÃO tem senha")

if '@' in celery_app.conf.result_backend:
    print("  [OK] celery_app.conf.result_backend tem senha")
else:
    print("  [ERRO] celery_app.conf.result_backend NÃO tem senha")

print("\n" + "=" * 60)

