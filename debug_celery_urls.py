#!/usr/bin/env python
# -*- coding: utf-8 -*-
from dotenv import load_dotenv
import os
load_dotenv('app/.env')

# Importar o módulo diretamente usando importlib
import importlib
celery_module = importlib.import_module('app.report_analysis.celery_app')

print("=== Variáveis do módulo celery_app ===")
print(f"CELERY_BROKER_URL: {celery_module.CELERY_BROKER_URL}")
print(f"CELERY_RESULT_BACKEND: {celery_module.CELERY_RESULT_BACKEND}")
print(f"REDIS_PASSWORD definido: {'Sim' if celery_module.REDIS_PASSWORD else 'Nao'}")

print("\n=== Configurações do Celery ===")
from app.report_analysis import celery_app
print(f"celery_app.conf.broker_url: {celery_app.conf.broker_url}")
print(f"celery_app.conf.result_backend: {celery_app.conf.result_backend}")

print("\n=== Comparação ===")
if '@' in celery_module.CELERY_BROKER_URL:
    print("[OK] CELERY_BROKER_URL do modulo TEM senha")
else:
    print("[ERRO] CELERY_BROKER_URL do modulo NAO TEM senha")

if '@' in celery_app.conf.broker_url:
    print("[OK] broker_url do Celery TEM senha")
else:
    print("[ERRO] broker_url do Celery NAO TEM senha")

if celery_module.CELERY_BROKER_URL == celery_app.conf.broker_url:
    print("✓ URLs são iguais")
else:
    print("✗ URLs são DIFERENTES!")
    print(f"  Módulo: {celery_module.CELERY_BROKER_URL}")
    print(f"  Celery: {celery_app.conf.broker_url}")

