#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para debug do alinhamento de imagens
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.services.physical_test_pdf_generator import PhysicalTestPDFGenerator
import cv2
import numpy as np
from PIL import Image

def debug_alinhamento():
    app = create_app()
    with app.app_context():
        pdf_generator = PhysicalTestPDFGenerator()
        
        # Gerar gabarito
        print("🔧 Gerando gabarito...")
        gabarito_image, gabarito_coords = pdf_generator._gerar_gabarito_referencia('eafb4493-e47a-43e2-98ea-70f75bf6b103')
        
        if gabarito_image is None:
            print("❌ Erro ao gerar gabarito")
            return
        
        # Carregar imagem do usuário (usar a imagem anexada)
        print("🔧 Carregando imagem do usuário...")
        user_image_path = "formulario_preenchido_debug.png"  # Usar a imagem gerada
        
        if not os.path.exists(user_image_path):
            print(f"❌ Arquivo não encontrado: {user_image_path}")
            return
            
        user_image = Image.open(user_image_path)
        
        # Converter para numpy arrays
        gabarito_array = np.array(gabarito_image)
        user_array = np.array(user_image)
        
        print(f"📏 Gabarito: {gabarito_array.shape}")
        print(f"📏 Usuário: {user_array.shape}")
        
        # Testar alinhamento
        print("🔧 Testando alinhamento...")
        user_aligned = pdf_generator._alinhar_por_perspectiva(gabarito_array, user_array)
        
        if user_aligned is None:
            print("❌ Falha no alinhamento")
            return
        
        print(f"✅ Alinhamento bem-sucedido: {user_aligned.shape}")
        
        # Salvar imagem alinhada para debug
        cv2.imwrite("debug_gabarito.png", gabarito_array)
        cv2.imwrite("debug_usuario_original.png", user_array)
        cv2.imwrite("debug_usuario_alinhado.png", user_aligned)
        
        print("✅ Imagens de debug salvas:")
        print("  - debug_gabarito.png")
        print("  - debug_usuario_original.png") 
        print("  - debug_usuario_alinhado.png")

if __name__ == "__main__":
    debug_alinhamento()
