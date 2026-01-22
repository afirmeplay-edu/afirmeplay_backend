#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script de Diagnóstico Executivo
Executa todos os testes em sequência e gera relatório final
"""

import subprocess
import sys
from pathlib import Path

class DiagnosticRunner:
    def __init__(self):
        self.results = {}
    
    def print_header(self, title: str):
        """Imprime header formatado"""
        print("\n" + "="*70)
        print(f"🔧 {title}")
        print("="*70)
    
    def run_script(self, script_name: str, description: str) -> bool:
        """Executa um script Python"""
        self.print_header(description)
        
        script_path = Path(script_name)
        
        if not script_path.exists():
            print(f"❌ Script não encontrado: {script_name}")
            return False
        
        try:
            result = subprocess.run([sys.executable, script_name], 
                                  capture_output=False, 
                                  text=True)
            self.results[script_name] = result.returncode == 0
            return result.returncode == 0
        
        except Exception as e:
            print(f"❌ Erro ao executar {script_name}: {str(e)}")
            self.results[script_name] = False
            return False
    
    def print_final_report(self):
        """Imprime relatório final"""
        self.print_header("RELATÓRIO FINAL")
        
        print("\n📊 Resumo de Execução:")
        for script, success in self.results.items():
            status = "✅ SUCESSO" if success else "❌ ERRO"
            print(f"   {status}: {script}")
        
        print(f"\n📋 Próximas Etapas:")
        print(f"""
1. VERIFICAR VISUALMENTE:
   - Abrir arquivos em: debug_corrections/grid_overlay/
   - block_01_grid_14px.jpg  (verde)
   - block_01_grid_18px.jpg  (vermelho)
   - block_01_grid_comparison.jpg (ambas)
   
2. DETERMINAR QUAL LINHA_HEIGHT ESTÁ CORRETO:
   - Se bolhas alinham com VERDE → usar 14px
   - Se bolhas alinham com VERMELHO → usar 18px
   
3. IMPLEMENTAR SOLUÇÃO:
   - Ver instruções em compare_expected_vs_real.py
   - Modificar correction_n.py linha ~2595
   - Desabilitar ajuste dinâmico ou atualizar JSON
   
4. TESTAR COM IMAGEM REAL:
   - python run.py
   - Submeter formulário de teste
   - Verificar se fill_ratios ficaram consistentes

        """)

def main():
    print("""
╔════════════════════════════════════════════════════════════════════╗
║   🔍 DIAGNÓSTICO COMPLETO DE ALINHAMENTO DA GRADE                 ║
║   Sistema de Detecção de Bolhas (Answer Sheet Correction)         ║
╚════════════════════════════════════════════════════════════════════╝
    """)
    
    runner = DiagnosticRunner()
    
    # Script 1: Diagnóstico de linha
    runner.run_script(
        "diagnose_grid_alignment.py",
        "1/4 - DIAGNÓSTICO: Análise de Line Height"
    )
    
    # Script 2: Medição de espaçamento real (se houver imagens)
    print("\n⏳ Tentando medir espaçamento real das bolhas...")
    runner.run_script(
        "measure_real_spacing.py",
        "2/4 - MEDIÇÃO: Espaçamento Real de Bolhas"
    )
    
    # Script 3: Gerar overlays de grid
    print("\n⏳ Gerando visualizações de grade...")
    runner.run_script(
        "generate_grid_overlay.py",
        "3/4 - VISUALIZAÇÃO: Grid Overlay"
    )
    
    # Script 4: Comparação esperado vs real
    runner.run_script(
        "compare_expected_vs_real.py",
        "4/4 - COMPARAÇÃO: Esperado vs Real"
    )
    
    # Relatório final
    runner.print_final_report()

if __name__ == "__main__":
    main()
