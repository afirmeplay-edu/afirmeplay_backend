#!/usr/bin/env python3
"""
Script de teste para as rotas de opções de filtros
"""

import requests
import json

# Configurações
BASE_URL = "http://localhost:5000"
TOKEN = "SEU_TOKEN_JWT_AQUI"  # Substitua pelo token real

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

def test_estados():
    """Testa a rota de estados"""
    print("🔍 Testando rota de estados...")
    try:
        response = requests.get(f"{BASE_URL}/evaluation-results/opcoes-filtros/estados", headers=headers)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Estados encontrados: {data.get('total', 0)}")
            print("Primeiros estados:", data.get('estados', [])[:3])
        else:
            print("Erro:", response.text)
    except Exception as e:
        print(f"Erro na requisição: {e}")

def test_municipios():
    """Testa a rota de municípios"""
    print("\n🔍 Testando rota de municípios...")
    try:
        response = requests.get(f"{BASE_URL}/evaluation-results/opcoes-filtros/municipios/ALAGOAS", headers=headers)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Municípios encontrados: {data.get('total', 0)}")
            print("Primeiros municípios:", data.get('municipios', [])[:3])
        else:
            print("Erro:", response.text)
    except Exception as e:
        print(f"Erro na requisição: {e}")

def test_avaliacoes():
    """Testa a rota de avaliações"""
    print("\n🔍 Testando rota de avaliações...")
    try:
        params = {
            "estado": "ALAGOAS",
            "municipio": "618f56d1-2167-439e-bf0b-d3d2be54271c"
        }
        response = requests.get(f"{BASE_URL}/evaluation-results/opcoes-filtros/avaliacoes", 
                              headers=headers, params=params)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Avaliações encontradas: {data.get('total', 0)}")
            print("Primeiras avaliações:", data.get('avaliacoes', [])[:3])
        else:
            print("Erro:", response.text)
    except Exception as e:
        print(f"Erro na requisição: {e}")

def test_opcoes_completas():
    """Testa a rota principal de opções"""
    print("\n🔍 Testando rota principal de opções...")
    try:
        params = {
            "estado": "ALAGOAS",
            "municipio": "618f56d1-2167-439e-bf0b-d3d2be54271c"
        }
        response = requests.get(f"{BASE_URL}/evaluation-results/opcoes-filtros", 
                              headers=headers, params=params)
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            opcoes = data.get('opcoes', {})
            print(f"Estados: {len(opcoes.get('estados', []))}")
            print(f"Municípios: {len(opcoes.get('municipios', []))}")
            print(f"Escolas: {len(opcoes.get('escolas', []))}")
            print(f"Séries: {len(opcoes.get('series', []))}")
            print(f"Turmas: {len(opcoes.get('turmas', []))}")
            print(f"Avaliações: {len(opcoes.get('avaliacoes', []))}")
        else:
            print("Erro:", response.text)
    except Exception as e:
        print(f"Erro na requisição: {e}")

if __name__ == "__main__":
    print("🚀 Iniciando testes das rotas de opções de filtros...")
    print("⚠️  IMPORTANTE: Substitua TOKEN pelo seu token JWT válido!")
    
    test_estados()
    test_municipios()
    test_avaliacoes()
    test_opcoes_completas()
    
    print("\n✅ Testes concluídos!") 