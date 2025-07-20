#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para testar a correção de questões de múltipla escolha
"""
import json

def test_multiple_choice_correction():
    """Testa a função de correção de múltipla escolha"""
    
    # Simular dados de teste
    test_cases = [
        {
            "name": "Resposta correta por ID",
            "student_answer": "D",
            "alternatives": [
                {"id": "A", "text": "20 mil litros.", "isCorrect": False},
                {"id": "B", "text": "5 mil litros.", "isCorrect": False},
                {"id": "C", "text": "10 mil litros.", "isCorrect": False},
                {"id": "D", "text": "15 mil litros.", "isCorrect": True}
            ],
            "expected": True
        },
        {
            "name": "Resposta incorreta por ID",
            "student_answer": "A",
            "alternatives": [
                {"id": "A", "text": "20 mil litros.", "isCorrect": False},
                {"id": "B", "text": "5 mil litros.", "isCorrect": False},
                {"id": "C", "text": "10 mil litros.", "isCorrect": False},
                {"id": "D", "text": "15 mil litros.", "isCorrect": True}
            ],
            "expected": False
        },
        {
            "name": "Resposta correta por texto",
            "student_answer": "15 mil litros.",
            "alternatives": [
                {"id": "A", "text": "20 mil litros.", "isCorrect": False},
                {"id": "B", "text": "5 mil litros.", "isCorrect": False},
                {"id": "C", "text": "10 mil litros.", "isCorrect": False},
                {"id": "D", "text": "15 mil litros.", "isCorrect": True}
            ],
            "expected": True
        },
        {
            "name": "Alternatives como string JSON",
            "student_answer": "D",
            "alternatives": json.dumps([
                {"id": "A", "text": "20 mil litros.", "isCorrect": False},
                {"id": "B", "text": "5 mil litros.", "isCorrect": False},
                {"id": "C", "text": "10 mil litros.", "isCorrect": False},
                {"id": "D", "text": "15 mil litros.", "isCorrect": True}
            ]),
            "expected": True
        }
    ]
    
    # Importar a função de teste
    try:
        from app.services.evaluation_result_service import EvaluationResultService
        print("✅ Função importada com sucesso!")
    except Exception as e:
        print(f"❌ Erro ao importar função: {e}")
        return
    
    # Executar testes
    print("\n🧪 Executando testes de correção...")
    
    passed = 0
    total = len(test_cases)
    
    for i, test_case in enumerate(test_cases, 1):
        try:
            result = EvaluationResultService.check_multiple_choice_answer(
                test_case["student_answer"], 
                test_case["alternatives"]
            )
            
            success = result == test_case["expected"]
            status = "✅ PASSOU" if success else "❌ FALHOU"
            
            print(f"{i}. {test_case['name']}: {status}")
            print(f"   Resposta: {test_case['student_answer']}")
            print(f"   Esperado: {test_case['expected']}, Obtido: {result}")
            
            if success:
                passed += 1
                
        except Exception as e:
            print(f"{i}. {test_case['name']}: ❌ ERRO - {e}")
    
    print(f"\n📊 Resultado: {passed}/{total} testes passaram")
    
    if passed == total:
        print("🎉 Todos os testes passaram!")
    else:
        print("⚠️ Alguns testes falharam. Verifique a implementação.")

if __name__ == "__main__":
    print("=== Teste de Correção de Múltipla Escolha ===")
    test_multiple_choice_correction()
    print("=== Fim dos Testes ===") 