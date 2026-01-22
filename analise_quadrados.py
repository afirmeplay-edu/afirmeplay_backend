#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para testar a deteccao real de quadrados na imagem
e capturar logs de DEBUG do warpPerspective
"""

import sys
import os
from pathlib import Path

# Ativar venv
sys.path.insert(0, str(Path(__file__).parent))

import cv2
import numpy as np
import json
import logging
from glob import glob

# Configurar logging para capturar DEBUG
logging.basicConfig(
    level=logging.DEBUG,
    format='%(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constantes
A4_WIDTH_CM = 21.0
A4_HEIGHT_CM = 29.7
A4_WIDTH_PX = 827
A4_HEIGHT_PX = 1169
SQUARE_SIZE_PIXELS = 20  # Tamanho esperado dos quadrados

def detectar_quadrados_simples(img_gray):
    """
    Deteccao simplificada de quadrados usando deteccao de bordas
    """
    
    # Threshold
    _, thresh = cv2.threshold(img_gray, 127, 255, cv2.THRESH_BINARY)
    
    # Encontrar contornos
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    squares_found = []
    
    for contour in contours:
        # Approximar contorno
        epsilon = 0.02 * cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, epsilon, True)
        
        # Quadrados tem 4 vértices
        if len(approx) == 4:
            area = cv2.contourArea(contour)
            # Quadrados esperados tem area entre 200 e 600 pixels
            if 200 < area < 600:
                # Calcular centro
                M = cv2.moments(contour)
                if M["m00"] != 0:
                    cx = int(M["m10"] / M["m00"])
                    cy = int(M["m01"] / M["m00"])
                    squares_found.append({
                        'center': np.array([cx, cy]),
                        'area': area,
                        'contour': approx
                    })
    
    return squares_found


def identificar_cantos(squares):
    """
    Identifica TL, TR, BR, BL a partir dos quadrados encontrados
    """
    if len(squares) < 4:
        logger.warning(f"Apenas {len(squares)} quadrados encontrados (esperado 4)")
        return None
    
    # Encontrar os 4 cantos usando k-means
    centers = np.array([s['center'] for s in squares])
    
    # Encontrar quadrante de cada ponto
    h_max, w_max = np.max(centers, axis=0)
    h_min, w_min = np.min(centers, axis=0)
    h_mid = (h_min + h_max) / 2
    w_mid = (w_min + w_max) / 2
    
    tl = br = tr = bl = None
    
    for i, square in enumerate(squares):
        cx, cy = square['center']
        
        # TL: canto superior esquerdo
        if cx < w_mid and cy < h_mid:
            if tl is None or (abs(cx - w_min) + abs(cy - h_min)) < (abs(tl['center'][0] - w_min) + abs(tl['center'][1] - h_min)):
                tl = square
        
        # TR: canto superior direito
        elif cx > w_mid and cy < h_mid:
            if tr is None or (abs(cx - w_max) + abs(cy - h_min)) < (abs(tr['center'][0] - w_max) + abs(tr['center'][1] - h_min)):
                tr = square
        
        # BR: canto inferior direito
        elif cx > w_mid and cy > h_mid:
            if br is None or (abs(cx - w_max) + abs(cy - h_max)) < (abs(br['center'][0] - w_max) + abs(br['center'][1] - h_max)):
                br = square
        
        # BL: canto inferior esquerdo
        else:
            if bl is None or (abs(cx - w_min) + abs(cy - h_max)) < (abs(bl['center'][0] - w_min) + abs(bl['center'][1] - h_max)):
                bl = square
    
    if all([tl, tr, br, bl]):
        return {
            'TL': tl['center'],
            'TR': tr['center'],
            'BR': br['center'],
            'BL': bl['center']
        }
    
    return None


def analisar_imagem(img_path):
    """
    Analisa uma imagem capturando dados de warpPerspective
    """
    
    print(f"\n{'='*70}")
    print(f"ANALISE: {Path(img_path).name}")
    print(f"{'='*70}")
    
    img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        logger.error("Nao consegui ler a imagem")
        return
    
    logger.info(f"Dimensoes originais: {img.shape}")
    
    # Detectar quadrados
    squares = detectar_quadrados_simples(img)
    logger.info(f"Quadrados detectados: {len(squares)}")
    
    # Identificar cantos
    cantos = identificar_cantos(squares)
    
    if cantos is None:
        logger.error("Nao consegui identificar os 4 cantos")
        return
    
    logger.info(f"\nCantos detectados:")
    logger.info(f"  TL: {cantos['TL']}")
    logger.info(f"  TR: {cantos['TR']}")
    logger.info(f"  BR: {cantos['BR']}")
    logger.info(f"  BL: {cantos['BL']}")
    
    # Criar pontos para transformacao
    src_points = np.array([
        cantos['TL'],
        cantos['TR'],
        cantos['BR'],
        cantos['BL']
    ], dtype="float32")
    
    dst_points = np.array([
        [0, 0],
        [A4_WIDTH_PX - 1, 0],
        [A4_WIDTH_PX - 1, A4_HEIGHT_PX - 1],
        [0, A4_HEIGHT_PX - 1]
    ], dtype="float32")
    
    # Matriz de transformacao
    M = cv2.getPerspectiveTransform(src_points, dst_points)
    
    logger.info(f"\nMatriz de transformacao:")
    logger.info(f"  {M}")
    
    # Aplicar transformacao
    img_normalized = cv2.warpPerspective(img, M, (A4_WIDTH_PX, A4_HEIGHT_PX))
    
    logger.info(f"\nDimensoes normalizadas: {img_normalized.shape}")
    
    # Calcular escalas
    width_px = np.linalg.norm(cantos['TR'] - cantos['TL'])
    height_px = np.linalg.norm(cantos['BL'] - cantos['TL'])
    
    px_per_cm_x = width_px / A4_WIDTH_CM
    px_per_cm_y = height_px / A4_HEIGHT_CM
    
    logger.info(f"\nEscala:")
    logger.info(f"  px_per_cm_x: {px_per_cm_x:.2f}")
    logger.info(f"  px_per_cm_y: {px_per_cm_y:.2f}")
    logger.info(f"  Proporcao (W/H): {width_px/height_px:.4f} (esperado 0.7071)")
    
    diff_percent = abs((px_per_cm_y / px_per_cm_x - 1) * 100)
    if diff_percent > 2.0:
        logger.warning(f"  AVISO: Escalas diferem em {diff_percent:.1f}%")
    
    # Retornar dados para analise
    return {
        'img_path': img_path,
        'cantos': cantos,
        'px_per_cm_x': px_per_cm_x,
        'px_per_cm_y': px_per_cm_y,
        'proporcao': width_px / height_px,
        'normalized': img_normalized
    }


def main():
    print("\n" + "="*70)
    print("ANALISE DE DETECCAO DE QUADRADOS E WARPERSPECTIVE")
    print("="*70)
    
    debug_dir = Path('debug_corrections')
    images = sorted(glob(str(debug_dir / '*_original.jpg')))
    
    if not images:
        logger.error("Nenhuma imagem encontrada")
        return
    
    logger.info(f"Encontradas {len(images)} imagens")
    
    # Analisar primeira imagem
    resultado = analisar_imagem(images[0])
    
    if resultado:
        # Salvar imagem normalizada
        output_path = debug_dir / 'debug_normalized_test.jpg'
        cv2.imwrite(str(output_path), resultado['normalized'])
        logger.info(f"\nImagem normalizada salva: {output_path}")


if __name__ == "__main__":
    main()
