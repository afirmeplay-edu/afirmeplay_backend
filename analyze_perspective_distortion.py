#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para analisar distorção de perspectiva no warpPerspective
Identifica onde e por que há desalinhamento progressivo
"""

import json
import numpy as np
import cv2
from pathlib import Path

def analise_scale_info():
    """Analisa se há escala diferente em X vs Y"""
    print("\n" + "="*70)
    print("1. ANÁLISE DE ESCALA (px_per_cm_x vs px_per_cm_y)")
    print("="*70)
    
    # Simulação com valores típicos do A4
    A4_WIDTH_CM = 21.0
    A4_HEIGHT_CM = 29.7
    A4_WIDTH_PX = 827  # ~39.37 px/cm
    A4_HEIGHT_PX = 1169
    
    print(f"\n📏 Tamanho A4 normalizado:")
    print(f"  Dimensões: {A4_WIDTH_PX}x{A4_HEIGHT_PX}px")
    print(f"  Proporção (W/H): {A4_WIDTH_PX/A4_HEIGHT_PX:.4f}")
    
    # Escala padrão (correta)
    px_per_cm_ideal = 39.37
    print(f"\n✅ Escala padrão (correta):")
    print(f"  px_per_cm_x: {px_per_cm_ideal:.2f}")
    print(f"  px_per_cm_y: {px_per_cm_ideal:.2f}")
    print(f"  Proporção: 1:1 (uniforme)")
    
    # Cenário 1: Escala desigual (PROBLEMA)
    print(f"\n❌ Cenário 1: Escala desigual (px_per_cm_x ≠ px_per_cm_y)")
    px_per_cm_x_bad = 39.37
    px_per_cm_y_bad = 42.0  # Mais "esticado" verticalmente
    
    print(f"  px_per_cm_x: {px_per_cm_x_bad:.2f}")
    print(f"  px_per_cm_y: {px_per_cm_y_bad:.2f}")
    print(f"  Diferença: {px_per_cm_y_bad - px_per_cm_x_bad:.2f} ({((px_per_cm_y_bad/px_per_cm_x_bad - 1) * 100):.1f}% mais alto)")
    
    # Impacto no espaçamento
    line_height_18 = 18  # pixels
    line_height_18_cm = line_height_18 / px_per_cm_x_bad  # em cm
    line_height_18_px_bad = line_height_18_cm * px_per_cm_y_bad  # recalculado com escala Y diferente
    
    print(f"\n⚠️  IMPACTO no espaçamento:")
    print(f"  line_height esperado: 18px (em escala uniforme)")
    print(f"  = {line_height_18_cm:.4f}cm")
    print(f"  = {line_height_18_px_bad:.1f}px (com escala Y diferente!)")
    print(f"  Diferença: +{line_height_18_px_bad - line_height_18:.1f}px por questão")
    print(f"  Acumulado (26 questões): +{(line_height_18_px_bad - line_height_18) * 25:.1f}px")
    
    # Cenário 2: Perspectiva inclinada
    print(f"\n❌ Cenário 2: Perspectiva inclinada (pitch)")
    print(f"  Imagem original fotografada em ângulo")
    print(f"  warpPerspective corrige a inclinação")
    print(f"  MAS pode criar compressão/expansão não-linear")
    print(f"  Resultado: espaçamento muda ao descer na página")


def analise_warp_perspective():
    """Analisa como warpPerspective causa distorção"""
    print("\n" + "="*70)
    print("2. ANÁLISE DO warpPerspective")
    print("="*70)
    
    A4_WIDTH_PX = 827
    A4_HEIGHT_PX = 1169
    
    print(f"\n📐 Transformação de perspectiva:")
    print(f"  src_points = [TL, TR, BR, BL] detectados na imagem original")
    print(f"  dst_points = [0,0], [{A4_WIDTH_PX},0], [{A4_WIDTH_PX},{A4_HEIGHT_PX}], [0,{A4_HEIGHT_PX}]")
    print(f"\n⚠️  PROBLEMA: Se os quadrados detectados (src) não forem exatamente")
    print(f"     proporcionais ao A4, a transformação cria distorção.")
    
    # Simulação: quadrados detectados com erro
    print(f"\n🔍 Exemplo de erro na detecção:")
    
    # Caso correto
    src_correct = np.array([
        [100, 100],      # TL
        [2000, 100],     # TR
        [2000, 3000],    # BR
        [100, 3000]      # BL
    ], dtype="float32")
    
    width_correct = 2000 - 100
    height_correct = 3000 - 100
    aspect_correct = width_correct / height_correct
    
    print(f"\n✅ Detecção CORRETA:")
    print(f"  Largura: {width_correct}px")
    print(f"  Altura: {height_correct}px")
    print(f"  Proporção (W/H): {aspect_correct:.4f}")
    print(f"  A4 esperado (21/29.7): {21/29.7:.4f}")
    
    # Caso com erro
    src_error = np.array([
        [100, 100],      # TL (correto)
        [2000, 100],     # TR (correto)
        [2000, 2800],    # BR (30 pixels acima do esperado!)
        [100, 2800]      # BL (30 pixels acima)
    ], dtype="float32")
    
    width_error = 2000 - 100
    height_error = 2800 - 100
    aspect_error = width_error / height_error
    
    print(f"\n❌ Detecção COM ERRO (BR/BL 30px acima):")
    print(f"  Largura: {width_error}px")
    print(f"  Altura: {height_error}px (esperado: {height_correct})")
    print(f"  Proporção (W/H): {aspect_error:.4f}")
    print(f"  DIFERENÇA: {height_correct - height_error}px ({((1 - height_error/height_correct)*100):.1f}% mais curto)")
    
    # Impacto
    print(f"\n⚠️  IMPACTO da detecção com erro:")
    print(f"  Quando warped para {A4_WIDTH_PX}x{A4_HEIGHT_PX}:")
    print(f"  - A imagem original tem {height_error}px")
    print(f"  - Mas será esticada para {A4_HEIGHT_PX}px")
    print(f"  - Fator de esticamento: {A4_HEIGHT_PX/height_error:.4f}")
    print(f"  - Espaçamento será multiplicado por {A4_HEIGHT_PX/height_error:.4f}")
    print(f"  - 18px × {A4_HEIGHT_PX/height_error:.4f} = {18 * A4_HEIGHT_PX/height_error:.1f}px ❌")


def analise_quadrados_deteccao():
    """Analisa como a detecção de quadrados afeta o resultado"""
    print("\n" + "="*70)
    print("3. QUALIDADE DA DETECÇÃO DE QUADRADOS DE REFERÊNCIA")
    print("="*70)
    
    print(f"""
