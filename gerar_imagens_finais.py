#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gera imagens finais do gabarito preenchido e formulário vazio
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.formularios import gerar_formulario_com_qrcode
import tempfile

def gerar_imagens_finais():
    """
    Gera gabarito preenchido e formulário vazio
    """
    print("🎯 GERANDO IMAGENS FINAIS...")
    
    # Dados de teste
    test_data = {
        'id': 'test-final',
        'title': 'Prova Final - Coordenadas Ajustadas'
    }
    
    # 1. Gerar formulário vazio (para aluno preencher)
    print("🔧 Gerando formulário vazio...")
    
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        temp_path_formulario = tmp.name
    
    try:
        # Formulário vazio (sem respostas preenchidas)
        formulario_vazio, coords_formulario, qr_coords = gerar_formulario_com_qrcode(
            'ALUNO_TESTE',
            'João Silva Santos', 
            4,  # 4 questões
            temp_path_formulario,
            None,  # Sem dados de gabarito
            test_data
        )
        
        if formulario_vazio:
            formulario_vazio.save('formulario_vazio_final.png')
            print("✅ Formulário vazio salvo: formulario_vazio_final.png")
        else:
            print("❌ Erro ao gerar formulário vazio")
            return False
            
    except Exception as e:
        print(f"❌ Erro ao gerar formulário vazio: {str(e)}")
        return False
    finally:
        if os.path.exists(temp_path_formulario):
            os.unlink(temp_path_formulario)
    
    # 2. Gerar gabarito preenchido
    print("🔧 Gerando gabarito preenchido...")
    
    # Dados do gabarito com respostas corretas
    gabarito_data = {
        'id': 'GABARITO_FINAL',
        'nome': 'GABARITO DE REFERÊNCIA',
        'questoes': [
            {'numero': 1, 'resposta_correta': 'A'},
            {'numero': 2, 'resposta_correta': 'B'},
            {'numero': 3, 'resposta_correta': 'A'},
            {'numero': 4, 'resposta_correta': 'A'}
        ]
    }
    
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        temp_path_gabarito = tmp.name
    
    try:
        # Gabarito preenchido
        gabarito_preenchido, coords_gabarito, qr_coords_gab = gerar_formulario_com_qrcode(
            'GABARITO_FINAL',
            'GABARITO DE REFERÊNCIA', 
            4,  # 4 questões
            temp_path_gabarito,
            gabarito_data,
            test_data
        )
        
        if gabarito_preenchido:
            # Preencher as respostas corretas no gabarito
            from app.services.physical_test_pdf_generator import PhysicalTestPDFGenerator
            pdf_generator = PhysicalTestPDFGenerator()
            
            # Simular questões com respostas corretas
            class QuestaoSimulada:
                def __init__(self, numero, resposta):
                    self.numero = numero
                    self.correct_answer = resposta
            
            questoes = [
                QuestaoSimulada(1, 'A'),
                QuestaoSimulada(2, 'B'),
                QuestaoSimulada(3, 'A'),
                QuestaoSimulada(4, 'A')
            ]
            
            # Preencher respostas corretas
            gabarito_final = pdf_generator._preencher_respostas_corretas(
                gabarito_preenchido, 
                coords_gabarito, 
                questoes
            )
            
            if gabarito_final:
                gabarito_final.save('gabarito_preenchido_final.png')
                print("✅ Gabarito preenchido salvo: gabarito_preenchido_final.png")
            else:
                gabarito_preenchido.save('gabarito_preenchido_final.png')
                print("✅ Gabarito (sem preenchimento automático) salvo: gabarito_preenchido_final.png")
        else:
            print("❌ Erro ao gerar gabarito")
            return False
            
    except Exception as e:
        print(f"❌ Erro ao gerar gabarito: {str(e)}")
        return False
    finally:
        if os.path.exists(temp_path_gabarito):
            os.unlink(temp_path_gabarito)
    
    print("\n🎉 IMAGENS GERADAS COM SUCESSO!")
    print("📁 Arquivos criados:")
    print("  - formulario_vazio_final.png (para o aluno preencher)")
    print("  - gabarito_preenchido_final.png (com respostas corretas)")
    
    return True

if __name__ == "__main__":
    sucesso = gerar_imagens_finais()
    if sucesso:
        print("\n✅ Processo concluído com sucesso!")
    else:
        print("\n❌ Erro no processo de geração das imagens.")
