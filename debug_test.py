#!/usr/bin/env python3
"""
Script para debugar por que uma avaliação específica não está aparecendo
"""

from app import create_app, db
from app.models.test import Test
from app.models.classTest import ClassTest
from app.models.educationStage import EducationStage
from app.models.user import User

def debug_test():
    app = create_app()
    with app.app_context():
        test_id = '054f44d7-24f5-4854-af6b-bb11f4258175'
        
        print("=== DEBUGGING TEST ===")
        print(f"Test ID: {test_id}")
        
        # 1. Verificar se existe na tabela test
        test = Test.query.get(test_id)
        if test:
            print(f"✅ Test encontrado na tabela 'test'")
            print(f"   - Title: {test.title}")
            print(f"   - Status: {test.status}")
            print(f"   - Created by: {test.created_by}")
            print(f"   - Course: {test.course}")
        else:
            print(f"❌ Test NÃO encontrado na tabela 'test'")
            return
        
        # 2. Verificar se existe na tabela class_test
        class_tests = ClassTest.query.filter_by(test_id=test_id).all()
        print(f"\n=== CLASS_TESTS ===")
        print(f"Encontrados {len(class_tests)} registros na tabela 'class_test'")
        
        for ct in class_tests:
            print(f"   - ClassTest ID: {ct.id}")
            print(f"   - Class ID: {ct.class_id}")
            print(f"   - Status: {ct.status}")
            print(f"   - Application: {ct.application}")
            print(f"   - Expiration: {ct.expiration}")
        
        # 3. Verificar se o usuário criador existe
        if test.created_by:
            user = User.query.get(test.created_by)
            if user:
                print(f"\n✅ Usuário criador encontrado: {user.name} ({user.role})")
            else:
                print(f"\n❌ Usuário criador NÃO encontrado: {test.created_by}")
        
        # 4. Verificar se o curso existe
        if test.course:
            try:
                import uuid
                course_uuid = uuid.UUID(test.course)
                course_obj = EducationStage.query.get(course_uuid)
                if course_obj:
                    print(f"\n✅ Curso encontrado: {course_obj.name}")
                else:
                    print(f"\n❌ Curso NÃO encontrado: {test.course}")
            except Exception as e:
                print(f"\n❌ Erro ao buscar curso: {e}")
        
        # 5. Simular a query da rota
        print(f"\n=== SIMULANDO QUERY DA ROTA ===")
        
        # Query base
        query = ClassTest.query.join(Test, ClassTest.test_id == Test.id)
        print(f"Query base: {query}")
        
        # Contar total
        total = query.count()
        print(f"Total de aplicações: {total}")
        
        # Filtrar por test_id específico
        specific_query = query.filter(ClassTest.test_id == test_id)
        specific_count = specific_query.count()
        print(f"Aplicações para este test_id: {specific_count}")
        
        # Verificar se aparece na primeira página
        first_page = query.limit(10).all()
        test_found = any(ct.test_id == test_id for ct in first_page)
        print(f"Aparece na primeira página: {'✅ Sim' if test_found else '❌ Não'}")
        
        # Listar primeiros 5 resultados
        print(f"\n=== PRIMEIROS 5 RESULTADOS ===")
        for i, ct in enumerate(first_page[:5]):
            print(f"{i+1}. Test ID: {ct.test_id}")
            print(f"   - Title: {ct.test.title if ct.test else 'N/A'}")
            print(f"   - Status: {ct.status}")
            print(f"   - Created by: {ct.test.created_by if ct.test else 'N/A'}")

if __name__ == "__main__":
    debug_test() 