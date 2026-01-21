#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para comparar valores esperados vs. reais
Testa ambos os cenários (14px e 18px) e recomenda qual usar
"""

import json
import numpy as np
from pathlib import Path
from typing import Dict, List

class ExpectedVsRealAnalyzer:
    def __init__(self):
        self.results = {}
    
    def load_all_configs(self) -> Dict[int, Dict]:
        """Carrega configurações de todos os blocos"""
        configs = {}
        
        for block_num in range(1, 5):
            config_file = f"app/services/cartao_resposta/block_{block_num:02d}_coordinates_adjustment.json"
            
            if Path(config_file).exists():
                with open(config_file, 'r') as f:
                    configs[block_num] = json.load(f)
        
        return configs
    
    def analyze_block(self, block_num: int, config: Dict) -> Dict:
        """Analisa um bloco específico"""
        num_questions = 26
        start_y = config.get('start_y', 15)
        line_height_json = config.get('line_height', 14)
        block_height = config.get('block_height_ref', 473)
        
        # Cálculos
        padding = 16  # 8px top + 8px bottom
        usable_height = block_height - padding
        ideal_line_height = usable_height / num_questions
        
        # Determinar qual será usado
        use_line_height = round(ideal_line_height) if abs(line_height_json - ideal_line_height) > 0.5 else line_height_json
        
        result = {
            'block_num': block_num,
            'line_height_json': line_height_json,
            'ideal_line_height': ideal_line_height,
            'use_line_height': use_line_height,
            'will_adjust': use_line_height != line_height_json,
            'accumulated_diff': 25 * (use_line_height - line_height_json),
            'positions': {}
        }
        
        # Calcular posições para questões-chave
        for q_idx in [0, 6, 13, 19, 25]:
            q_num = q_idx + 1
            y_json = start_y + q_idx * line_height_json
            y_expected = start_y + q_idx * use_line_height
            
            result['positions'][q_num] = {
                'index': q_idx,
                'y_with_14px': y_json,
                'y_with_18px': start_y + q_idx * 18,
                'y_final': y_expected
            }
        
        return result
    
    def print_summary_table(self, all_results: Dict[int, Dict]):
        """Imprime tabela comparativa"""
        print("\n" + "="*70)
        print("📊 RESUMO POR BLOCO")
        print("="*70)
        
        print("\nBLOCO │ LINE_H │ IDEAL │ USA │ AJUSTE │ DIFER.ACUM")
        print("─────┼────────┼───────┼─────┼────────┼───────────")
        
        for block_num in sorted(all_results.keys()):
            r = all_results[block_num]
            ajuste_icon = "❌" if r['will_adjust'] else "✅"
            
            print(f"  {r['block_num']}  │  {r['line_height_json']:2d}px │ {r['ideal_line_height']:5.2f} │ {r['use_line_height']:2d}px │ {ajuste_icon}     │  +{r['accumulated_diff']}px")
    
    def print_position_comparison(self, all_results: Dict[int, Dict]):
        """Imprime comparação de posições"""
        print("\n" + "="*70)
        print("📍 POSIÇÕES ESPERADAS (questões selecionadas)")
        print("="*70)
        
        for block_num in sorted(all_results.keys()):
            r = all_results[block_num]
            
            print(f"\n🔹 BLOCO {block_num}:")
            print(f"   Usando line_height: {r['use_line_height']}px")
            print(f"\n   Questão │ Y com 14px │ Y com 18px │ Y Final (usado)")
            print(f"   ────────┼────────────┼────────────┼────────────────")
            
            for q_num in sorted(r['positions'].keys()):
                pos = r['positions'][q_num]
                print(f"     Q{q_num:2d}   │  {pos['y_with_14px']:3d}px    │  {pos['y_with_18px']:3d}px    │  {pos['y_final']:3d}px")
    
    def print_recommendations(self, all_results: Dict[int, Dict]):
        """Imprime recomendações"""
        print("\n" + "="*70)
        print("🎯 RECOMENDAÇÕES")
        print("="*70)
        
        blocks_with_adjust = [r for r in all_results.values() if r['will_adjust']]
        
        if blocks_with_adjust:
            print(f"\n❌ ENCONTRADO PROBLEMA:")
            print(f"   {len(blocks_with_adjust)} bloco(s) está(ão) com ajuste automático ativado")
            
            for r in blocks_with_adjust:
                print(f"\n   Bloco {r['block_num']}:")
                print(f"   - JSON especifica:     {r['line_height_json']}px")
                print(f"   - Código calcula:      {r['ideal_line_height']:.2f}px → {r['use_line_height']}px")
                print(f"   - Diferença acumulada: +{r['accumulated_diff']}px até Q26")
            
            print(f"\n✅ SOLUÇÃO RECOMENDADA:")
            print(f"   Desabilitar o ajuste dinâmico do line_height em correction_n.py")
            print(f"   E usar o valor calibrado do JSON diretamente: {all_results[1]['line_height_json']}px")
            
        else:
            print(f"\n✅ Nenhum ajuste detectado - Tudo em ordem!")
    
    def run(self):
        """Executa análise completa"""
        print("\n" + "="*70)
        print("🔍 ANÁLISE: ESPERADO vs. REAL")
        print("="*70)
        
        configs = self.load_all_configs()
        
        if not configs:
            print("\n❌ Nenhuma configuração encontrada")
            return
        
        print(f"\n✅ Encontradas {len(configs)} configurações de blocos")
        
        # Analisar cada bloco
        all_results = {}
        for block_num, config in sorted(configs.items()):
            result = self.analyze_block(block_num, config)
            all_results[block_num] = result
        
        # Imprimir resultados
        self.print_summary_table(all_results)
        self.print_position_comparison(all_results)
        self.print_recommendations(all_results)
        
        # Armazenar para análise posterior
        self.results = all_results


class ActionPlan:
    """Plano de ação baseado nos resultados"""
    
    @staticmethod
    def print_detailed_action_plan(analyzer: ExpectedVsRealAnalyzer):
        """Imprime plano de ação detalhado"""
        print("\n" + "="*70)
        print("📋 PLANO DE AÇÃO")
        print("="*70)
        
        blocks_with_adjust = [r for r in analyzer.results.values() if r['will_adjust']]
        
        if not blocks_with_adjust:
            print("\n✅ Nenhuma ação necessária - Sistema está funcionando corretamente!")
            return
        
        print(f"""
