#!/usr/bin/env python3
"""
Script para identificar dados órfãos no banco de dados.
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

def check_orphan_data():
    """Verifica dados órfãos no banco"""
    engine = get_database_connection()
    
    queries = [
        # 1. test_questions com question_id inexistente
        ("test_questions com question_id inexistente", """
            SELECT COUNT(*) as quantidade
            FROM test_questions tq 
            LEFT JOIN question q ON tq.question_id = q.id 
            WHERE q.id IS NULL
        """),
        
        # 2. test_questions com test_id inexistente
        ("test_questions com test_id inexistente", """
            SELECT COUNT(*) as quantidade
            FROM test_questions tq 
            LEFT JOIN test t ON tq.test_id = t.id 
            WHERE t.id IS NULL
        """),
        
        # 3. test_sessions com test_id inexistente
        ("test_sessions com test_id inexistente", """
            SELECT COUNT(*) as quantidade
            FROM test_sessions ts 
            LEFT JOIN test t ON ts.test_id = t.id 
            WHERE t.id IS NULL
        """),
        
        # 4. test_sessions com student_id inexistente
        ("test_sessions com student_id inexistente", """
            SELECT COUNT(*) as quantidade
            FROM test_sessions ts 
            LEFT JOIN student s ON ts.student_id = s.id 
            WHERE s.id IS NULL
        """),
        
        # 5. student_answers com question_id inexistente
        ("student_answers com question_id inexistente", """
            SELECT COUNT(*) as quantidade
            FROM student_answers sa 
            LEFT JOIN question q ON sa.question_id = q.id 
            WHERE q.id IS NULL
        """),
        
        # 6. student_answers com test_id inexistente
        ("student_answers com test_id inexistente", """
            SELECT COUNT(*) as quantidade
            FROM student_answers sa 
            LEFT JOIN test t ON sa.test_id = t.id 
            WHERE t.id IS NULL
        """),
        
        # 7. student_answers com student_id inexistente
        ("student_answers com student_id inexistente", """
            SELECT COUNT(*) as quantidade
            FROM student_answers sa 
            LEFT JOIN student s ON sa.student_id = s.id 
            WHERE s.id IS NULL
        """),
        
        # 8. class_test com test_id inexistente
        ("class_test com test_id inexistente", """
            SELECT COUNT(*) as quantidade
            FROM class_test ct 
            LEFT JOIN test t ON ct.test_id = t.id 
            WHERE t.id IS NULL
        """),
        
        # 9. class_test com class_id inexistente
        ("class_test com class_id inexistente", """
            SELECT COUNT(*) as quantidade
            FROM class_test ct 
            LEFT JOIN class c ON ct.class_id = c.id 
            WHERE c.id IS NULL
        """),
        
        # 10. class_subject com class_id inexistente
        ("class_subject com class_id inexistente", """
            SELECT COUNT(*) as quantidade
            FROM class_subject cs 
            LEFT JOIN class c ON cs.class_id = c.id 
            WHERE c.id IS NULL
        """),
        
        # 11. class_subject com subject_id inexistente
        ("class_subject com subject_id inexistente", """
            SELECT COUNT(*) as quantidade
            FROM class_subject cs 
            LEFT JOIN subject s ON cs.subject_id = s.id 
            WHERE s.id IS NULL
        """),
        
        # 12. class_subject com teacher_id inexistente
        ("class_subject com teacher_id inexistente", """
            SELECT COUNT(*) as quantidade
            FROM class_subject cs 
            LEFT JOIN teacher t ON cs.teacher_id = t.id 
            WHERE t.id IS NULL
        """),
        
        # 13. student com user_id inexistente
        ("student com user_id inexistente", """
            SELECT COUNT(*) as quantidade
            FROM student s 
            LEFT JOIN users u ON s.user_id = u.id 
            WHERE u.id IS NULL
        """),
        
        # 14. student com grade_id inexistente
        ("student com grade_id inexistente", """
            SELECT COUNT(*) as quantidade
            FROM student s 
            LEFT JOIN grade g ON s.grade_id = g.id 
            WHERE g.id IS NULL
        """),
        
        # 15. student com class_id inexistente
        ("student com class_id inexistente", """
            SELECT COUNT(*) as quantidade
            FROM student s 
            LEFT JOIN class c ON s.class_id = c.id 
            WHERE c.id IS NULL
        """),
        
        # 16. student com school_id inexistente
        ("student com school_id inexistente", """
            SELECT COUNT(*) as quantidade
            FROM student s 
            LEFT JOIN school sc ON s.school_id = sc.id 
            WHERE sc.id IS NULL
        """),
        
        # 17. teacher com user_id inexistente
        ("teacher com user_id inexistente", """
            SELECT COUNT(*) as quantidade
            FROM teacher t 
            LEFT JOIN users u ON t.user_id = u.id 
            WHERE u.id IS NULL
        """),
        
        # 18. school_teacher com school_id inexistente
        ("school_teacher com school_id inexistente", """
            SELECT COUNT(*) as quantidade
            FROM school_teacher st 
            LEFT JOIN school s ON st.school_id = s.id 
            WHERE s.id IS NULL
        """),
        
        # 19. school_teacher com teacher_id inexistente
        ("school_teacher com teacher_id inexistente", """
            SELECT COUNT(*) as quantidade
            FROM school_teacher st 
            LEFT JOIN teacher t ON st.teacher_id = t.id 
            WHERE t.id IS NULL
        """),
        
        # 20. teacher_class com teacher_id inexistente
        ("teacher_class com teacher_id inexistente", """
            SELECT COUNT(*) as quantidade
            FROM teacher_class tc 
            LEFT JOIN teacher t ON tc.teacher_id = t.id 
            WHERE t.id IS NULL
        """),
        
        # 21. teacher_class com class_id inexistente
        ("teacher_class com class_id inexistente", """
            SELECT COUNT(*) as quantidade
            FROM teacher_class tc 
            LEFT JOIN class c ON tc.class_id = c.id 
            WHERE c.id IS NULL
        """),
        
        # 22. evaluation_results com test_id inexistente
        ("evaluation_results com test_id inexistente", """
            SELECT COUNT(*) as quantidade
            FROM evaluation_results er 
            LEFT JOIN test t ON er.test_id = t.id 
            WHERE t.id IS NULL
        """),
        
        # 23. evaluation_results com student_id inexistente
        ("evaluation_results com student_id inexistente", """
            SELECT COUNT(*) as quantidade
            FROM evaluation_results er 
            LEFT JOIN student s ON er.student_id = s.id 
            WHERE s.id IS NULL
        """),
        
        # 24. evaluation_results com session_id inexistente
        ("evaluation_results com session_id inexistente", """
            SELECT COUNT(*) as quantidade
            FROM evaluation_results er 
            LEFT JOIN test_sessions ts ON er.session_id = ts.id 
            WHERE ts.id IS NULL
        """),
        
        # 25. user_quick_links com user_id inexistente
        ("user_quick_links com user_id inexistente", """
            SELECT COUNT(*) as quantidade
            FROM user_quick_links uql 
            LEFT JOIN users u ON uql.user_id = u.id 
            WHERE u.id IS NULL
        """),
        
        # 26. games com userId inexistente
        ("games com userId inexistente", """
            SELECT COUNT(*) as quantidade
            FROM games g 
            LEFT JOIN users u ON g.userId = u.id 
            WHERE u.id IS NULL
        """),
        
        # 27. manager com user_id inexistente
        ("manager com user_id inexistente", """
            SELECT COUNT(*) as quantidade
            FROM manager m 
            LEFT JOIN users u ON m.user_id = u.id 
            WHERE u.id IS NULL
        """),
        
        # 28. manager com school_id inexistente
        ("manager com school_id inexistente", """
            SELECT COUNT(*) as quantidade
            FROM manager m 
            LEFT JOIN school s ON m.school_id = s.id 
            WHERE s.id IS NULL AND m.school_id IS NOT NULL
        """),
        
        # 29. manager com city_id inexistente
        ("manager com city_id inexistente", """
            SELECT COUNT(*) as quantidade
            FROM manager m 
            LEFT JOIN city c ON m.city_id = c.id 
            WHERE c.id IS NULL AND m.city_id IS NOT NULL
        """),
        
        # 30. question com created_by inexistente
        ("question com created_by inexistente", """
            SELECT COUNT(*) as quantidade
            FROM question q 
            LEFT JOIN users u ON q.created_by = u.id 
            WHERE u.id IS NULL AND q.created_by IS NOT NULL
        """),
        
        # 31. question com last_modified_by inexistente
        ("question com last_modified_by inexistente", """
            SELECT COUNT(*) as quantidade
            FROM question q 
            LEFT JOIN users u ON q.last_modified_by = u.id 
            WHERE u.id IS NULL AND q.last_modified_by IS NOT NULL
        """),
        
        # 32. question com subject_id inexistente
        ("question com subject_id inexistente", """
            SELECT COUNT(*) as quantidade
            FROM question q 
            LEFT JOIN subject s ON q.subject_id = s.id 
            WHERE s.id IS NULL AND q.subject_id IS NOT NULL
        """),
        
        # 33. question com grade_level inexistente
        ("question com grade_level inexistente", """
            SELECT COUNT(*) as quantidade
            FROM question q 
            LEFT JOIN grade g ON q.grade_level = g.id 
            WHERE g.id IS NULL AND q.grade_level IS NOT NULL
        """),
        
        # 34. question com education_stage_id inexistente
        ("question com education_stage_id inexistente", """
            SELECT COUNT(*) as quantidade
            FROM question q 
            LEFT JOIN education_stage es ON q.education_stage_id = es.id 
            WHERE es.id IS NULL AND q.education_stage_id IS NOT NULL
        """),
        
        # 35. test com created_by inexistente
        ("test com created_by inexistente", """
            SELECT COUNT(*) as quantidade
            FROM test t 
            LEFT JOIN users u ON t.created_by = u.id 
            WHERE u.id IS NULL AND t.created_by IS NOT NULL
        """),
        
        # 36. test com subject inexistente
        ("test com subject inexistente", """
            SELECT COUNT(*) as quantidade
            FROM test t 
            LEFT JOIN subject s ON t.subject = s.id 
            WHERE s.id IS NULL AND t.subject IS NOT NULL
        """),
        
        # 37. test com grade_id inexistente
        ("test com grade_id inexistente", """
            SELECT COUNT(*) as quantidade
            FROM test t 
            LEFT JOIN grade g ON t.grade_id = g.id 
            WHERE g.id IS NULL AND t.grade_id IS NOT NULL
        """),
        
        # 38. grade com education_stage_id inexistente
        ("grade com education_stage_id inexistente", """
            SELECT COUNT(*) as quantidade
            FROM grade g 
            LEFT JOIN education_stage es ON g.education_stage_id = es.id 
            WHERE es.id IS NULL AND g.education_stage_id IS NOT NULL
        """),
        
        # 39. skill com subject_id inexistente
        ("skill com subject_id inexistente", """
            SELECT COUNT(*) as quantidade
            FROM skills sk 
            LEFT JOIN subject s ON sk.subject_id = s.id 
            WHERE s.id IS NULL AND sk.subject_id IS NOT NULL
        """),
        
        # 40. skill com grade_id inexistente
        ("skill com grade_id inexistente", """
            SELECT COUNT(*) as quantidade
            FROM skills sk 
            LEFT JOIN grade g ON sk.grade_id = g.id 
            WHERE g.id IS NULL AND sk.grade_id IS NOT NULL
        """),
        
        # 41. class com school_id inexistente
        ("class com school_id inexistente", """
            SELECT COUNT(*) as quantidade
            FROM class c 
            LEFT JOIN school s ON c.school_id = s.id 
            WHERE s.id IS NULL AND c.school_id IS NOT NULL
        """),
        
        # 42. class com grade_id inexistente
        ("class com grade_id inexistente", """
            SELECT COUNT(*) as quantidade
            FROM class c 
            LEFT JOIN grade g ON c.grade_id = g.id 
            WHERE g.id IS NULL AND c.grade_id IS NOT NULL
        """),
        
        # 43. school com city_id inexistente
        ("school com city_id inexistente", """
            SELECT COUNT(*) as quantidade
            FROM school s 
            LEFT JOIN city c ON s.city_id = c.id 
            WHERE c.id IS NULL AND s.city_id IS NOT NULL
        """),
        
        # 44. users com city_id inexistente
        ("users com city_id inexistente", """
            SELECT COUNT(*) as quantidade
            FROM users u 
            LEFT JOIN city c ON u.city_id = c.id 
            WHERE c.id IS NULL AND u.city_id IS NOT NULL
        """),
        
        # 45. student_answers com corrected_by inexistente
        ("student_answers com corrected_by inexistente", """
            SELECT COUNT(*) as quantidade
            FROM student_answers sa 
            LEFT JOIN users u ON sa.corrected_by = u.id 
            WHERE u.id IS NULL AND sa.corrected_by IS NOT NULL
        """),
        
        # 46. test_sessions com corrected_by inexistente
        ("test_sessions com corrected_by inexistente", """
            SELECT COUNT(*) as quantidade
            FROM test_sessions ts 
            LEFT JOIN users u ON ts.corrected_by = u.id 
            WHERE u.id IS NULL AND ts.corrected_by IS NOT NULL
        """)
    ]
    
    print("=" * 80)
    print("VERIFICAÇÃO DE DADOS ÓRFÃOS NO BANCO DE DADOS")
    print("=" * 80)
    print()
    
    total_orphans = 0
    problems_found = []
    
    with engine.connect() as conn:
        for problem_name, query in queries:
            try:
                result = conn.execute(text(query))
                count = result.scalar()
                
                if count > 0:
                    problems_found.append((problem_name, count))
                    total_orphans += count
                    print(f"❌ {problem_name}: {count} registros")
                else:
                    print(f"✅ {problem_name}: 0 registros")
                    
            except Exception as e:
                print(f"⚠️  {problem_name}: ERRO - {e}")
    
    print()
    print("=" * 80)
    print(f"TOTAL DE DADOS ÓRFÃOS ENCONTRADOS: {total_orphans}")
    print("=" * 80)
    
    if problems_found:
        print("\n🔧 COMANDOS SQL PARA LIMPAR DADOS ÓRFÃOS:")
        print("=" * 80)
        
        for problem_name, count in problems_found:
            if "test_questions com question_id" in problem_name:
                print("-- Limpar test_questions com question_id inexistente")
                print("DELETE FROM test_questions WHERE question_id NOT IN (SELECT id FROM question);")
                print()
            elif "test_questions com test_id" in problem_name:
                print("-- Limpar test_questions com test_id inexistente")
                print("DELETE FROM test_questions WHERE test_id NOT IN (SELECT id FROM test);")
                print()
            elif "test_sessions com test_id" in problem_name:
                print("-- Limpar test_sessions com test_id inexistente")
                print("DELETE FROM test_sessions WHERE test_id NOT IN (SELECT id FROM test);")
                print()
            elif "test_sessions com student_id" in problem_name:
                print("-- Limpar test_sessions com student_id inexistente")
                print("DELETE FROM test_sessions WHERE student_id NOT IN (SELECT id FROM student);")
                print()
            elif "student_answers com question_id" in problem_name:
                print("-- Limpar student_answers com question_id inexistente")
                print("DELETE FROM student_answers WHERE question_id NOT IN (SELECT id FROM question);")
                print()
            elif "student_answers com test_id" in problem_name:
                print("-- Limpar student_answers com test_id inexistente")
                print("DELETE FROM student_answers WHERE test_id NOT IN (SELECT id FROM test);")
                print()
            elif "student_answers com student_id" in problem_name:
                print("-- Limpar student_answers com student_id inexistente")
                print("DELETE FROM student_answers WHERE student_id NOT IN (SELECT id FROM student);")
                print()
    
    return total_orphans, problems_found

if __name__ == "__main__":
    try:
        total_orphans, problems = check_orphan_data()
        
        if total_orphans == 0:
            print("\n🎉 NENHUM DADO ÓRFÃO ENCONTRADO!")
            print("O banco está limpo e as migrações devem funcionar perfeitamente.")
        else:
            print(f"\n⚠️  {total_orphans} dados órfãos encontrados.")
            print("Execute os comandos SQL acima para limpar os dados antes de aplicar migrações.")
            
    except Exception as e:
        print(f"Erro durante verificação: {e}")
        import traceback
        traceback.print_exc()
