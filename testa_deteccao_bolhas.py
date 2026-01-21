#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para testar deteccao de bolhas com imagem sintetica
"""

import cv2
import numpy as np
from pathlib import Path
import json

def carregar_config():
    json_path = Path("app/services/cartao_resposta/block_01_coordinates_adjustment.json")
    with open(json_path) as f:
        return json.load(f)

def criar_imagem_teste():
    """Cria imagem de teste com bolhas sinteticas"""
    
    config = carregar_config()
    BLOCK_WIDTH = 142
    BLOCK_HEIGHT = 473
    line_height = config.get('line_height', 18)
    start_x = config.get('start_x', 32)
    bubble_size = config.get('bubble_size', 15)
    
    # Criar imagem branca
    img = np.ones((BLOCK_HEIGHT, BLOCK_WIDTH), dtype=np.uint8) * 240
    
    # Desenhar bolhas em posicoes esperadas (26 questoes)
    bolhas_desenhadas = []
    
    for q in range(1, 27):
        # Posicao Y esperada
        y = (q - 1) * line_height + 10  # +10 para ter margem do topo
        
        # Posicao X (algumas posicoes horizontais diferentes para simular alternativas)
        x_positions = [25, 50, 75, 100]  # 4 alternativas
        
        for alt, x in enumerate(x_positions, 1):
            # Desenhar bolha (circulo preenchido com preto)
            cv2.circle(img, (x, y), bubble_size // 2, 0, -1)
            bolhas_desenhadas.append((x, y, q, alt))
    
    return img, bolhas_desenhadas

def detectar_bolhas(img_block):
    """Detecta bolhas usando HoughCircles"""
    img_blur = cv2.GaussianBlur(img_block, (5, 5), 0)
    
    circles = cv2.HoughCircles(
        img_blur,
        cv2.HOUGH_GRADIENT,
        dp=1,
        minDist=20,
        param1=50,
        param2=30,
        minRadius=7,
        maxRadius=8
    )
    
    if circles is None:
        return []
    
    circles = np.uint16(np.around(circles))
    return [(x, y, r) for x, y, r in circles[0]]

def main():
    print("\nTeste de Deteccao de Bolhas - Imagem Sintetica")
    print("="*70)
    
    config = carregar_config()
    line_height = config.get('line_height', 18)
    
    # Criar imagem de teste
    img, bolhas_esperadas = criar_imagem_teste()
    
    print(f"\nImagem criada: {img.shape}")
    print(f"Bolhas desenhadas (sinteticas): {len(bolhas_esperadas)}")
    
    # Detectar bolhas
    bolhas_detectadas = detectar_bolhas(img)
    print(f"Bolhas detectadas: {len(bolhas_detectadas)}")
    
    # Visualizar
    img_viz = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    
    # Desenhar grid esperado (linhas verdes)
    for q in range(1, 27):
        y = (q - 1) * line_height + 10
        cv2.line(img_viz, (0, y), (142, y), (0, 255, 0), 1)
    
    # Desenhar bolhas detectadas (circulos vermelhos)
    for x, y, r in bolhas_detectadas:
        cv2.circle(img_viz, (x, y), r, (0, 0, 255), 2)
    
    # Salvar
    output_path = Path("debug_corrections/teste_deteccao_bolhas.jpg")
    cv2.imwrite(str(output_path), img_viz)
    print(f"\nImagem salva: {output_path}")
    
    # Analisar
    print(f"\nAnalise:")
    print(f"  Esperado: {len(bolhas_esperadas)} bolhas (26 questoes x 4 alternativas)")
    print(f"  Detectado: {len(bolhas_detectadas)} bolhas")
    print(f"  Taxa de deteccao: {len(bolhas_detectadas)/len(bolhas_esperadas)*100:.1f}%")
    
    if len(bolhas_detectadas) >= len(bolhas_esperadas) * 0.9:
        print(f"\n  OK: Deteccao aceitavel!")
    else:
        print(f"\n  AVISO: Muitas bolhas nao foram detectadas!")
        print(f"  Problema pode ser:")
        print(f"    1. Parametros de HoughCircles inadequados")
        print(f"    2. Tamanho de bolha muito pequeno ou muito grande")
        print(f"    3. Contraste insuficiente na imagem")

if __name__ == "__main__":
    main()
