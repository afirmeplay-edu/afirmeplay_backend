#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Teste da função _gerar_pdf_reportlab corrigida
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.routes.report_routes import _gerar_pdf_reportlab

def test_pdf_generation():
    """Testa a geração do PDF com dados de exemplo"""
    
    # Dados de exemplo para teste
    template_data = {
        'periodo': '2025.1',
        'municipio': 'CAMPO ALEGRE',
        'uf': 'AL',
        'escola': 'E. M. E. B. MONSENHOR HILDEBRANDO',
        'mes': 'MAIO',
        'ano': '2025',
        'sumario_p1': '3',
        'sumario_p2': '3',
        'sumario_p3': '4',
        'sumario_p4': '4',
        'sumario_p41': '4-5',
        'sumario_p42': '5',
        'sumario_p43': '6',
        'sumario_p44': '7',
        'simulados_label': '1º Simulado',
        'referencia': '9º de 2025',
        'escola_extenso': 'ESCOLA MUNICIPAL DE EDUCAÇÃO BÁSICA MONSENHOR HILDEBRANDO',
        'total_avaliados': 222,
        'percentual_avaliados': '89%',
        'participacao': [
            {
                'serie_turno': '9º A',
                'matriculados': 30,
                'avaliados': 28,
                'percentual': 93,
                'faltosos': 2
            },
            {
                'serie_turno': '9º B',
                'matriculados': 32,
                'avaliados': 29,
                'percentual': 91,
                'faltosos': 3
            }
        ],
        'total_label': '9º GERAL',
        'total_matriculados': 62,
        'total_avaliados': 57,
        'total_faltosos': 5,
        'participacao_texto_padrao': 'A escola avaliou 57 alunos do 9º ano...',
        'lp_niveis': [
            ['9º A', '2', '5', '12', '9'],
            ['9º B', '3', '4', '15', '7']
        ],
        'lp_totais': ['9º GERAL', '5', '9', '27', '16'],
        'lp_resumo_lista': [
            'Abaixo do Básico: 5 alunos (8,8%)',
            'Básico: 9 alunos (15,8%)',
            'Adequado: 27 alunos (47,4%)',
            'Avançado: 16 alunos (28,1%)'
        ],
        'mat_niveis': [
            ['9º A', '4', '8', '10', '6'],
            ['9º B', '5', '7', '12', '5']
        ],
        'mat_totais': ['9º GERAL', '9', '15', '22', '11'],
        'proficiencia': [
            {
                'serie_turno': '9º A',
                'lp': '298.5',
                'mat': '268.2',
                'media': '283.4',
                'municipal': 'SIM'
            },
            {
                'serie_turno': '9º B',
                'lp': '299.1',
                'mat': '268.5',
                'media': '283.8',
                'municipal': 'SIM'
            }
        ],
        'proficiencia_texto_padrao': 'A proficiência média da escola nesta avaliação diagnóstica foi de 298,86 em LP e 268,29 em Matemática...',
        'lp_rotulos_1_13': ['H1', 'H2', 'H3', 'H4', 'H5', 'H6', 'H7', 'H8', 'H9', 'H10', 'H11', 'H12', 'H13'],
        'lp_pct_1_13': ['85%', '78%', '92%', '67%', '89%', '76%', '94%', '71%', '88%', '73%', '91%', '69%', '87%'],
        'lp_rotulos_14_26': ['H14', 'H15', 'H16', 'H17', 'H18', 'H19', 'H20', 'H21', 'H22', 'H23', 'H24', 'H25', 'H26'],
        'lp_pct_14_26': ['82%', '75%', '90%', '64%', '86%', '79%', '93%', '68%', '84%', '77%', '89%', '72%', '85%']
    }
    
    try:
        print("Gerando PDF de teste...")
        pdf_content = _gerar_pdf_reportlab(template_data)
        
        # Salvar o PDF gerado
        with open('teste_relatorio.pdf', 'wb') as f:
            f.write(pdf_content)
        
        print(f"PDF gerado com sucesso! Tamanho: {len(pdf_content)} bytes")
        print("Arquivo salvo como: teste_relatorio.pdf")
        
        return True
        
    except Exception as e:
        print(f"Erro ao gerar PDF: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_pdf_generation()
    if success:
        print("\n✅ Teste concluído com sucesso!")
    else:
        print("\n❌ Teste falhou!")
        sys.exit(1)
