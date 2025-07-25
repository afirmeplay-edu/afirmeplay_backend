#!/usr/bin/env python3
"""
Script de teste para verificar se a verificação de expiração das avaliações está funcionando
"""

import requests
import json
from datetime import datetime, timedelta

# Configurações
BASE_URL = "http://localhost:5000"
STUDENT_TOKEN = "seu_token_do_aluno_aqui"  # Substitua pelo token real
TEST_ID = "id_da_avaliacao_aqui"  # Substitua pelo ID real

def test_expiration_check():
    """Testa se a verificação de expiração está funcionando"""
    
    headers = {
        "Authorization": f"Bearer {STUDENT_TOKEN}",
        "Content-Type": "application/json"
    }
    
    print("🔍 Testando verificação de expiração de avaliações...")
    print("=" * 60)
    
    # 1. Testar listagem de avaliações da classe do aluno
    print("\n1. Testando listagem de avaliações da classe...")
    try:
        response = requests.get(f"{BASE_URL}/tests/my-class/tests", headers=headers)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Listagem bem-sucedida: {len(data.get('tests', []))} avaliações encontradas")
            
            # Verificar se há avaliações expiradas
            for test in data.get('tests', []):
                availability = test.get('availability', {})
                application_info = test.get('application_info', {})
                
                print(f"\n📋 Avaliação: {test.get('title', 'N/A')}")
                print(f"   Status: {availability.get('status', 'N/A')}")
                print(f"   Disponível: {availability.get('is_available', False)}")
                print(f"   Data de aplicação: {application_info.get('application', 'N/A')}")
                print(f"   Data de expiração: {application_info.get('expiration', 'N/A')}")
                print(f"   Hora atual: {application_info.get('current_time', 'N/A')}")
                
                # Verificar se avaliação expirada está marcada como não disponível
                if availability.get('status') == 'expired':
                    print(f"   ✅ Avaliação expirada corretamente marcada como 'expired'")
                elif availability.get('status') == 'available' and application_info.get('expiration'):
                    # Verificar se a data de expiração já passou
                    expiration_str = application_info.get('expiration')
                    current_str = application_info.get('current_time')
                    
                    if expiration_str and current_str:
                        try:
                            expiration = datetime.fromisoformat(expiration_str.replace('Z', '+00:00'))
                            current = datetime.fromisoformat(current_str.replace('Z', '+00:00'))
                            
                            if current > expiration:
                                print(f"   ❌ PROBLEMA: Avaliação expirada mas ainda marcada como disponível!")
                            else:
                                print(f"   ✅ Avaliação ainda não expirou")
                        except Exception as e:
                            print(f"   ⚠️ Erro ao comparar datas: {e}")
        else:
            print(f"❌ Erro na listagem: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ Erro ao testar listagem: {e}")
    
    # 2. Testar verificação se pode iniciar avaliação específica
    print(f"\n2. Testando verificação se pode iniciar avaliação {TEST_ID}...")
    try:
        response = requests.get(f"{BASE_URL}/student-answers/student/{TEST_ID}/can-start", headers=headers)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Verificação bem-sucedida")
            print(f"   Pode iniciar: {data.get('can_start', False)}")
            print(f"   Motivo: {data.get('reason', 'N/A')}")
            
            test_info = data.get('test_info', {})
            print(f"   Data de aplicação: {test_info.get('application', 'N/A')}")
            print(f"   Data de expiração: {test_info.get('expiration', 'N/A')}")
            
            # Verificar se avaliação expirada está bloqueada
            if not data.get('can_start') and 'expirada' in data.get('reason', '').lower():
                print(f"   ✅ Avaliação expirada corretamente bloqueada")
            elif data.get('can_start') and test_info.get('expiration'):
                # Verificar se a data de expiração já passou
                expiration_str = test_info.get('expiration')
                if expiration_str:
                    try:
                        expiration = datetime.fromisoformat(expiration_str.replace('Z', '+00:00'))
                        current = datetime.utcnow()
                        
                        if current > expiration:
                            print(f"   ❌ PROBLEMA: Avaliação expirada mas ainda permitindo início!")
                        else:
                            print(f"   ✅ Avaliação ainda não expirou")
                    except Exception as e:
                        print(f"   ⚠️ Erro ao comparar datas: {e}")
        else:
            print(f"❌ Erro na verificação: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ Erro ao testar verificação: {e}")
    
    # 3. Testar tentativa de iniciar sessão (se a avaliação existir)
    print(f"\n3. Testando tentativa de iniciar sessão...")
    try:
        response = requests.post(f"{BASE_URL}/tests/{TEST_ID}/start-session", headers=headers)
        if response.status_code == 201:
            print(f"✅ Sessão iniciada com sucesso")
        elif response.status_code == 410:
            print(f"✅ Avaliação expirada - início bloqueado corretamente")
        elif response.status_code == 200:
            print(f"✅ Sessão já existente")
        else:
            print(f"❌ Erro ao iniciar sessão: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ Erro ao testar início de sessão: {e}")
    
    print("\n" + "=" * 60)
    print("🎯 Teste de verificação de expiração concluído!")

if __name__ == "__main__":
    print("🚀 Iniciando teste de verificação de expiração...")
    print("⚠️  IMPORTANTE: Configure o TOKEN e TEST_ID antes de executar!")
    print()
    
    if STUDENT_TOKEN == "seu_token_do_aluno_aqui" or TEST_ID == "id_da_avaliacao_aqui":
        print("❌ Configure o STUDENT_TOKEN e TEST_ID no script antes de executar!")
        print("   - STUDENT_TOKEN: Token JWT de um aluno")
        print("   - TEST_ID: ID de uma avaliação que tenha data de expiração")
    else:
        test_expiration_check() 