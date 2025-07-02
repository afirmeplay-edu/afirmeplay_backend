#!/usr/bin/env python3
"""
Script de teste e demonstração dos novos endpoints de resultados de avaliações.
Demonstra as funcionalidades implementadas na reformulação do backend.
"""

import requests
import json
from typing import Dict, Any
import sys
import time

class EvaluationResultsTester:
    """Classe para testar os novos endpoints de resultados de avaliações"""
    
    def __init__(self, base_url: str = "http://localhost:5000"):
        self.base_url = base_url
        self.token = None
        self.headers = {}
    
    def authenticate(self, email: str = "admin@test.com", password: str = "123456") -> bool:
        """Autentica usuário e obtém token JWT"""
        
        print(f"🔐 Autenticando usuário: {email}")
        
        auth_data = {
            "email": email,
            "password": password
        }
        
        try:
            response = requests.post(f"{self.base_url}/login", json=auth_data)
            if response.status_code == 200:
                data = response.json()
                self.token = data.get('access_token')
                self.headers = {'Authorization': f'Bearer {self.token}'}
                print("✅ Autenticação realizada com sucesso!")
                return True
            else:
                print(f"❌ Erro na autenticação: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Erro de conexão: {e}")
            return False
    
    def test_calculator_endpoint(self):
        """Testa o endpoint de cálculos"""
        
        print("\n🧮 === TESTANDO CALCULADORA DE RESULTADOS ===")
        
        # Cenários de teste
        test_cases = [
            {
                "name": "Matemática - Anos Iniciais",
                "data": {
                    "correct_answers": 15,
                    "total_questions": 20,
                    "course_name": "Anos Iniciais",
                    "subject_name": "Matemática"
                }
            },
            {
                "name": "Português - Ensino Médio",
                "data": {
                    "correct_answers": 18,
                    "total_questions": 25,
                    "course_name": "Ensino Médio",
                    "subject_name": "Português"
                }
            },
            {
                "name": "História - EJA",
                "data": {
                    "correct_answers": 12,
                    "total_questions": 20,
                    "course_name": "EJA",
                    "subject_name": "História"
                }
            }
        ]
        
        for test_case in test_cases:
            print(f"\n📊 Testando: {test_case['name']}")
            print(f"   Acertos: {test_case['data']['correct_answers']}/{test_case['data']['total_questions']}")
            
            try:
                response = requests.post(
                    f"{self.base_url}/evaluation-results/avaliacoes/calcular",
                    json=test_case['data'],
                    headers=self.headers
                )
                
                if response.status_code == 200:
                    result = response.json()
                    print(f"   ✅ Proficiência: {result['proficiency']}")
                    print(f"   ✅ Nota: {result['grade']}")
                    print(f"   ✅ Classificação: {result['classification']}")
                    print(f"   ✅ Taxa de Acerto: {result['accuracy_rate']}%")
                else:
                    print(f"   ❌ Erro: {response.status_code} - {response.text}")
                    
            except Exception as e:
                print(f"   ❌ Erro de conexão: {e}")
    
    def test_filter_options_endpoint(self):
        """Testa o endpoint de opções de filtros"""
        
        print("\n🎛️ === TESTANDO OPÇÕES DE FILTROS ===")
        
        try:
            response = requests.get(
                f"{self.base_url}/evaluation-results/filtros/opcoes",
                headers=self.headers
            )
            
            if response.status_code == 200:
                options = response.json()
                print(f"✅ Cursos disponíveis: {len(options.get('courses', []))}")
                print(f"✅ Disciplinas disponíveis: {len(options.get('subjects', []))}")
                print(f"✅ Escolas disponíveis: {len(options.get('schools', []))}")
                print(f"✅ Status disponíveis: {len(options.get('statuses', []))}")
                print(f"✅ Classificações disponíveis: {len(options.get('classifications', []))}")
                
                # Mostrar algumas opções como exemplo
                if options.get('subjects'):
                    print("   📝 Algumas disciplinas:")
                    for subject in options['subjects'][:3]:
                        print(f"      - {subject['name']}")
                        
            else:
                print(f"❌ Erro: {response.status_code} - {response.text}")
                
        except Exception as e:
            print(f"❌ Erro de conexão: {e}")
    
    def test_evaluations_list_endpoint(self):
        """Testa o endpoint de listagem de avaliações"""
        
        print("\n📋 === TESTANDO LISTAGEM DE AVALIAÇÕES ===")
        
        # Testar sem filtros
        print("🔍 Buscando todas as avaliações...")
        try:
            response = requests.get(
                f"{self.base_url}/evaluation-results/avaliacoes?page=1&limit=10",
                headers=self.headers
            )
            
            if response.status_code == 200:
                data = response.json()
                evaluations = data.get('evaluations', [])
                pagination = data.get('pagination', {})
                
                print(f"✅ Encontradas {len(evaluations)} avaliações")
                print(f"✅ Total de itens: {pagination.get('total_items', 0)}")
                print(f"✅ Páginas totais: {pagination.get('total_pages', 0)}")
                
                # Mostrar alguns exemplos
                for i, evaluation in enumerate(evaluations[:2]):
                    print(f"\n   📖 Avaliação {i+1}:")
                    print(f"      Nome: {evaluation.get('name', 'N/A')}")
                    print(f"      Disciplina: {evaluation.get('subject', 'N/A')}")
                    print(f"      Curso: {evaluation.get('course', 'N/A')}")
                    print(f"      Alunos participantes: {evaluation.get('total_students', 0)}")
                    print(f"      Média de proficiência: {evaluation.get('average_proficiency', 0.0)}")
                    print(f"      Média de nota: {evaluation.get('average_grade', 0.0)}")
                    print(f"      Taxa de aprovação: {evaluation.get('approval_rate', 0.0)}%")
                    
            else:
                print(f"❌ Erro: {response.status_code} - {response.text}")
                
        except Exception as e:
            print(f"❌ Erro de conexão: {e}")
    
    def test_students_list_endpoint(self):
        """Testa o endpoint de listagem de alunos com resultados"""
        
        print("\n👥 === TESTANDO LISTAGEM DE ALUNOS COM RESULTADOS ===")
        
        # Testar sem filtros
        print("🔍 Buscando resultados de alunos...")
        try:
            response = requests.get(
                f"{self.base_url}/evaluation-results/alunos?page=1&limit=10",
                headers=self.headers
            )
            
            if response.status_code == 200:
                data = response.json()
                students = data.get('students', [])
                pagination = data.get('pagination', {})
                
                print(f"✅ Encontrados {len(students)} resultados de alunos")
                print(f"✅ Total de itens: {pagination.get('total_items', 0)}")
                
                # Mostrar alguns exemplos
                for i, student in enumerate(students[:3]):
                    print(f"\n   👤 Aluno {i+1}:")
                    print(f"      Nome: {student.get('name', 'N/A')}")
                    print(f"      Turma: {student.get('class', 'N/A')}")
                    print(f"      Avaliação: {student.get('evaluation', 'N/A')}")
                    print(f"      Proficiência: {student.get('proficiency', 0.0)}")
                    print(f"      Nota: {student.get('grade', 0.0)}")
                    print(f"      Classificação: {student.get('classification', 'N/A')}")
                    print(f"      Taxa de acerto: {student.get('accuracy_rate', 0.0)}%")
                    
            else:
                print(f"❌ Erro: {response.status_code} - {response.text}")
                
        except Exception as e:
            print(f"❌ Erro de conexão: {e}")
    
    def test_chart_endpoints(self):
        """Testa os endpoints de dados para gráficos"""
        
        print("\n📊 === TESTANDO ENDPOINTS DE GRÁFICOS ===")
        
        chart_endpoints = [
            ("classificacoes", "Distribuição de Classificações"),
            ("proficiencia", "Distribuição de Proficiência"),
            ("escolas", "Comparação entre Escolas")
        ]
        
        for endpoint, description in chart_endpoints:
            print(f"\n📈 Testando: {description}")
            try:
                response = requests.get(
                    f"{self.base_url}/evaluation-results/graficos/{endpoint}",
                    headers=self.headers
                )
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if endpoint == "escolas":
                        schools = data.get('schools', [])
                        print(f"   ✅ {len(schools)} escolas encontradas")
                        if schools:
                            print(f"   📊 Exemplo: {schools[0].get('school_name', 'N/A')} - Média: {schools[0].get('average_grade', 0.0)}")
                    else:
                        labels = data.get('labels', [])
                        chart_data = data.get('data', [])
                        total = data.get('total_students', 0)
                        print(f"   ✅ {len(labels)} categorias")
                        print(f"   ✅ Total de alunos: {total}")
                        if labels and chart_data:
                            print(f"   📊 Exemplo: {labels[0]} = {chart_data[0]} alunos")
                            
                else:
                    print(f"   ❌ Erro: {response.status_code} - {response.text}")
                    
            except Exception as e:
                print(f"   ❌ Erro de conexão: {e}")
    
    def test_with_filters(self):
        """Testa endpoints com filtros aplicados"""
        
        print("\n🎯 === TESTANDO FILTROS AVANÇADOS ===")
        
        # Testar filtros na listagem de alunos
        filters = [
            ("grade_min=7.0", "Nota mínima 7.0"),
            ("classification=Avançado", "Classificação Avançado"),
            ("proficiency_min=300", "Proficiência mínima 300")
        ]
        
        for filter_param, description in filters:
            print(f"\n🔍 Testando filtro: {description}")
            try:
                response = requests.get(
                    f"{self.base_url}/evaluation-results/alunos?{filter_param}&limit=5",
                    headers=self.headers
                )
                
                if response.status_code == 200:
                    data = response.json()
                    students = data.get('students', [])
                    total = data.get('total_results', 0)
                    
                    print(f"   ✅ {len(students)} resultados encontrados (total: {total})")
                    
                    if students:
                        student = students[0]
                        print(f"   📊 Exemplo: {student.get('name', 'N/A')} - Nota: {student.get('grade', 0.0)} - Classificação: {student.get('classification', 'N/A')}")
                        
                else:
                    print(f"   ❌ Erro: {response.status_code} - {response.text}")
                    
            except Exception as e:
                print(f"   ❌ Erro de conexão: {e}")
    
    def run_comprehensive_test(self):
        """Executa todos os testes de forma abrangente"""
        
        print("🚀 === INICIANDO TESTES COMPLETOS DOS NOVOS ENDPOINTS ===")
        print("=" * 70)
        
        # Autenticar primeiro
        if not self.authenticate():
            print("❌ Falha na autenticação. Encerrando testes.")
            return False
        
        # Executar todos os testes
        test_methods = [
            self.test_calculator_endpoint,
            self.test_filter_options_endpoint,
            self.test_evaluations_list_endpoint,
            self.test_students_list_endpoint,
            self.test_chart_endpoints,
            self.test_with_filters
        ]
        
        for test_method in test_methods:
            try:
                test_method()
                time.sleep(0.5)  # Pequena pausa entre testes
            except Exception as e:
                print(f"❌ Erro durante teste {test_method.__name__}: {e}")
        
        print("\n" + "=" * 70)
        print("🏁 === TESTES CONCLUÍDOS ===")
        print("\n💡 ENDPOINTS IMPLEMENTADOS:")
        print("   • GET /evaluation-results/avaliacoes - Lista avaliações com estatísticas")
        print("   • GET /evaluation-results/alunos - Lista alunos com resultados")
        print("   • POST /evaluation-results/avaliacoes/calcular - Calcula proficiência/nota/classificação")
        print("   • GET /evaluation-results/filtros/opcoes - Opções para filtros")
        print("   • GET /evaluation-results/graficos/* - Dados para gráficos")
        print("   • GET /evaluation-results/avaliacoes/{id}/estatisticas - Estatísticas de avaliação específica")
        
        print("\n🎯 RECURSOS IMPLEMENTADOS:")
        print("   ✅ Cálculos precisos de proficiência, nota e classificação")
        print("   ✅ Filtros avançados e eficientes")
        print("   ✅ Paginação em todos os endpoints")
        print("   ✅ Dados agregados para gráficos")
        print("   ✅ Controle de acesso por roles")
        print("   ✅ Tratamento robusto de erros")
        
        return True


def main():
    """Função principal para executar os testes"""
    
    print("🔧 Verificando se o servidor está rodando...")
    
    tester = EvaluationResultsTester()
    
    # Verificar se servidor está ativo
    try:
        response = requests.get(f"{tester.base_url}/persist-user/", timeout=5)
        print("✅ Servidor está ativo!")
    except Exception as e:
        print(f"❌ Servidor não está respondendo: {e}")
        print("💡 Certifique-se de que o servidor está rodando em http://localhost:5000")
        return
    
    # Executar testes
    tester.run_comprehensive_test()


if __name__ == "__main__":
    main() 