#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ÍNDICE DE SCRIPTS DE DIAGNÓSTICO
================================

Todos os scripts necessários para diagnosticar e resolver
o problema de desalinhamento da grade.
"""

scripts = {
    "quick_scenario_test.py": {
        "nome": "🚀 COMECE AQUI",
        "descricao": "Simulador visual rápido - mostra o impacto de 14px vs 18px",
        "comando": "python quick_scenario_test.py",
        "tempo": "< 1 segundo",
        "requer_imagens": False,
        "saida": "Texto no terminal com comparação visual"
    },
    
    "diagnose_grid_alignment.py": {
        "nome": "📊 Diagnóstico Teórico",
        "descricao": "Análise dos parâmetros e do ajuste dinâmico",
        "comando": "python diagnose_grid_alignment.py",
        "tempo": "< 1 segundo",
        "requer_imagens": False,
        "saida": "Relatório com análise teórica dos valores"
    },
    
    "measure_real_spacing.py": {
        "nome": "📏 Medição Real",
        "descricao": "Detecta bolhas reais e mede espaçamento",
        "comando": "python measure_real_spacing.py",
        "tempo": "2-5 segundos",
        "requer_imagens": True,
        "saida": "Posições das bolhas e estatísticas de espaçamento"
    },
    
    "generate_grid_overlay.py": {
        "nome": "🎨 Visualização",
        "descricao": "Gera imagens com overlay de grades (VERDE=14px, VERMELHO=18px)",
        "comando": "python generate_grid_overlay.py",
        "tempo": "2-5 segundos",
        "requer_imagens": True,
        "saida": "Imagens em debug_corrections/grid_overlay/"
    },
    
    "compare_expected_vs_real.py": {
        "nome": "🔍 Comparação & Ação",
        "descricao": "Análise comparativa e plano de ação detalhado",
        "comando": "python compare_expected_vs_real.py",
        "tempo": "< 1 segundo",
        "requer_imagens": False,
        "saida": "Recomendação com instruções específicas"
    },
    
    "run_full_diagnostic.py": {
        "nome": "🚀 Diagnóstico Completo",
        "descricao": "Executa todos os scripts em sequência",
        "comando": "python run_full_diagnostic.py",
        "tempo": "5-10 segundos",
        "requer_imagens": False,  # Tenta adaptar-se
        "saida": "Relatório consolidado com próximas etapas"
    }
}

def print_index():
    print("""
╔════════════════════════════════════════════════════════════════════╗
║  📚 ÍNDICE DE SCRIPTS DE DIAGNÓSTICO                              ║
║     Alinhamento da Grade - Sistema de Detecção de Bolhas          ║
╚════════════════════════════════════════════════════════════════════╝
    """)
    
    print("\n🎯 ROTEIROS RECOMENDADOS:\n")
    
    print("┌─ ROTEIRO RÁPIDO (5 minutos) ─────────────────────────┐")
    print("│                                                       │")
    print("│  1️⃣  python quick_scenario_test.py                 │")
    print("│  2️⃣  python diagnose_grid_alignment.py             │")
    print("│  3️⃣  python compare_expected_vs_real.py            │")
    print("│                                                       │")
    print("└───────────────────────────────────────────────────────┘")
    
    print("\n┌─ ROTEIRO COMPLETO (15-20 minutos) ────────────────────┐")
    print("│                                                        │")
    print("│  1️⃣  python run_full_diagnostic.py                  │")
    print("│      (Executa automaticamente os próximos 3)          │")
    print("│                                                        │")
    print("│  2️⃣  VISUALIZAR em: debug_corrections/grid_overlay/  │")
    print("│      block_*_grid_comparison.jpg                      │")
    print("│                                                        │")
    print("│  3️⃣  DECIDIR baseado nas visualizações               │")
    print("│                                                        │")
    print("│  4️⃣  IMPLEMENTAR solução em correction_n.py          │")
    print("│                                                        │")
    print("│  5️⃣  TESTAR com python run.py                        │")
    print("│                                                        │")
    print("└────────────────────────────────────────────────────────┘")
    
    print("\n\n📖 DETALHES DOS SCRIPTS:\n")
    
    for i, (script_name, info) in enumerate(scripts.items(), 1):
        status = "✅" if not info['requer_imagens'] else "📸"
        print(f"{i}. {info['nome']}")
        print(f"   Script: {script_name}")
        print(f"   Descrição: {info['descricao']}")
        print(f"   Comando: {info['comando']}")
        print(f"   Tempo: {info['tempo']}")
        print(f"   Requer imagens: {'Sim 📸' if info['requer_imagens'] else 'Não ' + status}")
        print(f"   Saída: {info['saida']}")
        print()
    
    print("\n" + "="*70)
    print("🔑 COMO USAR\n")
    print("""
