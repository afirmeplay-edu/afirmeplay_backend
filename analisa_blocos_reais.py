#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para analisar bolhas reais em um bloco individual
"""

import cv2
import numpy as np
from pathlib import Path
import json

# Constantes
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
    grupo_num = 0
    y_ref = None
    
    for x, y, r in bolhas_sorted:
        if y_ref is None or abs(y - y_ref) > threshold:
            # Novo grupo
            grupo_num += 1
            y_ref = y
            grupos[grupo_num] = []
        
        grupos[grupo_num].append((x, y, r))
    
    return grupos


def main():
    print("\n" + "="*70)
    print("ANALISE: Bolhas Reais em Blocos")
    print("="*70)
    
    config = carregar_config()
    line_height = config.get('line_height', 18)
    start_x_config = config.get('start_x', 32)
    
    # Testar com imagens de blocos
    block_images = [
        "20260121_095600_412_04_block_01_real_only.jpg",
        "20260121_095600_412_04_block_02_real_only.jpg",
        "20260121_095600_412_04_block_03_real_only.jpg",
        "20260121_095600_412_04_block_04_real_only.jpg",
    ]
    
    for block_file in block_images:
        block_path = Path("debug_corrections") / block_file
        if not block_path.exists():
            continue
        
        print(f"\n{'='*70}")
        print(f"Analisando: {block_file}")
        print(f"{'='*70}")
        
        img = cv2.imread(str(block_path), 0)
        print(f"Tamanho: {img.shape}")
        print(f"Min: {img.min()}, Max: {img.max()}, Mean: {img.mean():.1f}")
        
        # Detectar bolhas
        bolhas = detectar_bolhas(img)
        print(f"\nBolhas detectadas: {len(bolhas)}")
        
        if not bolhas:
            print("  (Nenhuma bolha ou imagem muito clara)")
            continue
        
        # Agrupar por linha
        grupos = agrupar_por_linha(bolhas, LINE_Y_THRESHOLD)
        
        print(f"Linhas (grupos) encontrados: {len(grupos)}")
        print(f"Esperado: 26 questoes")
        
        if len(grupos) == 0:
            continue
        
        # Mostrar posicoes
        print(f"\n{'Q':<3} {'Pos Y':<10} {'Bolhas':<10} {'Expected Y':<12} {'Diff':<10}")
        print("-" * 60)
        
        for q, grupo_num in enumerate(sorted(grupos.keys()), 1):
            grupo_bolhas = grupos[grupo_num]
            
            # Media Y das bolhas
            y_detected = np.mean([y for x, y, r in grupo_bolhas])
            
            # Esperado
            expected_y = (q - 1) * line_height
            
            # Diferenca
            diff = y_detected - expected_y
            
            num_bolhas = len(grupo_bolhas)
            
            if q <= 5 or q >= 24:  # Mostrar primeiras e ultimas
                print(f"{q:<3} {y_detected:<10.0f} {num_bolhas:<10} {expected_y:<12.0f} {diff:<+10.1f}")
            elif q == 6:
                print(f"... {'':.<58}")
        
        # Analise
        print(f"\n" + "="*70)
        if len(grupos) < 20:
            print(f"✗ PROBLEMA: Apenas {len(grupos)} questoes (esperado 26)")
        elif len(grupos) > 28:
            print(f"✗ PROBLEMA: {len(grupos)} questoes (esperado 26)")
        else:
            print(f"✓ {len(grupos)} questoes detectadas")
            
            # Calcular progresso de desvio
            desvios = []
            for q, grupo_num in enumerate(sorted(grupos.keys()), 1):
                grupo_bolhas = grupos[grupo_num]
                y_detected = np.mean([y for x, y, r in grupo_bolhas])
                expected_y = (q - 1) * line_height
                diff = abs(y_detected - expected_y)
                desvios.append(diff)
            
            desvio_inicial = desvios[0] if desvios else 0
            desvio_final = desvios[-1] if desvios else 0
            desvio_max = max(desvios) if desvios else 0
            
            print(f"\nDesvios:")
            print(f"  Inicial (Q1): {desvio_inicial:.1f}px")
            print(f"  Final (Q26): {desvio_final:.1f}px")
            print(f"  Maximo: {desvio_max:.1f}px")
            
            if desvio_final > desvio_inicial * 1.5:
                print(f"  ⚠ DESALINHAMENTO PROGRESSIVO detectado!")
                print(f"    Progresso: {((desvio_final / desvio_inicial - 1) * 100):+.1f}%")


if __name__ == "__main__":
    main()