📍 Onde estão os quadrados no formulário?

Típico layout:
┌─────────────────────────────────────────────┐
│ [TL]                                  [TR]  │  Quadrados de referência
│                                             │  (canto superior)
│                                             │
│            [CONTEÚDO]                       │  
│            (26 questões)                    │
│                                             │
│                                             │
│ [BL]                                  [BR]  │  Quadrados de referência
│                                             │  (canto inferior)
└─────────────────────────────────────────────┘

⚠️  PROBLEMA COMUM:
  Se os quadrados não forem detectados com precisão:
  - TL/TR muito acima → altura fica curta
  - BL/BR muito abaixo → altura fica longa
  - TL/BL desalinhados → incluso horizontal
  
  Resultado: warpPerspective compensa de forma não-uniforme!

🔍 Verificação necessária:
  1. São os quadrados sempre detectados no mesmo lugar?
  2. A detecção varia entre imagens?
  3. Há "ruído" na detecção que cause oscilação?
  """)


def analise_acumulacao_erro():
    """Mostra como o erro se acumula"""
    print("\n" + "="*70)
    print("4. ACUMULAÇÃO DE ERRO")
    print("="*70)
    
    print(f"\n📊 Cenário: Erro de 3% na escala vertical")
    
    line_height = 18  # pixels (esperado)
    scale_error_percent = 3
    scale_factor = 1 + (scale_error_percent / 100)
    
    print(f"\n  Line height esperado: {line_height}px")
    print(f"  Escala Y: {scale_factor:.4f} (3% maior)")
    print(f"  Line height real: {line_height * scale_factor:.2f}px")
    print(f"  Erro por questão: +{line_height * (scale_factor - 1):.2f}px")
    
    print(f"\n  Posição das questões com 3% de erro:")
    print(f"  Q  │ Esperado │ Real     │ Erro acumulado")
    print(f"  ───┼──────────┼──────────┼────────────────")
    
    for q in [1, 5, 10, 15, 20, 26]:
        y_expected = 15 + (q - 1) * line_height
        y_real = 15 + (q - 1) * line_height * scale_factor
        error = y_real - y_expected
        print(f"  {q:2d} │   {y_expected:4d}px │  {y_real:5.1f}px │   +{error:.1f}px")
    
    print(f"\n  ⚠️  NO FIM DA PÁGINA (Q26): +{25 * line_height * (scale_factor - 1):.0f}px de erro!")


def recomendacoes():
    """Fornece recomendações de investigação"""
    print("\n" + "="*70)
    print("5. RECOMENDAÇÕES PARA INVESTIGAÇÃO")
    print("="*70)
    
    print("""
