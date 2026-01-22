#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para medir distorção progressiva em diferentes regiões da imagem
Compara espaçamento no topo, meio e fundo
"""

import cv2
import numpy as np
from pathlib import Path

def measure_spacing_by_region(image_path, block_num=1):
    """Mede espaçamento vertical em diferentes regiões"""
    
    if not Path(image_path).exists():
        print(f"❌ Arquivo não encontrado: {image_path}")
        return
    
    img = cv2.imread(image_path)
    if img is None:
        print(f"❌ Não conseguiu carregar: {image_path}")
        return
    
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    
    print(f"\n{'='*70}")
    print(f"📐 Análise de Distorção por Região")
    print(f"{'='*70}")
    print(f"Arquivo: {Path(image_path).name}")
    print(f"Dimensões: {w}x{h}px")
    
    # Detectar bolhas
    circles = cv2.HoughCircles(
        gray,
        cv2.HOUGH_GRADIENT,
        dp=1,
        minDist=15,
        param1=50,
        param2=30,
        minRadius=4,
        maxRadius=12
    )
    
    if circles is None or len(circles[0]) == 0:
        print("❌ Nenhuma bolha detectada")
        return
    
    circles = circles[0].astype(int)
    print(f"✅ {len(circles)} bolhas detectadas")
    
    # Agrupar por Y (questões)
    circles_by_y = {}
    for x, y, r in circles:
        y_rounded = round(y / 5) * 5  # Arredondar para 5px
        if y_rounded not in circles_by_y:
            circles_by_y[y_rounded] = []
        circles_by_y[y_rounded].append(x)
    
    y_positions = sorted(circles_by_y.keys())
    
    # Dividir em 3 regiões: topo, meio, fundo
    total_y = len(y_positions)
    third = total_y // 3
    
    regions = {
        'TOPO (Q1-Q9)': y_positions[:third],
        'MEIO (Q10-Q18)': y_positions[third:2*third],
        'FUNDO (Q19-Q26)': y_positions[2*third:]
    }
    
    print(f"\n📊 Espaçamento por Região:")
    print(f"{'Região':<20} │ Mín(px) │ Máx(px) │ Média(px) │ StdDev(px) │ Status")
    print(f"{'-'*20}─┼─────────┼─────────┼───────────┼────────────┼─────────")
    
    for region_name, y_list in regions.items():
        if len(y_list) < 2:
            continue
        
        # Calcular espaçamentos
        spacings = [y_list[i+1] - y_list[i] for i in range(len(y_list)-1)]
        
        min_sp = min(spacings)
        max_sp = max(spacings)
        mean_sp = np.mean(spacings)
        std_sp = np.std(spacings)
        
        # Detectar anomalia
        if std_sp > 3:
            status = "⚠️ ALTA VARIAÇÃO"
        elif abs(mean_sp - 18) > 2:
            status = "⚠️ FORA DO ESPERADO"
        else:
            status = "✓ OK"
        
        print(f"{region_name:<20} │ {min_sp:>6}  │ {max_sp:>6}  │ {mean_sp:>8.1f}  │ {std_sp:>9.1f}  │ {status}")
    
    # Análise de progressão
    print(f"\n📈 Análise de Progressão (mudança de espaçamento):")
    
    spacings_all = [y_positions[i+1] - y_positions[i] for i in range(len(y_positions)-1)]
    
    if len(spacings_all) > 5:
        # Primeira metade vs segunda metade
        mid = len(spacings_all) // 2
        mean_top_half = np.mean(spacings_all[:mid])
        mean_bottom_half = np.mean(spacings_all[mid:])
        
        diff_percent = ((mean_bottom_half - mean_top_half) / mean_top_half * 100) if mean_top_half > 0 else 0
        
        print(f"  Espaçamento (primeira metade): {mean_top_half:.1f}px")
        print(f"  Espaçamento (segunda metade): {mean_bottom_half:.1f}px")
        print(f"  Mudança: {diff_percent:+.1f}%")
        
        if abs(diff_percent) > 10:
            print(f"  ⚠️  DISTORÇÃO PROGRESSIVA DETECTADA!")
            if diff_percent > 0:
                print(f"     → Espaçamento aumenta (fundo comprimido)")
            else:
                print(f"     → Espaçamento diminui (topo comprimido)")


def main():
    print("""
🔬 ANALISADOR DE DISTORÇÃO PROGRESSIVA
======================================

Este script verifica se há distorção não-linear
(espaçamento diferente em topo, meio e fundo)
    """)
    
    # Procurar por imagens de debug
    debug_dir = Path("debug_corrections")
    
    if not debug_dir.exists():
        print(f"❌ Diretório não encontrado: {debug_dir}")
        print("\nExecute primeiro: python run.py")
        return
    
    # Encontrar imagens de blocos
    block_files = sorted(debug_dir.glob("*_block_*_real*.jpg"))
    
    if not block_files:
        print(f"❌ Nenhuma imagem de bloco encontrada em {debug_dir}")
        return
    
    print(f"\n✅ Encontradas {len(block_files)} imagens de blocos\n")
    
    for block_file in block_files:
        try:
            measure_spacing_by_region(str(block_file))
        except Exception as e:
            print(f"❌ Erro ao processar {block_file.name}: {str(e)}")
    
    print(f"\n{'='*70}")
    print("💡 INTERPRETAÇÃO:")
    print(f"{'='*70}")
    print("""
✅ OK:
  - Espaçamento consistente em todas as regiões (~18px)
  - Desvio padrão < 2px
  - Mudança < 5% entre primeira e segunda metade

⚠️  PROBLEMA:
  - Espaçamento varia > 20% entre regiões
  - Desvio padrão > 3px
  - Mudança > 10% entre primeira e segunda metade
  
  → Indica distorção de perspectiva não-linear

🔧 SOLUÇÃO:
  - Verificar qualidade de detecção de quadrados
  - Considerar usar cv2.undistort() para câmera com distorção
  - Ajustar pontos de referência (TL, TR, BR, BL)
    """)


if __name__ == "__main__":
    main()
