#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script final para diagnostico: Compara posicoes esperadas vs detectadas
"""

import cv2
import numpy as np
from pathlib import Path
from glob import glob
import json

# Constantes
A4_WIDTH_PX = 827
A4_HEIGHT_PX = 1169
BLOCK_HEIGHT_PX = 473  # Altura padrao do bloco
START_Y = 15
LINE_HEIGHT = 18  # Valor novo em JSON

def carregar_coordenadas(block_num):
    """Carrega coordenadas de ajuste do JSON"""
    json_file = Path(f"app/services/cartao_resposta/block_{block_num:02d}_coordinates_adjustment.json")
    if not json_file.exists():
        print(f"Arquivo nao existe: {json_file}")
        return None
    
    with open(json_file, 'r') as f:
        config = json.load(f)
    
    return config


def calcular_posicoes_esperadas(block_height=BLOCK_HEIGHT_PX):
    """Calcula as posicoes Y esperadas para cada questao"""
    
    config = carregar_coordenadas(1)  # Usar block 1 como referencia
    if not config:
        return None
    
    line_height = config.get('line_height', LINE_HEIGHT)
    start_y = config.get('start_y', START_Y)
    
    print(f"\nConfiguracao do JSON:")
    print(f"  line_height: {line_height} px")
    print(f"  start_y: {start_y} px")
    print(f"  block_height: {block_height} px")
    
    # Calcular posicoes para 26 questoes
    print(f"\nPosicoes esperadas (Y coordinate):")
    print(f"{'Q':<3} {'Expected':<10} {'% from start':<15} {'Cumulative pix':<15}")
    print("-" * 50)
    
    posicoes = {}
    for q in range(1, 27):
        y_pos = start_y + (q - 1) * line_height
        percent_used = (y_pos / block_height) * 100
        posicoes[q] = y_pos
        
        if q in [1, 5, 10, 15, 20, 25, 26]:
            print(f"{q:<3} {y_pos:<10.0f} {percent_used:<15.1f}% {y_pos:<15.0f}")
    
    final_y = start_y + (26 - 1) * line_height
    print(f"\nQ26 final Y: {final_y} px")
    print(f"Block height: {block_height} px")
    print(f"Space after Q26: {block_height - final_y} px")
    
    if final_y > block_height:
        print(f"AVISO: Q26 ultrapassa limite do bloco!")
        print(f"  Excesso: {final_y - block_height} px")
    
    return posicoes


def verificar_json():
    """Verifica conteudo dos JSONs"""
    
    print("\n" + "="*70)
    print("VERIFICACAO DE ARQUIVOS JSON DE CONFIGURACAO")
    print("="*70)
    
    for block_num in range(1, 5):
        config = carregar_coordenadas(block_num)
        if config:
            print(f"\nBlock {block_num}:")
            print(f"  line_height: {config.get('line_height')}")
            print(f"  start_x: {config.get('start_x')}")
            print(f"  start_y: {config.get('start_y')}")
            print(f"  bubble_size: {config.get('bubble_size')}")
            print(f"  bubble_gap: {config.get('bubble_gap')}")


def main():
    print("\n" + "="*70)
    print("DIAGNOSTICO FINAL: GRID E POSICOES ESPERADAS")
    print("="*70)
    
    verificar_json()
    posicoes = calcular_posicoes_esperadas()
    
    if posicoes:
        print(f"\nCONCLUSAO:")
        print(f"✓ Grid deve começar em Y={START_Y}")
        print(f"✓ Cada questão deve estar 18 px abaixo da anterior")
        print(f"✓ Questão 26 deve estar em Y={START_Y + 25*18} = {START_Y + 25*18} px")
        print(f"✓ Se isso nao está acontecendo, o problema é:")
        print(f"  1. Na deteccao de bolhas (HoughCircles)")
        print(f"  2. No agrupamento por linha")
        print(f"  3. Ou em como as posicoes sao calculadas")


if __name__ == "__main__":
    main()
