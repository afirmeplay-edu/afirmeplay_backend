#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para testar diretamente a função correction_n e capturar logs de debug
sem precisar de Flask
"""

import sys
import os
import logging
from pathlib import Path

# Configurar logging ANTES de importar correction_n
logging.basicConfig(
    level=logging.DEBUG,
    format='%(levelname)s - %(message)s'
)

# Adicionar diretório ao path
backend_path = str(Path(__file__).parent)
sys.path.insert(0, backend_path)

import cv2
import numpy as np
import glob

def main():
    print("""
╔════════════════════════════════════════════════════════════════════╗
║  🔍 TESTANDO WARPERSPECTIVE - CAPTURANDO LOGS DE DEBUG             ║
╚════════════════════════════════════════════════════════════════════╝
    """)
    
    # Encontrar imagens de debug
    debug_dir = Path(backend_path) / 'debug_corrections'
    if not debug_dir.exists():
        print(f"❌ Diretório não encontrado: {debug_dir}")
        return
    
    # Procurar por imagens que mostram "normalized" ou "original"
    debug_images = sorted(glob.glob(str(debug_dir / '*_original.jpg')))
    
    if not debug_images:
        print(f"❌ Nenhuma imagem _original.jpg encontrada em {debug_dir}")
        # Tentar outras extensões
        debug_images = sorted(glob.glob(str(debug_dir / '*.jpg')))[:5]
        if not debug_images:
            return
    
    print(f"✅ Encontradas {len(debug_images)} imagens de debug\n")
    
    # Tentar importar correction_n
    try:
        from app.services.cartao_resposta import correction_n
        print("✅ Importada correction_n com sucesso\n")
    except Exception as e:
        print(f"❌ Erro importando: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Processar algumas imagens
    for i, img_path in enumerate(debug_images[:2]):
        print("\n" + "="*70)
        print(f"📄 Imagem {i+1}: {Path(img_path).name}")
        print("="*70)
        
        img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            print(f"❌ Erro lendo imagem")
            continue
        
        print(f"Dimensões originais: {img.shape}")
        
        try:
            # Criar instância do corretor
            corretor = correction_n.CartaoRespostaCorretor()
            
            # Chamar função de normalização
            result = corretor.normalizar_para_a4(img)
            
            if result is not None:
                print(f"✅ Normalização bem-sucedida")
                print(f"Dimensões normalizadas: {result.shape}")
            else:
                print(f"⚠️  Normalização retornou None")
                
        except Exception as e:
            print(f"❌ Erro: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()
