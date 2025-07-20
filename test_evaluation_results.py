#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de teste para verificar a funcionalidade dos resultados de avaliação
"""
import requests
import json
import time

# Configuração
BASE_URL = "http://localhost:5000"
TEST_ENDPOINTS = [
    "/evaluation-results/test/ping",
    "/evaluation-results/test/avaliacoes",
    "/evaluation-results/test/relatorio-detalhado/test-eval-1"
]

def test_endpoints():
    """Testa os endpoints de avaliação"""
    print("🧪 Testando endpoints de avaliação...")
    
    for endpoint in TEST_ENDPOINTS:
        try:
            url = f"{BASE_URL}{endpoint}"
            print(f"\n📡 Testando: {endpoint}")
            
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                print(f"✅ Sucesso! Status: {response.status_code}")
                data = response.json()
                
                if endpoint == "/evaluation-results/test/ping":
                    print(f"   Mensagem: {data.get('message')}")
                    print(f"   Timestamp: {data.get('timestamp')}")
                
                elif endpoint == "/evaluation-results/test/avaliacoes":
                    print(f"   Total de avaliações: {data.get('total', 0)}")
                    if data.get('data'):
                        first_eval = data['data'][0]
                        print(f"   Primeira avaliação: {first_eval.get('titulo')}")
                        print(f"   Status: {first_eval.get('status')}")
                        print(f"   Média nota: {first_eval.get('media_nota')}")
                
                elif endpoint == "/evaluation-results/test/relatorio-detalhado/test-eval-1":
                    print(f"   Avaliação: {data.get('avaliacao', {}).get('titulo')}")
                    print(f"   Total questões: {data.get('avaliacao', {}).get('total_questoes')}")
                    print(f"   Total alunos: {len(data.get('alunos', []))}")
                
            else:
                print(f"❌ Erro! Status: {response.status_code}")
                print(f"   Resposta: {response.text}")
                
        except requests.exceptions.ConnectionError:
            print(f"❌ Erro de conexão: Não foi possível conectar ao servidor")
        except requests.exceptions.Timeout:
            print(f"❌ Timeout: Requisição demorou muito")
        except Exception as e:
            print(f"❌ Erro inesperado: {str(e)}")

def test_database_connection():
    """Testa a conexão com o banco de dados"""
    print("\n🗄️ Testando conexão com banco de dados...")
    
    try:
        # Testar endpoint que acessa o banco
        url = f"{BASE_URL}/evaluation-results/test/ping"
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            print("✅ Conexão com banco de dados OK")
        else:
            print("❌ Problema na conexão com banco de dados")
            
    except Exception as e:
        print(f"❌ Erro ao testar banco: {str(e)}")

def main():
    """Função principal"""
    print("🚀 Iniciando testes de avaliação...")
    print(f"📍 URL base: {BASE_URL}")
    
    # Testar conexão com banco
    test_database_connection()
    
    # Testar endpoints
    test_endpoints()
    
    print("\n✅ Testes concluídos!")

if __name__ == "__main__":
    main() 