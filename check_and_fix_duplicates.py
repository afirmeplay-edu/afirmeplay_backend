#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para verificar e corrigir duplicatas de nomes de turmas
e adicionar constraint UNIQUE(school_id, name) em schemas multi-tenant
"""

import psycopg2
from psycopg2 import sql
import os
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv('.env')

DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:devpass@127.0.0.1:5432/afirmeplay_dev')

def get_city_schemas(cursor):
    """Obtém todos os schemas city_*"""
    cursor.execute("""
        SELECT schema_name 
        FROM information_schema.schemata 
        WHERE schema_name LIKE 'city_%'
        ORDER BY schema_name;
    """)
    return [row[0] for row in cursor.fetchall()]

def process_schema(cursor, schema_name, auto_fix=False):
    """Processa duplicatas e constraint para um schema específico"""
    print(f"\n{'='*60}")
    print(f"📍 Processando schema: {schema_name}")
    print(f"{'='*60}")
    
    total_renamed = 0
    
    try:
        # 1. Verificar duplicatas
        cursor.execute(sql.SQL("""
            SELECT school_id, name, COUNT(*) as count
            FROM {schema}.class
            GROUP BY school_id, name
            HAVING COUNT(*) > 1
            ORDER BY count DESC;
        """).format(schema=sql.Identifier(schema_name)))
        
        duplicates = cursor.fetchall()
        
        if duplicates:
            print(f"\n⚠️  Encontradas {len(duplicates)} combinações duplicadas em {schema_name}:")
            for school_id, name, count in duplicates[:5]:  # Mostrar apenas 5
                print(f"   - Escola: {school_id}, Turma: '{name}' - {count} turmas")
            if len(duplicates) > 5:
                print(f"   ... e mais {len(duplicates) - 5} combinações")
            
            if auto_fix:
                print(f"\n🔧 Renomeando duplicatas em {schema_name}...")
                cursor.execute(sql.SQL("""
                    WITH duplicates AS (
                        SELECT id, school_id, name,
                               ROW_NUMBER() OVER (PARTITION BY school_id, name ORDER BY id) as rn
                        FROM {schema}.class
                    )
                    UPDATE {schema}.class
                    SET name = {schema}.class.name || ' (' || duplicates.rn || ')'
                    FROM duplicates
                    WHERE {schema}.class.id = duplicates.id 
                      AND duplicates.rn > 1
                    RETURNING {schema}.class.id, {schema}.class.name;
                """).format(schema=sql.Identifier(schema_name)))
                
                renamed = cursor.fetchall()
                total_renamed = len(renamed)
                print(f"✅ {total_renamed} turmas renomeadas em {schema_name}")
                for class_id, new_name in renamed[:3]:  # Mostrar apenas 3
                    print(f"   - ID: {class_id} → '{new_name}'")
                if len(renamed) > 3:
                    print(f"   ... e mais {len(renamed) - 3} turmas")
            else:
                return False, duplicates
        else:
            print(f"✅ Nenhuma duplicata encontrada em {schema_name}")
        
        # 2. Verificar se constraint já existe
        cursor.execute("""
            SELECT constraint_name 
            FROM information_schema.table_constraints 
            WHERE table_schema = %s
              AND table_name = 'class' 
              AND constraint_name = 'unique_class_name_per_school';
        """, (schema_name,))
        
        constraint_exists = cursor.fetchone()
        
        if constraint_exists:
            print(f"✅ Constraint já existe em {schema_name}")
        else:
            # 3. Adicionar constraint
            print(f"➕ Adicionando constraint em {schema_name}...")
            cursor.execute(sql.SQL("""
                ALTER TABLE {schema}.class 
                ADD CONSTRAINT unique_class_name_per_school 
                UNIQUE (school_id, name);
            """).format(schema=sql.Identifier(schema_name)))
            
            print(f"✅ Constraint adicionada em {schema_name}")
        
        return True, total_renamed
        
    except psycopg2.Error as e:
        print(f"\n❌ Erro ao processar {schema_name}: {e}")
        return False, 0

def main():
    print("🔍 Conectando ao banco de dados...")
    
    # Conectar ao banco
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    try:
        # Obter todos os schemas city_*
        print("\n📂 Buscando schemas city_*...")
        city_schemas = get_city_schemas(cursor)
        
        if not city_schemas:
            print("❌ Nenhum schema city_* encontrado!")
            return
        
        print(f"✅ Encontrados {len(city_schemas)} schemas:")
        for schema in city_schemas:
            print(f"   - {schema}")
        
        # Primeira passagem: verificar duplicatas em todos os schemas
        print("\n" + "="*60)
        print("🔍 FASE 1: Verificando duplicatas em todos os schemas")
        print("="*60)
        
        schemas_with_duplicates = []
        for schema in city_schemas:
            cursor.execute(sql.SQL("""
                SELECT COUNT(*)
                FROM (
                    SELECT school_id, name, COUNT(*) as count
                    FROM {schema}.class
                    GROUP BY school_id, name
                    HAVING COUNT(*) > 1
                ) AS dups;
            """).format(schema=sql.Identifier(schema)))
            
            dup_count = cursor.fetchone()[0]
            if dup_count > 0:
                schemas_with_duplicates.append((schema, dup_count))
                print(f"⚠️  {schema}: {dup_count} duplicatas")
            else:
                print(f"✅ {schema}: sem duplicatas")
        
        # Se houver duplicatas, perguntar se deve corrigir
        auto_fix = False
        if schemas_with_duplicates:
            print(f"\n⚠️  Total de schemas com duplicatas: {len(schemas_with_duplicates)}")
            response = input("\n❓ Deseja renomear automaticamente TODAS as duplicatas? (s/n): ")
            auto_fix = response.lower() == 's'
            
            if not auto_fix:
                print("❌ Operação cancelada. Corrija as duplicatas manualmente antes de adicionar as constraints.")
                return
        
        # Segunda passagem: processar cada schema
        print("\n" + "="*60)
        print("🔧 FASE 2: Processando schemas")
        print("="*60)
        
        total_schemas_processed = 0
        total_renamed_global = 0
        
        for schema in city_schemas:
            success, renamed_count = process_schema(cursor, schema, auto_fix)
            if success:
                total_schemas_processed += 1
                total_renamed_global += renamed_count
        
        # Commit final
        conn.commit()
        
        # Resumo final
        print("\n" + "="*60)
        print("✨ RESUMO FINAL")
        print("="*60)
        print(f"✅ Schemas processados: {total_schemas_processed}/{len(city_schemas)}")
        print(f"✅ Total de turmas renomeadas: {total_renamed_global}")
        print(f"✅ Constraint adicionada em todos os schemas")
        print("\n✨ Processo concluído com sucesso!")
        
    except psycopg2.Error as e:
        print(f"\n❌ Erro ao executar operação: {e}")
        conn.rollback()
    
    finally:
        cursor.close()
        conn.close()
        print("\n🔌 Conexão fechada.")

if __name__ == "__main__":
    main()
