#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para debugar problemas de import
"""
import sys
import os

def test_basic_imports():
    """Testa imports basicos"""
    print("Testando imports basicos...")
    
    try:
        import sqlalchemy
        print("SQLAlchemy OK")
    except Exception as e:
        print(f"SQLAlchemy erro: {e}")
    
    try:
        import psycopg2
        print("psycopg2 OK")
    except Exception as e:
        print(f"psycopg2 erro: {e}")

def test_app_imports():
    """Testa imports da aplicacao"""
    print("\nTestando imports da aplicacao...")
    
    try:
        from app import db
        print("app.db OK")
    except Exception as e:
        print(f"app.db erro: {e}")
    
    try:
        from app.models import Test, Student, TestSession
        print("app.models OK")
    except Exception as e:
        print(f"app.models erro: {e}")

def test_new_imports():
    """Testa imports dos novos arquivos"""
    print("\nTestando imports dos novos arquivos...")
    
    try:
        from app.models.evaluationResult import EvaluationResult
        print("EvaluationResult OK")
    except Exception as e:
        print(f"EvaluationResult erro: {e}")
    
    try:
        from app.services.evaluation_result_service import EvaluationResultService
        print("EvaluationResultService OK")
    except Exception as e:
        print(f"EvaluationResultService erro: {e}")

if __name__ == "__main__":
    print("=== Debug de Imports ===")
    test_basic_imports()
    test_app_imports()
    test_new_imports()
    print("=== Fim do Debug ===") 