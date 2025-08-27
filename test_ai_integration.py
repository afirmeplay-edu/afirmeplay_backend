# -*- coding: utf-8 -*-
"""
Teste da integração com OpenAI
"""

import sys
import os

# Adicionar o diretório raiz ao path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.openai_config.openai_config import get_openai_client, ANALYSIS_PROMPT_BASE
from app.services.ai_analysis_service import AIAnalysisService

def test_openai_connection():
    """Testa conexão com OpenAI"""
    try:
        client = get_openai_client()
        print("✅ Cliente OpenAI criado com sucesso")
        return True
    except Exception as e:
        print(f"❌ Erro ao criar cliente OpenAI: {str(e)}")
        return False

def test_ai_service():
    """Testa o serviço de IA"""
    try:
        service = AIAnalysisService()
        print("✅ Serviço de IA criado com sucesso")
        return True
    except Exception as e:
        print(f"❌ Erro ao criar serviço de IA: {str(e)}")
        return False

def test_sample_analysis():
    """Testa análise com dados de exemplo"""
    try:
        service = AIAnalysisService()
        
        # Dados de exemplo
        sample_data = {
            "avaliacao": {
                "id": "test-123",
                "titulo": "Avaliação Diagnóstica 2025.1",
                "descricao": "Teste de avaliação",
                "disciplinas": ["Língua Portuguesa", "Matemática"],
                "questoes_anuladas": ["Q10", "Q11"]
            },
            "total_alunos": {
                "total_geral": {
                    "matriculados": 249,
                    "avaliados": 222,
                    "faltosos": 27,
                    "percentual": 89.2
                },
                "por_turma": [
                    {
                        "turma": "9º A",
                        "matriculados": 30,
                        "avaliados": 27,
                        "faltosos": 3,
                        "percentual": 90.0
                    }
                ]
            },
            "proficiencia": {
                "por_disciplina": {
                    "Língua Portuguesa": {
                        "media_geral": 298.86,
                        "por_turma": [
                            {"turma": "9º A", "proficiencia": 298.86}
                        ]
                    },
                    "Matemática": {
                        "media_geral": 268.29,
                        "por_turma": [
                            {"turma": "9º A", "proficiencia": 268.29}
                        ]
                    }
                },
                "media_municipal_por_disciplina": {
                    "Língua Portuguesa": 272.19,
                    "Matemática": 293.55
                }
            },
            "nota_geral": {
                "por_disciplina": {
                    "Língua Portuguesa": {
                        "media_geral": 6.77,
                        "por_turma": [
                            {"turma": "9º A", "nota": 6.77}
                        ]
                    },
                    "Matemática": {
                        "media_geral": 5.85,
                        "por_turma": [
                            {"turma": "9º A", "nota": 5.85}
                        ]
                    }
                },
                "media_municipal_por_disciplina": {
                    "Língua Portuguesa": 6.5,
                    "Matemática": 6.2
                }
            },
            "acertos_por_habilidade": {
                "Língua Portuguesa": {
                    "habilidades": [
                        {"codigo": "LP1", "percentual": 85.0, "questoes": [{"numero": 1}]},
                        {"codigo": "LP2", "percentual": 65.0, "questoes": [{"numero": 2}]}
                    ]
                },
                "Matemática": {
                    "habilidades": [
                        {"codigo": "MAT1", "percentual": 45.0, "questoes": [{"numero": 3}]},
                        {"codigo": "MAT2", "percentual": 75.0, "questoes": [{"numero": 4}]}
                    ]
                }
            }
        }
        
        print("📊 Analisando dados de exemplo...")
        analysis = service.analyze_report_data(sample_data)
        
        print("✅ Análise concluída com sucesso!")
        print("\n📝 Resultados da análise:")
        for section, text in analysis.items():
            print(f"\n--- {section.upper()} ---")
            print(text[:200] + "..." if len(text) > 200 else text)
        
        return True
        
    except Exception as e:
        print(f"❌ Erro na análise de exemplo: {str(e)}")
        return False

def main():
    """Função principal de teste"""
    print("🚀 Testando integração com OpenAI...\n")
    
    # Teste 1: Conexão OpenAI
    print("1. Testando conexão com OpenAI...")
    if not test_openai_connection():
        return False
    
    # Teste 2: Serviço de IA
    print("\n2. Testando serviço de IA...")
    if not test_ai_service():
        return False
    
    # Teste 3: Análise de exemplo
    print("\n3. Testando análise com dados de exemplo...")
    if not test_sample_analysis():
        return False
    
    print("\n🎉 Todos os testes passaram com sucesso!")
    print("✅ Integração com OpenAI configurada e funcionando!")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
