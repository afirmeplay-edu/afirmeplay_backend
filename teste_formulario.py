#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de teste para gerar formulário de exemplo
"""

import sys
import os

# Adicionar o diretório pai ao path para encontrar o módulo app
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Importar a função do formulário
from app.formularios import gerar_formulario_com_qrcode

def main():
    print("Gerando formulário de teste...")
    
    # Dados de teste
    aluno_id = "12345"
    aluno_nome = "João Silva Santos"
    num_questoes_total = 20
    nome_arquivo_saida = "teste_formulario.png"
    
    # Dados completos do aluno para teste
    student_data = {
        'student_name': 'João Silva Santos',
        'class_name': '9º Ano A',
        'school_name': 'Escola Municipal Rui Palmeira',
        'city_name': 'São Miguel dos Campos',
        'state_name': 'Alagoas'
    }
    
    # Dados do teste
    test_data = {
        'id': 'test-123',
        'title': '2º AVALIE SÃO MIGUEL'
    }
    
    try:
        # Gerar o formulário
        resultado = gerar_formulario_com_qrcode(
            aluno_id=aluno_id,
            aluno_nome=aluno_nome,
            num_questoes_total=num_questoes_total,
            nome_arquivo_saida=nome_arquivo_saida,
            student_data=student_data,
            test_data=test_data
        )
        
        if resultado[0] is not None:
            print(f"✅ Formulário gerado com sucesso!")
            print(f"📁 Arquivo salvo como: {nome_arquivo_saida}")
            print(f"📏 Dimensões: {resultado[0].size}")
            print(f"📍 Coordenadas QR: {resultado[1]}")
            print(f"📍 Coordenadas respostas: {len(resultado[2])} questões")
        else:
            print("❌ Erro ao gerar formulário")
            
    except Exception as e:
        print(f"❌ Erro: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
