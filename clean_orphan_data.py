#!/usr/bin/env python3
"""
Script para limpar dados órfãos no banco de dados de forma segura.
"""

import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv('app/.env')

def get_database_connection():
    """Conecta ao banco de dados usando a URL do .env"""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL não encontrada no arquivo .env")
    
    engine = create_engine(database_url)
    return engine

def clean_orphan_data():
    """Limpa dados órfãos do banco de forma segura"""
    engine = get_database_connection()
    
    print("=" * 80)
    print("LIMPEZA DE DADOS ÓRFÃOS NO BANCO DE DADOS")
    print("=" * 80)
    print()
    
    # Comandos de limpeza (DELETE)
    delete_commands = [
        ("test_questions com question_id inexistente", """
            DELETE FROM test_questions 
            WHERE question_id NOT IN (SELECT id FROM question)
        """),
        
        ("test_questions com test_id inexistente", """
            DELETE FROM test_questions 
            WHERE test_id NOT IN (SELECT id FROM test)
        """),
        
        ("test_sessions com test_id inexistente", """
            DELETE FROM test_sessions 
            WHERE test_id NOT IN (SELECT id FROM test)
        """),
        
        ("test_sessions com student_id inexistente", """
            DELETE FROM test_sessions 
            WHERE student_id NOT IN (SELECT id FROM student)
        """),
        
        ("student_answers com question_id inexistente", """
            DELETE FROM student_answers 
            WHERE question_id NOT IN (SELECT id FROM question)
        """),
        
        ("student_answers com test_id inexistente", """
            DELETE FROM student_answers 
            WHERE test_id NOT IN (SELECT id FROM test)
        """),
        
        ("student_answers com student_id inexistente", """
            DELETE FROM student_answers 
            WHERE student_id NOT IN (SELECT id FROM student)
        """),
        
        ("class_test com test_id inexistente", """
            DELETE FROM class_test 
            WHERE test_id NOT IN (SELECT id FROM test)
        """),
        
        ("class_test com class_id inexistente", """
            DELETE FROM class_test 
            WHERE class_id NOT IN (SELECT id FROM class)
        """),
        
        ("class_subject com class_id inexistente", """
            DELETE FROM class_subject 
            WHERE class_id NOT IN (SELECT id FROM class)
        """),
        
        ("class_subject com subject_id inexistente", """
            DELETE FROM class_subject 
            WHERE subject_id NOT IN (SELECT id FROM subject)
        """),
        
        ("class_subject com teacher_id inexistente", """
            DELETE FROM class_subject 
            WHERE teacher_id NOT IN (SELECT id FROM teacher)
        """),
        
        ("student com user_id inexistente", """
            DELETE FROM student 
            WHERE user_id NOT IN (SELECT id FROM users)
        """),
        
        ("student com grade_id inexistente", """
            DELETE FROM student 
            WHERE grade_id NOT IN (SELECT id FROM grade)
        """),
        
        ("student com class_id inexistente", """
            DELETE FROM student 
            WHERE class_id NOT IN (SELECT id FROM class)
        """),
        
        ("student com school_id inexistente", """
            DELETE FROM student 
            WHERE school_id NOT IN (SELECT id FROM school)
        """),
        
        ("teacher com user_id inexistente", """
            DELETE FROM teacher 
            WHERE user_id NOT IN (SELECT id FROM users)
        """),
        
        ("school_teacher com school_id inexistente", """
            DELETE FROM school_teacher 
            WHERE school_id NOT IN (SELECT id FROM school)
        """),
        
        ("school_teacher com teacher_id inexistente", """
            DELETE FROM school_teacher 
            WHERE teacher_id NOT IN (SELECT id FROM teacher)
        """),
        
        ("teacher_class com teacher_id inexistente", """
            DELETE FROM teacher_class 
            WHERE teacher_id NOT IN (SELECT id FROM teacher)
        """),
        
        ("teacher_class com class_id inexistente", """
            DELETE FROM teacher_class 
            WHERE class_id NOT IN (SELECT id FROM class)
        """),
        
        ("evaluation_results com test_id inexistente", """
            DELETE FROM evaluation_results 
            WHERE test_id NOT IN (SELECT id FROM test)
        """),
        
        ("evaluation_results com student_id inexistente", """
            DELETE FROM evaluation_results 
            WHERE student_id NOT IN (SELECT id FROM student)
        """),
        
        ("evaluation_results com session_id inexistente", """
            DELETE FROM evaluation_results 
            WHERE session_id NOT IN (SELECT id FROM test_sessions)
        """),
        
        ("user_quick_links com user_id inexistente", """
            DELETE FROM user_quick_links 
            WHERE user_id NOT IN (SELECT id FROM users)
        """),
        
        ("games com userId inexistente", """
            DELETE FROM games 
            WHERE "userId" NOT IN (SELECT id FROM users)
        """),
        
        ("manager com user_id inexistente", """
            DELETE FROM manager 
            WHERE user_id NOT IN (SELECT id FROM users)
        """),
        
        ("manager com school_id inexistente", """
            DELETE FROM manager 
            WHERE school_id IS NOT NULL AND school_id NOT IN (SELECT id FROM school)
        """),
        
        ("manager com city_id inexistente", """
            DELETE FROM manager 
            WHERE city_id IS NOT NULL AND city_id NOT IN (SELECT id FROM city)
        """)
    ]
    
    # Comandos de atualização (UPDATE para NULL)
    update_commands = [
        ("question com created_by inexistente", """
            UPDATE question 
            SET created_by = NULL 
            WHERE created_by IS NOT NULL AND created_by NOT IN (SELECT id FROM users)
        """),
        
        ("question com last_modified_by inexistente", """
            UPDATE question 
            SET last_modified_by = NULL 
            WHERE last_modified_by IS NOT NULL AND last_modified_by NOT IN (SELECT id FROM users)
        """),
        
        ("question com subject_id inexistente", """
            UPDATE question 
            SET subject_id = NULL 
            WHERE subject_id IS NOT NULL AND subject_id NOT IN (SELECT id FROM subject)
        """),
        
        ("question com grade_level inexistente", """
            UPDATE question 
            SET grade_level = NULL 
            WHERE grade_level IS NOT NULL AND grade_level NOT IN (SELECT id FROM grade)
        """),
        
        ("question com education_stage_id inexistente", """
            UPDATE question 
            SET education_stage_id = NULL 
            WHERE education_stage_id IS NOT NULL AND education_stage_id NOT IN (SELECT id FROM education_stage)
        """),
        
        ("test com created_by inexistente", """
            UPDATE test 
            SET created_by = NULL 
            WHERE created_by IS NOT NULL AND created_by NOT IN (SELECT id FROM users)
        """),
        
        ("test com subject inexistente", """
            UPDATE test 
            SET subject = NULL 
            WHERE subject IS NOT NULL AND subject NOT IN (SELECT id FROM subject)
        """),
        
        ("test com grade_id inexistente", """
            UPDATE test 
            SET grade_id = NULL 
            WHERE grade_id IS NOT NULL AND grade_id NOT IN (SELECT id FROM grade)
        """),
        
        ("grade com education_stage_id inexistente", """
            UPDATE grade 
            SET education_stage_id = NULL 
            WHERE education_stage_id IS NOT NULL AND education_stage_id NOT IN (SELECT id FROM education_stage)
        """),
        
        ("skill com subject_id inexistente", """
            UPDATE skills 
            SET subject_id = NULL 
            WHERE subject_id IS NOT NULL AND subject_id NOT IN (SELECT id FROM subject)
        """),
        
        ("skill com grade_id inexistente", """
            UPDATE skills 
            SET grade_id = NULL 
            WHERE grade_id IS NOT NULL AND grade_id NOT IN (SELECT id FROM grade)
        """),
        
        ("class com school_id inexistente", """
            UPDATE class 
            SET school_id = NULL 
            WHERE school_id IS NOT NULL AND school_id NOT IN (SELECT id FROM school)
        """),
        
        ("class com grade_id inexistente", """
            UPDATE class 
            SET grade_id = NULL 
            WHERE grade_id IS NOT NULL AND grade_id NOT IN (SELECT id FROM grade)
        """),
        
        ("school com city_id inexistente", """
            UPDATE school 
            SET city_id = NULL 
            WHERE city_id IS NOT NULL AND city_id NOT IN (SELECT id FROM city)
        """),
        
        ("users com city_id inexistente", """
            UPDATE users 
            SET city_id = NULL 
            WHERE city_id IS NOT NULL AND city_id NOT IN (SELECT id FROM city)
        """),
        
        ("student_answers com corrected_by inexistente", """
            UPDATE student_answers 
            SET corrected_by = NULL 
            WHERE corrected_by IS NOT NULL AND corrected_by NOT IN (SELECT id FROM users)
        """),
        
        ("test_sessions com corrected_by inexistente", """
            UPDATE test_sessions 
            SET corrected_by = NULL 
            WHERE corrected_by IS NOT NULL AND corrected_by NOT IN (SELECT id FROM users)
        """)
    ]
    
    total_deleted = 0
    total_updated = 0
    
    with engine.connect() as conn:
        # Executar comandos DELETE
        print("🗑️  EXECUTANDO COMANDOS DELETE:")
        print("-" * 50)
        
        for description, query in delete_commands:
            try:
                result = conn.execute(text(query))
                deleted_count = result.rowcount
                total_deleted += deleted_count
                
                if deleted_count > 0:
                    print(f"✅ {description}: {deleted_count} registros removidos")
                else:
                    print(f"ℹ️  {description}: 0 registros removidos")
                    
            except Exception as e:
                print(f"❌ {description}: ERRO - {e}")
        
        print()
        
        # Executar comandos UPDATE
        print("🔄 EXECUTANDO COMANDOS UPDATE:")
        print("-" * 50)
        
        for description, query in update_commands:
            try:
                result = conn.execute(text(query))
                updated_count = result.rowcount
                total_updated += updated_count
                
                if updated_count > 0:
                    print(f"✅ {description}: {updated_count} registros atualizados")
                else:
                    print(f"ℹ️  {description}: 0 registros atualizados")
                    
            except Exception as e:
                print(f"❌ {description}: ERRO - {e}")
        
        # Commit das mudanças
        conn.commit()
    
    print()
    print("=" * 80)
    print(f"✅ LIMPEZA CONCLUÍDA!")
    print(f"📊 Total de registros removidos: {total_deleted}")
    print(f"📊 Total de registros atualizados: {total_updated}")
    print("=" * 80)
    
    return total_deleted, total_updated

if __name__ == "__main__":
    try:
        print("⚠️  ATENÇÃO: Este script irá limpar dados órfãos do banco!")
        print("Certifique-se de ter feito backup antes de continuar.")
        print()
        
        response = input("Deseja continuar? (digite 'SIM' para confirmar): ")
        
        if response.upper() == 'SIM':
            deleted, updated = clean_orphan_data()
            
            if deleted > 0 or updated > 0:
                print("\n🎉 Limpeza concluída com sucesso!")
                print("Agora você pode executar as migrações sem problemas.")
            else:
                print("\n✅ Nenhum dado órfão encontrado para limpeza.")
        else:
            print("❌ Operação cancelada pelo usuário.")
            
    except Exception as e:
        print(f"❌ Erro durante limpeza: {e}")
        import traceback
        traceback.print_exc()
