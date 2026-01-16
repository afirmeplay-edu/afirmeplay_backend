# -*- coding: utf-8 -*-
"""
Script para alinhar e comparar imagens de referência e real dos blocos
Permite visualizar onde estão as bolhas em ambas as imagens para análise de alinhamento
"""

import cv2
import numpy as np
import os
import sys
import argparse
from pathlib import Path


def load_image(image_path: str) -> np.ndarray:
    """Carrega uma imagem"""
    if not os.path.exists(image_path):
        print(f"❌ Erro: Arquivo não encontrado: {image_path}")
        return None
    
    img = cv2.imread(image_path)
    if img is None:
        print(f"❌ Erro: Não foi possível carregar imagem: {image_path}")
        return None
    
    return img


def detect_border(img: np.ndarray) -> tuple:
    """
    Detecta a borda preta do bloco e retorna área interna
    """
    # Converter para grayscale
    if len(img.shape) == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        gray = img.copy()
    
    h, w = gray.shape
    
    # Threshold para detectar borda preta
    _, thresh = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY_INV)
    
    # Encontrar contornos externos
    cnts = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cnts = cnts[0] if len(cnts) == 2 else cnts[1]
    
    if not cnts:
        return None, None
    
    # Encontrar maior contorno (borda do bloco)
    largest_cnt = max(cnts, key=cv2.contourArea)
    x, y, w_cnt, h_cnt = cv2.boundingRect(largest_cnt)
    
    # Validar se o contorno faz sentido (não pode ser muito pequeno ou muito grande)
    if w_cnt < w * 0.3 or h_cnt < h * 0.3:
        # Contorno muito pequeno, provavelmente não é a borda
        return None, None
    
    if w_cnt > w * 0.95 or h_cnt > h * 0.95:
        # Contorno muito grande, provavelmente pegou a imagem toda
        return None, None
    
    # Extrair área interna (sem borda)
    border_thickness = 2
    inner_x = max(0, x + border_thickness)
    inner_y = max(0, y + border_thickness)
    inner_w = max(1, w_cnt - 2 * border_thickness)
    inner_h = max(1, h_cnt - 2 * border_thickness)
    
    # Garantir que não ultrapassa os limites
    inner_x = min(inner_x, w - 1)
    inner_y = min(inner_y, h - 1)
    inner_w = min(inner_w, w - inner_x)
    inner_h = min(inner_h, h - inner_y)
    
    if inner_w <= 0 or inner_h <= 0:
        return None, None
    
    inner_area = img[inner_y:inner_y+inner_h, inner_x:inner_x+inner_w]
    border_info = {
        'x': x, 'y': y, 'w': w_cnt, 'h': h_cnt,
        'inner_x': inner_x, 'inner_y': inner_y,
        'inner_w': inner_w, 'inner_h': inner_h
    }
    
    return inner_area, border_info


