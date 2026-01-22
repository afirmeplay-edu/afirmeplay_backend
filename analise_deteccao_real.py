#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Analisa deteccao de quadrados usando exato algoritmo do correction_n.py
"""

import cv2
import numpy as np
from pathlib import Path
from glob import glob
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

A4_WIDTH_PX = 827
A4_HEIGHT_PX = 1169
A4_WIDTH_CM = 21.0
A4_HEIGHT_CM = 29.7


def detectar_quadrados_a4_real(img, img_path=""):
    """
    Replica exatamente a logica de deteccao de _detectar_quadrados_a4
    """
    
    # Converter para grayscale
    if len(img.shape) == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        gray = img.copy()
    
    img_height, img_width = gray.shape[:2]
    img_area = img_width * img_height
    
    logger.info(f"\nImage shape: {gray.shape}")
    logger.info(f"Image area: {img_area}")
    
    # Threshold
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    
    logger.info(f"Binary image - black pixels: {np.count_nonzero(binary)}")
    
    # Encontrar contornos
    contours, hierarchy = cv2.findContours(binary, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    
    logger.info(f"Contours found: {len(contours)}")
    
    # Filtros
    min_area = img_area * 0.0001
    max_area = img_area * 0.002
    margin_x = img_width * 0.1
    margin_y = img_height * 0.1
    
    logger.info(f"Area range: {min_area:.0f} - {max_area:.0f} px")
    logger.info(f"Margins: X={margin_x:.0f}, Y={margin_y:.0f}")
    
    squares = []
    
    for i, cnt in enumerate(contours):
        peri = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.04 * peri, True)
        
        # Deve ter 4 vértices
        if len(approx) != 4:
            continue
        
        area = cv2.contourArea(approx)
        
        # Filtrar por area
        if not (min_area < area < max_area):
            continue
        
        # Aspect ratio
        x, y, w, h = cv2.boundingRect(approx)
        aspect_ratio = w / float(h) if h > 0 else 0
        
        if not (0.9 < aspect_ratio < 1.1):
            continue
        
        # Centro
        M = cv2.moments(approx)
        if M["m00"] == 0:
            continue
        
        cx = int(M["m10"] / M["m00"])
        cy = int(M["m01"] / M["m00"])
        
        # Proximidade à borda
        is_near_edge = (
            cx < margin_x or
            cx > img_width - margin_x or
            cy < margin_y or
            cy > img_height - margin_y
        )
        
        if not is_near_edge:
            continue
        
        logger.info(f"  Quadrado {len(squares)+1}: center=({cx},{cy}), area={area:.0f}, aspect={aspect_ratio:.2f}")
        
        squares.append({
            'contour': approx,
            'center': (cx, cy),
            'area': area,
            'vertices': approx.reshape(-1, 2)
        })
    
    if len(squares) < 4:
        logger.warning(f"Apenas {len(squares)} quadrados detectados!")
        return None
    
    logger.info(f"SUCCESS: {len(squares)} quadrados detectados")
    
    # Classificar por canto
    corners = {"TL": [], "TR": [], "BR": [], "BL": []}
    
    for s in squares:
        cx, cy = s["center"]
        if cx < img_width / 2 and cy < img_height / 2:
            corners["TL"].append(s)
        elif cx >= img_width / 2 and cy < img_height / 2:
            corners["TR"].append(s)
        elif cx >= img_width / 2 and cy >= img_height / 2:
            corners["BR"].append(s)
        else:
            corners["BL"].append(s)
    
    # Verificar se todos têm quadrados
    for corner, items in corners.items():
        if not items:
            logger.warning(f"Missing quadrado no canto {corner}")
            return None
    
    # Extrair vértices corretos
    ordered_squares = {}
    for corner, items in corners.items():
        best_square = max(items, key=lambda x: x["area"])
        vertices = best_square["vertices"]
        
        if corner == "TL":
            distances = vertices[:, 0] + vertices[:, 1]
            corner_vertex = vertices[np.argmin(distances)]
        elif corner == "TR":
            scores = vertices[:, 0] - vertices[:, 1]
            corner_vertex = vertices[np.argmax(scores)]
        elif corner == "BR":
            distances = vertices[:, 0] + vertices[:, 1]
            corner_vertex = vertices[np.argmax(distances)]
        else:  # BL
            scores = vertices[:, 0] - vertices[:, 1]
            corner_vertex = vertices[np.argmin(scores)]
        
        ordered_squares[corner] = [float(corner_vertex[0]), float(corner_vertex[1])]
    
    logger.info(f"\nDetected corners:")
    logger.info(f"  TL: {ordered_squares['TL']}")
    logger.info(f"  TR: {ordered_squares['TR']}")
    logger.info(f"  BR: {ordered_squares['BR']}")
    logger.info(f"  BL: {ordered_squares['BL']}")
    
    return ordered_squares


def analisar_transformacao(squares):
    """
    Analisa a transformacao warpPerspective
    """
    
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
    
    logger.info(f"\nTransformation matrix:")
    M = cv2.getPerspectiveTransform(src_points, dst_points)
    logger.info(f"  {M}")
    
    # Calcular escalas
    width_px = np.linalg.norm(np.array(squares['TR']) - np.array(squares['TL']))
    height_px = np.linalg.norm(np.array(squares['BL']) - np.array(squares['TL']))
    
    px_per_cm_x = width_px / A4_WIDTH_CM
    px_per_cm_y = height_px / A4_HEIGHT_CM
    
    logger.info(f"\nScale analysis:")
    logger.info(f"  Width: {width_px:.2f} px")
    logger.info(f"  Height: {height_px:.2f} px")
    logger.info(f"  px_per_cm_x: {px_per_cm_x:.2f}")
    logger.info(f"  px_per_cm_y: {px_per_cm_y:.2f}")
    logger.info(f"  Proportion (W/H): {width_px/height_px:.4f} (expected 0.7071)")
    
    diff_percent = abs((px_per_cm_y / px_per_cm_x - 1) * 100)
    if diff_percent > 2.0:
        logger.warning(f"  SCALES DIFFER by {diff_percent:.1f}%")


def main():
    print("\n" + "="*70)
    print("ANALISE REAL DE DETECCAO DE QUADRADOS")
    print("="*70)
    
    debug_dir = Path('debug_corrections')
    images = sorted(glob(str(debug_dir / '*_original.jpg')))
    
    if not images:
        logger.error("No images found")
        return
    
    # Testar primeira imagem
    img_path = images[0]
    logger.info(f"\nProcessing: {Path(img_path).name}")
    
    img = cv2.imread(img_path)
    if img is None:
        logger.error("Could not read image")
        return
    
    squares = detectar_quadrados_a4_real(img, img_path)
    
    if squares:
        analisar_transformacao(squares)
    else:
        logger.error("Could not detect squares")


if __name__ == "__main__":
    main()
