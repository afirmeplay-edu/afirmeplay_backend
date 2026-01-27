#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para coletar e analisar logs de DEBUG do warpPerspective
"""

import subprocess
import re
import sys

def run_and_capture_logs():
    """Executa run.py e captura logs de DEBUG"""
    
    print("""
╔════════════════════════════════════════════════════════════════════╗
║  🔍 COLETANDO LOGS DE DEBUG DO WARPPERSPECTIVE                     ║
╚════════════════════════════════════════════════════════════════════╝
    """)
    
    print("Executando: python run.py\n")
    print("="*70)
    
    try:
        result = subprocess.run(
            [sys.executable, "run.py"],
            capture_output=True,
            text=True,
            timeout=120
        )
        
        full_output = result.stdout + result.stderr
        
        # Extrair linhas com DEBUG
        debug_lines = []
        for line in full_output.split('\n'):
            if 'DEBUG' in line or '🔍' in line or 'ESCALA' in line or 'DIFERENTES' in line:
                debug_lines.append(line)
        
        if debug_lines:
            print("\n🔍 LOGS DE DEBUG ENCONTRADOS:\n")
            for line in debug_lines:
                print(line)
        else:
            print("⚠️  Nenhum log de DEBUG encontrado")
            print("\nÚltimas 50 linhas de output:")
            print('\n'.join(full_output.split('\n')[-50:]))
        
        # Salvar todos os logs em arquivo
        with open('debug_logs_warp.txt', 'w', encoding='utf-8') as f:
            f.write("LOGS COMPLETOS DE RUN.PY\n")
            f.write("="*70 + "\n\n")
            f.write(full_output)
        
        print("\n" + "="*70)
        print("✅ Logs salvos em: debug_logs_warp.txt")
        
        return full_output
        
    except subprocess.TimeoutExpired:
        print("❌ Timeout executando run.py (> 120 segundos)")
        return None
    except Exception as e:
        print(f"❌ Erro: {str(e)}")
        return None


def analyze_logs_for_distortion(log_text):
    """Analisa logs para detectar distorção"""
    
    if not log_text:
        return
    
    print("\n" + "="*70)
    print("📊 ANÁLISE DOS LOGS")
    print("="*70)
    
    # Extrair informações de escala
    scale_pattern = r'px_per_cm_[xy]: ([\d.]+)'
    scales = re.findall(scale_pattern, log_text)
    
    if len(scales) >= 2:
        px_per_cm_x = float(scales[0])
        px_per_cm_y = float(scales[1])
        
        print(f"\n📏 Escalas detectadas:")
        print(f"  px_per_cm_x: {px_per_cm_x:.2f}")
        print(f"  px_per_cm_y: {px_per_cm_y:.2f}")
        
        if abs(px_per_cm_x - px_per_cm_y) > 0.5:
            diff_percent = ((px_per_cm_y / px_per_cm_x - 1) * 100)
            print(f"  ⚠️  ESCALAS DIFERENTES! Diferença: {diff_percent:+.1f}%")
        else:
            print(f"  ✅ Escalas uniformes (OK)")
    
    # Extrair coordenadas dos quadrados
    tl_pattern = r'TL \(src\): \[([\d.]+)\s+([\d.]+)\]'
    tr_pattern = r'TR \(src\): \[([\d.]+)\s+([\d.]+)\]'
    br_pattern = r'BR \(src\): \[([\d.]+)\s+([\d.]+)\]'
    bl_pattern = r'BL \(src\): \[([\d.]+)\s+([\d.]+)\]'
    
    tl = re.search(tl_pattern, log_text)
    tr = re.search(tr_pattern, log_text)
    br = re.search(br_pattern, log_text)
    bl = re.search(bl_pattern, log_text)
    
    if tl and tr and br and bl:
        print(f"\n📍 Quadrados detectados (src_points):")
        tl_coords = (float(tl.group(1)), float(tl.group(2)))
        tr_coords = (float(tr.group(1)), float(tr.group(2)))
        br_coords = (float(br.group(1)), float(br.group(2)))
        bl_coords = (float(bl.group(1)), float(bl.group(2)))
        
        print(f"  TL: {tl_coords}")
        print(f"  TR: {tr_coords}")
        print(f"  BR: {br_coords}")
        print(f"  BL: {bl_coords}")
        
        # Calcular proporções
        width = tr_coords[0] - tl_coords[0]
        height = bl_coords[1] - tl_coords[1]
        proportion = width / height if height > 0 else 0
        
        print(f"\n  Largura (TR.x - TL.x): {width:.1f}px")
        print(f"  Altura (BL.y - TL.y): {height:.1f}px")
        print(f"  Proporção (W/H): {proportion:.4f}")
        print(f"  Esperado para A4: 0.7071")
        
        if abs(proportion - 0.7071) > 0.05:
            print(f"  ⚠️  PROPORÇÃO DIFERENTE DO ESPERADO!")
        else:
            print(f"  ✅ Proporção correta")


def main():
    log_output = run_and_capture_logs()
    
    if log_output:
        analyze_logs_for_distortion(log_output)
        
        print("\n" + "="*70)
        print("💡 PRÓXIMOS PASSOS")
        print("="*70)
        print("""
1. Verifique os logs acima
2. Se px_per_cm_x ≠ px_per_cm_y:
   → Problema é ESCALA DESIGUAL
   → Solução: Corrigir detecção de quadrados ou usar cv2.undistort()

3. Se proporção diferente de 0.7071:
   → Problema é PERSPECTIVA INCLINADA
   → Solução: Verificar detecção de quadrados ou usar cv2.undistort()

4. Se espaçamento varia muito (logs anteriores):
   → Problema é DISTORÇÃO NÃO-LINEAR
   → Solução: Investigar mais fundo
        """)


if __name__ == "__main__":
    main()