def align_images_by_border(img_ref: np.ndarray, img_real: np.ndarray) -> tuple:
    """
    Alinha duas imagens usando a borda do bloco como referência
    """
    # Detectar bordas em ambas
    inner_ref, border_ref = detect_border(img_ref)
    inner_real, border_real = detect_border(img_real)
    
    # Se não conseguir detectar borda, usar imagem completa
    if inner_ref is None:
        print("⚠️ Aviso: Não foi possível detectar borda na referência, usando imagem completa")
        inner_ref = img_ref.copy()
        if len(inner_ref.shape) == 3:
            # Converter para grayscale se for colorida
            inner_ref = cv2.cvtColor(inner_ref, cv2.COLOR_BGR2GRAY)
    
    if inner_real is None:
        print("⚠️ Aviso: Não foi possível detectar borda na real, usando imagem completa")
        inner_real = img_real.copy()
        if len(inner_real.shape) == 3:
            # Converter para grayscale se for colorida
            inner_real = cv2.cvtColor(inner_real, cv2.COLOR_BGR2GRAY)
    
    # Garantir que ambas são grayscale
    if len(inner_ref.shape) == 3:
        inner_ref = cv2.cvtColor(inner_ref, cv2.COLOR_BGR2GRAY)
    if len(inner_real.shape) == 3:
        inner_real = cv2.cvtColor(inner_real, cv2.COLOR_BGR2GRAY)
    
    # Redimensionar para mesmo tamanho (usar tamanho da referência)
    h_ref, w_ref = inner_ref.shape[:2]
    h_real, w_real = inner_real.shape[:2]
    
    print(f"   Tamanho ref: {w_ref}x{h_ref}, real: {w_real}x{h_real}")
    
    # Redimensionar imagem real para tamanho da referência
    if (w_real, h_real) != (w_ref, h_ref):
        inner_real_resized = cv2.resize(inner_real, (w_ref, h_ref), interpolation=cv2.INTER_AREA)
        print(f"   Redimensionado real para: {w_ref}x{h_ref}")
    else:
        inner_real_resized = inner_real.copy()
    
    # Validar que as imagens não estão vazias
    if inner_ref.size == 0 or inner_real_resized.size == 0:
        print("❌ Erro: Imagem vazia após processamento")
        return None, None, None, None
    
    return inner_ref, inner_real_resized, border_ref, border_real


def detect_bubbles_in_image(img: np.ndarray, bubble_radius: int = 10) -> list:
    """
    Detecta bolhas na imagem usando HoughCircles
    """
    # Converter para grayscale
    if len(img.shape) == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        gray = img.copy()
    
    # Aplicar blur
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    
    # Detectar círculos
    circles = cv2.HoughCircles(
        blurred,
        cv2.HOUGH_GRADIENT,
        dp=1,
        minDist=bubble_radius * 2,
        param1=50,
        param2=25,
        minRadius=max(3, bubble_radius - 5),
        maxRadius=bubble_radius + 10
    )
    
    bubbles = []
    if circles is not None:
        circles = np.round(circles[0, :]).astype("int")
        for (x, y, r) in circles:
            bubbles.append({'x': x, 'y': y, 'radius': r})
    
    return bubbles


