#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Teste standalone do warpPerspective - extrai apenas a logica necessaria
"""

import cv2
import numpy as np
import glob
import logging
import json
from pathlib import Path

# Config logging
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)
logger = logging.getLogger(__name__)

# Constantes
A4_WIDTH_CM = 21.0
A4_HEIGHT_CM = 29.7
A4_WIDTH_PX = 827
A4_HEIGHT_PX = 1169

def test_warp_perspective():
    """Testa warpPerspective em imagens debug"""
    
    print("\n" + "="*70)
    print("TESTE: warpPerspective Analysis")
    print("="*70 + "\n")
    
    debug_dir = Path('debug_corrections')
    images = sorted(glob.glob(str(debug_dir / '*_original.jpg')))
    
    if not images:
        print("ERROR: No images found")
        return
    
    print(f"Found {len(images)} original images\n")
    
    # Testar apenas a primeira imagem
    img_path = images[0]
    print(f"Processing: {Path(img_path).name}")
    print("-"*70)
    
    img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        print("ERROR: Could not read image")
        return
    
    print(f"Image shape: {img.shape}")
    
    # Simular deteccao de quadrados (usando corners fixos para teste)
    h, w = img.shape
    
    # Quadrados detectados (estimativa baseada em scan típico)
    # Normalmente isso viria de _detectar_quadrados()
    squares = {
        'TL': np.array([50, 50]),
        'TR': np.array([w - 50, 50]),
        'BR': np.array([w - 50, h - 50]),
        'BL': np.array([50, h - 50])
    }
    
    print(f"\nEstimated squares (for test):")
    print(f"  TL: {squares['TL']}")
    print(f"  TR: {squares['TR']}")
    print(f"  BR: {squares['BR']}")
    print(f"  BL: {squares['BL']}")
    
    # Criar arrays de pontos para transformacao
    src_points = np.array([
        squares['TL'],
        squares['TR'],
        squares['BR'],
        squares['BL']
    ], dtype="float32")
    
    dst_points = np.array([
        [0, 0],
        [A4_WIDTH_PX - 1, 0],
        [A4_WIDTH_PX - 1, A4_HEIGHT_PX - 1],
        [0, A4_HEIGHT_PX - 1]
    ], dtype="float32")
    
    logger.info(f"\nDEBUG - Source points (detected):")
    logger.info(f"  TL (src): {src_points[0]}")
    logger.info(f"  TR (src): {src_points[1]}")
    logger.info(f"  BR (src): {src_points[2]}")
    logger.info(f"  BL (src): {src_points[3]}")
    
    logger.info(f"\nDEBUG - Destination points (A4 normalized):")
    logger.info(f"  TL (dst): {dst_points[0]}")
    logger.info(f"  TR (dst): {dst_points[1]}")
    logger.info(f"  BR (dst): {dst_points[2]}")
    logger.info(f"  BL (dst): {dst_points[3]}")
    
    # Calcular matriz
    M = cv2.getPerspectiveTransform(src_points, dst_points)
    
    logger.info(f"\nDEBUG - Transformation matrix:")
    logger.info(f"  {M}")
    
    # Aplicar transformacao
    img_normalized = cv2.warpPerspective(img, M, (A4_WIDTH_PX, A4_HEIGHT_PX))
    
    logger.info(f"\nDEBUG - Image dimensions:")
    logger.info(f"  Original: {img.shape}")
    logger.info(f"  Normalized: {img_normalized.shape}")
    
    # Calcular escala
    width_original_px = np.linalg.norm(np.array(squares['TR']) - np.array(squares['TL']))
    height_original_px = np.linalg.norm(np.array(squares['BL']) - np.array(squares['TL']))
    
    px_per_cm_x = width_original_px / A4_WIDTH_CM
    px_per_cm_y = height_original_px / A4_HEIGHT_CM
    
    logger.info(f"\nDEBUG - Scale:")
    logger.info(f"  px_per_cm_x: {px_per_cm_x:.2f}")
    logger.info(f"  px_per_cm_y: {px_per_cm_y:.2f}")
    logger.info(f"  Proportion (W/H): {width_original_px/height_original_px:.4f} (expected 0.7071 for A4)")
    
    if abs(px_per_cm_x - px_per_cm_y) > 0.5:
        diff_percent = ((px_per_cm_y / px_per_cm_x - 1) * 100)
        logger.info(f"  WARNING: Scales differ by {diff_percent:+.1f}%")

if __name__ == "__main__":
    test_warp_perspective()
