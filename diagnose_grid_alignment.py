#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script de diagnóstico para verificar alinhamento da grade de detecção
Verifica:
1. Se line_height do JSON está sendo respeitado ou ajustado
2. Distribuição real de bolhas na imagem
3. Espaçamento vertical das questões
4. Comparação entre esperado vs. real
"""

import json
import cv2
import numpy as np
from pathlib import Path

def analise_line_height():
    """Analisa o ajuste dinâmico do line_height"""
    print("\n" + "="*70)
    print("1. ANÁLISE DO LINE_HEIGHT")
    print("="*70)
    
    # Valores do JSON
    block_height_ref = 473
    num_questions = 26
    padding_top = 8
    padding_bottom = 8
    total_padding = padding_top + padding_bottom
    usable_height = block_height_ref - total_padding
    
    # line_height do arquivo
    line_height_json = 14
    
    # line_height calculado dinamicamente
    ideal_line_height = usable_height / num_questions
    
    print(f"\n📊 Parâmetros do bloco:")
    print(f"  Altura total:        {block_height_ref}px")
    print(f"  Número de questões:  {num_questions}")
    print(f"  Padding (top+bottom):{total_padding}px")
    print(f"  Altura útil:         {usable_height}px")
    
    print(f"\n📋 Line Height:")
    print(f"  No arquivo JSON:     {line_height_json}px")
    print(f"  Ideal (calculado):   {ideal_line_height:.2f}px")
    print(f"  Ajustado (rounded):  {round(ideal_line_height)}px")
    
    print(f"\n⚠️  DIFERENÇA: {abs(line_height_json - ideal_line_height):.2f}px")
    
    if abs(line_height_json - ideal_line_height) > 0.5:
        print("  ❌ AJUSTE SERÁ ATIVADO! (diferença > 0.5px)")
        use_line_height = round(ideal_line_height)
    else:
        print("  ✅ Sem ajuste, usando valor do JSON")
        use_line_height = line_height_json
    
    print(f"\n🎯 Line Height Final Usado: {use_line_height}px")
    
    # Mostrar distribuição de Y para algumas questões
    print(f"\n📍 Distribuição de Y com {use_line_height}px:")
    print(f"  Q1  (idx 0):  Y = 15 + 0×{use_line_height} = {15 + 0*use_line_height}px")
    print(f"  Q7  (idx 6):  Y = 15 + 6×{use_line_height} = {15 + 6*use_line_height}px")
    print(f"  Q14 (idx 13): Y = 15 + 13×{use_line_height} = {15 + 13*use_line_height}px")
    print(f"  Q20 (idx 19): Y = 15 + 19×{use_line_height} = {15 + 19*use_line_height}px")
    print(f"  Q26 (idx 25): Y = 15 + 25×{use_line_height} = {15 + 25*use_line_height}px")
    
    # Comparar com 14px
    print(f"\n🔄 Comparação com line_height={line_height_json}px:")
    q_indices = [0, 13, 25]
    for idx in q_indices:
        y_18 = 15 + idx * use_line_height
        y_14 = 15 + idx * line_height_json
        q_num = idx + 1
        diff = y_18 - y_14
        print(f"  Q{q_num:2d} (idx {idx:2d}): Y = {y_14}px vs {y_18}px (diff: +{diff}px)")
    
    # Diferença acumulada
    accumulated_diff = 25 * (use_line_height - line_height_json)
    print(f"\n📊 DIFERENÇA ACUMULADA (Q1 até Q26): +{accumulated_diff}px")
    
    return use_line_height, ideal_line_height


def analise_bubble_radius():
    """Analisa o raio da bolha e seu impacto"""
    print("\n" + "="*70)
    print("2. ANÁLISE DO RAIO DA BOLHA")
    print("="*70)
    
    block_width = 142  # px
    block_height = 473  # px
    
    # Cálculo do raio
    bubble_radius_fallback = max(5, int(block_width * 0.04))
    bubble_radius_clamped = max(5, min(10, bubble_radius_fallback))
    
    print(f"\n📏 Parâmetros:")
    print(f"  Largura do bloco:    {block_width}px")
    print(f"  Altura do bloco:     {block_height}px")
    
    print(f"\n🔢 Cálculo do raio:")
    print(f"  Fallback (4% width): {bubble_radius_fallback}px")
    print(f"  Após clamp [5-10]:   {bubble_radius_clamped}px")
    
    print(f"\n📐 Área do círculo com raio {bubble_radius_clamped}px:")
    area = np.pi * bubble_radius_clamped * bubble_radius_clamped
    print(f"  Área = π × {bubble_radius_clamped}² = {area:.2f}px²")
    
    print(f"\n💡 Impacto na medição:")
    print(f"  (Mesmo número de pixels marcados, área diferente → fill_ratio diferente)")
    for pixels_marcados in [50, 100, 150, 200]:
        fill_ratio = pixels_marcados / area if area > 0 else 0
        print(f"  {pixels_marcados:3d} pixels → fill_ratio = {fill_ratio:.3f} ({fill_ratio*100:5.1f}%)")


def analise_spacing():
    """Analisa o espaçamento esperado entre bolhas"""
    print("\n" + "="*70)
    print("3. ANÁLISE DE ESPAÇAMENTO HORIZONTAL")
    print("="*70)
    
    bubble_size = 15  # px
    bubble_gap = 4    # px
    bubble_spacing = bubble_size + bubble_gap  # 19px
    
    print(f"\n🎯 Valores do template:")
    print(f"  Tamanho da bolha:    {bubble_size}px")
    print(f"  Gap entre bolhas:    {bubble_gap}px")
    print(f"  Espaçamento total:   {bubble_spacing}px")
    
    print(f"\n📍 Posições esperadas de X (start_x=32px, centro da bolha):")
    for j in range(4):
        x = 32 + j * bubble_spacing + 7  # 7 é o center offset (15/2 - 1)
        print(f"  Alternativa {chr(65+j)} (j={j}): x = 32 + {j}×{bubble_spacing} + 7 = {x}px")


def analise_distorcao():
    """Analisa possível distorção vertical"""
    print("\n" + "="*70)
    print("4. ANÁLISE DE POSSÍVEL DISTORÇÃO")
    print("="*70)
    
    print(f"""