def create_alignment_visualization(img_ref: np.ndarray, img_real: np.ndarray,
                                  bubbles_ref: list, bubbles_real: list,
                                  output_path: str):
    """
    Cria visualização comparativa das duas imagens alinhadas
    """
    h, w = img_ref.shape[:2]
    
    # Criar imagem combinada (lado a lado)
    combined = np.zeros((h, w * 2 + 50, 3), dtype=np.uint8)
    combined.fill(255)  # Fundo branco
    
    # Converter para BGR se necessário (garantir que ambas são BGR)
    if len(img_ref.shape) == 2:
        img_ref_bgr = cv2.cvtColor(img_ref, cv2.COLOR_GRAY2BGR)
    elif len(img_ref.shape) == 3:
        img_ref_bgr = img_ref.copy()
    else:
        print("⚠️ Formato de imagem de referência inválido")
        return
    
    if len(img_real.shape) == 2:
        img_real_bgr = cv2.cvtColor(img_real, cv2.COLOR_GRAY2BGR)
    elif len(img_real.shape) == 3:
        img_real_bgr = img_real.copy()
    else:
        print("⚠️ Formato de imagem real inválido")
        return
    
    # Validar que as imagens têm conteúdo válido
    if img_ref_bgr.size == 0 or img_real_bgr.size == 0:
        print("❌ Erro: Imagem vazia")
        return
    
    # Verificar se as imagens não estão completamente escuras ou claras
    ref_mean = np.mean(img_ref_bgr)
    real_mean = np.mean(img_real_bgr)
    print(f"   Intensidade média - Ref: {ref_mean:.1f}, Real: {real_mean:.1f}")
    
    if real_mean < 10:
        print("⚠️ Aviso: Imagem real muito escura, pode haver problema no processamento")
    if real_mean > 245:
        print("⚠️ Aviso: Imagem real muito clara, pode haver problema no processamento")
    
    # Colocar imagens lado a lado
    combined[0:h, 0:w] = img_ref_bgr
    combined[0:h, w+50:w*2+50] = img_real_bgr
    
    # Desenhar bolhas detectadas na referência (verde)
    for bubble in bubbles_ref:
        cv2.circle(combined, (bubble['x'], bubble['y']), bubble['radius'], (0, 255, 0), 2)
        cv2.circle(combined, (bubble['x'], bubble['y']), 2, (0, 255, 0), -1)
    
    # Desenhar bolhas detectadas na real (azul)
    for bubble in bubbles_real:
        x_offset = w + 50
        cv2.circle(combined, (bubble['x'] + x_offset, bubble['y']), bubble['radius'], (255, 0, 0), 2)
        cv2.circle(combined, (bubble['x'] + x_offset, bubble['y']), 2, (255, 0, 0), -1)
    
    # Adicionar labels
    cv2.putText(combined, "REFERENCIA", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
    cv2.putText(combined, "REAL", (w + 60, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
    
    # Adicionar contadores
    cv2.putText(combined, f"Bolhas: {len(bubbles_ref)}", (10, h - 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
    cv2.putText(combined, f"Bolhas: {len(bubbles_real)}", (w + 60, h - 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)
    
    # Criar versão sobreposta (transparência)
    overlay = img_ref_bgr.copy()
    overlay_real = img_real_bgr.copy()
    
    # Redimensionar real para mesmo tamanho se necessário
    if overlay_real.shape != overlay.shape:
        overlay_real = cv2.resize(overlay_real, (overlay.shape[1], overlay.shape[0]))
    
    # Criar overlay com transparência
    overlay_combined = cv2.addWeighted(overlay, 0.5, overlay_real, 0.5, 0)
    
    # Desenhar bolhas na sobreposição
    for bubble in bubbles_ref:
        cv2.circle(overlay_combined, (bubble['x'], bubble['y']), bubble['radius'], (0, 255, 0), 2)
    
    for bubble in bubbles_real:
        # Ajustar coordenadas se necessário
        if overlay_real.shape != img_real_bgr.shape:
            scale_x = overlay.shape[1] / img_real_bgr.shape[1]
            scale_y = overlay.shape[0] / img_real_bgr.shape[0]
            x = int(bubble['x'] * scale_x)
            y = int(bubble['y'] * scale_y)
        else:
            x, y = bubble['x'], bubble['y']
        cv2.circle(overlay_combined, (x, y), bubble['radius'], (255, 0, 0), 2)
    
    # Salvar imagens
    cv2.imwrite(output_path, combined)
    overlay_path = output_path.replace('.jpg', '_overlay.jpg')
    cv2.imwrite(overlay_path, overlay_combined)
    
    print(f"✅ Imagem lado a lado salva: {output_path}")
    print(f"✅ Imagem sobreposta salva: {overlay_path}")


def find_latest_debug_images(debug_dir: str = "debug_corrections", block_num: int = None):
    """
    Encontra automaticamente as imagens mais recentes no diretório de debug
    """
    if not os.path.exists(debug_dir):
        return None, None
    
    # Buscar todas as imagens de referência
    ref_pattern = f"*_block_{block_num:02d}_reference.jpg" if block_num else "*_block_*_reference.jpg"
    ref_files = list(Path(debug_dir).glob(ref_pattern))
    
    # Se não encontrar com padrão específico, buscar qualquer imagem de referência
    if not ref_files:
        ref_files = list(Path(debug_dir).glob("*_block_*_reference.jpg"))
    
    # Buscar imagem real do bloco (prioridade: original > roi > threshold)
    if block_num:
        patterns = [
            f"*_block_{block_num:02d}_original.jpg",
            f"*_block_{block_num:02d}_roi.jpg",
            f"*_block_{block_num:02d}_threshold.jpg"
        ]
    else:
        patterns = [
            "*_block_*_original.jpg",
            "*_block_*_roi.jpg",
            "*_block_*_threshold.jpg"
        ]
    
    roi_files = []
    for pattern in patterns:
        files = list(Path(debug_dir).glob(pattern))
        if files:
            roi_files = files
            break
    
    # Pegar as mais recentes
    ref_path = max(ref_files, key=os.path.getmtime) if ref_files else None
    roi_path = max(roi_files, key=os.path.getmtime) if roi_files else None
    
    return str(ref_path) if ref_path else None, str(roi_path) if roi_path else None


def main():
    parser = argparse.ArgumentParser(
        description='Alinha e compara imagens de referência e real dos blocos',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos de uso:
  # Usar imagens específicas
  python scripts/align_block_images.py -r debug_corrections/08_block_01_reference.jpg -i debug_corrections/05_block_01_roi.jpg
  
  # Buscar automaticamente imagens do bloco 1
  python scripts/align_block_images.py --block 1 --auto
  
  # Buscar automaticamente qualquer bloco
  python scripts/align_block_images.py --auto
        """
    )
    parser.add_argument('--reference', '-r', type=str, default=None,
                       help='Caminho para imagem de referência')
    parser.add_argument('--real', '-i', type=str, default=None,
                       help='Caminho para imagem real do bloco')
    parser.add_argument('--auto', '-a', action='store_true',
                       help='Buscar automaticamente imagens no diretório debug_corrections')
    parser.add_argument('--block', '-b', type=int, default=None,
                       help='Número do bloco para busca automática (ex: 1, 2)')
    parser.add_argument('--output', '-o', type=str, default=None,
                       help='Caminho de saída (padrão: auto-gerado)')
    parser.add_argument('--bubble-radius', type=int, default=10,
                       help='Raio esperado das bolhas em pixels (padrão: 10)')
    parser.add_argument('--debug-dir', type=str, default='debug_corrections',
                       help='Diretório de debug (padrão: debug_corrections)')
    parser.add_argument('--save-intermediate', action='store_true',
                       help='Salvar imagens intermediárias para debug')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("Script de Alinhamento de Imagens de Blocos")
    print("=" * 60)
    
    # Buscar imagens automaticamente se solicitado
    if args.auto:
        print(f"\n🔍 Buscando imagens automaticamente no diretório '{args.debug_dir}'...")
        ref_path, real_path = find_latest_debug_images(args.debug_dir, args.block)
        
        if ref_path:
            args.reference = ref_path
            print(f"   ✅ Referência encontrada: {ref_path}")
        else:
            print(f"   ❌ Referência não encontrada")
        
        if real_path:
            args.real = real_path
            print(f"   ✅ Real encontrada: {real_path}")
        else:
            print(f"   ❌ Real não encontrada")
        
        if not ref_path or not real_path:
            print("\n❌ Erro: Não foi possível encontrar as imagens automaticamente.")
            print("   Use --reference e --real para especificar manualmente.")
            return 1
    
    # Validar que temos os caminhos necessários
    if not args.reference or not args.real:
        print("\n❌ Erro: É necessário fornecer --reference e --real, ou usar --auto")
        parser.print_help()
        return 1
    
    # Gerar nome de saída se não fornecido
    if not args.output:
        block_suffix = f"_block_{args.block:02d}" if args.block else ""
        args.output = f"aligned_comparison{block_suffix}.jpg"
    
    # Carregar imagens
    print(f"\n📂 Carregando imagem de referência: {args.reference}")
    img_ref = load_image(args.reference)
    if img_ref is None:
        return 1
    
    print(f"📂 Carregando imagem real: {args.real}")
    img_real = load_image(args.real)
    if img_real is None:
        return 1
    
    print(f"   Referência: {img_ref.shape}")
    print(f"   Real: {img_real.shape}")
    
    # Salvar imagens originais para debug se solicitado
    if args.save_intermediate:
        cv2.imwrite("debug_ref_original.jpg", img_ref)
        cv2.imwrite("debug_real_original.jpg", img_real)
        print("   💾 Imagens originais salvas para debug")
    
    # Alinhar imagens
    print("\n🔧 Alinhando imagens...")
    inner_ref, inner_real, border_ref, border_real = align_images_by_border(img_ref, img_real)
    
    if inner_ref is None or inner_real is None:
        print("❌ Erro: Falha ao alinhar imagens")
        return 1
    
    if border_ref:
        print(f"   Borda ref: {border_ref['w']}x{border_ref['h']}")
    if border_real:
        print(f"   Borda real: {border_real['w']}x{border_real['h']}")
    
    print(f"   Área interna ref: {inner_ref.shape}")
    print(f"   Área interna real: {inner_real.shape}")
    
    # Validar que as imagens têm tamanho válido
    if inner_ref.size == 0 or inner_real.size == 0:
        print("❌ Erro: Imagens vazias após alinhamento")
        return 1
    
    # Salvar imagens após alinhamento para debug se solicitado
    if args.save_intermediate:
        cv2.imwrite("debug_ref_aligned.jpg", inner_ref)
        cv2.imwrite("debug_real_aligned.jpg", inner_real)
        print("   💾 Imagens alinhadas salvas para debug")
    
    # Detectar bolhas
    print(f"\n🔍 Detectando bolhas (raio esperado: {args.bubble_radius}px)...")
    bubbles_ref = detect_bubbles_in_image(inner_ref, args.bubble_radius)
    bubbles_real = detect_bubbles_in_image(inner_real, args.bubble_radius)
    
    print(f"   Bolhas na referência: {len(bubbles_ref)}")
    print(f"   Bolhas na real: {len(bubbles_real)}")
    
    # Calcular offsets médios entre bolhas correspondentes
    if bubbles_ref and bubbles_real:
        print(f"\n📊 Analisando offsets...")
        # Tentar parear bolhas mais próximas
        offsets_x = []
        offsets_y = []
        
        for bubble_ref in bubbles_ref[:min(5, len(bubbles_ref))]:  # Limitar a 5 primeiras
            min_dist = float('inf')
            closest_bubble = None
            
            for bubble_real in bubbles_real:
                dist = np.sqrt((bubble_ref['x'] - bubble_real['x'])**2 + 
                             (bubble_ref['y'] - bubble_real['y'])**2)
                if dist < min_dist:
                    min_dist = dist
                    closest_bubble = bubble_real
            
            if closest_bubble and min_dist < 50:  # Se estiver dentro de 50px
                offset_x = closest_bubble['x'] - bubble_ref['x']
                offset_y = closest_bubble['y'] - bubble_ref['y']
                offsets_x.append(offset_x)
                offsets_y.append(offset_y)
                print(f"   Bolha ref ({bubble_ref['x']}, {bubble_ref['y']}) -> real ({closest_bubble['x']}, {closest_bubble['y']}): offset=({offset_x:+d}, {offset_y:+d})")
        
        if offsets_x:
            avg_offset_x = np.mean(offsets_x)
            avg_offset_y = np.mean(offsets_y)
            print(f"\n   📌 Offset médio: X={avg_offset_x:+.1f}px, Y={avg_offset_y:+.1f}px")
    
    # Criar visualização
    print(f"\n🎨 Criando visualização...")
    create_alignment_visualization(
        inner_ref, inner_real,
        bubbles_ref, bubbles_real,
        args.output
    )
    
    print(f"\n✅ Concluído! Imagens salvas:")
    print(f"   - {args.output}")
    print(f"   - {args.output.replace('.jpg', '_overlay.jpg')}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
