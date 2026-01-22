"""
Reproduzir visualmente o que acontece no redimensionamento do bloco

Problema: 163x473 → 142x473
- Largura reduz 12.88%
- Altura não muda
- Resultado: distorção NÃO uniforme

Isso causa que as bolhas pareçam "esticadas" verticalmente no fim,
porque a largura está compactada.
"""

import cv2
import numpy as np

print("\n" + "="*80)
print("SIMULAÇÃO: Distorção do redimensionamento")
print("="*80)

# Criar imagem sintética com grid de referência
ORIGINAL_WIDTH = 163
ORIGINAL_HEIGHT = 473
TARGET_WIDTH = 142
TARGET_HEIGHT = 473

# Criar imagem com grid para visualizar a distorção
img = np.ones((ORIGINAL_HEIGHT, ORIGINAL_WIDTH, 3), dtype=np.uint8) * 255

# Desenhar grade de linhas verticais (a cada 10px)
for x in range(0, ORIGINAL_WIDTH, 10):
    cv2.line(img, (x, 0), (x, ORIGINAL_HEIGHT), (200, 200, 200), 1)

# Desenhar grade de linhas horizontais (a cada 20px)
for y in range(0, ORIGINAL_HEIGHT, 20):
    cv2.line(img, (0, y), (ORIGINAL_WIDTH, y), (200, 200, 200), 1)

# Desenhar bolhas em posições específicas (grid esperado no bloco)
START_X = 32
START_Y = 15
LINE_HEIGHT = 18
BUBBLE_SIZE = 15
BUBBLE_SPACING = 19

# Desenhar bolhas
questions = [1, 6, 12, 18, 24, 26]  # Amostra de questões
for q_idx, q_num in enumerate(questions):
    y = START_Y + (q_num - 1) * LINE_HEIGHT
    
    # Desenhar as 4 alternativas
    for alt_idx in range(4):
        x = START_X + alt_idx * BUBBLE_SPACING + BUBBLE_SIZE // 2
        if x < ORIGINAL_WIDTH and y < ORIGINAL_HEIGHT:
            cv2.circle(img, (x, y), BUBBLE_SIZE // 2, (0, 0, 255), 2)
            cv2.putText(img, chr(65 + alt_idx), (x-3, y+3), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.3, (0, 0, 255), 1)
    
    # Escrever número da questão
    cv2.putText(img, f"Q{q_num}", (5, y+3), 
               cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 0, 0), 1)

# Salvar imagem original
cv2.imwrite("debug_corrections/01_original_163x473.jpg", img)
print(f"\n✓ Imagem original: 163x473px")
print(f"  Salva em: debug_corrections/01_original_163x473.jpg")

# Redimensionar
img_resized = cv2.resize(img, (TARGET_WIDTH, TARGET_HEIGHT), interpolation=cv2.INTER_AREA)

# Salvar imagem redimensionada
cv2.imwrite("debug_corrections/02_resized_142x473.jpg", img_resized)
print(f"\n✓ Imagem redimensionada: 142x473px")
print(f"  Salva em: debug_corrections/02_resized_142x473.jpg")

# ============= ANÁLISE DE DISTORÇÃO =============

print("\n" + "-"*80)
print("ANÁLISE DE DISTORÇÃO:")
print("-"*80)

scale_x = TARGET_WIDTH / ORIGINAL_WIDTH
scale_y = TARGET_HEIGHT / ORIGINAL_HEIGHT

print(f"\nFator de escala:")
print(f"  X: {ORIGINAL_WIDTH}px → {TARGET_WIDTH}px = {scale_x:.6f}")
print(f"  Y: {ORIGINAL_HEIGHT}px → {TARGET_HEIGHT}px = {scale_y:.6f}")
print(f"  Diferença: {abs(scale_x - scale_y):.6f}")

# Analisar posição de bolhas antes e depois
print(f"\nPosição das bolhas (centro X, Y):")
print(f"{'Q':<4} {'Antes':<30} {'Depois':<30}")
print(f"{'':<4} {'X':<15} {'Y':<15} {'X':<15} {'Y':<15}")
print("-" * 70)

for q_idx, q_num in enumerate(questions):
    y_before = START_Y + (q_num - 1) * LINE_HEIGHT
    
    # A bolha está em X=58 (alternativa B)
    x_before = START_X + 1 * BUBBLE_SPACING + BUBBLE_SIZE // 2
    
    # Calcular posição após redimensionamento
    x_after = round(x_before * scale_x)
    y_after = round(y_before * scale_y)
    
    print(f"Q{q_num:<2} {x_before:<7.1f} {y_before:<7.1f}          {x_after:<7.1f} {y_after:<7.1f}")

# ============= PERCENTUAIS DE USO =============

print(f"\n" + "-"*80)
print("PERCENTUAIS DE USO DO ESPAÇO VERTICAL:")
print("-"*80)

print(f"\nQuanto da altura do bloco cada questão ocupa:")
print(f"{'Q':<4} {'Y (px)':<10} {'% do bloco':<12} {'Distância'}")
print("-" * 50)

for q_num in questions:
    y = START_Y + (q_num - 1) * LINE_HEIGHT
    percent = (y / TARGET_HEIGHT) * 100
    distance_to_end = TARGET_HEIGHT - (y + BUBBLE_SIZE // 2)
    print(f"Q{q_num:<2} {y:<10} {percent:<11.1f}% {distance_to_end:+3.0f}px")

# Calcular espaçamento entre questões
print(f"\n" + "-"*80)
print("ESPAÇAMENTO ENTRE QUESTÕES (em pixels redimensionados):")
print("-"*80)

for i in range(len(questions) - 1):
    q1 = questions[i]
    q2 = questions[i+1]
    
    y1 = START_Y + (q1 - 1) * LINE_HEIGHT
    y2 = START_Y + (q2 - 1) * LINE_HEIGHT
    
    # Após redimensionamento
    y1_after = round(y1 * scale_y)
    y2_after = round(y2 * scale_y)
    
    spacing_before = y2 - y1
    spacing_after = y2_after - y1_after
    
    change = ((spacing_after - spacing_before) / spacing_before) * 100 if spacing_before > 0 else 0
    
    print(f"Q{q1} → Q{q2}: {spacing_before}px → {spacing_after}px ({change:+.1f}%)")

print("\n" + "="*80)
print("CONCLUSÃO:")
print("="*80)
print(f"""
O redimensionamento de {ORIGINAL_WIDTH}x{ORIGINAL_HEIGHT}px para {TARGET_WIDTH}x{TARGET_HEIGHT}px
causa DISTORÇÃO porque os fatores de escala são diferentes:

- Eixo X: reduz 12.88% (163 → 142)
- Eixo Y: não muda (473 → 473)

Resultado:
1. As bolhas ficam MAIS COMPACTADAS horizontalmente
2. Mas a altura não muda, então parecem MAIS ALTAS proporcionalmente
3. Isso cria ilusão de óptica: parecem MAIORES

Além disso, como já detectamos que o grid ultrapassa a altura em 3px,
qualquer clipping ou rounding pode amplificar esse efeito nas últimas questões.

SOLUÇÃO:
Manter a proporção de aspecto durante redimensionamento ou
aumentar o tamanho do bloco normalizado de 142px para algo maior.
""")

print("="*80 + "\n")
