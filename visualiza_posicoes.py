#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para visualizar e medir: posicoes detectadas vs esperadas
"""

import cv2
import numpy as np
from pathlib import Path
import json

# Constantes
BLOCK_WIDTH = 142
BLOCK_HEIGHT = 473
LINE_Y_THRESHOLD = 8  # px
BUBBLE_SIZE_MIN = 20
BUBBLE_SIZE_MAX = 50

def carregar_config():
    """Carrega config do JSON"""
    json_path = Path("app/services/cartao_resposta/block_01_coordinates_adjustment.json")
    with open(json_path) as f:
        return json.load(f)

def detectar_bolhas(img_block):
    """Detecta bolhas usando HoughCircles"""
    # Aplicar blur
    img_blur = cv2.GaussianBlur(img_block, (5, 5), 0)
    
    # HoughCircles (como faz o codigo real)
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


def agrupar_por_linha(bolhas, threshold=LINE_Y_THRESHOLD):
    """Agrupa bolhas por coordenada Y"""
    if not bolhas:
        return {}
    
    # Ordenar por Y
    bolhas_sorted = sorted(bolhas, key=lambda b: b[1])
    
    grupos = {}
    grupo_atual = None
    y_ref = None
    
    for x, y, r in bolhas_sorted:
        if y_ref is None or abs(y - y_ref) > threshold:
            # Novo grupo
            grupo_atual = (x + y) / 2  # Usar media como ID
            y_ref = y
            grupos[grupo_atual] = []
        
        grupos[grupo_atual].append((x, y, r))
    
    return grupos


def main():
    print("\n" + "="*70)
    print("ANALISE: Posicoes Detectadas vs Esperadas")
    print("="*70)
    
    config = carregar_config()
    
    # Carregar imagem normalizada
    norm_img_path = Path("debug_corrections") / "20260121_095600_412_01_a4_normalized.jpg"
    if not norm_img_path.exists():
        print(f"Imagem nao encontrada: {norm_img_path}")
        return
    
    img = cv2.imread(str(norm_img_path), 0)
    print(f"\nImagem normalizada: {img.shape}")
    
    # Extrair bloco 01 (teoricamente em x=32-174, y=15-488)
    start_x = config.get('start_x', 32)
    start_y = config.get('start_y', 15)
    
    print(f"\nExtraindo bloco 01:")
    print(f"  X: {start_x} a {start_x + BLOCK_WIDTH}")
    print(f"  Y: {start_y} a {start_y + BLOCK_HEIGHT}")
    
    block_img = img[start_y:start_y+BLOCK_HEIGHT, start_x:start_x+BLOCK_WIDTH]
    if block_img.shape[0] < BLOCK_HEIGHT or block_img.shape[1] < BLOCK_WIDTH:
        print(f"  AVISO: Bloco incompleto! Tamanho obtido: {block_img.shape}")
    else:
        print(f"  OK: Tamanho {block_img.shape}")
    
    # Detectar bolhas
    print(f"\nDetectando bolhas...")
    bolhas = detectar_bolhas(block_img)
    print(f"  Bolhas detectadas: {len(bolhas)}")
    
    if not bolhas:
        print("  ERRO: Nenhuma bolha detectada!")
        return
    
    # Agrupar por linha
    print(f"\nAgrupando por linha (threshold={LINE_Y_THRESHOLD}px)...")
    grupos = agrupar_por_linha(bolhas, LINE_Y_THRESHOLD)
    
    print(f"  Grupos encontrados: {len(grupos)}")
    print(f"  Esperado: 26 questoes")
    
    # Calcular posicoes esperadas
    line_height = config.get('line_height', 18)
    
    print(f"\nComparacao Esperado vs Detectado:")
    print(f"{'Q':<3} {'Expected Y':<12} {'Detected Y':<12} {'Diff':<10} {'Status':<10}")
    print("-" * 60)
    
    linha_ids_sorted = sorted(grupos.keys())
    
    for q in range(1, 27):
        expected_y = start_y + (q - 1) * line_height - start_y  # Relativo ao bloco
        
        if q - 1 < len(linha_ids_sorted):
            grupo_bolhas = grupos[linha_ids_sorted[q - 1]]
            # Calcular media Y das bolhas do grupo (relativo ao bloco)
            detected_y = np.mean([y for x, y, r in grupo_bolhas])
        else:
            detected_y = None
        
        if detected_y is not None:
            diff = detected_y - expected_y
            percent = (diff / line_height * 100) if line_height > 0 else 0
            status = "OK" if abs(diff) < 2 else "DESVIO" if abs(diff) < 5 else "ERRO"
            
            print(f"{q:<3} {expected_y:<12.0f} {detected_y:<12.0f} {diff:<+10.1f} {status:<10}")
        else:
            print(f"{q:<3} {expected_y:<12.0f} {'N/A':<12} {'N/A':<10} {'FALTA':<10}")
    
    # Analise
    print(f"\n" + "="*70)
    print("DIAGNOSTICO:")
    print("="*70)
    
    if len(grupos) < 20:
        print(f"✗ Apenas {len(grupos)} questoes detectadas (esperado 26)")
        print("  → Problema: Bolhas nao estao sendo detectadas ou agrupadas corretamente")
    elif len(grupos) > 28:
        print(f"✗ {len(grupos)} questoes detectadas (esperado 26)")
        print("  → Problema: Bolhas estao sendo super-segmentadas")
    else:
        print(f"✓ {len(grupos)} questoes detectadas (esperado 26)")
        
        # Verificar desalinhamento progressivo
        print(f"\n✓ Se ha desvio progressivo crescente, o problema esta em:")
        print(f"  1. Deteccao imprecisa de bolhas (HoughCircles)")
        print(f"  2. Agrupamento por Y muito restritivo (threshold={LINE_Y_THRESHOLD})")
        print(f"  3. Calculo de offset do bloco incorrecto")


if __name__ == "__main__":
    main()
