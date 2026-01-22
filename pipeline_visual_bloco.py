"""
Diagnóstico VISUAL: Entender como a imagem é cortada, redimensionada e o grid aplicado

Pipeline:
1. Imagem original: 827x1169px (A4 normalizado com warpPerspective)
2. Extrai ROI do bloco: ~163x473px (coordenadas de triângulos)
3. Redimensiona para: 142x473px (block_width_ref x block_height_ref)
4. Aplica grid: start_x=32, start_y=15, line_height=18, bubble_spacing=19px

PROBLEMA: Durante redimensionamento de 163px → 142px, a escala fica não uniforme?
"""

import math

# ============= PIPELINE VISUAL =============

print("\n" + "="*80)
print("PIPELINE DE PROCESSAMENTO DO BLOCO")
print("="*80)

# Passo 1: Imagem original normalizada
ORIGINAL_WIDTH = 827
ORIGINAL_HEIGHT = 1169
print(f"\n1️⃣  IMAGEM ORIGINAL (A4 com warpPerspective):")
print(f"   {ORIGINAL_WIDTH} x {ORIGINAL_HEIGHT}px (aspecto: {ORIGINAL_WIDTH/ORIGINAL_HEIGHT:.4f})")

# Passo 2: ROI do bloco (coordenadas de triângulos)
# Um bloco típico tem ~163px de largura
BLOCK_ROI_WIDTH_EXTRACTED = 163  # pixel width of ROI before resize
BLOCK_ROI_HEIGHT_EXTRACTED = 473  # pixel height (full height)
print(f"\n2️⃣  ROI EXTRAÍDO DO BLOCO (coordenadas de triângulos):")
print(f"   {BLOCK_ROI_WIDTH_EXTRACTED} x {BLOCK_ROI_HEIGHT_EXTRACTED}px (aspecto: {BLOCK_ROI_WIDTH_EXTRACTED/BLOCK_ROI_HEIGHT_EXTRACTED:.4f})")

# Passo 3: Redimensionamento
BLOCK_WIDTH_TARGET = 142
BLOCK_HEIGHT_TARGET = 473
print(f"\n3️⃣  REDIMENSIONADO PARA (block_width_ref x block_height_ref):")
print(f"   {BLOCK_WIDTH_TARGET} x {BLOCK_HEIGHT_TARGET}px (aspecto: {BLOCK_WIDTH_TARGET/BLOCK_HEIGHT_TARGET:.4f})")

# Calcular fatores de escala
scale_x = BLOCK_WIDTH_TARGET / BLOCK_ROI_WIDTH_EXTRACTED
scale_y = BLOCK_HEIGHT_TARGET / BLOCK_ROI_HEIGHT_EXTRACTED

print(f"\n   Fatores de escala:")
print(f"   - Largura:  {BLOCK_ROI_WIDTH_EXTRACTED}px → {BLOCK_WIDTH_TARGET}px (fator: {scale_x:.4f})")
print(f"   - Altura:   {BLOCK_ROI_HEIGHT_EXTRACTED}px → {BLOCK_HEIGHT_TARGET}px (fator: {scale_y:.4f})")
print(f"   - Diferença entre escalas: {abs(scale_x - scale_y):.6f}")

if abs(scale_x - scale_y) > 0.001:
    print(f"   ⚠️  ESCALAS DIFERENTES! Causa distorção não uniforme!")
else:
    print(f"   ✓ Escalas uniformes (aceita escala uniforme)")

# ============= GRID NA IMAGEM REDIMENSIONADA =============

print("\n" + "-"*80)
print("GRID APLICADO NA IMAGEM REDIMENSIONADA (142x473)")
print("-"*80)

START_X = 32
START_Y = 15
LINE_HEIGHT = 18
BUBBLE_SIZE = 15
BUBBLE_GAP = 4
NUM_QUESTIONS = 26

# Calcular espaço ocupado pelo grid
first_q_y = START_Y + 0 * LINE_HEIGHT  # 15px
last_q_y = START_Y + (NUM_QUESTIONS - 1) * LINE_HEIGHT  # 465px
grid_height = last_q_y - first_q_y + BUBBLE_SIZE  # 15 → 465 + 15 = 480px
grid_width = 32 + 3*19 + BUBBLE_SIZE // 2 + 4  # ~107px

