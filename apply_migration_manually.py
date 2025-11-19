#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Script para aplicar migração manualmente via SQL"""

from app import create_app, db

app = create_app()

with app.app_context():
    try:
        # Verificar se as colunas já existem
        inspector = db.inspect(db.engine)
        columns = inspector.get_columns('report_aggregates')
        column_names = [col['name'] for col in columns]
        
        # Aplicar migração se necessário
        with db.engine.connect() as conn:
            if 'ai_analysis' not in column_names:
                print("Adicionando coluna ai_analysis...")
                conn.execute(db.text("""
                    ALTER TABLE report_aggregates 
                    ADD COLUMN ai_analysis JSON DEFAULT '{}'::json
                """))
                conn.commit()
                print("OK: Coluna ai_analysis adicionada")
            else:
                print("Coluna ai_analysis ja existe")
            
            if 'ai_analysis_generated_at' not in column_names:
                print("Adicionando coluna ai_analysis_generated_at...")
                conn.execute(db.text("""
                    ALTER TABLE report_aggregates 
                    ADD COLUMN ai_analysis_generated_at TIMESTAMP
                """))
                conn.commit()
                print("OK: Coluna ai_analysis_generated_at adicionada")
            else:
                print("Coluna ai_analysis_generated_at ja existe")
            
            if 'ai_analysis_is_dirty' not in column_names:
                print("Adicionando coluna ai_analysis_is_dirty...")
                conn.execute(db.text("""
                    ALTER TABLE report_aggregates 
                    ADD COLUMN ai_analysis_is_dirty BOOLEAN DEFAULT false NOT NULL
                """))
                conn.commit()
                print("OK: Coluna ai_analysis_is_dirty adicionada")
            else:
                print("Coluna ai_analysis_is_dirty ja existe")
        
        # Atualizar versão do Alembic
        print("\nAtualizando versao do Alembic...")
        with db.engine.connect() as conn:
            # Verificar se a migração já está registrada
            result = conn.execute(db.text("""
                SELECT version_num FROM alembic_version
            """))
            current_version = result.scalar()
            print(f"Versao atual: {current_version}")
            
            # Se não estiver em a1b2c3d4e5f6, atualizar
            if current_version != 'a1b2c3d4e5f6':
                # Marcar como aplicada (mas manter no merge head)
                print("Migracao aplicada manualmente. Versao mantida no merge head.")
        
        print("\nVerificando colunas novamente...")
        inspector = db.inspect(db.engine)
        columns = inspector.get_columns('report_aggregates')
        column_names = [col['name'] for col in columns]
        
        required_columns = ['ai_analysis', 'ai_analysis_generated_at', 'ai_analysis_is_dirty']
        all_ok = True
        for col_name in required_columns:
            if col_name in column_names:
                print(f"OK: {col_name} existe")
            else:
                print(f"ERRO: {col_name} nao existe")
                all_ok = False
        
        if all_ok:
            print("\nSUCESSO: Todas as colunas foram adicionadas!")
        else:
            print("\nERRO: Algumas colunas nao foram adicionadas")
            
    except Exception as e:
        print(f"ERRO: {str(e)}")
        import traceback
        traceback.print_exc()