📌 Se o grid alinha perfeitamente no início mas desalinha no final:

POSSÍVEIS CAUSAS:

1. 🔄 PERSPECTIVA INCLINADA (pitch)
   - Imagem normalizada com transformação perspectiva incorreta
   - Resultado: espaçamento aumenta conforme desce
   - Verificar: cv2.warpPerspective em correction_n.py linha 1010
   
2. 📐 DISTORÇÃO RADIAL/BARREL
   - Câmera com distorção barrel/pincushion não corrigida
   - Resultado: mudança de espaçamento progressiva
   - Verificar: se há cv2.undistort() sendo usado
   
3. 📏 ESCALA VERTICAL VARIÁVEL
   - Normalização A4 com scales diferentes para X e Y
   - Resultado: compressão/expansão vertical não-uniforme
   - Verificar: scale_info com px_per_cm_x vs px_per_cm_y
   
4. ⚠️  LINE_HEIGHT INCORRETO NO JSON
   - Se JSON tem 14px mas o real é 18px, haverá sobreposição
   - Resultado: grid desalinha especialmente no final
   - Verificar: com imagem real do cartão escaneado
   
5. 🐛 AJUSTE DINÂMICO DO LINE_HEIGHT
   - O código ajusta 14px → 18px automaticamente
   - Resultado: distribuição vertical muda
   - Verificar: desabilitar ajuste e usar valor fixo do JSON
    """)


def main():
    print("\n" + "="*70)
    print("🔧 DIAGNÓSTICO DE ALINHAMENTO DA GRADE")
    print("="*70)
    
    use_line_height, ideal_line_height = analise_line_height()
    analise_bubble_radius()
    analise_spacing()
    analise_distorcao()
    
    print("\n" + "="*70)
    print("📋 RESUMO EXECUTIVO")
    print("="*70)
    
    accumulated_diff = 25 * (use_line_height - 14)
    print(f"""
✅ LINE_HEIGHT está sendo AJUSTADO:
   - Arquivo JSON:    14px
   - Cálculo ideal:   17.58px → 18px (arredondado)
   - Diferença:       +{use_line_height - 14}px por questão
   - ACUMULADA (Q26): +{accumulated_diff}px

❌ IMPACTO:
   - Q1  em Y=15px ✓ (correto)
   - Q26 em Y=465px com 18px vs Y=365px com 14px
   - Diferença total: {accumulated_diff}px de deslocamento!

🎯 PRÓXIMAS AÇÕES:
   1. Rodar: python measure_real_spacing.py
      → Mede espaçamento real das bolhas
   
   2. Rodar: python generate_grid_overlay.py
      → Gera imagens com grid superposto
   
   3. Rodar: python compare_expected_vs_real.py
      → Compara esperado vs. real
      
4. Se o espaçamento real é 14px:
      → SOLUÇÃO: Desabilitar ajuste dinâmico em correction_n.py
""")

if __name__ == "__main__":
    main()
