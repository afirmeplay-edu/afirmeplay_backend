#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para debugar o erro na rota /evaluation-results/opcoes-filtros/avaliacoes
"""

import requests
import json
import sys
import os

# Adicionar o diretório do projeto ao path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_avaliacoes_route():
    """Testa a rota de avaliações com os parâmetros que estão causando erro"""
    
    # URL base (ajuste conforme necessário)
    base_url = "http://127.0.0.1:5000"
    
    # Parâmetros que estão causando o erro 500
    params = {
        'estado': 'ALAGOAS',
        'municipio': '618f56d1-2167-439e-bf0b-d3d2be54271c'
    }
    
    # Headers necessários (ajuste o token conforme necessário)
    headers = {
        'Authorization': 'Bearer SEU_TOKEN_AQUI',  # Substitua pelo token válido
        'Content-Type': 'application/json'
    }
    
    try:
        print("Testando rota de avaliações...")
        print(f"URL: {base_url}/evaluation-results/opcoes-filtros/avaliacoes")
        print(f"Parâmetros: {params}")
        
        response = requests.get(
            f"{base_url}/evaluation-results/opcoes-filtros/avaliacoes",
            params=params,
            headers=headers
        )
        
        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            print("✅ Sucesso!")
            print(f"Response: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
        else:
            print("❌ Erro!")
            print(f"Response: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("❌ Erro de conexão. Verifique se o servidor está rodando.")
    except Exception as e:
        print(f"❌ Erro inesperado: {str(e)}")

def test_database_queries():
    """Testa as queries do banco de dados diretamente"""
    
    try:
        from app import create_app
        from app.models.city import City
        from app.models.school import School
        from app.models.studentClass import Class
        from app.models.grades import Grade
        from app.models.test import Test
        from app.models.classTest import ClassTest
        
        app = create_app()
        
        with app.app_context():
            print("\n=== Testando queries do banco de dados ===")
            
            # Teste 1: Verificar se o município existe
            municipio_id = '618f56d1-2167-439e-bf0b-d3d2be54271c'
            city = City.query.get(municipio_id)
            print(f"1. Município encontrado: {city.name if city else 'NÃO ENCONTRADO'}")
            
            if city:
                # Teste 2: Verificar escolas do município
                escolas = School.query.filter_by(city_id=municipio_id).all()
                print(f"2. Escolas no município: {len(escolas)}")
                
                if escolas:
                    escola_ids = [e.id for e in escolas]
                    print(f"   IDs das escolas: {escola_ids[:5]}...")  # Primeiros 5
                    
                    # Teste 3: Verificar classes das escolas
                    classes = Class.query.filter(Class.school_id.in_(escola_ids)).all()
                    print(f"3. Classes nas escolas: {len(classes)}")
                    
                    if classes:
                        # Teste 4: Verificar se há grades associadas
                        grades = Grade.query.all()
                        print(f"4. Grades disponíveis: {len(grades)}")
                        
                        # Teste 5: Verificar avaliações
                        avaliacoes = Test.query.join(ClassTest, Test.id == ClassTest.test_id)\
                                               .join(Class, ClassTest.class_id == Class.id)\
                                               .join(School, Class.school_id == School.id)\
                                               .join(Grade, Class.grade_id == Grade.id)\
                                               .filter(School.id.in_(escola_ids))\
                                               .distinct().all()
                        
                        print(f"5. Avaliações encontradas: {len(avaliacoes)}")
                        
                        if avaliacoes:
                            print("   Primeiras avaliações:")
                            for i, av in enumerate(avaliacoes[:3]):
                                print(f"   - {av.title} (ID: {av.id})")
                        else:
                            print("   ⚠️ Nenhuma avaliação encontrada!")
                            
                            # Verificar se há dados nas tabelas relacionadas
                            total_tests = Test.query.count()
                            total_class_tests = ClassTest.query.count()
                            print(f"   Total de testes: {total_tests}")
                            print(f"   Total de class_tests: {total_class_tests}")
                    else:
                        print("   ⚠️ Nenhuma classe encontrada!")
                else:
                    print("   ⚠️ Nenhuma escola encontrada!")
            else:
                print("   ⚠️ Município não encontrado!")
                
    except Exception as e:
        print(f"❌ Erro ao testar queries: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("=== Debug da Rota de Avaliações ===\n")
    
    # Teste 1: Queries do banco
    test_database_queries()
    
    print("\n" + "="*50 + "\n")
    
    # Teste 2: Rota HTTP (requer token válido)
    print("Para testar a rota HTTP, você precisa:")
    print("1. Ter o servidor rodando")
    print("2. Ter um token JWT válido")
    print("3. Substituir 'SEU_TOKEN_AQUI' no script")
    print("\nDeseja testar a rota HTTP? (s/n): ", end="")
    
    # Descomente a linha abaixo se quiser testar a rota HTTP
    # test_avaliacoes_route() 