🔧 Para diagnosticar o problema:

PASSO 1: Verificar scale_info
────────────────────────────────
  Adicionar logs em correction_n.py linha ~1023:
  
  ```python
  print(f"px_per_cm_x: {px_per_cm_x:.2f}")
  print(f"px_per_cm_y: {px_per_cm_y:.2f}")
  if px_per_cm_x != px_per_cm_y:
      print(f"⚠️  ESCALAS DIFERENTES! Proporção: {px_per_cm_y/px_per_cm_x:.4f}")
  ```

PASSO 2: Verificar quadrados detectados
────────────────────────────────────────
  Adicionar logs em correction_n.py linha ~995:
  
  ```python
  print(f"Quadrados detectados:")
  print(f"  TL: {squares['TL']}")
  print(f"  TR: {squares['TR']}")
  print(f"  BR: {squares['BR']}")
  print(f"  BL: {squares['BL']}")
  
  width = np.linalg.norm(np.array(squares['TR']) - np.array(squares['TL']))
  height = np.linalg.norm(np.array(squares['BL']) - np.array(squares['TL']))
  print(f"Proporção: {width/height:.4f} (esperado ~0.707 para A4)")
  ```

PASSO 3: Salvar imagem warped com grid de referência
──────────────────────────────────────────────────────
  Verificar se:
  - Topo da imagem está bem alinhado
  - Meio da imagem começa a desalinhar
  - Fundo está muito desalinhado
  
  Se for assim → problema é no warpPerspective

PASSO 4: Verificar se problema é na IMAGEM ORIGINAL
─────────────────────────────────────────────────────
  Se a imagem original já tem distorção, o warpPerspective
  não consegue corrigir perfeitamente.
  
  Solução: Usar cv2.undistort() ou cv2.getOptimalNewCameraMatrix()

AÇÕES RECOMENDADAS:
───────────────────
1. ✓ Executar com logs para ver scale_info
2. ✓ Executar com logs para ver quadrados detectados  
3. ✓ Gerar imagem warped para inspeção visual
4. ✓ Se necessário, adicionar undistort() antes do warpPerspective
  """)

def main():
    print("\n" + "="*70)
    print("🔬 INVESTIGAÇÃO DE DISTORÇÃO DE PERSPECTIVA")
    print("="*70)
    
    analise_scale_info()
    analise_warp_perspective()
    analise_quadrados_deteccao()
    analise_acumulacao_erro()
    recomendacoes()
    
    print("\n" + "="*70)
    print("📝 PRÓXIMO PASSO")
    print("="*70)
    print("""
Execute estes comandos para coletar dados:

1. Adicionar logs em correction_n.py (ver PASSO 1 e 2 acima)
2. Rodar: python run.py
3. Verificar console output para scale_info e quadrados detectados
4. Enviar para análise

Ou se preferir testar direto, criar um script que:
- Carrega uma imagem de debug
- Mede espaçamento em diferentes Y (topo, meio, fundo)
- Compara com o esperado
  """)


if __name__ == "__main__":
    main()
