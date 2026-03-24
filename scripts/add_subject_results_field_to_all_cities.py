#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para adicionar campo subject_results (JSONB) à tabela evaluation_results
em todos os schemas de cidades (multi-tenancy)

Uso:
    python scripts/add_subject_results_field_to_all_cities.py

Descrição:
    - Busca todos os schemas city_xxx no banco de dados
    - Adiciona o campo subject_results (JSONB) na tabela evaluation_results de cada schema
    - Registra sucesso/erro para cada schema
"""

import sys
import os

# Adicionar o diretório raiz ao path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from sqlalchemy import text
import logging

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_all_city_schemas():
    """
    Busca todos os schemas de cidades no banco de dados
    
    Returns:
        list: Lista de nomes de schemas (ex: ['city_123', 'city_456'])
    """
    query = text("""
        SELECT schema_name 
        FROM information_schema.schemata 
        WHERE schema_name LIKE 'city_%'
        ORDER BY schema_name
    """)
    
    result = db.session.execute(query)
    schemas = [row[0] for row in result]
    
    logger.info(f"Encontrados {len(schemas)} schemas de cidades")
    return schemas


def check_column_exists(schema_name, table_name, column_name):
    """
    Verifica se uma coluna existe em uma tabela de um schema específico
    
    Args:
        schema_name: Nome do schema
        table_name: Nome da tabela
        column_name: Nome da coluna
        
    Returns:
        bool: True se a coluna existe, False caso contrário
    """
    query = text("""
        SELECT EXISTS (
            SELECT 1 
            FROM information_schema.columns 
            WHERE table_schema = :schema_name 
            AND table_name = :table_name 
            AND column_name = :column_name
        )
    """)
    
    result = db.session.execute(
        query,
        {
            'schema_name': schema_name,
            'table_name': table_name,
            'column_name': column_name
        }
    )
    
    return result.scalar()


def add_subject_results_column(schema_name):
    """
    Adiciona o campo subject_results à tabela evaluation_results de um schema
    
    Args:
        schema_name: Nome do schema (ex: 'city_123')
        
    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        # Verificar se a coluna já existe
        if check_column_exists(schema_name, 'evaluation_results', 'subject_results'):
            return True, f"Campo 'subject_results' já existe no schema {schema_name}"
        
        # Adicionar a coluna
        alter_query = text(f"""
            ALTER TABLE {schema_name}.evaluation_results 
            ADD COLUMN subject_results JSONB NULL
        """)
        
        db.session.execute(alter_query)
        db.session.commit()
        
        logger.info(f"✅ Campo adicionado com sucesso no schema: {schema_name}")
        return True, f"Campo adicionado com sucesso"
        
    except Exception as e:
        db.session.rollback()
        error_msg = f"Erro ao adicionar campo no schema {schema_name}: {str(e)}"
        logger.error(f"❌ {error_msg}")
        return False, error_msg


def main():
    """
    Função principal do script
    """
    logger.info("=" * 80)
    logger.info("Iniciando script para adicionar campo subject_results")
    logger.info("=" * 80)
    
    app = create_app()
    
    with app.app_context():
        # Buscar todos os schemas de cidades
        schemas = get_all_city_schemas()
        
        if not schemas:
            logger.warning("⚠️  Nenhum schema de cidade encontrado!")
            return
        
        # Contadores
        success_count = 0
        error_count = 0
        already_exists_count = 0
        
        # Processar cada schema
        logger.info(f"\nProcessando {len(schemas)} schemas...")
        logger.info("-" * 80)
        
        for i, schema_name in enumerate(schemas, 1):
            logger.info(f"\n[{i}/{len(schemas)}] Processando schema: {schema_name}")
            
            success, message = add_subject_results_column(schema_name)
            
            if success:
                if "já existe" in message:
                    already_exists_count += 1
                else:
                    success_count += 1
            else:
                error_count += 1
        
        # Resumo final
        logger.info("\n" + "=" * 80)
        logger.info("RESUMO DA EXECUÇÃO")
        logger.info("=" * 80)
        logger.info(f"Total de schemas processados: {len(schemas)}")
        logger.info(f"✅ Sucesso (campo adicionado): {success_count}")
        logger.info(f"ℹ️  Campo já existia: {already_exists_count}")
        logger.info(f"❌ Erros: {error_count}")
        logger.info("=" * 80)
        
        if error_count > 0:
            logger.warning("\n⚠️  Alguns schemas apresentaram erros. Verifique os logs acima.")
            sys.exit(1)
        else:
            logger.info("\n🎉 Script executado com sucesso!")
            sys.exit(0)


if __name__ == '__main__':
    main()
