#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Teste simples da função PDF sem dependências do Flask
"""

import sys
import os

# Adicionar o diretório atual ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Mock simples das dependências
class MockModule:
    def __init__(self, name):
        self.__name__ = name
        self.__file__ = f"<mock {name}>"

# Criar módulos mock
sys.modules['flask'] = MockModule('flask')
sys.modules['flask_jwt_extended'] = MockModule('flask_jwt_extended')
sys.modules['app'] = MockModule('app')
sys.modules['app.decorators'] = MockModule('app.decorators')
sys.modules['app.decorators.role_required'] = MockModule('app.decorators.role_required')
sys.modules['app.models'] = MockModule('app.models')
sys.modules['app.models.test'] = MockModule('app.models.test')
sys.modules['app.models.student'] = MockModule('app.models.student')
sys.modules['app.models.studentAnswer'] = MockModule('app.models.studentAnswer')
sys.modules['app.models.testSession'] = MockModule('app.models.testSession')
sys.modules['app.models.question'] = MockModule('app.models.question')
sys.modules['app.models.subject'] = MockModule('app.models.subject')
sys.modules['app.models.school'] = MockModule('app.models.school')
sys.modules['app.models.city'] = MockModule('app.models.city')
sys.modules['app.models.studentClass'] = MockModule('app.models.studentClass')
sys.modules['app.models.grades'] = MockModule('app.models.grades')
sys.modules['app.models.classTest'] = MockModule('app.models.classTest')
sys.modules['app.models.evaluationResult'] = MockModule('app.models.evaluationResult')
sys.modules['app.services'] = MockModule('app.services')
sys.modules['app.services.ai_analysis_service'] = MockModule('app.services.ai_analysis_service')

# Mock das classes
class MockClass:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

# Mock das funções
def mock_function(*args, **kwargs):
    return MockClass()

# Adicionar ao módulo app
app_module = sys.modules['app']
app_module.db = MockClass()
app_module.logging = MockClass()
app_module.logging.error = lambda x: print(f"LOG ERROR: {x}")

# Mock das funções de decorator
role_module = sys.modules['app.decorators.role_required']
role_module.role_required = mock_function
role_module.get_current_user_from_token = mock_function

# Mock das classes de modelo
for model_name in ['test', 'student', 'studentAnswer', 'testSession', 'question', 
                   'subject', 'school', 'city', 'studentClass', 'grades', 'classTest', 'evaluationResult']:
    model_module = sys.modules[f'app.models.{model_name}']
    model_module.query = MockClass()
    model_module.query.get = lambda x: MockClass()
    model_module.query.filter_by = lambda **kwargs: MockClass()
    model_module.query.filter = lambda *args: MockClass()
    model_module.query.all = lambda: []
    model_module.query.order_by = lambda x: MockClass()

# Mock do AI service
ai_module = sys.modules['app.services.ai_analysis_service']
ai_module.AIAnalysisService = MockClass()

# Agora tentar importar
try:
    from app.routes.report_routes import _gerar_pdf_reportlab
    print("✅ Função importada com sucesso!")
except Exception as e:
    print(f"❌ Erro ao importar: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

def test_pdf_generation():
    """Testa a geração do PDF com dados mínimos"""
    
    # Dados mínimos para teste
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
            }
        ],
        'total_label': '9º GERAL',
        'total_matriculados': 30,
        'total_avaliados': 28,
        'total_faltosos': 2,
        'participacao_texto_padrao': 'A escola avaliou 28 alunos do 9º ano...',
        'lp_niveis': [['9º A', '2', '5', '12', '9']],
        'lp_totais': ['9º GERAL', '2', '5', '12', '9'],
        'lp_resumo_lista': [
            'Abaixo do Básico: 2 alunos (7,1%)',
            'Básico: 5 alunos (17,9%)',
            'Adequado: 12 alunos (42,9%)',
            'Avançado: 9 alunos (32,1%)'
        ],
        'mat_niveis': [['9º A', '4', '8', '10', '6']],
        'mat_totais': ['9º GERAL', '4', '8', '10', '6'],
        'proficiencia': [
            {
                'serie_turno': '9º A',
                'lp': '298.5',
                'mat': '268.2',
                'media': '283.4',
                'municipal': 'SIM'
            }
        ],
        'proficiencia_texto_padrao': 'A proficiência média da escola nesta avaliação diagnóstica foi de 298,5 em LP e 268,2 em Matemática...',
        'lp_rotulos_1_13': ['H1', 'H2', 'H3', 'H4', 'H5', 'H6', 'H7', 'H8', 'H9', 'H10', 'H11', 'H12', 'H13'],
        'lp_pct_1_13': ['85%', '78%', '92%', '67%', '89%', '76%', '94%', '71%', '88%', '73%', '91%', '69%', '87%'],
        'lp_rotulos_14_26': ['H14', 'H15', 'H16', 'H17', 'H18', 'H19', 'H20', 'H21', 'H22', 'H23', 'H24', 'H25', 'H26'],
        'lp_pct_14_26': ['82%', '75%', '90%', '64%', '86%', '79%', '93%', '68%', '84%', '77%', '89%', '72%', '85%']
    }
    
    try:
        print("🚀 Gerando PDF de teste...")
        pdf_content = _gerar_pdf_reportlab(template_data)
        
        # Salvar o PDF gerado
        with open('teste_simples.pdf', 'wb') as f:
            f.write(pdf_content)
        
        print(f"✅ PDF gerado com sucesso! Tamanho: {len(pdf_content)} bytes")
        print("📁 Arquivo salvo como: teste_simples.pdf")
        
        return True
        
    except Exception as e:
        print(f"❌ Erro ao gerar PDF: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🎯 Iniciando teste da função PDF...")
    success = test_pdf_generation()
    if success:
        print("\n🎉 Teste concluído com sucesso!")
    else:
        print("\n💥 Teste falhou!")
        sys.exit(1)
