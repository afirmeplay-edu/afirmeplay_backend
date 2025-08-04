#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Teste simples do servidor
"""

import requests
import json

def test_server():
    """Testa se o servidor está funcionando"""
    
    try:
        # Teste básico de ping
        response = requests.get("http://127.0.0.1:5000/evaluation-results/test/ping")
        print(f"Ping status: {response.status_code}")
        if response.status_code == 200:
            print(f"Ping response: {response.json()}")
        
        # Teste de avaliações sem autenticação
        response = requests.get("http://127.0.0.1:5000/evaluation-results/test/avaliacoes")
        print(f"\nTeste avaliações status: {response.status_code}")
        if response.status_code == 200:
            print(f"Teste avaliações response: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
            
    except requests.exceptions.ConnectionError:
        print("❌ Servidor não está rodando!")
        print("Execute: python run.py")
    except Exception as e:
        print(f"❌ Erro: {str(e)}")

if __name__ == "__main__":
    test_server() 