1. OPÇÃO A: Diagnóstico Rápido (recomendado primeiro)
   ─────────────────────────────────────────────────
   $ python quick_scenario_test.py
   $ python diagnose_grid_alignment.py
   $ python compare_expected_vs_real.py
   
   Tempo: ~5 minutos
   Não precisa de imagens de debug

2. OPÇÃO B: Diagnóstico Completo (com visualizações)
   ──────────────────────────────────────────────────
   $ python run_full_diagnostic.py
   
   Depois:
   - Abrir visualizações em debug_corrections/grid_overlay/
   - Comparar visualmente (VERDE 14px vs VERMELHO 18px)
   
   Tempo: ~10-15 minutos
   Precisa de imagens de debug (gerar com python run.py)

3. OPÇÃO C: Passo a Passo (máximo controle)
   ─────────────────────────────────────────
   $ python quick_scenario_test.py      # Entender o problema
   $ python measure_real_spacing.py      # Medir realidade
   $ python generate_grid_overlay.py     # Visualizar
   $ python compare_expected_vs_real.py  # Decidir
   
   Tempo: ~15-20 minutos
    """)
    
    print("\n" + "="*70)
    print("⚙️  PRÉ-REQUISITOS\n")
    print("""
✅ Instalado:
   - Python 3.7+
   - cv2 (OpenCV)
   - numpy
   
⚠️  Para Opção B e C (com visualizações):
   - Execute primeiro: python run.py
   - Isso vai gerar imagens em debug_corrections/
   
📂 Estrutura esperada:
   .
   ├── diagnose_grid_alignment.py
   ├── measure_real_spacing.py
   ├── generate_grid_overlay.py
   ├── compare_expected_vs_real.py
   ├── run_full_diagnostic.py
   ├── quick_scenario_test.py
   ├── app/services/cartao_resposta/
   │   ├── block_01_coordinates_adjustment.json
   │   ├── block_02_coordinates_adjustment.json
   │   ├── block_03_coordinates_adjustment.json
   │   ├── block_04_coordinates_adjustment.json
   │   └── correction_n.py
   └── debug_corrections/  (gerado ao rodar python run.py)
       ├── *_block_*_real*.jpg
       └── grid_overlay/  (gerado pelos scripts)
    """)
    
    print("\n" + "="*70)
    print("📋 INTERPRETAÇÃO DOS RESULTADOS\n")
    print("""
CENÁRIO 1: Bolhas alinham com VERDE (14px)
─────────────────────────────────────────
✅ Conclusão: line_height está incorreto (deveria ser 14px)
🔧 Ação: Desabilitar ajuste dinâmico em correction_n.py linha ~2595

CENÁRIO 2: Bolhas alinham com VERMELHO (18px)
──────────────────────────────────────────────
✅ Conclusão: ajuste está correto (18px é o valor certo)
🔧 Ação: Aceitar o ajuste OU atualizar JSON para 18px

CENÁRIO 3: Desalinhamento progressivo
──────────────────────────────────────
⚠️  Possível causa: Distorção vertical na normalização perspectiva
🔧 Ação: Investigar warpPerspective em correction_n.py linha ~1010
    """)
    
    print("\n" + "="*70)
    print("🆘 AJUDA RÁPIDA\n")
    print("""
P: Por onde começo?
R: Execute: python quick_scenario_test.py

P: Preciso de imagens?
R: Não para diagnóstico rápido, sim para visualizações.
   Gere com: python run.py (uma vez)

P: Qual script escolho?
R: Veja os "ROTEIROS RECOMENDADOS" acima.

P: As imagens estão em branco?
R: Problemas comuns:
   - Diretório debug_corrections/ não existe
   - Parâmetros de overlay incorretos
   - Dimensões de imagem fora do esperado

P: Quais são os valores corretos?
R: Execute compare_expected_vs_real.py - tem recomendação específica
    """)
    
    print("\n" + "="*70)
    print("📞 PRÓXIMAS ETAPAS\n")
    print("""
1. Escolha um dos roteiros acima
2. Execute os scripts na ordem
3. Leia os resultados com atenção
4. Siga o plano de ação específico
5. Implemente a solução em correction_n.py
6. Teste com python run.py
7. Verifique se fill_ratios ficaram consistentes
    """)

if __name__ == "__main__":
    print_index()
