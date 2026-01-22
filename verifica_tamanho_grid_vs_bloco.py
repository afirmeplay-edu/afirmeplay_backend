"""
Diagnóstico: Comparar tamanho do GRID com o tamanho REAL do bloco normalizado
Hipótese: O grid pode estar MAIOR que a imagem 142x473
"""

import json

# Configuração do bloco
BLOCK_WIDTH = 142  # px
BLOCK_HEIGHT = 473  # px
START_X = 32  # px
START_Y = 15  # px
LINE_HEIGHT = 18  # px
BUBBLE_SIZE = 15  # px (diâmetro)
BUBBLE_GAP = 4  # px
BUBBLE_SPACING = BUBBLE_SIZE + BUBBLE_GAP  # 19px

# Números de alternativas por questão
NUM_ALTERNATIVES = 4  # A, B, C, D

# Número de questões
NUM_QUESTIONS = 26

# ============= CÁLCULOS =============

print("\n" + "="*70)
print("DIAGNÓSTICO: Tamanho do GRID vs Tamanho do BLOCO")
print("="*70)

print(f"\n📐 DIMENSÕES DO BLOCO NORMALIZADO:")
print(f"   Largura:  {BLOCK_WIDTH}px")
print(f"   Altura:   {BLOCK_HEIGHT}px")

print(f"\n📍 CONFIGURAÇÃO DO GRID:")
print(f"   Start X:        {START_X}px")
print(f"   Start Y:        {START_Y}px")
print(f"   Line Height:    {LINE_HEIGHT}px")
print(f"   Bubble Size:    {BUBBLE_SIZE}px")
print(f"   Bubble Gap:     {BUBBLE_GAP}px")
print(f"   Bubble Spacing: {BUBBLE_SPACING}px (15+4)")

print(f"\n❓ QUESTÕES:")
print(f"   Total:      {NUM_QUESTIONS} questões")
print(f"   Alternativas por questão: {NUM_ALTERNATIVES} (A, B, C, D)")

# ============= CÁLCULOS HORIZONTAIS =============

print("\n" + "-"*70)
print("📊 ANÁLISE HORIZONTAL (ALTERNATIVAS A-D)")
print("-"*70)

# Posição X de cada alternativa
x_positions = []
for j in range(NUM_ALTERNATIVES):
    x = START_X + int(j * BUBBLE_SPACING) + BUBBLE_SIZE // 2
    x_positions.append(x)
    print(f"   {chr(65+j)}: X = {START_X} + {j}*{BUBBLE_SPACING} + {BUBBLE_SIZE//2} = {x}px")

max_x = max(x_positions)
last_bubble_right = max_x + BUBBLE_SIZE // 2
right_edge = last_bubble_right + 4  # pequeno padding

print(f"\n   Última bolha (D): Centro X = {max_x}px")
print(f"   Borda direita da última bolha: {last_bubble_right}px")
print(f"   Com padding: ~{right_edge}px")
print(f"\n   ✓ Bloco width = {BLOCK_WIDTH}px → Cabe OK na largura")

# ============= CÁLCULOS VERTICAIS =============

print("\n" + "-"*70)
print("📊 ANÁLISE VERTICAL (QUESTÕES 1-26)")
print("-"*70)

# Posição Y de cada questão
y_positions = []
for i in range(NUM_QUESTIONS):
    y = START_Y + int(i * LINE_HEIGHT)
    y_positions.append(y)
    if i == 0 or i == NUM_QUESTIONS // 2 or i == NUM_QUESTIONS - 1:
        print(f"   Q{i+1:2d}: Y = {START_Y} + {i:2d}*{LINE_HEIGHT} = {y:4d}px")
    elif i == 1:
        print(f"   ...")

max_y = max(y_positions)
last_bubble_bottom = max_y + BUBBLE_SIZE // 2
bottom_edge = last_bubble_bottom + 4  # pequeno padding

