#!/usr/bin/env python3
"""
Script para testar o fluxo completo de correção de avaliações
"""

import requests
import json
import sys
from datetime import datetime, timedelta

# Configurações
BASE_URL = "http://localhost:5000"
LOGIN_URL = f"{BASE_URL}/login"

# Credenciais
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
                print("✅ Login realizado com sucesso!")
                return token
            else:
                print("❌ Token não encontrado na resposta")
                return None
        else:
            print(f"❌ Erro no login: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"❌ Erro de conexão no login: {e}")
        return None

def test_endpoint(method, url, token=None, data=None, description=""):
    """Testa um endpoint específico"""
    headers = {}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    
    try:
        if method.upper() == 'GET':
            response = requests.get(url, headers=headers)
        elif method.upper() == 'POST':
            response = requests.post(url, headers=headers, json=data)
        elif method.upper() == 'PUT':
            response = requests.put(url, headers=headers, json=data)
        elif method.upper() == 'PATCH':
            response = requests.patch(url, headers=headers, json=data)
        else:
            print(f"❌ Método {method} não suportado")
            return False
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ {description} - Status: {response.status_code}")
            return result
        else:
            print(f"❌ {description} - Status: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ {description} - Erro: {e}")
        return False

def test_correction_flow():
    """Testa o fluxo completo de correção de avaliações"""
    print("🧪 TESTANDO FLUXO DE CORREÇÃO DE AVALIAÇÕES")
    print("=" * 60)
    
    # 1. Login
    token = get_auth_token()
    if not token:
        print("❌ Falha no login. Abortando teste.")
        return False
    
    print("\n📋 PASSO 1: Verificando avaliações enviadas para correção")
    print("-" * 50)
    
    # 2. Buscar avaliações enviadas (que precisam de correção)
    submitted_evaluations = test_endpoint(
        'GET', 
        f"{BASE_URL}/evaluation-results/admin/submitted-evaluations", 
        token, 
        description="Buscar avaliações enviadas"
    )
    
    if not submitted_evaluations:
        print("❌ Não foi possível buscar avaliações enviadas")
        return False
    
    print(f"📊 Encontradas {len(submitted_evaluations)} avaliação(ões) enviada(s)")
    
    if not submitted_evaluations:
        print("⚠️  Nenhuma avaliação enviada encontrada. Criando uma para teste...")
        
        # Criar uma avaliação de teste
        test_evaluation = {
            "title": "Teste de Correção",
            "description": "Avaliação para testar o fluxo de correção",
            "subject": "Português",
            "grade": "9º ano",
            "time_limit": 60,
            "questions": [
                {
                    "text": "Qual é a capital do Brasil?",
                    "type": "multipleChoice",
                    "options": [
                        {"text": "São Paulo", "isCorrect": False},
                        {"text": "Rio de Janeiro", "isCorrect": False},
                        {"text": "Brasília", "isCorrect": True},
                        {"text": "Salvador", "isCorrect": False}
                    ],
                    "value": 1.0
                }
            ]
        }
        
        created_eval = test_endpoint(
            'POST',
            f"{BASE_URL}/test",
            token,
            test_evaluation,
            "Criar avaliação de teste"
        )
        
        if not created_eval:
            print("❌ Não foi possível criar avaliação de teste")
            return False
        
        # Simular submissão de resposta
        test_answer = {
            "test_id": created_eval.get('id'),
            "student_id": 1,  # Assumindo que existe um aluno com ID 1
            "answers": [
                {
                    "question_id": created_eval['questions'][0]['id'],
                    "answer_text": "Brasília",
                    "is_correct": True
                }
            ]
        }
        
        submitted = test_endpoint(
            'POST',
            f"{BASE_URL}/submit-evaluation",
            token,
            test_answer,
            "Submeter avaliação de teste"
        )
        
        if not submitted:
            print("❌ Não foi possível submeter avaliação de teste")
            return False
        
        # Buscar novamente
        submitted_evaluations = test_endpoint(
            'GET', 
            f"{BASE_URL}/evaluation-results/admin/submitted-evaluations", 
            token, 
            description="Buscar avaliações enviadas (após criação)"
        )
    
    # 3. Selecionar primeira avaliação para correção
    if submitted_evaluations:
        evaluation_to_correct = submitted_evaluations[0]
        evaluation_id = evaluation_to_correct.get('id')
        session_id = evaluation_to_correct.get('sessionId')
        
        print(f"\n📝 PASSO 2: Corrigindo avaliação ID {evaluation_id}")
        print("-" * 50)
        
        # 4. Usar os dados que já vêm na lista
        evaluation_details = evaluation_to_correct
        
        print(f"📋 Avaliação: {evaluation_details.get('testTitle', 'Sem título')}")
        print(f"👤 Aluno: {evaluation_details.get('studentName', 'N/A')}")
        print(f"📅 Enviada em: {evaluation_details.get('submittedAt', 'N/A')}")
        print(f"📊 Questões: {evaluation_details.get('totalQuestions', 0)} total, {evaluation_details.get('answeredQuestions', 0)} respondidas")
        
        # 5. Simular correção das respostas
        print(f"\n✏️  PASSO 3: Aplicando correções")
        print("-" * 50)
        
        questions_data = []
        for question in evaluation_details.get('questions', []):
            question_id = question.get('id')
            student_answer = question.get('studentAnswer', '')
            is_correct = question.get('isCorrect', False)
            
            # Simular correção manual (todas corretas para teste)
            manual_points = 1.0 if is_correct else 0.0
            
            corrected_question = {
                "questionId": question_id,
                "manualPoints": manual_points,
                "feedback": "Resposta correta" if is_correct else "Resposta incorreta"
            }
            questions_data.append(corrected_question)
            
            print(f"✅ Questão {question_id}: {student_answer} -> {manual_points} pontos")
        
        # 6. Enviar correções
        correction_data = {
            "sessionId": session_id,
            "questions": questions_data,
            "generalFeedback": "Avaliação corrigida com sucesso"
        }
        
        correction_result = test_endpoint(
            'PATCH',
            f"{BASE_URL}/evaluation-results/admin/evaluations/{evaluation_id}/correct",
            token,
            correction_data,
            "Enviar correções da avaliação"
        )
        
        if not correction_result:
            print("❌ Não foi possível enviar correções")
            return False
        
        print("✅ Correções enviadas com sucesso!")
        
        # 7. Finalizar avaliação
        print(f"\n🏁 PASSO 4: Finalizando avaliação")
        print("-" * 50)
        
        finalization_data = {
            "sessionId": session_id,
            "questions": questions_data,
            "generalFeedback": "Avaliação finalizada com sucesso"
        }
        
        finalization_result = test_endpoint(
            'PATCH',
            f"{BASE_URL}/evaluation-results/admin/evaluations/{evaluation_id}/finish",
            token,
            finalization_data,
            "Finalizar avaliação"
        )
        
        if not finalization_result:
            print("❌ Não foi possível finalizar avaliação")
            return False
        
        print("✅ Avaliação finalizada com sucesso!")
        
        # 8. Verificar resultados
        print(f"\n📊 PASSO 5: Verificando resultados")
        print("-" * 50)
        
        results = test_endpoint(
            'GET',
            f"{BASE_URL}/evaluation-results/list",
            token,
            description="Verificar lista de resultados"
        )
        
        if results:
            print(f"📈 Total de resultados: {len(results)}")
            if results:
                latest_result = results[0]
                print(f"🎯 Último resultado: {latest_result.get('student_name', 'N/A')} - {latest_result.get('score', 'N/A')} pontos")
        
        # 9. Verificar estatísticas atualizadas
        stats = test_endpoint(
            'GET',
            f"{BASE_URL}/evaluation-results/stats",
            token,
            description="Verificar estatísticas atualizadas"
        )
        
        if stats:
            print(f"📊 Estatísticas atualizadas:")
            print(f"   - Total de avaliações: {stats.get('total_evaluations', 'N/A')}")
            print(f"   - Avaliações finalizadas: {stats.get('completed_evaluations', 'N/A')}")
            print(f"   - Pontuação média: {stats.get('average_score', 'N/A')}")
        
        print("\n🎉 FLUXO DE CORREÇÃO TESTADO COM SUCESSO!")
        return True
    
    else:
        print("❌ Nenhuma avaliação disponível para correção")
        return False

if __name__ == "__main__":
    print("🚀 Iniciando teste do fluxo de correção de avaliações...")
    success = test_correction_flow()
    
    if success:
        print("\n✅ TESTE CONCLUÍDO COM SUCESSO!")
        print("🎯 O fluxo de correção de avaliações está funcionando corretamente!")
    else:
        print("\n❌ TESTE FALHOU!")
        print("🔧 Verifique os logs acima para identificar os problemas.")
    
    sys.exit(0 if success else 1) 