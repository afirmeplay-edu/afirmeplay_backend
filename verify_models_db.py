#!/usr/bin/env python3
"""
Script para verificar se os campos dos models correspondem ao schema do banco de dados.
"""

import os
import sys
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import json
from datetime import datetime

# Adicionar o diretório do app ao path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

# Carregar variáveis de ambiente
load_dotenv('app/.env')

# Importar models
from app.models import *

def get_database_connection():
    """Conecta ao banco de dados usando a URL do .env"""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL não encontrada no arquivo .env")
    
    engine = create_engine(database_url)
    return engine

def get_table_schema(engine, table_name):
    """Extrai o schema de uma tabela específica"""
    inspector = inspect(engine)
    
    try:
        columns = inspector.get_columns(table_name)
        foreign_keys = inspector.get_foreign_keys(table_name)
        indexes = inspector.get_indexes(table_name)
        
        schema = {
            'columns': {},
            'foreign_keys': foreign_keys,
            'indexes': indexes
        }
        
        for col in columns:
            schema['columns'][col['name']] = {
                'type': str(col['type']),
                'nullable': col['nullable'],
                'default': col['default'],
                'primary_key': col.get('primary_key', False),
                'autoincrement': col.get('autoincrement', False)
            }
        
        return schema
    except Exception as e:
        print(f"Erro ao obter schema da tabela {table_name}: {e}")
        return None

def get_model_fields(model_class):
    """Extrai os campos definidos em um model SQLAlchemy"""
    if not hasattr(model_class, '__table__'):
        return {}
    
    fields = {}
    table = model_class.__table__
    
    for column in table.columns:
        fields[column.name] = {
            'type': str(column.type),
            'nullable': column.nullable,
            'default': column.default,
            'primary_key': column.primary_key,
            'autoincrement': column.autoincrement
        }
    
    return fields

def compare_schemas(model_fields, db_schema):
    """Compara os campos do model com o schema do banco"""
    if not db_schema:
        return {'error': 'Schema do banco não encontrado'}
    
    differences = {
        'missing_in_db': [],
        'missing_in_model': [],
        'type_differences': [],
        'nullable_differences': [],
        'default_differences': []
    }
    
    # Campos que estão no model mas não no banco
    for field_name, field_info in model_fields.items():
        if field_name not in db_schema['columns']:
            differences['missing_in_db'].append({
                'field': field_name,
                'model_info': field_info
            })
    
    # Campos que estão no banco mas não no model
    for field_name, field_info in db_schema['columns'].items():
        if field_name not in model_fields:
            differences['missing_in_model'].append({
                'field': field_name,
                'db_info': field_info
            })
        else:
            # Comparar tipos e propriedades
            model_field = model_fields[field_name]
            
            # Comparar tipos (simplificado)
            if str(model_field['type']) != str(field_info['type']):
                differences['type_differences'].append({
                    'field': field_name,
                    'model_type': str(model_field['type']),
                    'db_type': str(field_info['type'])
                })
            
            # Comparar nullable
            if model_field['nullable'] != field_info['nullable']:
                differences['nullable_differences'].append({
                    'field': field_name,
                    'model_nullable': model_field['nullable'],
                    'db_nullable': field_info['nullable']
                })
    
    return differences

def get_all_models():
    """Retorna todos os models definidos no projeto"""
    models = []
    
    # Lista de todos os models importados no __init__.py
    model_classes = [
        City, School, SchoolTeacher, Teacher, Student, Subject, 
        Class, ClassSubject, ClassTest, Test, TestQuestion, 
        EducationStage, Grade, Skill, Question, StudentAnswer, 
        TestSession, UserQuickLinks, TeacherClass, User, Game, 
        EvaluationResult, Manager
    ]
    
    for model_class in model_classes:
        if hasattr(model_class, '__tablename__'):
            models.append({
                'name': model_class.__name__,
                'table_name': model_class.__tablename__,
                'class': model_class
            })
    
    return models

def generate_report(results):
    """Gera um relatório das diferenças encontradas"""
    report = []
    report.append("=" * 80)
    report.append("RELATÓRIO DE VERIFICAÇÃO: MODELS vs BANCO DE DADOS")
    report.append("=" * 80)
    report.append(f"Data/Hora: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    report.append("")
    
    total_issues = 0
    
    for result in results:
        model_name = result['model_name']
        table_name = result['table_name']
        differences = result['differences']
        
        report.append(f"MODEL: {model_name} (Tabela: {table_name})")
        report.append("-" * 60)
        
        if 'error' in differences:
            report.append(f"❌ ERRO: {differences['error']}")
            total_issues += 1
        else:
            # Campos faltando no banco
            if differences['missing_in_db']:
                report.append("❌ CAMPOS FALTANDO NO BANCO:")
                for diff in differences['missing_in_db']:
                    report.append(f"  - {diff['field']} ({diff['model_info']['type']})")
                    total_issues += 1
            
            # Campos faltando no model
            if differences['missing_in_model']:
                report.append("❌ CAMPOS FALTANDO NO MODEL:")
                for diff in differences['missing_in_model']:
                    report.append(f"  - {diff['field']} ({diff['db_info']['type']})")
                    total_issues += 1
            
            # Diferenças de tipo
            if differences['type_differences']:
                report.append("⚠️  DIFERENÇAS DE TIPO:")
                for diff in differences['type_differences']:
                    report.append(f"  - {diff['field']}: Model({diff['model_type']}) vs DB({diff['db_type']})")
                    total_issues += 1
            
            # Diferenças de nullable
            if differences['nullable_differences']:
                report.append("⚠️  DIFERENÇAS DE NULLABLE:")
                for diff in differences['nullable_differences']:
                    report.append(f"  - {diff['field']}: Model(nullable={diff['model_nullable']}) vs DB(nullable={diff['db_nullable']})")
                    total_issues += 1
            
            if not any([differences['missing_in_db'], differences['missing_in_model'], 
                       differences['type_differences'], differences['nullable_differences']]):
                report.append("✅ Model e banco estão sincronizados!")
        
        report.append("")
    
    report.append("=" * 80)
    report.append(f"TOTAL DE PROBLEMAS ENCONTRADOS: {total_issues}")
    report.append("=" * 80)
    
    return "\n".join(report)

def main():
    """Função principal"""
    try:
        print("Conectando ao banco de dados...")
        engine = get_database_connection()
        
        print("Obtendo lista de models...")
        models = get_all_models()
        
        print(f"Encontrados {len(models)} models para verificar...")
        
        results = []
        
        for model_info in models:
            model_name = model_info['name']
            table_name = model_info['table_name']
            model_class = model_info['class']
            
            print(f"Verificando {model_name}...")
            
            # Obter campos do model
            model_fields = get_model_fields(model_class)
            
            # Obter schema do banco
            db_schema = get_table_schema(engine, table_name)
            
            # Comparar
            differences = compare_schemas(model_fields, db_schema)
            
            results.append({
                'model_name': model_name,
                'table_name': table_name,
                'differences': differences
            })
        
        # Gerar relatório
        report = generate_report(results)
        
        # Salvar relatório
        report_filename = f"model_db_verification_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(report_filename, 'w', encoding='utf-8') as f:
            f.write(report)
        
        print("\n" + report)
        print(f"\nRelatório salvo em: {report_filename}")
        
    except Exception as e:
        print(f"Erro durante a verificação: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
