#!/usr/bin/env python3
"""
Script para debugar os endpoints que falharam nos testes
"""

import requests
import json

BASE_URL = "http://localhost:5000"
LOGIN_URL = f"{BASE_URL}/login"

LOGIN_CREDENTIALS = {
    "registration": "moises@innovplay.com",
    "password": "12345678"
}

def get_auth_token():
    """Faz login e retorna o token JWT"""
    try:
        response = requests.post(LOGIN_URL, json=LOGIN_CREDENTIALS)
        if response.status_code == 200:
            data = response.json()
            return data.get('token')
        else:
            print(f"❌ Erro no login: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"❌ Erro de conexão no login: {e}")
        return None

def test_failing_endpoint(url, description, headers):
    """Testa um endpoint específico e mostra detalhes do erro"""
    try:
        print(f"\n🔍 Testando: {description}")
        print(f"URL: {url}")
        
        response = requests.get(url, headers=headers)
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ Sucesso!")
            try:
                data = response.json()
                if isinstance(data, list):
                    print(f"   Retornou lista com {len(data)} itens")
                elif isinstance(data, dict):
                    print(f"   Retornou objeto com chaves: {list(data.keys())}")
            except:
                print(f"   Resposta não-JSON: {response.text[:100]}...")
        else:
            print("❌ Falhou!")
            print(f"Headers da resposta: {dict(response.headers)}")
            try:
                error_data = response.json()
                print(f"Erro JSON: {json.dumps(error_data, indent=2)}")
            except:
                print(f"Erro texto: {response.text}")
                
    except Exception as e:
        print(f"❌ Erro de conexão: {e}")

def main():
    print("🔧 Debugando endpoints que falharam nos testes...")
    
    # Obter token
    token = get_auth_token()
    if not token:
        print("❌ Não foi possível obter token. Abortando.")
        return
    
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    # Endpoints que falharam
    failing_endpoints = [
        (f"{BASE_URL}/evaluation-results/stats", "Estatísticas de resultados"),
        (f"{BASE_URL}/evaluation-results/list", "Lista de resultados"),
        (f"{BASE_URL}/questions/recent", "Questões recentes"),
        (f"{BASE_URL}/test", "Lista de avaliações"),
    ]
    
    for url, description in failing_endpoints:
        test_failing_endpoint(url, description, headers)
    
    print("\n" + "="*60)
    print("🔧 Debug concluído!")

if __name__ == "__main__":
    main() 