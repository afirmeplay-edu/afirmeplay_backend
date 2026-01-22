# -*- coding: utf-8 -*-
"""
Script para detectar blocos e bolhas em imagem processada (A4 normalizada)
Baseado em correction_n.py, mas focado apenas em detecção e visualização
"""

import cv2
import numpy as np
import json
import os
import sys
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Adicionar o diretório raiz ao path para importar módulos do app
script_dir = Path(__file__).parent.parent
sys.path.insert(0, str(script_dir))

from app.services.cartao_resposta.correction_n import AnswerSheetCorrectionN


class BlocksAndBubblesDetector:
    """Detector de blocos e bolhas em imagem A4 normalizada"""
    
    def __init__(self, img_path: str, output_dir: str = "debug_corrections"):
        """
        Inicializa o detector
        
        Args:
            img_path: Caminho para imagem processada (A4 normalizada)
            output_dir: Diretório para salvar imagens de debug
        """
        self.img_path = img_path
        self.output_dir = output_dir
        
        # Criar diretório de saída se não existir
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Carregar imagem
        self.img_a4 = cv2.imread(img_path)
        if self.img_a4 is None:
            raise ValueError(f"Não foi possível carregar a imagem: {img_path}")
        
        # Converter para grayscale se necessário
        if len(self.img_a4.shape) == 3:
            self.img_a4_gray = cv2.cvtColor(self.img_a4, cv2.COLOR_BGR2GRAY)
        else:
            self.img_a4_gray = self.img_a4.copy()
            self.img_a4 = cv2.cvtColor(self.img_a4_gray, cv2.COLOR_GRAY2BGR)
        
        self.img_h, self.img_w = self.img_a4_gray.shape[:2]
        print(f"[INFO] Imagem carregada: {self.img_w}x{self.img_h}px")
        
        # Calcular scale_info baseado nas dimensões da imagem
        # Assumindo que a imagem já está normalizada para A4 padrão (100 DPI)
        A4_WIDTH_CM = 21.0
        A4_HEIGHT_CM = 29.7
        PX_PER_CM = 100 / 2.54  # ~39.37 pixels por cm (100 DPI)
        
        # Calcular px_per_cm baseado nas dimensões reais da imagem
        px_per_cm_x = self.img_w / A4_WIDTH_CM
        px_per_cm_y = self.img_h / A4_HEIGHT_CM
        
        self.scale_info = {
            'a4_width_px': self.img_w,
            'a4_height_px': self.img_h,
            'px_per_cm_x': px_per_cm_x,
            'px_per_cm_y': px_per_cm_y,
            'a4_width_cm': A4_WIDTH_CM,
            'a4_height_cm': A4_HEIGHT_CM
        }
        
        print(f"[INFO] Scale info: {px_per_cm_x:.2f} px/cm (X), {px_per_cm_y:.2f} px/cm (Y)")
        
        # Criar instância do serviço de correção para usar suas funções
        self.correction_service = AnswerSheetCorrectionN(debug=True)
    
    def mapear_area_blocos(self) -> Dict:
        """
        Mapeia área dos blocos diretamente do CSS (mesma lógica de correction_n.py)
        
        Returns:
            Dict com informações da área dos blocos (x, y, width, height em pixels)
        """
        # Valores do CSS (em cm):
        # .answer-sheet: padding-top: 2.2cm, padding-left: 1.5cm, padding-right: 1.5cm, padding-bottom: 1.8cm
        # .answer-sheet-header: height: 6.4cm
        # .instructions-box: height: 3.8cm
        # .applicator-box: height: 2.6cm
        # .answer-grid-wrapper: height: 12.9cm, padding: 0.3cm
        
        px_per_cm_x = self.scale_info['px_per_cm_x']
        px_per_cm_y = self.scale_info['px_per_cm_y']
        
        # Calcular posição Y do início da área dos blocos
        # padding-top (2.2cm) + header (6.4cm) + instruções (3.8cm) + aplicador (2.6cm) = 15cm
        top_offset_cm = 2.2 + 6.4 + 3.8 + 2.6
        block_area_y = int(top_offset_cm * px_per_cm_y)
        
        # Calcular posição X (padding-left)
        block_area_x = int(1.5 * px_per_cm_x)  # padding-left: 1.5cm
        
        # Calcular largura (A4 width - padding-left - padding-right)
        # A4: 21cm - 1.5cm - 1.5cm = 18cm
        block_area_width = int(18.0 * px_per_cm_x)
        
        # Calcular altura (do .answer-grid-wrapper: 12.9cm)
        block_area_height = int(12.9 * px_per_cm_y)
        
        block_area_info = {
            'x': block_area_x,
            'y': block_area_y,
            'width': block_area_width,
            'height': block_area_height
        }
        
        print(f"[INFO] Área dos blocos mapeada: x={block_area_x}px, y={block_area_y}px, width={block_area_width}px, height={block_area_height}px")
        
        return block_area_info
    
    def extrair_blocos(self, block_area_info: Dict, num_blocks: int = 4) -> List[Tuple[np.ndarray, Dict]]:
        """
        Extrai blocos da área mapeada
        
        Args:
            block_area_info: Informações da área dos blocos
            num_blocks: Número de blocos esperados (padrão: 4)
            
        Returns:
            Lista de tuplas (bloco_roi, posição_info)
        """
        block_area_x = block_area_info['x']
        block_area_y = block_area_info['y']
        block_area_width = block_area_info['width']
        block_area_height = block_area_info['height']
        
        px_per_cm_x = self.scale_info['px_per_cm_x']
        
        # Do CSS: gap entre blocos = 0.4cm
        BLOCK_GAP_CM = 0.4
        BLOCK_GAP_PX = int(BLOCK_GAP_CM * px_per_cm_x)
        
        # Calcular largura de cada bloco
        total_gap = BLOCK_GAP_PX * (num_blocks - 1)
        block_width = (block_area_width - total_gap) // num_blocks
        
        # Para altura, vamos usar a altura total da área (cada bloco tem altura variável)
        # Mas vamos extrair com altura máxima primeiro
        block_height = block_area_height
        
        blocks = []
        
        for block_idx in range(num_blocks):
            block_num = block_idx + 1
            
            # Posição X: calcular baseado no índice do bloco
            block_x = block_area_x + (block_idx * (block_width + BLOCK_GAP_PX))
            
            # Posição Y: mesma para todos (topo da área dos blocos)
            block_y = block_area_y
            
            # Extrair ROI do bloco
            block_roi = self.img_a4_gray[block_y:block_y+block_height, block_x:block_x+block_width]
            
            if block_roi.size == 0:
                print(f"[AVISO] Bloco {block_num}: ROI vazio (x={block_x}, y={block_y}, w={block_width}, h={block_height})")
                continue
            
            position_info = {
                'block_num': block_num,
                'x': block_x,
                'y': block_y,
                'width': block_width,
                'height': block_height,
                'absolute_x': block_x,
                'absolute_y': block_y
            }
            
            blocks.append((block_roi, position_info))
            print(f"[INFO] Bloco {block_num}: Extraído em x={block_x}px, y={block_y}px, w={block_width}px, h={block_height}px")
        
        return blocks
    
    def detectar_bolhas_no_bloco(self, block_roi: np.ndarray, block_num: int) -> List[Dict]:
        """
        Detecta todas as bolhas em um bloco
        
        Args:
            block_roi: ROI do bloco
            block_num: Número do bloco
            
        Returns:
            Lista de bolhas detectadas
        """
        # Usar a função do correction_service
        bubbles = self.correction_service._detectar_todas_bolhas(block_roi, block_num)
        print(f"[INFO] Bloco {block_num}: {len(bubbles)} bolhas detectadas")
        return bubbles
    
    def desenhar_resultados(self, block_area_info: Dict, blocks_data: List[Tuple[np.ndarray, Dict, List[Dict]]]) -> np.ndarray:
        """
        Desenha resultados da detecção na imagem
        
        Args:
            block_area_info: Informações da área dos blocos
            blocks_data: Lista de (bloco_roi, position_info, bubbles)
            
        Returns:
            Imagem com desenhos
        """
        # Criar cópia da imagem para desenhar
        img_result = self.img_a4.copy()
        
        # Desenhar área dos blocos (retângulo verde)
        cv2.rectangle(img_result,
                     (block_area_info['x'], block_area_info['y']),
                     (block_area_info['x'] + block_area_info['width'], 
                      block_area_info['y'] + block_area_info['height']),
                     (0, 255, 0), 2)
        cv2.putText(img_result, "AREA BLOCOS", 
                   (block_area_info['x'] + 10, block_area_info['y'] - 10),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        
        # Desenhar cada bloco e suas bolhas
        for block_roi, position_info, bubbles in blocks_data:
            block_num = position_info['block_num']
            block_x = position_info['absolute_x']
            block_y = position_info['absolute_y']
            block_w = position_info['width']
            block_h = position_info['height']
            
            # Desenhar retângulo do bloco (azul)
            cv2.rectangle(img_result,
                         (block_x, block_y),
                         (block_x + block_w, block_y + block_h),
                         (255, 0, 0), 2)
            cv2.putText(img_result, f"BLOCO {block_num}",
                       (block_x + 10, block_y - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)
            
            # Desenhar cada bolha detectada (círculo vermelho)
            for bubble in bubbles:
                # Coordenadas relativas ao bloco
                bubble_x_rel = bubble['x']
                bubble_y_rel = bubble['y']
                
                # Converter para coordenadas absolutas na imagem
                bubble_x_abs = block_x + bubble_x_rel
                bubble_y_abs = block_y + bubble_y_rel
                
                # Desenhar círculo
                radius = max(bubble['w'], bubble['h']) // 2
                cv2.circle(img_result, (bubble_x_abs, bubble_y_abs), radius, (0, 0, 255), 2)
                
                # Desenhar contorno se disponível
                if 'contour' in bubble:
                    contour = bubble['contour']
                    # Ajustar contorno para coordenadas absolutas
                    contour_abs = contour + np.array([[block_x, block_y]], dtype=np.int32)
                    cv2.drawContours(img_result, [contour_abs], -1, (0, 0, 255), 1)
        
        return img_result
    
    def processar(self, num_blocks: int = 4) -> Dict:
        """
        Processa detecção completa de blocos e bolhas
        
        Args:
            num_blocks: Número de blocos esperados
            
        Returns:
            Dict com resultados da detecção
        """
        print("\n" + "="*60)
        print("DETECÇÃO DE BLOCOS E BOLHAS")
        print("="*60)
        
        # 1. Mapear área dos blocos
        print("\n[1/4] Mapeando área dos blocos...")
        block_area_info = self.mapear_area_blocos()
        
        # 2. Extrair blocos
        print(f"\n[2/4] Extraindo {num_blocks} blocos...")
        blocks = self.extrair_blocos(block_area_info, num_blocks)
        
        # 3. Detectar bolhas em cada bloco
        print(f"\n[3/4] Detectando bolhas em cada bloco...")
        blocks_data = []
        for block_roi, position_info in blocks:
            block_num = position_info['block_num']
            bubbles = self.detectar_bolhas_no_bloco(block_roi, block_num)
            blocks_data.append((block_roi, position_info, bubbles))
        
        # 4. Desenhar resultados
        print(f"\n[4/4] Desenhando resultados...")
        img_result = self.desenhar_resultados(block_area_info, blocks_data)
        
        # Salvar imagem de resultado
        output_filename = Path(self.img_path).stem + "_detection_result.jpg"
        output_path = os.path.join(self.output_dir, output_filename)
        cv2.imwrite(output_path, img_result)
        print(f"\n[OK] Imagem de resultado salva: {output_path}")
        
        # Salvar imagens individuais de cada bloco com bolhas
        for block_roi, position_info, bubbles in blocks_data:
            block_num = position_info['block_num']
            
            # Criar imagem do bloco com bolhas desenhadas
            if len(block_roi.shape) == 2:
                block_img = cv2.cvtColor(block_roi, cv2.COLOR_GRAY2BGR)
            else:
                block_img = block_roi.copy()
            
            # Desenhar bolhas no bloco
            for bubble in bubbles:
                bubble_x = bubble['x']
                bubble_y = bubble['y']
                radius = max(bubble['w'], bubble['h']) // 2
                cv2.circle(block_img, (bubble_x, bubble_y), radius, (0, 0, 255), 2)
                
                if 'contour' in bubble:
                    cv2.drawContours(block_img, [bubble['contour']], -1, (0, 0, 255), 1)
            
            # Adicionar texto com número de bolhas
            cv2.putText(block_img, f"BLOCO {block_num}: {len(bubbles)} bolhas",
                       (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            # Salvar
            block_filename = Path(self.img_path).stem + f"_block_{block_num:02d}_bubbles.jpg"
            block_path = os.path.join(self.output_dir, block_filename)
            cv2.imwrite(block_path, block_img)
            print(f"[OK] Bloco {block_num} salvo: {block_path}")
        
        # Resumo
        total_bubbles = sum(len(bubbles) for _, _, bubbles in blocks_data)
        print(f"\n" + "="*60)
        print("RESUMO")
        print("="*60)
        print(f"Blocos detectados: {len(blocks_data)}")
        print(f"Total de bolhas detectadas: {total_bubbles}")
        for block_roi, position_info, bubbles in blocks_data:
            print(f"  Bloco {position_info['block_num']}: {len(bubbles)} bolhas")
        
        return {
            'block_area_info': block_area_info,
            'blocks_data': [
                {
                    'block_num': pos['block_num'],
                    'position': pos,
                    'num_bubbles': len(bubbles)
                }
                for _, pos, bubbles in blocks_data
            ],
            'total_bubbles': total_bubbles,
            'output_path': output_path
        }


def main():
    parser = argparse.ArgumentParser(
        description='Detecta blocos e bolhas em imagem processada (A4 normalizada)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  # Usar imagem específica
  python scripts/detect_blocks_and_bubbles.py -i debug_corrections/20260119_160236_929_02_processed.jpg
  
  # Especificar número de blocos
  python scripts/detect_blocks_and_bubbles.py -i debug_corrections/20260119_160236_929_02_processed.jpg --blocks 4
  
  # Especificar diretório de saída
  python scripts/detect_blocks_and_bubbles.py -i debug_corrections/20260119_160236_929_02_processed.jpg -o output/
        """
    )
    parser.add_argument('-i', '--image', type=str, required=True,
                       help='Caminho para imagem processada (A4 normalizada)')
    parser.add_argument('-o', '--output', type=str, default='debug_corrections',
                       help='Diretório de saída para imagens de debug (padrão: debug_corrections)')
    parser.add_argument('--blocks', type=int, default=4,
                       help='Número de blocos esperados (padrão: 4)')
    
    args = parser.parse_args()
    
    # Validar arquivo
    if not os.path.exists(args.image):
        print(f"[ERRO] Arquivo não encontrado: {args.image}")
        return 1
    
    try:
        # Criar detector
        detector = BlocksAndBubblesDetector(args.image, args.output)
        
        # Processar
        results = detector.processar(args.blocks)
        
        print(f"\n[OK] Processamento concluído!")
        print(f"    Resultado salvo em: {results['output_path']}")
        
        return 0
        
    except Exception as e:
        print(f"[ERRO] Erro: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
