#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para testar warpPerspective e capturar logs
"""

import sys
import os
import logging
from pathlib import Path

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)

backend_path = str(Path(__file__).parent)
sys.path.insert(0, backend_path)

import cv2
import glob

def main():
    print("="*70)
    print("TEST: warpPerspective logs")
    print("="*70)
    
    debug_dir = Path(backend_path) / 'debug_corrections'
    
    # Procurar por imagens originais
    debug_images = sorted(glob.glob(str(debug_dir / '*_original.jpg')))
    
    if not debug_images:
        debug_images = sorted(glob.glob(str(debug_dir / '*.jpg')))[:1]
        if not debug_images:
            print("ERROR: No images found")
            return
    
    print(f"Found {len(debug_images)} images\n")
    
    try:
        from app.services.cartao_resposta import correction_n
        print("SUCCESS: Imported correction_n\n")
    except Exception as e:
        print(f"ERROR importing: {e}")
        return
    
    # Testar com primeira imagem
    img_path = debug_images[0]
    print(f"Testing: {Path(img_path).name}")
    print("-"*70)
    
    img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        print("ERROR reading image")
        return
    
    print(f"Image shape: {img.shape}")
    print()
    
    try:
        corretor = correction_n.CartaoRespostaCorretor()
        print("Created CartaoRespostaCorretor instance\n")
        
        # Chamar função normalizacao 
        print("Calling normalizar_para_a4()...")
        print("-"*70)
        result = corretor.normalizar_para_a4(img)
        print("-"*70)
        
        if result is not None:
            print(f"SUCCESS: Shape = {result.shape}")
        else:
            print("WARNING: Function returned None")
            
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
