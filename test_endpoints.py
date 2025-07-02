#!/usr/bin/env python3
"""
Script para testar os endpoints que estavam com erro 500
"""

import requests
import json

def test_endpoint(url, description):
    """Testa um endpoint e retorna o resultado"""
    try:
        print(f"🔄 Testando {description}...")
        response = requests.get(url)
        
        if response.status_code == 200:
            print(f"✅ {description} - Status: {response.status_code}")
            return True
        elif response.status_code == 401:
            print(f"🔐 {description} - Status: {response.status_code} (Requer autenticação - normal)")
            return True
        else:
            print(f"❌ {description} - Status: {response.status_code}")
            try:
                error_data = response.json()
                print(f"   Erro: {error_data}")
            except:
                print(f"   Erro: {response.text}")
            return False
    except Exception as e:
        print(f"❌ {description} - Erro de conexão: {e}")
        return False

def main():
    """Função principal para testar os endpoints"""
    base_url = "http://localhost:5000"
    
    endpoints = [
        (f"{base_url}/test", "Lista de avaliações"),
        (f"{base_url}/test/", "Lista de avaliações (com barra)"),
        (f"{base_url}/questions/", "Lista de questões"),
        (f"{base_url}/health", "Health check"),
    ]
    
    print("🧪 Testando endpoints que estavam com erro 500...\n")
    
    results = []
    for url, description in endpoints:
        result = test_endpoint(url, description)
        results.append(result)
        print()
    
    # Resumo
    successful = sum(results)
    total = len(results)
    
    print("📊 RESUMO DOS TESTES:")
    print(f"✅ Sucessos: {successful}/{total}")
    print(f"❌ Falhas: {total - successful}/{total}")
    
    if successful == total:
        print("\n🎉 Todos os endpoints estão funcionando!")
    else:
        print(f"\n⚠️  {total - successful} endpoint(s) ainda com problemas")

if __name__ == "__main__":
    main() 