print(f"\n   Questão 26: Centro Y = {max_y}px")
print(f"   Borda inferior da última bolha: {last_bubble_bottom}px")
print(f"   Com padding: ~{bottom_edge}px")
print(f"\n   Bloco height = {BLOCK_HEIGHT}px")
print(f"   Espaço necessário para o grid: ~{bottom_edge}px")

if bottom_edge > BLOCK_HEIGHT:
    excess = bottom_edge - BLOCK_HEIGHT
    percent = (excess / BLOCK_HEIGHT) * 100
    print(f"\n   ❌ PROBLEMA DETECTADO:")
    print(f"      Grid EXCEDE o bloco em {excess}px ({percent:.1f}%)")
    print(f"      O grid está MAIOR que a imagem!")
else:
    margin = BLOCK_HEIGHT - bottom_edge
    percent = (margin / BLOCK_HEIGHT) * 100
    print(f"\n   ✓ Grid cabe dentro do bloco com {margin}px de margem ({percent:.1f}%)")

# ============= ANÁLISE DA PROGRESSÃO =============

print("\n" + "-"*70)
print("📈 PROGRESSÃO DAS QUESTÕES (Início, Meio, Fim)")
print("-"*70)

indices = [0, NUM_QUESTIONS // 2, NUM_QUESTIONS - 1]
for idx in indices:
    y = y_positions[idx]
    bubble_bottom = y + BUBBLE_SIZE // 2
    percent_used = (bubble_bottom / BLOCK_HEIGHT) * 100
    print(f"   Q{idx+1:2d}: Y={y:4d}px → Bottom={bubble_bottom:4d}px → {percent_used:5.1f}% do bloco")

# ============= CONCLUSÃO =============

print("\n" + "="*70)
print("CONCLUSÃO:")
print("="*70)

if bottom_edge > BLOCK_HEIGHT:
    print(f"""
    O GRID ESTÁ MAIOR QUE O BLOCO!
    
    - Bloco normalizado: {BLOCK_HEIGHT}px de altura
    - Grid necessário: ~{bottom_edge}px
    - Diferença: {excess}px ({percent:.1f}%)
    
    CAUSA RAIZ:
    Ao redimensionar a imagem para caber no bloco, o grid continua
    usando as mesmas proporções, mas a imagem é ENCOLHIDA.
    
    SOLUÇÃO POSSÍVEL:
    1. Recalcular line_height para caber no {BLOCK_HEIGHT}px disponível
       line_height ideal = {BLOCK_HEIGHT} / {NUM_QUESTIONS} = {BLOCK_HEIGHT/NUM_QUESTIONS:.2f}px
       
    2. OU aumentar o tamanho normalizado do bloco para {bottom_edge}px
""")
else:
    print(f"""
    O grid cabe dentro do bloco com folga.
    Margem: {margin}px ({percent:.1f}%)
    
    A questão é: por que as bolhas ficam maiores no fim?
    Pode ser perspectiva ou escala não linear na detecção.
""")

print("="*70 + "\n")

# ============= VERIFICAR COM ARQUIVO DE CONFIGURAÇÃO =============

print("🔍 Carregando arquivo de configuração do bloco 01...")
try:
    with open("app/services/cartao_resposta/block_01_coordinates_adjustment.json", "r") as f:
        config = json.load(f)
    
    print(f"\n📄 Configuração do arquivo:")
    print(f"   start_x: {config.get('start_x')}px")
    print(f"   start_y: {config.get('start_y')}px")
    print(f"   line_height: {config.get('line_height')}px")
    print(f"   block_width_ref: {config.get('block_width_ref')}px")
    print(f"   block_height_ref: {config.get('block_height_ref')}px")
    print(f"   bubble_size: {config.get('bubble_size')}px")
    print(f"   bubble_gap: {config.get('bubble_gap')}px")
    
except Exception as e:
    print(f"❌ Erro ao carregar arquivo: {e}")

print("\n" + "="*70)
