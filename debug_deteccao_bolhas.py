#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para debug da detecção de bolhas
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.services.physical_test_pdf_generator import PhysicalTestPDFGenerator
import cv2
import numpy as np
from PIL import Image, ImageDraw

def debug_deteccao_bolhas():
    app = create_app()
    with app.app_context():
        pdf_generator = PhysicalTestPDFGenerator()
        
        # Gerar gabarito
        print("🔧 Gerando gabarito...")
        gabarito_image, gabarito_coords = pdf_generator._gerar_gabarito_referencia('eafb4493-e47a-43e2-98ea-70f75bf6b103')
        
        if gabarito_image is None:
            print("❌ Erro ao gerar gabarito")
            return
        
        # Carregar imagem do usuário
        print("🔧 Carregando imagem do usuário...")
        user_image_path = "formulario_preenchido_debug.png"
        
        if not os.path.exists(user_image_path):
            print(f"❌ Arquivo não encontrado: {user_image_path}")
            return
            
        user_image = Image.open(user_image_path)
        
        # Converter para numpy arrays
        gabarito_array = np.array(gabarito_image)
        user_array = np.array(user_image)
        
        # Alinhar imagem do usuário
        print("🔧 Alinhando imagem...")
        user_aligned = pdf_generator._alinhar_por_perspectiva(gabarito_array, user_array)
        
        if user_aligned is None:
            print("❌ Falha no alinhamento")
            return
        
        # Converter para grayscale
        if len(user_aligned.shape) == 3:
            user_gray = cv2.cvtColor(user_aligned, cv2.COLOR_BGR2GRAY)
        else:
            user_gray = user_aligned
        
        print(f"📏 Imagem alinhada: {user_gray.shape}")
        
        # Testar detecção de bolhas
        print("🔧 Testando detecção de bolhas...")
        respostas = pdf_generator._detectar_bolhas_por_coordenadas(user_gray, gabarito_coords)
        
        print(f"📊 Respostas detectadas: {respostas}")
        
        # Criar imagem de debug com coordenadas marcadas
        debug_image = user_aligned.copy()
        draw = ImageDraw.Draw(Image.fromarray(debug_image))
        
        # Marcar coordenadas das bolhas
        x_positions = [112, 162, 212, 262]
        y_positions = [950, 995, 1040, 1085]
        
        for i, y in enumerate(y_positions):
            for j, x in enumerate(x_positions):
                # Desenhar círculo vermelho nas coordenadas
                draw.ellipse([x-10, y-10, x+10, y+10], outline="red", width=2)
                draw.text((x+15, y-5), f"{i+1}{chr(65+j)}", fill="red")
        
        # Salvar imagem de debug
        Image.fromarray(debug_image).save("debug_coordenadas_marcadas.png")
        print("✅ Imagem de debug salva: debug_coordenadas_marcadas.png")

if __name__ == "__main__":
    debug_deteccao_bolhas()