🔧 PASSO 1: VERIFICAR COM IMAGENS REAIS
   ─────────────────────────────────────
   1. Rodar: python measure_real_spacing.py
      → Isso vai detectar bolhas reais e medir espaçamento
   
   2. Rodar: python generate_grid_overlay.py
      → Gera imagens com overlay das grades
   
   3. INSPECIONAR VISUALMENTE:
      - Abrir debug_corrections/grid_overlay/block_*_grid_*.jpg
      - Ver se as bolhas reais alinham mais com a grade VERDE (14px)
        ou VERMELHA (18px)

🔧 PASSO 2: TOMAR DECISÃO
   ──────────────────────
   SE bolhas alinham com VERDE (14px):
      → Desabilitar ajuste dinâmico (veja instrução abaixo)
   
   SE bolhas alinham com VERMELHO (18px):
      → Atualizar JSON para line_height=18px
      → Desabilitar ajuste dinâmico

🔧 PASSO 3: IMPLEMENTAR SOLUÇÃO (Opção A - Desabilitar ajuste)
   ───────────────────────────────────────────────────────────
   Arquivo: app/services/cartao_resposta/correction_n.py
   Linha: 2595-2600
   
   ANTES:
   ────────────────────────────────────────────────────────
   if abs(line_height - ideal_line_height) > 0.5:
       adjusted_line_height = round(ideal_line_height)
       use_line_height = adjusted_line_height
   
   DEPOIS:
   ────────────────────────────────────────────────────────
   # ⚠️ AJUSTE DESABILIZADO - usar valor do JSON diretamente
   # if abs(line_height - ideal_line_height) > 0.5:
   #     adjusted_line_height = round(ideal_line_height)
   #     use_line_height = adjusted_line_height
   
   use_line_height = line_height  # Sempre usar valor do JSON

🔧 PASSO 4: TESTAR
   ────────────────
   1. Rodar a aplicação novamente: python run.py
   2. Submeter uma imagem de teste
   3. Verificar se o alinhamento melhorou
   4. Comparar fill_ratios no log (devem ser mais consistentes)

📊 RESULTADOS ESPERADOS:
   ─────────────────────
   - fill_ratios mais consistentes (não crescente de Q1 até Q26)
   - Menos avisos de "múltiplas bolhas marcadas"
   - Detecção mais precisa de respostas
        """)


def main():
    analyzer = ExpectedVsRealAnalyzer()
    analyzer.run()
    
    ActionPlan.print_detailed_action_plan(analyzer)

if __name__ == "__main__":
    main()
