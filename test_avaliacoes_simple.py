#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Teste simples da função obter_avaliacoes
"""

import sys
import os

# Adicionar o diretório do projeto ao path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_obter_avaliacoes():
    """Testa a função obter_avaliacoes diretamente"""
    
    try:
        from app import create_app
        from app.models.city import City
        from app.models.school import School
        from app.models.studentClass import Class
        from app.models.grades import Grade
        from app.models.test import Test
        from app.models.classTest import ClassTest
        from sqlalchemy import func
        
        app = create_app()
        
        with app.app_context():
            print("=== Teste da função obter_avaliacoes ===\n")
            
            # Parâmetros de teste
            estado = 'ALAGOAS'
            municipio = '618f56d1-2167-439e-bf0b-d3d2be54271c'
            escola = None
            serie = None
            turma = None
            
            print(f"Parâmetros: estado={estado}, municipio={municipio}")
            print(f"escola={escola}, serie={serie}, turma={turma}\n")
            
            # Teste 1: Verificar se o município existe
            city = City.query.get(municipio)
            if not city:
                city = City.query.filter(City.name.ilike(f"%{municipio}%")).first()
            
            print(f"1. Município encontrado: {city.name if city else 'NÃO ENCONTRADO'}")
            
            if not city:
                print("❌ Município não encontrado!")
                return
            
            # Teste 2: Buscar escolas do município
            escolas = School.query.filter_by(city_id=city.id).all()
            print(f"2. Escolas no município: {len(escolas)}")
            
            if not escolas:
                print("❌ Nenhuma escola encontrada no município!")
                return
            
            escola_ids = [e.id for e in escolas]
            print(f"   IDs das escolas: {escola_ids[:3]}...")  # Primeiros 3
            
            # Teste 3: Verificar se há classes nas escolas
            classes = Class.query.filter(Class.school_id.in_(escola_ids)).all()
            print(f"3. Classes nas escolas: {len(classes)}")
            
            if not classes:
                print("❌ Nenhuma classe encontrada nas escolas!")
                return
            
            # Teste 4: Verificar se há class_tests
            class_tests = ClassTest.query.filter(ClassTest.class_id.in_([c.id for c in classes])).all()
            print(f"4. ClassTests encontrados: {len(class_tests)}")
            
            if not class_tests:
                print("❌ Nenhum ClassTest encontrado!")
                return
            
            # Teste 5: Verificar se há testes
            test_ids = [ct.test_id for ct in class_tests]
            tests = Test.query.filter(Test.id.in_(test_ids)).all()
            print(f"5. Testes encontrados: {len(tests)}")
            
            if not tests:
                print("❌ Nenhum teste encontrado!")
                return
            
            # Teste 6: Query completa com LEFT JOIN
            print("\n6. Testando query completa...")
            
            query_avaliacoes = Test.query.join(ClassTest, Test.id == ClassTest.test_id)\
                                        .join(Class, ClassTest.class_id == Class.id)\
                                        .join(School, Class.school_id == School.id)\
                                        .outerjoin(Grade, Class.grade_id == Grade.id)\
                                        .filter(School.id.in_(escola_ids))\
                                        .distinct()
            
            print(f"   Query SQL: {query_avaliacoes}")
            
            try:
                avaliacoes = query_avaliacoes.all()
                print(f"   ✅ Avaliações encontradas: {len(avaliacoes)}")
                
                if avaliacoes:
                    print("   Primeiras avaliações:")
                    for i, av in enumerate(avaliacoes[:3]):
                        print(f"   - {av.title} (ID: {av.id})")
                        
                    # Teste 7: Verificar se há grades associadas
                    grades_with_tests = Grade.query.join(Class, Grade.id == Class.grade_id)\
                                                  .join(ClassTest, Class.id == ClassTest.class_id)\
                                                  .join(Test, ClassTest.test_id == Test.id)\
                                                  .filter(Test.id.in_([a.id for a in avaliacoes]))\
                                                  .distinct().all()
                    
                    print(f"\n7. Grades com testes: {len(grades_with_tests)}")
                    for grade in grades_with_tests:
                        print(f"   - {grade.name} (ID: {grade.id})")
                        
                else:
                    print("   ⚠️ Nenhuma avaliação encontrada na query!")
                    
            except Exception as e:
                print(f"   ❌ Erro na query: {str(e)}")
                import traceback
                traceback.print_exc()
                
    except Exception as e:
        print(f"❌ Erro geral: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_obter_avaliacoes() 