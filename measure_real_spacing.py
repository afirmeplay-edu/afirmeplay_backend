#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para medir espaçamento real das bolhas em uma imagem de bloco
Detecta automaticamente as bolhas e mede:
1. Posição real de cada bolha
2. Espaçamento vertical entre questões
3. Espaçamento horizontal entre alternativas
4. Compara com valores esperados
"""

import cv2
import numpy as np
import json
from pathlib import Path
from typing import List, Dict, Tuple

class BubbleSpacingAnalyzer:
    def __init__(self, block_image_path: str, block_num: int = 1):
        self.image_path = block_image_path
        self.block_num = block_num
        self.image = None
        self.bubbles = []
        
    def load_image(self) -> bool:
        """Carrega a imagem do bloco"""
        if not Path(self.image_path).exists():
            print(f"❌ Erro: Arquivo não encontrado: {self.image_path}")
            return False
        
        self.image = cv2.imread(self.image_path)
        if self.image is None:
            print(f"❌ Erro: Não foi possível carregar a imagem: {self.image_path}")
            return False
        
        print(f"✅ Imagem carregada: {self.image.shape}")
        return True
    
    def detect_bubbles(self) -> List[Dict]:
        """Detecta bolhas usando HoughCircles"""
        if self.image is None:
            return []
        
        gray = cv2.cvtColor(self.image, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        
        # Detectar círculos usando HoughCircles
        circles = cv2.HoughCircles(
            blurred,
            cv2.HOUGH_GRADIENT,
            dp=1,
            minDist=15,      # Distância mínima entre centros
            param1=50,       # Threshold para Canny
            param2=30,       # Threshold para acumulador
            minRadius=3,
            maxRadius=10
        )
        
        if circles is None:
            print("❌ Nenhuma bolha detectada")
            return []
        
        circles = np.uint16(np.around(circles))
        bubbles = []
        
        for (x, y, r) in circles[0, :]:
            bubbles.append({
                'x': int(x),
                'y': int(y),
                'radius': int(r),
                'area': np.pi * r * r
            })
        
        # Ordenar por Y (linha) e depois X (coluna)
        bubbles_sorted = sorted(bubbles, key=lambda b: (b['y'], b['x']))
        
        print(f"✅ {len(bubbles_sorted)} bolhas detectadas\n")
        
        for i, bubble in enumerate(bubbles_sorted):
            print(f"  Bolha {i+1:2d}: X={bubble['x']:3d}, Y={bubble['y']:3d}, R={bubble['radius']}px, Área={bubble['area']:.0f}px²")
        
        return bubbles_sorted
    
    def analyze_vertical_spacing(self):
        """Analisa espaçamento vertical entre questões"""
        print("\n" + "="*70)
        print("📊 ANÁLISE DE ESPAÇAMENTO VERTICAL")
        print("="*70)
        
        if not self.bubbles:
            print("❌ Nenhuma bolha para analisar")
            return
        
        # Agrupar bolhas por Y (questões)
        lines = {}
        for bubble in self.bubbles:
            y = bubble['y']
            # Agrupar com tolerância de ±2px
            found_line = False
            for existing_y in lines:
                if abs(y - existing_y) <= 2:
                    lines[existing_y].append(bubble)
                    found_line = True
                    break
            
            if not found_line:
                lines[y] = [bubble]
        
        # Ordenar linhas
        sorted_lines = sorted(lines.items())
        
        print(f"\n🔍 Encontradas {len(sorted_lines)} linhas (questões)")
        print(f"\nQ  │ Y (real) │ Y (esperado com 14px) │ Y (esperado com 18px) │ Diff │")
        print(f"───┼──────────┼──────────────────────┼──────────────────────┼──────┤")
        
        for q_num, (y_real, bubbles_in_line) in enumerate(sorted_lines, 1):
            y_expected_14 = 15 + (q_num - 1) * 14
            y_expected_18 = 15 + (q_num - 1) * 18
            
            # Qual se aproxima mais?
            diff_14 = abs(y_real - y_expected_14)
            diff_18 = abs(y_real - y_expected_18)
            
            closer = "14px" if diff_14 < diff_18 else "18px"
            min_diff = min(diff_14, diff_18)
            
            print(f"{q_num:2d} │ {y_real:7d} │ {y_expected_14:20d} │ {y_expected_18:20d} │ {min_diff:4d} ({closer})")
            
            if q_num <= 2 or q_num in [13, 14, 25, 26]:
                # Mostrar alternativas desta questão
                print(f"     └─ {len(bubbles_in_line)} bolhas (alternativas):")
                for bubble in sorted(bubbles_in_line, key=lambda b: b['x']):
                    print(f"        X={bubble['x']:3d}, Raio={bubble['radius']}", end="")
                    if len(bubbles_in_line) > 1:
                        print(f" [{chr(65 + bubbles_in_line.index(bubble))}]", end="")
                    print()
        
        # Calcular espaçamento real
        print(f"\n📏 Espaçamento vertical real entre questões:")
        spacings = []
        for i in range(1, len(sorted_lines)):
            y1 = sorted_lines[i-1][0]
            y2 = sorted_lines[i][0]
            spacing = y2 - y1
            spacings.append(spacing)
            if i <= 2 or i == len(sorted_lines) - 1:
                print(f"  Q{i} → Q{i+1}: {spacing}px")
        
        if spacings:
            avg_spacing = np.mean(spacings)
            std_spacing = np.std(spacings)
            min_spacing = np.min(spacings)
            max_spacing = np.max(spacings)
            
            print(f"\n📊 Estatísticas:")
            print(f"  Espaçamento médio: {avg_spacing:.2f}px")
            print(f"  Desvio padrão:     {std_spacing:.2f}px")
            print(f"  Mínimo:            {min_spacing}px")
            print(f"  Máximo:            {max_spacing}px")
            print(f"  Variação:          {max_spacing - min_spacing}px")
            
            # Comparar com esperado
            print(f"\n🎯 Comparação com esperado:")
            print(f"  Se fosse 14px: espaçamento esperado = 14px")
            print(f"  Se fosse 18px: espaçamento esperado = 18px")
            
            if avg_spacing < 16:
                print(f"  ✅ Mais próximo de 14px (ajuste NÃO deveria ser aplicado!)")
            else:
                print(f"  ✅ Mais próximo de 18px (ajuste está correto)")
    
    def analyze_horizontal_spacing(self):
        """Analisa espaçamento horizontal entre alternativas"""
        print("\n" + "="*70)
        print("📏 ANÁLISE DE ESPAÇAMENTO HORIZONTAL")
        print("="*70)
        
        if not self.bubbles:
            print("❌ Nenhuma bolha para analisar")
            return
        
        # Agrupar bolhas por Y
        lines = {}
        for bubble in self.bubbles:
            y = bubble['y']
            found_line = False
            for existing_y in lines:
                if abs(y - existing_y) <= 2:
                    lines[existing_y].append(bubble)
                    found_line = True
                    break
            
            if not found_line:
                lines[y] = [bubble]
        
        sorted_lines = sorted(lines.items())
        
        print(f"\n🔍 Análise de questões com múltiplas alternativas:\n")
        
        for q_num, (y_real, bubbles_in_line) in enumerate(sorted_lines, 1):
            if len(bubbles_in_line) < 2:
                continue  # Pular questões com 1 alternativa
            
            # Ordenar por X
            bubbles_sorted_x = sorted(bubbles_in_line, key=lambda b: b['x'])
            
            print(f"Q{q_num} (Y={y_real}px, {len(bubbles_sorted_x)} alternativas):")
            
            # Mostrar posições
            for alt_idx, bubble in enumerate(bubbles_sorted_x):
                alt_letter = chr(65 + alt_idx)
                print(f"  {alt_letter}: X={bubble['x']:3d}px, Raio={bubble['radius']}px")
            
            # Espaçamento entre alternativas
            if len(bubbles_sorted_x) > 1:
                print(f"  Espaçamento entre alternativas:")
                for i in range(len(bubbles_sorted_x) - 1):
                    spacing = bubbles_sorted_x[i+1]['x'] - bubbles_sorted_x[i]['x']
                    alt1 = chr(65 + i)
                    alt2 = chr(65 + i + 1)
                    expected = 19  # bubble_spacing (15 + 4)
                    diff = spacing - expected
                    print(f"    {alt1} → {alt2}: {spacing}px (esperado: {expected}px, diff: {diff:+d}px)")
            
            print()

def main():
    print("\n" + "="*70)
    print("📐 MEDIDOR DE ESPAÇAMENTO DE BOLHAS")
    print("="*70)
    
    # Procurar por imagens de debug dos blocos
    debug_dir = Path("debug_corrections")
    
    if not debug_dir.exists():
        print(f"\n⚠️  Diretório não encontrado: {debug_dir}")
        print("\n📝 Uso manual:")
        print("   python measure_real_spacing.py <caminho_da_imagem> [numero_do_bloco]")
        print("\n💡 Exemplos:")
        print("   python measure_real_spacing.py debug_corrections/block_01.jpg 1")
        print("   python measure_real_spacing.py debug_corrections/block_02.jpg 2")
        
        # Tentar com argumento de linha de comando
        import sys
        if len(sys.argv) > 1:
            image_path = sys.argv[1]
            block_num = int(sys.argv[2]) if len(sys.argv) > 2 else 1
            
            analyzer = BubbleSpacingAnalyzer(image_path, block_num)
            if analyzer.load_image():
                analyzer.bubbles = analyzer.detect_bubbles()
                analyzer.analyze_vertical_spacing()
                analyzer.analyze_horizontal_spacing()
        return
    
    # Procurar arquivos de bloco
    block_files = sorted(debug_dir.glob("*block_*real*.jpg"))
    
    if not block_files:
        print(f"⚠️  Nenhuma imagem de bloco encontrada em {debug_dir}")
        print("   Procurando por padrão: *block_*real*.jpg")
        return
    
    print(f"\n✅ Encontrados {len(block_files)} arquivos de bloco\n")
    
    for block_file in block_files:
        print(f"\n{'='*70}")
        print(f"📸 Analisando: {block_file.name}")
        print(f"{'='*70}")
        
        # Extrair número do bloco do nome do arquivo
        import re
        match = re.search(r'block_(\d+)', block_file.name)
        block_num = int(match.group(1)) if match else 1
        
        analyzer = BubbleSpacingAnalyzer(str(block_file), block_num)
        if analyzer.load_image():
            analyzer.bubbles = analyzer.detect_bubbles()
            analyzer.analyze_vertical_spacing()
            analyzer.analyze_horizontal_spacing()

if __name__ == "__main__":
    main()
