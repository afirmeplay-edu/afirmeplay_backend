#!/usr/bin/env python3
"""
Script para testar os endpoints do backend com autenticação JWT
"""

import requests
import json
import sys
from datetime import datetime

# Configurações
BASE_URL = "http://localhost:5000"
LOGIN_URL = f"{BASE_URL}/login"

# Credenciais de teste fornecidas pelo usuário
LOGIN_CREDENTIALS = {
    "registration": "moises@innovplay.com",
    "password": "12345678"
}

def get_auth_token():
    """Faz login e retorna o token JWT"""
    try:
        print("🔐 Fazendo login para obter token JWT...")
        response = requests.post(LOGIN_URL, json=LOGIN_CREDENTIALS)
        
        if response.status_code == 200:
            data = response.json()
            token = data.get('token')
            if token:
                print(f"✅ Login bem-sucedido! Token obtido: {token[:20]}...")
                return token
            else:
                print("❌ Token não encontrado na resposta do login")
                return None
        else:
            print(f"❌ Erro no login: {response.status_code}")
            try:
                error_data = response.json()
                print(f"   Detalhes: {error_data}")
            except:
                print(f"   Resposta: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Erro de conexão no login: {e}")
        return None

def test_endpoint(url, description, headers=None, method='GET', data=None):
    """Testa um endpoint e retorna o resultado"""
    try:
        print(f"🔄 Testando {description}...")
        
        if method == 'GET':
            response = requests.get(url, headers=headers)
        elif method == 'POST':
            response = requests.post(url, headers=headers, json=data)
        else:
            print(f"❌ Método {method} não suportado")
            return False
        
        if response.status_code == 200:
            print(f"✅ {description} - Status: {response.status_code}")
            try:
                response_data = response.json()
                # Mostrar uma amostra dos dados retornados
                if isinstance(response_data, dict):
                    keys = list(response_data.keys())[:3]  # Primeiras 3 chaves
                    sample = {k: response_data[k] for k in keys}
                    print(f"   Dados: {sample}...")
                elif isinstance(response_data, list):
                    print(f"   Retornou lista com {len(response_data)} itens")
                else:
                    print(f"   Dados: {str(response_data)[:100]}...")
            except:
                print(f"   Resposta não-JSON: {response.text[:100]}...")
            return True
        elif response.status_code == 401:
            print(f"🔐 {description} - Status: {response.status_code} (Não autorizado)")
            return False
        elif response.status_code == 404:
            print(f"🔍 {description} - Status: {response.status_code} (Não encontrado)")
            return False
        else:
            print(f"❌ {description} - Status: {response.status_code}")
            try:
                error_data = response.json()
                print(f"   Erro: {error_data}")
            except:
                print(f"   Erro: {response.text[:200]}...")
            return False
    except Exception as e:
        print(f"❌ {description} - Erro de conexão: {e}")
        return False

def main():
    """Função principal para testar os endpoints"""
    print("🧪 Iniciando testes dos endpoints do backend...\n")
    
    # 1. Obter token de autenticação
    token = get_auth_token()
    if not token:
        print("❌ Não foi possível obter token de autenticação. Abortando testes.")
        sys.exit(1)
    
    # Headers com autenticação
    auth_headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    # 2. Definir endpoints para testar
    endpoints = [
        # Endpoint público (sem autenticação)
        (f"{BASE_URL}/health", "Health check", None, 'GET'),
        
        # Endpoints que requerem autenticação
        (f"{BASE_URL}/dashboard/stats", "Estatísticas do dashboard", auth_headers, 'GET'),
        (f"{BASE_URL}/dashboard/comprehensive-stats", "Estatísticas completas", auth_headers, 'GET'),
        (f"{BASE_URL}/evaluations/stats", "Estatísticas de avaliações", auth_headers, 'GET'),
        (f"{BASE_URL}/test-sessions/submitted", "Avaliações enviadas", auth_headers, 'GET'),
        (f"{BASE_URL}/subjects", "Lista de disciplinas", auth_headers, 'GET'),
        (f"{BASE_URL}/schools", "Lista de escolas", auth_headers, 'GET'),
        (f"{BASE_URL}/classes", "Lista de turmas", auth_headers, 'GET'),
        (f"{BASE_URL}/schools/recent", "Escolas recentes", auth_headers, 'GET'),
        (f"{BASE_URL}/students/recent", "Alunos recentes", auth_headers, 'GET'),
        (f"{BASE_URL}/questions/recent", "Questões recentes", auth_headers, 'GET'),
        (f"{BASE_URL}/evaluation-results/stats", "Estatísticas de resultados", auth_headers, 'GET'),
        (f"{BASE_URL}/evaluation-results/list", "Lista de resultados", auth_headers, 'GET'),
        
        # Endpoints de teste/avaliação
        (f"{BASE_URL}/test", "Lista de avaliações", auth_headers, 'GET'),
        (f"{BASE_URL}/questions", "Lista de questões", auth_headers, 'GET'),
    ]
    
    print("📋 Testando endpoints...\n")
    
    results = []
    for endpoint_data in endpoints:
        if len(endpoint_data) == 4:
            url, description, headers, method = endpoint_data
            data = None
        else:
            url, description, headers, method, data = endpoint_data
        
        result = test_endpoint(url, description, headers, method, data)
        results.append(result)
        print()
    
    # 3. Resumo dos resultados
    successful = sum(results)
    total = len(results)
    
    print("=" * 60)
    print("📊 RESUMO DOS TESTES:")
    print(f"✅ Sucessos: {successful}/{total}")
    print(f"❌ Falhas: {total - successful}/{total}")
    print(f"📅 Executado em: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if successful == total:
        print("\n🎉 Todos os endpoints estão funcionando!")
        sys.exit(0)
    else:
        print(f"\n⚠️  {total - successful} endpoint(s) ainda com problemas")
        sys.exit(1)

if __name__ == "__main__":
    main() 