print(f"\n   Grid span:")
print(f"   - Horizontal: {START_X}px → ~{32 + 3*19 + BUBBLE_SIZE}px (total: ~{grid_width}px)")
print(f"   - Vertical:   {first_q_y}px → {last_q_y + BUBBLE_SIZE//2}px (total: ~{grid_height}px)")

print(f"\n   Bloco tamanho: {BLOCK_WIDTH_TARGET} x {BLOCK_HEIGHT_TARGET}px")

if grid_height > BLOCK_HEIGHT_TARGET:
    excess = grid_height - BLOCK_HEIGHT_TARGET
    print(f"\n   ❌ Grid EXCEDE altura em {excess}px!")
    print(f"      Isso significa que a última bolha sai do bloco")
    print(f"      Qualquer clipping ou scaling causará desalinhamento")
else:
    print(f"\n   ✓ Grid cabe dentro da altura")

# ============= HIPÓTESE: POR QUE FICA MAIOR NO FIM =============

print("\n" + "="*80)
print("HIPÓTESE: POR QUE AS BOLHAS FICAM MAIORES NO FIM?")
print("="*80)

print("""
Possíveis razões:

1️⃣  CLIPPING DE IMAGEM:
    Se a imagem extraída tem 473px de altura mas o bloco normalizado
    também tem 473px, não há espaço para margem. Qualquer rounding
    ou scaling pode causar clipping nas últimas bolhas.
    
    Quando clipa-se a borda, a imagem parece maior.

2️⃣  REDIMENSIONAMENTO COM INTERPOLAÇÃO:
    cv2.resize() usa interpolação (padrão: INTER_LINEAR).
    Com 163→142px, há resampling que pode amplificar pixels no fim.
    
    Se a última bolha é parcialmente clippada, sua detecção 
    fica ampliada no resultado final.

3️⃣  DETECÇÃO DE BOLHAS EM BORDAS:
    HoughCircles pode funcionar diferente em bordas da imagem.
    Pixels clippados podem resultar em círculos detectados maiores.

4️⃣  PERSPECTIVA RESIDUAL:
    Mesmo após warpPerspective, pode haver perspectiva residual
    nos triângulos que define o bloco.
    
    Isso causaria escalagem não linear: mais comprimido no topo,
    mais esticado no fim.
""")

# ============= SOLUÇÃO SUGERIDA =============

print("\n" + "="*80)
print("SOLUÇÕES SUGERIDAS")
print("="*80)

# Opção 1: Aumentar altura do bloco
new_height = 476
print(f"""
OPÇÃO 1: AUMENTAR ALTURA DO BLOCO
   De:  {BLOCK_HEIGHT_TARGET}px
   Para: {new_height}px (grid_height = ~476px)
   
   Isso garante que não haja clipping.
   Desvantagem: Pode alterar proporções esperadas.
""")

# Opção 2: Reduzir line_height
ideal_line_height = BLOCK_HEIGHT_TARGET / NUM_QUESTIONS
print(f"""
OPÇÃO 2: REDUZIR LINE_HEIGHT
   De:  {LINE_HEIGHT}px
   Para: {ideal_line_height:.2f}px (idealmente {round(ideal_line_height)}px)
   
   Isso reduz o espaçamento vertical para caber exatamente.
   Desvantagem: Questões ficarão mais compactadas.
   
   Com line_height={round(ideal_line_height)}px:
   - Q1:  Y = 15px
   - Q26: Y = 15 + 25*{round(ideal_line_height)} = {15 + 25*round(ideal_line_height)}px
   - Total: {15 + 25*round(ideal_line_height) + BUBBLE_SIZE//2}px
""")

# Opção 3: Aumentar tamanho normalizado da página
print(f"""
OPÇÃO 3: AUMENTAR TAMANHO NORMALIZADO (bloco não reduz muito)
   Aumentar o bloco extraído antes de redimensionar
   Isso reduz o fator de escala:
   
   163px → 142px: fator {scale_x:.4f}
   170px → 142px: fator {142/170:.4f}
   
   Desvantagem: Afeta todo o pipeline de detecção.
""")

print("="*80 + "\n")
