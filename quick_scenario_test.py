#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Quick Tester - Script rápido para testar ambos os cenários
Simula o que aconteceria se usássemos 14px vs 18px
"""

def print_banner():
    print("""
╔════════════════════════════════════════════════════════════════════╗
║              📊 SIMULADOR: 14px vs 18px                           ║
║              Teste rápido do impacto do line_height                ║
╚════════════════════════════════════════════════════════════════════╝
    """)

def simulate_scenario():
    print_banner()
    
    # Parâmetros
    start_y = 15
    num_questions = 26
    
    print("\n📋 PARÂMETROS:")
    print(f"   start_y = {start_y}px")
    print(f"   Número de questões = {num_questions}")
    print(f"   Bubble size = 15px, gap = 4px, spacing = 19px")
    
    # Cenário 1: 14px
    print(f"\n{'='*70}")
    print(f"CENÁRIO 1️⃣  : line_height = 14px (JSON original)")
    print(f"{'='*70}")
    
    print(f"\nPosições das primeiras 10 questões:")
    print(f"{'Q':3s} │ Y (px)")
    print(f"────┼────────")
    
    positions_14 = []
    for q in range(1, 11):
        y = start_y + (q - 1) * 14
        positions_14.append(y)
        print(f"{q:2d}  │ {y:3d}")
    
    print(f"...\n")
    for q in [20, 21, 25, 26]:
        y = start_y + (q - 1) * 14
        positions_14.append(y)
        print(f"{q:2d}  │ {y:3d}")
    
    final_y_14 = start_y + (num_questions - 1) * 14
    print(f"\nÚltima questão (Q26) em Y = {final_y_14}px")
    print(f"Altura total ocupada: {final_y_14 - start_y}px")
    
    # Cenário 2: 18px
    print(f"\n{'='*70}")
    print(f"CENÁRIO 2️⃣  : line_height = 18px (ajuste dinâmico)")
    print(f"{'='*70}")
    
    print(f"\nPosições das primeiras 10 questões:")
    print(f"{'Q':3s} │ Y (px)")
    print(f"────┼────────")
    
    positions_18 = []
    for q in range(1, 11):
        y = start_y + (q - 1) * 18
        positions_18.append(y)
        print(f"{q:2d}  │ {y:3d}")
    
    print(f"...\n")
    for q in [20, 21, 25, 26]:
        y = start_y + (q - 1) * 18
        positions_18.append(y)
        print(f"{q:2d}  │ {y:3d}")
    
    final_y_18 = start_y + (num_questions - 1) * 18
    print(f"\nÚltima questão (Q26) em Y = {final_y_18}px")
    print(f"Altura total ocupada: {final_y_18 - start_y}px")
    
    # Comparação
    print(f"\n{'='*70}")
    print(f"📊 COMPARAÇÃO")
    print(f"{'='*70}")
    
    print(f"\n{'Questão':<10} │ {'Y (14px)':<10} │ {'Y (18px)':<10} │ {'Diferença':<10}")
    print(f"{'──────────':<10} ┼ {'──────────':<10} ┼ {'──────────':<10} ┼ {'──────────':<10}")
    
    comparison_questions = [1, 7, 14, 20, 26]
    for q in comparison_questions:
        y_14 = start_y + (q - 1) * 14
        y_18 = start_y + (q - 1) * 18
        diff = y_18 - y_14
        marker = "🔴" if q == 26 else "  "
        print(f"Q{q:<8} {marker} │ {y_14:<10} │ {y_18:<10} │ +{diff:<8}")
    
    # Diferença acumulada
    accumulated_diff = (num_questions - 1) * (18 - 14)
    print(f"\n⚠️  DIFERENÇA ACUMULADA (Q1 até Q26): +{accumulated_diff}px")
    print(f"   Isso significa que Q26 está {accumulated_diff}px mais para baixo com 18px!")
    
    # Impacto visual
    print(f"\n{'='*70}")
    print(f"💥 IMPACTO VISUAL")
    print(f"{'='*70}")
    
    print(f"""
Com line_height = 14px:
  ┌────────────────────────┐
  │ Q1 ●●●●     Y=15px     │  ← Alinhado
  │    (gap)               │
  │ Q2 ●●●●     Y=29px     │  ← Alinhado
  │ ... mais {num_questions-2} questões |
  │ Q26 ●●●●    Y={final_y_14}px    │  ← Alinhado
  └────────────────────────┘

Com line_height = 18px:
  ┌────────────────────────┐
  │ Q1 ●●●●     Y=15px     │  ← Alinhado
  │    (gap MAIOR)         │
  │ Q2 ●●●●     Y=33px     │  ← Espaço maior
  │ ... mais {num_questions-2} questões |
  │ Q26 ●●●●    Y={final_y_18}px    │  ← Espichado para baixo!
  └────────────────────────┘
           ↑
      Desalinhamento progressivo
    """)
    
    # Recomendação
    print(f"\n{'='*70}")
    print(f"🎯 RECOMENDAÇÃO")
    print(f"{'='*70}")
    
    print(f"""
📌 SE as bolhas reais estão mais próximas de Y=365px (Q26):
   → Usar 14px ✅
   → Desabilitar ajuste dinâmico
   
📌 SE as bolhas reais estão mais próximas de Y=465px (Q26):
   → Usar 18px ✅
   → Atualizar JSON ou aceitar o ajuste

💡 DICA: Use a visualização com overlay (grid_overlay) para comparar!
    """)

if __name__ == "__main__":
    simulate_scenario()
