#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Script para verificar colunas da tabela report_aggregates"""

from app import create_app, db
from sqlalchemy import inspect

app = create_app()

with app.app_context():
    inspector = inspect(db.engine)
    
    # Verificar se a tabela existe
    if 'report_aggregates' not in inspector.get_table_names():
        print("ERRO: Tabela 'report_aggregates' nao existe!")
    else:
        print("OK: Tabela 'report_aggregates' existe")
        
        # Obter todas as colunas
        columns = inspector.get_columns('report_aggregates')
        column_names = [col['name'] for col in columns]
        
        print(f"\nColunas encontradas ({len(column_names)}):")
        for col in columns:
            print(f"   - {col['name']} ({col['type']})")
        
        # Verificar colunas específicas de IA
        required_columns = ['ai_analysis', 'ai_analysis_generated_at', 'ai_analysis_is_dirty']
        
        print(f"\nVerificando colunas de IA:")
        for col_name in required_columns:
            if col_name in column_names:
                print(f"   OK: {col_name} - EXISTE")
            else:
                print(f"   ERRO: {col_name} - NAO EXISTE")

