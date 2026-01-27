#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para visualizar deteccao de bolhas vs grid esperado
"""

import cv2
import numpy as np
from pathlib import Path
import json

# Constantes
BUBBLE_SIZE_MIN = 20
BUBBLE_SIZE_MAX = 50
LINE_Y_THRESHOLD = 8

def carregar_config():
    json_path = Path("app/services/cartao_resposta/block_01_coordinates_adjustment.json")
    with open(json_path) as f:
        return json.load(f)

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
        minRadius=BUBBLE_SIZE_MIN // 2,
        maxRadius=BUBBLE_SIZE_MAX // 2
    )
    
    if circles is None:
        return []
    
    circles = np.uint16(np.around(circles))
    return [(x, y, r) for x, y, r in circles[0]]

def main():
    print("\nAnalise de Deteccao de Bolhas")
    print("="*70)
    
    config = carregar_config()
    line_height = config.get('line_height', 18)
    start_x = config.get('start_x', 32)
    start_y = config.get('start_y', 15)
    
    # Carregar imagem normalizada
    img_path = Path("debug_corrections/20260121_095600_412_01_a4_normalized.jpg")
    if not img_path.exists():
        print(f"Arquivo nao encontrado: {img_path}")
        return
    
    img = cv2.imread(str(img_path))
    img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Extrair bloco 01
    BLOCK_WIDTH = 142
    BLOCK_HEIGHT = 473
    
    block = img_gray[start_y:start_y+BLOCK_HEIGHT, start_x:start_x+BLOCK_WIDTH].copy()
    block_color = img[start_y:start_y+BLOCK_HEIGHT, start_x:start_x+BLOCK_WIDTH].copy()
    
    print(f"\nBloco 01: {block.shape}")
    print(f"Min: {block.min()}, Max: {block.max()}, Mean: {block.mean():.1f}")
    
    # Detectar bolhas
    bolhas = detectar_bolhas(block)
    print(f"Bolhas detectadas: {len(bolhas)}")
    
    if len(bolhas) == 0:
        print("AVISO: Nenhuma bolha detectada!")
        print("Isto pode significar:")
        print("  1. A imagem e muito clara (sem bolhas marcadas)")
        print("  2. Os parametros de HoughCircles nao estao otimizados")
        print("  3. Nao ha bolhas marcadas nesta imagem de teste")
        return
    
    # Desenhar grid esperado
    for q in range(1, 27):
        y_expected = (q - 1) * line_height
        cv2.line(block_color, (0, y_expected), (BLOCK_WIDTH, y_expected), (0, 255, 0), 1)
        if q % 5 == 1:
            cv2.putText(block_color, f"Q{q}", (5, y_expected + 15), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)
    
    # Desenhar bolhas detectadas
    for x, y, r in bolhas:
        cv2.circle(block_color, (x, y), r, (0, 0, 255), 2)
        cv2.circle(block_color, (x, y), 2, (0, 0, 255), -1)
    
    # Salvar resultado
    output_path = Path("debug_corrections/visual_bolhas_detectadas.jpg")
    cv2.imwrite(str(output_path), block_color)
    print(f"\nImagem salva: {output_path}")
    
    # Agrupar bolhas por linha
    bolhas_sorted = sorted(bolhas, key=lambda b: b[1])
    grupos = {}
    grupo_num = 0
    y_ref = None
    
    for x, y, r in bolhas_sorted:
        if y_ref is None or abs(y - y_ref) > LINE_Y_THRESHOLD:
            grupo_num += 1
            y_ref = y
            grupos[grupo_num] = []
        grupos[grupo_num].append((x, y, r))
    
    print(f"\nGrupos de bolhas encontrados: {len(grupos)}")
    print(f"Esperado: 26")
    
    print(f"\nComparacao Detectado vs Esperado:")
    print(f"{'Q':<3} {'Det Y':<8} {'Exp Y':<8} {'Diff':<8} {'Bolhas':<8}")
    print("-" * 40)
    
    for q, grupo_num in enumerate(sorted(grupos.keys()), 1):
        bolhas_grupo = grupos[grupo_num]
        y_det = np.mean([y for x, y, r in bolhas_grupo])
        y_exp = (q - 1) * line_height
        diff = y_det - y_exp
        n_bolhas = len(bolhas_grupo)
        
        if q <= 5 or q >= 24:
            print(f"{q:<3} {y_det:<8.0f} {y_exp:<8.0f} {diff:<+8.1f} {n_bolhas:<8}")
        elif q == 6:
            print("...")
    
    print(f"\nDiagnostico:")
    if len(grupos) >= 24 and len(grupos) <= 28:
        print("OK: Numero de grupos esta correto")
    else:
        print(f"AVISO: Apenas {len(grupos)} grupos detectados")

if __name__ == "__main__":
    main()
