#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para gerar imagens do formulário e gabarito para debug
"""

from app import create_app
from app.services.physical_test_pdf_generator import PhysicalTestPDFGenerator
import cv2
import numpy as np
from PIL import Image
import os

def gerar_imagens_debug():
    """Gera imagens do formulário e gabarito para visualização"""
    
    app = create_app()
    with app.app_context():
        print("🎯 GERANDO IMAGENS DE DEBUG...")
        
        # ID da prova
        test_id = 'eafb4493-e47a-43e2-98ea-70f75bf6b103'
        
        # Criar instância do gerador
        pdf_generator = PhysicalTestPDFGenerator()
        
        # 1. GERAR GABARITO DE REFERÊNCIA
        print("\n🔧 ETAPA 1: Gerando gabarito de referência...")
        gabarito_image, gabarito_coords = pdf_generator._gerar_gabarito_referencia(test_id)
        
        if gabarito_image and gabarito_coords:
            # Salvar gabarito
            gabarito_path = "gabarito_debug.png"
            if hasattr(gabarito_image, 'save'):
                # PIL Image
                gabarito_image.save(gabarito_path)
            else:
                # NumPy array
                cv2.imwrite(gabarito_path, gabarito_image)
            print(f"✅ Gabarito salvo: {gabarito_path}")
            print(f"📊 Coordenadas do gabarito: {len(gabarito_coords)} posições")
        else:
            print("❌ Erro ao gerar gabarito")
            return
        
        # 2. GERAR FORMULÁRIO DE EXEMPLO
        print("\n🔧 ETAPA 2: Gerando formulário de exemplo...")
        
        # Importar função do formularios.py
        import sys
        sys.path.append('.')
        from app.formularios import gerar_formulario_com_qrcode
        
        # Dados do aluno de exemplo
        student_data = {
            'id': 'ae3b4c91-4f9e-4e0e-bd97-ff1d40b6b22b',
            'nome': 'João Silva Santos',
            'escola': 'Escola Teste',
            'turma': '9º Ano A'
        }
        
        # Gerar formulário
        form_image, form_coords, qr_coords = gerar_formulario_com_qrcode(
            student_data['id'],
            student_data['nome'],
            4,  # 4 questões
            "formulario_debug.png",
            student_data,
            {'id': test_id, 'title': 'Avaliação teste aartur'}
        )
        
        if form_image and form_coords:
            print(f"✅ Formulário salvo: formulario_debug.png")
            print(f"📊 Coordenadas do formulário: {len(form_coords)} posições")
            print(f"📊 Coordenadas do QR: {qr_coords}")
        else:
            print("❌ Erro ao gerar formulário")
            return
        
        # 3. CRIAR FORMULÁRIO PREENCHIDO (SIMULADO)
        print("\n🔧 ETAPA 3: Criando formulário preenchido simulado...")
        
        # Carregar formulário base
        form_base = Image.open("formulario_debug.png")
        form_filled = form_base.copy()
        
        # Simular marcações (respostas: 1-A, 2-B, 3-A, 4-A)
        from PIL import ImageDraw
        draw = ImageDraw.Draw(form_filled)
        
        # Respostas simuladas
        respostas_simuladas = {
            1: 'A',  # Questão 1: A
            2: 'B',  # Questão 2: B  
            3: 'A',  # Questão 3: A
            4: 'A'   # Questão 4: A
        }
        
        # Mapear alternativas para índices
        alt_map = {'A': 0, 'B': 1, 'C': 2, 'D': 3}
        
        # Usar coordenadas corretas fixas
        x_positions_correct = [112, 162, 212, 262]  # Coordenadas X corretas
        y_positions_correct = [950, 995, 1040, 1085]  # Coordenadas Y corretas
        
        # Preencher bolhas usando coordenadas corretas
        for questao, resposta in respostas_simuladas.items():
            alt_idx = alt_map[resposta]
            
            # Usar coordenadas corretas em vez das do form_coords
            x = x_positions_correct[alt_idx]
            y = y_positions_correct[questao - 1]
            
            # Desenhar círculo preenchido
            radius = 8
            draw.ellipse([x-radius, y-radius, x+radius, y+radius], 
                       fill='black', outline='black')
            
            print(f"  ✅ Questão {questao}: {resposta} marcada em ({x},{y})")
        
        # Salvar formulário preenchido
        form_filled.save("formulario_preenchido_debug.png")
        print(f"✅ Formulário preenchido salvo: formulario_preenchido_debug.png")
        
        # 4. MOSTRAR INFORMAÇÕES DAS COORDENADAS
        print("\n📊 INFORMAÇÕES DAS COORDENADAS:")
        print(f"Gabarito: {len(gabarito_coords)} coordenadas")
        print(f"Formulário: {len(form_coords)} coordenadas")
        
        print("\n📋 Coordenadas do gabarito:")
        for i, coord in enumerate(gabarito_coords):
            questao = (i // 4) + 1
            alternativa = ['A', 'B', 'C', 'D'][i % 4]
            print(f"  Questão {questao} {alternativa}: {coord}")
        
        print("\n📋 Coordenadas do formulário:")
        for i, coord in enumerate(form_coords):
            questao = (i // 4) + 1
            alternativa = ['A', 'B', 'C', 'D'][i % 4]
            print(f"  Questão {questao} {alternativa}: {coord}")
        
        print("\n🎯 IMAGENS GERADAS:")
        print("  - gabarito_debug.png (gabarito de referência)")
        print("  - formulario_debug.png (formulário em branco)")
        print("  - formulario_preenchido_debug.png (formulário com respostas simuladas)")
        
        print("\n✅ Processo concluído!")

if __name__ == "__main__":
    gerar_imagens_debug()
