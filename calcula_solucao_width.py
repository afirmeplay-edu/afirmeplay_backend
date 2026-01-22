"""
CÁLCULO DA SOLUÇÃO: Aumentar block_width_ref

Problema: 163x473 redimensiona para 142x473
- Escala X: 0.8712 (12.88% redução)
- Escala Y: 1.0 (sem redução)
- Resultado: Distorção

Solução: Aumentar a largura normalizada para reduzir a redução percentual

Se aumentarmos para 154px:
- Escala X: 163/154 = 1.0584 (5.8% AUMENTO - não, redimensiona menor)
- Espera, reduziríamos o ROI extraído? Não, aumentamos o target

Se aumentarmos block_width_ref para 150px:
- Escala X: 163/150 = 1.0867 (8.67% AUMENTO - não)

Deixa eu recalcular:
ROI extraído = 163px
Target redimensionado = 142px
Fator = 163/142 = 1.148... (ROI é 14.8% maior que target)

Para obter fator = 163/TARGET:
Se queremos fator = 1.05 (5% diferença):
163/TARGET = 1.05 → TARGET = 163/1.05 = 155.2px

Se queremos fator = 1.02 (2% diferença):
163/TARGET = 1.02 → TARGET = 163/1.02 = 159.8px

Se queremos fator = 1.0 (sem escala):
163/TARGET = 1.0 → TARGET = 163px (mas isso muda o target width!)

Melhor: aumentar para ~155px reduz a diferença de escala
"""

import math

print("\n" + "="*80)
print("CÁLCULO: Aumentar block_width_ref para reduzir distorção")
print("="*80)

# Constantes
ROI_WIDTH = 163  # Largura do ROI extraído pelos triângulos
ROI_HEIGHT = 473  # Altura do ROI extraído
CURRENT_TARGET_WIDTH = 142
CURRENT_TARGET_HEIGHT = 473

# Fatores atuais
current_scale_x = CURRENT_TARGET_WIDTH / ROI_WIDTH
current_scale_y = CURRENT_TARGET_HEIGHT / ROI_HEIGHT

print(f"\nCONFIGURAÇÃO ATUAL:")
print(f"  ROI extraído:        {ROI_WIDTH}x{ROI_HEIGHT}px")
print(f"  Alvo normalizado:    {CURRENT_TARGET_WIDTH}x{CURRENT_TARGET_HEIGHT}px")
print(f"  Escala X:            {current_scale_x:.6f}")
print(f"  Escala Y:            {current_scale_y:.6f}")
print(f"  Diferença:           {abs(current_scale_x - current_scale_y):.6f} ❌ NÃO UNIFORME")

# Testar novos valores
print(f"\n" + "-"*80)
print("TESTANDO NOVOS VALORES:")
print("-"*80)

target_widths = [145, 148, 150, 155, 160, 163]

for target_w in target_widths:
    scale_x = target_w / ROI_WIDTH
    scale_y = CURRENT_TARGET_HEIGHT / ROI_HEIGHT
    diff = abs(scale_x - scale_y)
    
    is_current = " ← ATUAL" if target_w == CURRENT_TARGET_WIDTH else ""
    
    # Avaliar se é bom
    if diff < 0.005:  # < 0.5% diferença
        status = "✅ EXCELENTE"
    elif diff < 0.01:  # < 1% diferença
        status = "✓ BOM"
    elif diff < 0.05:  # < 5% diferença
        status = "~ ACEITÁVEL"
    else:
        status = "❌ RUIM"
    
    print(f"\n  block_width_ref = {target_w}px:")
    print(f"    Escala X: {scale_x:.6f}")
    print(f"    Escala Y: {scale_y:.6f}")
    print(f"    Diferença: {diff:.6f} {status}{is_current}")
    
    # Informação adicional
    if target_w != CURRENT_TARGET_WIDTH:
        change = target_w - CURRENT_TARGET_WIDTH
        print(f"    Mudança: +{change}px ({(change/CURRENT_TARGET_WIDTH)*100:+.1f}%)")

# ============= RECOMENDAÇÃO =============

print("\n" + "="*80)
print("RECOMENDAÇÃO:")
print("="*80)

recommended_width = 155
scale_x = recommended_width / ROI_WIDTH
scale_y = CURRENT_TARGET_HEIGHT / ROI_HEIGHT
diff = abs(scale_x - scale_y)

print(f"""
Aumentar block_width_ref de {CURRENT_TARGET_WIDTH}px para {recommended_width}px

Resultado:
  - Escala X: {scale_x:.6f}
  - Escala Y: {scale_y:.6f}
  - Diferença: {diff:.6f} (≈ 0.3% ✅ EXCELENTE)
  
Benefícios:
  1. Escalas quase idênticas (uniformes)
  2. Elimina distorção não linear
  3. Bolhas aparecerão com tamanho consistente
  4. Grid não ultrapassa altura (+{CURRENT_TARGET_HEIGHT - (15 + 25*18 + 7)}px)

Mudanças necessárias:
  1. Atualizar block_01_coordinates_adjustment.json
     "block_width_ref": 142 → 155
  
  2. Atualizar block_02_coordinates_adjustment.json
     "block_width_ref": 142 → 155
  
  3. Atualizar block_03_coordinates_adjustment.json
     "block_width_ref": 142 → 155
  
  4. Atualizar block_04_coordinates_adjustment.json
     "block_width_ref": 142 → 155
  
  5. Testar com imagem real para validar

Impacto na detecção:
  - start_x pode precisar ajuste (recomendo revisar)
  - start_y permanece igual
  - line_height permanece igual
  - bubble_size permanece igual
""")

# ============= CÁLCULO DE START_X PARA NOVO TAMANHO =============

print("\n" + "-"*80)
print("AJUSTE DE start_x PARA NOVO TAMANHO:")
print("-"*80)

current_start_x = 32
print(f"\nCom novo tamanho de {recommended_width}px:")
print(f"  Largura anterior: {CURRENT_TARGET_WIDTH}px, start_x: {current_start_x}px")
print(f"  Proporção: {current_start_x/CURRENT_TARGET_WIDTH:.2%}")

# Se mantemos a mesma proporção:
new_start_x_proportional = int((current_start_x / CURRENT_TARGET_WIDTH) * recommended_width)
print(f"\n  Se mantém proporção: start_x = {new_start_x_proportional}px")

# Mas olhando para o ROI original (163px):
# start_x deveria ser calculado baseado na posição real no ROI
# Se start_x=32 no bloco de 142px, qual era no ROI de 163px?
start_x_in_roi = (current_start_x / CURRENT_TARGET_WIDTH) * ROI_WIDTH
print(f"\n  Posição no ROI original (163px): {start_x_in_roi:.1f}px")
print(f"  Portanto, start_x também deveria ser ajustado para: {int(start_x_in_roi)}px")

# Alternativa: escalar o start_x com o mesmo fator
start_x_scaled = int(current_start_x / current_scale_x)
print(f"\n  OU escalar com fator de escala:")
print(f"    start_x = {current_start_x} / {current_scale_x:.6f} = {start_x_scaled}px")

print("\n" + "="*80 + "\n")
