#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Testa se o tamanho da normalizacao esta correto apos o fix
"""

import sys
sys.path.insert(0, '.')

import cv2
from pathlib import Path

# Importar e usar a funcao de normalizacao
from app.services.cartao_resposta.correction_n import AnswerSheetCorrectionN

print("\nTestando normalizacao com nova correcao de tamanho...\n")

img_path = Path('debug_corrections/20260121_095600_412_01_original.jpg')
img = cv2.imread(str(img_path), cv2.IMREAD_GRAYSCALE)

print(f"Imagem original: {img.shape}")

corretor = AnswerSheetCorrectionN(debug=False)

# Detectar quadrados
squares = corretor._detectar_quadrados_a4(img)

if squares:
    print(f"Quadrados detectados: OK")
    
    # Normalizar
    result = corretor._normalizar_para_a4(img, squares)
    
    if result:
        img_normalized, scale_info = result
        print(f"Imagem normalizada: {img_normalized.shape}")
        print(f"Esperado: (1171, 827)")
        
        if img_normalized.shape == (1171, 827):
            print("\n✓ SUCESSO! Tamanho correto!")
        else:
            print(f"\n✗ ERRO: Tamanho incorreto!")
            print(f"  Largura: {img_normalized.shape[1]} (esperado 827)")
            print(f"  Altura: {img_normalized.shape[0]} (esperado 1171)")
    else:
        print("Erro na normalizacao")
else:
    print("Erro na deteccao de quadrados")
