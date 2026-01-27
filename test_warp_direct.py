#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script de teste direto da função de correção, capturando logs de debug
"""

import sys
import os
from pathlib import Path

# Adicionar diretório da app ao path
sys.path.insert(0, str(Path(__file__).parent / 'app'))

# Importar apenas o que é necessário
import cv2
import numpy as np
from PIL import Image
import glob

def test_correction_with_debug_logs():
    """Testa função de correção capturando logs"""
    
    print("""
╔════════════════════════════════════════════════════════════════════╗
║  🔍 TESTANDO WARPERSPECTIVE COM LOGS DE DEBUG                      ║
╚════════════════════════════════════════════════════════════════════╝
    """)
    
    # Encontrar imagens de debug
    debug_images = glob.glob('debug_corrections/debug_*.png')
    
    if not debug_images:
        print("❌ Nenhuma imagem de debug encontrada em debug_corrections/")
        return
    
    print(f"✅ Encontradas {len(debug_images)} imagens de debug\n")
    
    # Importar a função de correção
    try:
        from services.cartao_resposta.correction_n import normalizar_para_a4
        print("✅ Importada função normalizar_para_a4\n")
    except ImportError as e:
        print(f"❌ Erro importando correction_n: {e}")
        return
    
    # Processar primeiras 3 imagens para debug
    for img_path in debug_images[:3]:
        print(f"\n{'='*70}")
        print(f"📄 Processando: {os.path.basename(img_path)}")
        print(f"{'='*70}")
        
        img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            print(f"❌ Erro lendo imagem")
            continue
        
        print(f"Dimensões originais: {img.shape}")
        
        # Chamar função com debug
        try:
            # A função vai logar informações de debug
            result = normalizar_para_a4(img)
            if result is not None:
                norm_img = result
                print(f"✅ Normalização bem-sucedida")
                print(f"Dimensões normalizadas: {norm_img.shape}")
            else:
                print(f"⚠️  Função retornou None")
        except Exception as e:
            print(f"❌ Erro: {str(e)}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    test_correction_with_debug_logs()
