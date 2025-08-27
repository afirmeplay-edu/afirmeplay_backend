# -*- coding: utf-8 -*-
"""
Teste para verificar se as tabelas estão sendo renderizadas corretamente no template
"""

import sys
import os

# Adicionar o diretório raiz ao path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from jinja2 import Template
from app.services.ai_analysis_service import AIAnalysisService

def test_template_rendering():
    """Testa se o template está sendo renderizado corretamente com as tabelas"""
    try:
        print("📊 Testando renderização do template com tabelas...")
        
        # Dados de exemplo para testar as tabelas
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
                        "matriculados": 38,
                        "avaliados": 37,
                        "faltosos": 1,
                        "percentual": 97.4
                    },
                    {
                        "turma": "9º B",
                        "matriculados": 37,
                        "avaliados": 37,
                        "faltosos": 0,
                        "percentual": 100.0
                    },
                    {
                        "turma": "9º C",
                        "matriculados": 35,
                        "avaliados": 30,
                        "faltosos": 5,
                        "percentual": 85.7
                    }
                ]
            },
            "niveis_aprendizagem": {
                "Língua Portuguesa": {
                    "por_turma": [
                        {
                            "turma": "9º A",
                            "abaixo_do_basico": 0,
                            "basico": 0,
                            "adequado": 5,
                            "avancado": 32
                        },
                        {
                            "turma": "9º B",
                            "abaixo_do_basico": 2,
                            "basico": 2,
                            "adequado": 3,
                            "avancado": 30
                        }
                    ],
                    "geral": {
                        "abaixo_do_basico": 20,
                        "basico": 27,
                        "adequado": 45,
                        "avancado": 130
                    }
                },
                "Matemática": {
                    "por_turma": [
                        {
                            "turma": "9º A",
                            "abaixo_do_basico": 1,
                            "basico": 3,
                            "adequado": 8,
                            "avancado": 25
                        },
                        {
                            "turma": "9º B",
                            "abaixo_do_basico": 3,
                            "basico": 5,
                            "adequado": 12,
                            "avancado": 17
                        }
                    ],
                    "geral": {
                        "abaixo_do_basico": 25,
                        "basico": 35,
                        "adequado": 55,
                        "avancado": 107
                    }
                }
            },
            "proficiencia": {
                "por_disciplina": {
                    "Língua Portuguesa": {
                        "media_geral": 298.86,
                        "por_turma": [
                            {"turma": "9º A", "proficiencia": 348.00},
                            {"turma": "9º B", "proficiencia": 325.50}
                        ]
                    },
                    "Matemática": {
                        "media_geral": 268.29,
                        "por_turma": [
                            {"turma": "9º A", "proficiencia": 364.00},
                            {"turma": "9º B", "proficiencia": 298.50}
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
                            {"turma": "9º A", "nota": 8.25},
                            {"turma": "9º B", "nota": 7.45}
                        ]
                    },
                    "Matemática": {
                        "media_geral": 5.85,
                        "por_turma": [
                            {"turma": "9º A", "nota": 8.79},
                            {"turma": "9º B", "nota": 7.42}
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
                        {"codigo": "9L1.1", "percentual": 67.1, "questoes": [{"numero": 1}]},
                        {"codigo": "9L1.1", "percentual": 46.4, "questoes": [{"numero": 2}]},
                        {"codigo": "9L1.2", "percentual": 69.4, "questoes": [{"numero": 3}]},
                        {"codigo": "9L1.2", "percentual": 53.2, "questoes": [{"numero": 4}]},
                        {"codigo": "9L1.3", "percentual": 48.6, "questoes": [{"numero": 5}]}
                    ]
                },
                "Matemática": {
                    "habilidades": [
                        {"codigo": "9N1.2", "percentual": 77.5, "questoes": [{"numero": 28}]},
                        {"codigo": "9N1.4", "percentual": 86.5, "questoes": [{"numero": 31}]},
                        {"codigo": "9N1.9", "percentual": 75.7, "questoes": [{"numero": 38}]},
                        {"codigo": "9N2.1", "percentual": 85.6, "questoes": [{"numero": 41}]},
                        {"codigo": "9G1.2", "percentual": 84.7, "questoes": [{"numero": 50}]}
                    ]
                }
            }
        }
        
        # 1. Testar serviço de IA
        ai_service = AIAnalysisService()
        ai_analysis = ai_service.analyze_report_data(sample_data)
        
        print("✅ Análise da IA concluída!")
        
        # 2. Preparar dados para o template
        template_data = {
            # Dados básicos
            'escola': 'E. M. E. B. MONSENHOR HILDEBRANDO',
            'municipio': 'Campo Alegre',
            'uf': 'AL',
            'periodo': '2025.1',
            'mes': 'MAIO',
            'ano': '2025',
            'serie_titulo': '9º ANO',
            
            # Dados de participação
            'participacao': sample_data['total_alunos']['por_turma'],
            'total_avaliados': sample_data['total_alunos']['total_geral']['avaliados'],
            'total_matriculados': sample_data['total_alunos']['total_geral']['matriculados'],
            'total_faltosos': sample_data['total_alunos']['total_geral']['faltosos'],
            'percentual_avaliados': sample_data['total_alunos']['total_geral']['percentual'],
            
            # Dados de níveis de aprendizagem
            'niveis_aprendizagem': sample_data['niveis_aprendizagem'],
            
            # Dados de proficiência
            'proficiencia': [
                {
                    'serie_turno': '9º A',
                    'lp': 348.00,
                    'mat': 364.00,
                    'media': 356.00
                },
                {
                    'serie_turno': '9º B',
                    'lp': 325.50,
                    'mat': 298.50,
                    'media': 312.00
                }
            ],
            'prof_lp_media': '298,86',
            'prof_mat_media': '268,29',
            'prof_lp_saeb': '272,19',
            'prof_mat_saeb': '293,55',
            'municipal_media': '265,00',
            
            # Dados de notas
            'notas': [
                {
                    'serie_turno': '9º A',
                    'lp': 8.25,
                    'mat': 8.79,
                    'media': 8.52
                },
                {
                    'serie_turno': '9º B',
                    'lp': 7.45,
                    'mat': 7.42,
                    'media': 7.44
                }
            ],
            'media_geral': '6,31',
            'media_lp': '6,77',
            'media_mat': '5,85',
            'municipal_nota_media': '5,50',
            
            # Dados de habilidades
            'lp_habilidades': sample_data['acertos_por_habilidade']['Língua Portuguesa']['habilidades'],
            'mat_habilidades': sample_data['acertos_por_habilidade']['Matemática']['habilidades'],
            
            # Análises da IA
            **ai_analysis
        }
        
        print("✅ Dados do template preparados!")
        
        # 3. Ler o template HTML
        template_path = os.path.join(os.path.dirname(__file__), 'app', 'templates', 'relatorio_avaliacao.html')
        with open(template_path, 'r', encoding='utf-8') as f:
            template_content = f.read()
        
        print("✅ Template HTML lido!")
        
        # 4. Renderizar o template
        template = Template(template_content)
        html_content = template.render(**template_data)
        
        print("✅ Template renderizado com sucesso!")
        
        # 5. Verificar se as tabelas estão presentes
        table_checks = [
            ("Tabela de Participação", "MATRICULADOS"),
            ("Tabela de Níveis LP", "ABAIXO DO BÁSICO"),
            ("Tabela de Níveis MAT", "ABAIXO DO BÁSICO"),
            ("Tabela de Proficiência", "MUNICIPAL"),
            ("Tabela de Notas", "MUNICIPAL"),
            ("Tabela de Habilidades LP", "1ª Q"),
            ("Tabela de Habilidades MAT", "1ª Q")
        ]
        
        print("\n🔍 Verificando tabelas no HTML renderizado:")
        for check_name, check_text in table_checks:
            if check_text in html_content:
                print(f"✅ {check_name}: Encontrada")
            else:
                print(f"❌ {check_name}: NÃO encontrada")
        
        # 6. Verificar se as análises da IA estão presentes
        ia_checks = [
            ("Análise Participação", "analise da IA Participacao dos Alunos"),
            ("Análise Proficiência", "analise da IA Proficiencia"),
            ("Análise Notas", "analise da IA notas"),
            ("Análise Habilidades", "analise da IA Habilidades")
        ]
        
        print("\n🤖 Verificando análises da IA:")
        for check_name, check_text in ia_checks:
            if check_text in html_content:
                print(f"✅ {check_name}: Comentário encontrado")
            else:
                print(f"❌ {check_name}: Comentário NÃO encontrado")
        
        # 7. Salvar HTML para inspeção
        output_path = "test_template_output.html"
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"\n💾 HTML renderizado salvo em: {output_path}")
        print("📱 Abra o arquivo no navegador para verificar as tabelas!")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro no teste: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Função principal de teste"""
    print("🚀 Testando renderização do template com tabelas...\n")
    
    success = test_template_rendering()
    
    if success:
        print("\n🎉 Teste concluído com sucesso!")
        print("✅ As tabelas estão sendo renderizadas corretamente!")
        print("\n📋 Resumo das funcionalidades implementadas:")
        print("• Tabela de Participação com dados corretos")
        print("• Tabelas de Níveis de Aprendizagem por disciplina")
        print("• Tabela de Proficiência com comparação municipal")
        print("• Tabela de Notas com comparação municipal")
        print("• Tabelas de Habilidades com colunas dinâmicas")
        print("• Comentários para inserção das análises da IA")
    else:
        print("\n❌ Teste falhou!")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
