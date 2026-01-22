"""
Script de teste: Validar que o novo tamanho 155x473 melhora a situação
"""

import json
import os

print("\n" + "="*80)
print("VALIDAÇÃO DAS MUDANÇAS - Antes de testar com imagem real")
print("="*80)

# 1. Verificar JSON files
print("\n1️⃣  VERIFICANDO ARQUIVOS JSON:")
print("-" * 80)

json_files = [
    "app/services/cartao_resposta/block_01_coordinates_adjustment.json",
    "app/services/cartao_resposta/block_02_coordinates_adjustment.json",
    "app/services/cartao_resposta/block_03_coordinates_adjustment.json",
    "app/services/cartao_resposta/block_04_coordinates_adjustment.json",
]

all_correct = True
for json_file in json_files:
    if os.path.exists(json_file):
        with open(json_file, 'r') as f:
            config = json.load(f)
        
        block_num = config.get('block_num')
        block_width = config.get('block_width_ref')
        start_x = config.get('start_x')
        line_height = config.get('line_height')
        
        is_correct = (block_width == 155 and start_x == 34 and line_height == 18)
        status = "✅" if is_correct else "❌"
        
        print(f"{status} Block {block_num}: width={block_width} (exp 155), start_x={start_x} (exp 34)")
        
        if not is_correct:
            all_correct = False
    else:
        print(f"❌ {json_file} - ARQUIVO NÃO ENCONTRADO")
        all_correct = False

# 2. Verificar correction_n.py
print("\n2️⃣  VERIFICANDO correction_n.py:")
print("-" * 80)

correction_file = "app/services/cartao_resposta/correction_n.py"
if os.path.exists(correction_file):
    with open(correction_file, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    if "STANDARD_BLOCK_WIDTH = 155" in content:
        print("✅ STANDARD_BLOCK_WIDTH = 155 encontrado")
    else:
        print("❌ STANDARD_BLOCK_WIDTH = 155 NÃO encontrado")
        all_correct = False
    
    if "STANDARD_BLOCK_HEIGHT = 473" in content:
        print("✅ STANDARD_BLOCK_HEIGHT = 473 encontrado")
    else:
        print("❌ STANDARD_BLOCK_HEIGHT = 473 NÃO encontrado")
        all_correct = False
else:
    print("❌ correction_n.py não encontrado")
    all_correct = False

# 3. Calcular novo grid
print("\n3️⃣  VALIDAÇÃO DO NOVO GRID:")
print("-" * 80)

NEW_BLOCK_WIDTH = 155
NEW_BLOCK_HEIGHT = 473
START_X = 34
START_Y = 15
LINE_HEIGHT = 18
NUM_QUESTIONS = 26
BUBBLE_SIZE = 15

# Posição da última questão
last_q_y = START_Y + (NUM_QUESTIONS - 1) * LINE_HEIGHT  # 465px
last_bubble_bottom = last_q_y + BUBBLE_SIZE // 2  # 472px
grid_exceed = last_bubble_bottom - NEW_BLOCK_HEIGHT  # -1px (margem)

print(f"Bloco: {NEW_BLOCK_WIDTH} x {NEW_BLOCK_HEIGHT}px")
print(f"Q26 Y posição: {last_q_y}px")
print(f"Q26 bolha borda inferior: {last_bubble_bottom}px")
print(f"Resultado: {'✅ CABE (+1px margem)' if grid_exceed < 0 else '❌ ULTRAPASSA (+' + str(grid_exceed) + 'px)'}")

# 4. Comparar escalas
print("\n4️⃣  COMPARAÇÃO DE ESCALAS:")
print("-" * 80)

ROI_WIDTH = 163
ROI_HEIGHT = 473

# Escala antiga
old_scale_x = 142 / ROI_WIDTH  # 0.8712
old_scale_y = 473 / ROI_HEIGHT  # 1.0
old_diff = abs(old_scale_x - old_scale_y)  # 0.1288

# Escala nova
new_scale_x = 155 / ROI_WIDTH  # 0.9509
new_scale_y = 473 / ROI_HEIGHT  # 1.0
new_diff = abs(new_scale_x - new_scale_y)  # 0.0491

print(f"Escala ANTIGA (142x473):")
print(f"  X: {old_scale_x:.6f}")
print(f"  Y: {old_scale_y:.6f}")
print(f"  Diferença: {old_diff:.6f} ❌ NÃO UNIFORME")

print(f"\nEscala NOVA (155x473):")
print(f"  X: {new_scale_x:.6f}")
print(f"  Y: {new_scale_y:.6f}")
print(f"  Diferença: {new_diff:.6f} ✅ MELHORADO")

improvement = ((old_diff - new_diff) / old_diff) * 100
print(f"\nMelhoria: {improvement:.1f}% (diferença reduzida em {old_diff - new_diff:.6f})")

# 5. Resumo final
print("\n" + "="*80)
if all_correct:
    print("✅ TODAS AS MUDANÇAS FORAM APLICADAS CORRETAMENTE!")
    print("\nPróximos passos:")
    print("1. Usar uma imagem real (com 26 questões marcadas)")
    print("2. Executar a correção normalmente")
    print("3. Verificar fill_ratios: Q1 e Q26 devem ser similares (não variar de 0.24 → 0.84)")
    print("4. Verificar debug images: Bolhas visualmente alinhadas do início ao fim")
    print("5. Se OK → fazer commit")
else:
    print("❌ ALGUMAS MUDANÇAS NÃO FORAM APLICADAS CORRETAMENTE!")
    print("Revise manualmente os arquivos acima.")

print("="*80 + "\n")
