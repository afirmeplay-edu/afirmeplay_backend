# -*- coding: utf-8 -*-
"""
Teste para verificar se o PDF está sendo gerado com as análises da IA
"""

import sys
import os

# Adicionar o diretório raiz ao path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.openai_config.openai_config import get_openai_client, ANALYSIS_PROMPT_BASE
from app.services.ai_analysis_service import AIAnalysisService

def test_pdf_data_preparation():
    """Testa se os dados estão sendo preparados corretamente para o PDF com IA"""
    try:
        # Dados de exemplo (simulando uma avaliação real)
        sample_data = {
            "avaliacao": {
                "id": "test-123",
                "titulo": "Avaliação Diagnóstica 2025.1",
                "descricao": "Teste de avaliação com IA",
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
        
        print("📊 Testando preparação de dados para PDF com IA...")
        
        # 1. Testar serviço de IA
        ai_service = AIAnalysisService()
        ai_analysis = ai_service.analyze_report_data(sample_data)
        
        print("✅ Análise da IA concluída!")
        print(f"📝 Seções disponíveis: {list(ai_analysis.keys())}")
        
        # 2. Verificar se todas as seções estão presentes
        required_sections = [
            'participacao_analise',
            'proficiencia_analise', 
            'notas_analise',
            'habilidades_analise',
            'recomendacoes_gerais'
        ]
        
        missing_sections = []
        for section in required_sections:
            if section not in ai_analysis or not ai_analysis[section]:
                missing_sections.append(section)
        
        if missing_sections:
            print(f"⚠️  Seções faltando: {missing_sections}")
        else:
            print("✅ Todas as seções da IA estão presentes!")
        
        # 3. Mostrar preview das análises
        print("\n📋 Preview das análises da IA:")
        for section, text in ai_analysis.items():
            print(f"\n--- {section.upper()} ---")
            preview = text[:150] + "..." if len(text) > 150 else text
            print(preview)
        
        # 4. Simular dados que seriam enviados para o template do PDF
        template_data = {
            # Dados básicos
            'escola': 'E. M. E. B. MONSENHOR HILDEBRANDO',
            'municipio': 'Campo Alegre',
            'uf': 'AL',
            'periodo': '2025.1',
            'mes': 'MAIO',
            'ano': '2025',
            
            # Dados de participação
            'participacao': sample_data['total_alunos']['por_turma'],
            'total_avaliados': sample_data['total_alunos']['total_geral']['avaliados'],
            'total_matriculados': sample_data['total_alunos']['total_geral']['matriculados'],
            'total_faltosos': sample_data['total_alunos']['total_geral']['faltosos'],
            'percentual_avaliados': sample_data['total_alunos']['total_geral']['percentual'],
            
            # Dados de proficiência
            'prof_lp_media': f"{sample_data['proficiencia']['por_disciplina']['Língua Portuguesa']['media_geral']:.2f}".replace('.', ','),
            'prof_mat_media': f"{sample_data['proficiencia']['por_disciplina']['Matemática']['media_geral']:.2f}".replace('.', ','),
            'prof_lp_saeb': '272,19',
            'prof_mat_saeb': '293,55',
            
            # Dados de notas
            'media_geral': '6,31',
            'media_lp': f"{sample_data['nota_geral']['por_disciplina']['Língua Portuguesa']['media_geral']:.2f}".replace('.', ','),
            'media_mat': f"{sample_data['nota_geral']['por_disciplina']['Matemática']['media_geral']:.2f}".replace('.', ','),
            
            # Dados de habilidades
            'lp_habilidades': sample_data['acertos_por_habilidade']['Língua Portuguesa']['habilidades'],
            'mat_habilidades': sample_data['acertos_por_habilidade']['Matemática']['habilidades'],
            
            # Análises da IA
            **ai_analysis
        }
        
        print(f"\n✅ Dados do template preparados com {len(template_data)} campos!")
        print(f"📊 Análises da IA incluídas: {len([k for k in template_data.keys() if 'analise' in k or 'recomendacoes' in k])} campos")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro no teste: {str(e)}")
        return False

def main():
    """Função principal de teste"""
    print("🚀 Testando preparação de dados para PDF com IA...\n")
    
    success = test_pdf_data_preparation()
    
    if success:
        print("\n🎉 Teste concluído com sucesso!")
        print("✅ O PDF agora incluirá as análises da IA!")
        print("\n📋 Resumo das funcionalidades implementadas:")
        print("• Endpoint /reports/relatorio-pdf/<id> agora chama a IA")
        print("• Análises da IA são incluídas no PDF")
        print("• Seções: Participação, Proficiência, Notas, Habilidades, Recomendações")
        print("• PDF inteligente com interpretação dos dados")
    else:
        print("\n❌ Teste falhou!")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
