#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para otimizar parametros de HoughCircles
"""

import cv2
import numpy as np
from pathlib import Path
import json

def carregar_config():
    json_path = Path("app/services/cartao_resposta/block_01_coordinates_adjustment.json")
    with open(json_path) as f:
        return json.load(f)

def criar_imagem_teste_v2():
    """Cria imagem de teste com bolhas sinteticas"""
    
    config = carregar_config()
    BLOCK_WIDTH = 142
    BLOCK_HEIGHT = 473
    line_height = config.get('line_height', 18)
    bubble_size = config.get('bubble_size', 15)
    
    # Criar imagem branca
    img = np.ones((BLOCK_HEIGHT, BLOCK_WIDTH), dtype=np.uint8) * 240
    
    # Desenhar bolhas em posicoes esperadas (26 questoes)
    bolhas_esperadas = 0
    
    for q in range(1, 27):
        y = (q - 1) * line_height + 10
        x_positions = [25, 50, 75, 100]
        
        for x in x_positions:
            cv2.circle(img, (x, y), bubble_size // 2, 0, -1)
            bolhas_esperadas += 1
    
    return img, bolhas_esperadas

def testar_parametros(img, param2_values, dp_values, minDist_values):
    """Testa diferentes combinacoes de parametros"""
    
    print(f"{'dp':<6} {'minDist':<8} {'param2':<8} {'Detectadas':<12} {'Taxa %':<10}")
    print("-" * 50)
    
    bolhas_esperadas = 104  # 26 * 4
    melhores_params = None
    melhor_taxa = 0
    
    img_blur = cv2.GaussianBlur(img, (5, 5), 0)
    
    for dp in dp_values:
        for minDist in minDist_values:
            for param2 in param2_values:
                try:
                    circles = cv2.HoughCircles(
                        img_blur,
                        cv2.HOUGH_GRADIENT,
                        dp=dp,
                        minDist=minDist,
                        param1=50,
                        param2=param2,
                        minRadius=5,
                        maxRadius=10
                    )
                    
                    n_detectadas = 0 if circles is None else len(circles[0])
                    taxa = n_detectadas / bolhas_esperadas * 100
                    
                    print(f"{dp:<6.1f} {minDist:<8} {param2:<8} {n_detectadas:<12} {taxa:<10.1f}%")
                    
                    if taxa > melhor_taxa:
                        melhor_taxa = taxa
                        melhores_params = (dp, minDist, param2, n_detectadas)
                        
                except Exception as e:
                    print(f"{dp:<6.1f} {minDist:<8} {param2:<8} ERROR: {str(e)[:20]}")
    
    return melhores_params, melhor_taxa

def main():
    print("\nOtimizacao de Parametros - HoughCircles")
    print("="*70)
    
    # Criar imagem de teste
    img, bolhas_esperadas = criar_imagem_teste_v2()
    print(f"\nBolhas esperadas: {bolhas_esperadas}")
    print(f"Imagem: {img.shape}")
    
    # Testar diferentes parametros
    param2_values = [15, 20, 25, 30, 35, 40]
    dp_values = [1.0, 1.1, 1.2]
    minDist_values = [10, 15, 20]
    
    print(f"\nTestando combinacoes de parametros:")
    print("(Parametros atuais: dp=1.2, minDist=15, param2=30)\n")
    
    melhores_params, melhor_taxa = testar_parametros(img, param2_values, dp_values, minDist_values)
    
    print("\n" + "="*70)
    if melhores_params:
        dp, minDist, param2, n_detectadas = melhores_params
        print(f"MELHORES PARAMETROS:")
        print(f"  dp: {dp}")
        print(f"  minDist: {minDist}")
        print(f"  param2: {param2}")
        print(f"  Bolhas detectadas: {n_detectadas} / {bolhas_esperadas}")
        print(f"  Taxa de deteccao: {melhor_taxa:.1f}%")
        
        if melhor_taxa >= 95:
            print(f"\nRECOMENDACAO: Estes parametros sao excelentes!")
        elif melhor_taxa >= 85:
            print(f"\nRECOMENDACAO: Estes parametros sao bons, mas pode melhorar.")
        else:
            print(f"\nRECOMENDACAO: Considere ajustar ainda mais.")
    
    print(f"\nParametros ATUAIS no codigo: dp=1.2, minDist=15, param2=30")

if __name__ == "__main__":
    main()
