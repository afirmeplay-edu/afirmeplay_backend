#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Analisa localizacao dos blocos na imagem normalizada
"""

import cv2
import numpy as np
from pathlib import Path

# Constantes
A4_WIDTH_PX = 827
A4_HEIGHT_PX = 1169

# Ler imagem normalizada do debug
debug_dir = Path('debug_corrections')
normalized_image = debug_dir / '20260121_095600_412_01_a4_normalized.jpg'

if not normalized_image.exists():
    print(f"Imagem nao encontrada: {normalized_image}")
    exit(1)

img = cv2.imread(str(normalized_image), 0)
print(f"\nImagem normalizada: {img.shape}")
print(f"Esperado: ({A4_HEIGHT_PX}, {A4_WIDTH_PX})")

# Verificar se está correto
if img.shape == (A4_HEIGHT_PX, A4_WIDTH_PX):
    print("✓ Tamanho correto!")
else:
    print(f"✗ Tamanho incorreto! Esperado ({A4_HEIGHT_PX}, {A4_WIDTH_PX}), obtido {img.shape}")

# Mostrar blocos detectados (se houver imagem deles)
blocks_image = debug_dir / '20260121_095600_412_03_area_blocos_cropped.jpg'
if blocks_image.exists():
    img_blocks = cv2.imread(str(blocks_image), 0)
    print(f"\nImagem com blocos: {img_blocks.shape}")
    
    # Verificar onde o bloco 01 esta (dentro de 142x473)
    # Teoricamente deve estar nas posicoes: x=32-174, y=15-488
    print(f"\nPosicoes teoricas dos blocos (bloco 01 como referencia):")
    print(f"  X: 32 (start_x) a {32+142} (start_x + width)")
    print(f"  Y: 15 (start_y) a {15+473} (start_y + height)")

print("\nCONCLUSAO:")
print("Se a imagem normalizada tem tamanho correto (1169x827),")
print("entao o problema nao esta no warpPerspective!")
