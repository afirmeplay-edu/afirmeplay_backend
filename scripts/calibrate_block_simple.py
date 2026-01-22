# -*- coding: utf-8 -*-
"""
Script SIMPLIFICADO de calibração visual do grid OMR

USO:
    python scripts/calibrate_block_simple.py \
        --block_image path/to/block1.jpg \
        --gabarito_id UUID \
        --block_num 1

ENTRADA:
    - Imagem de UM BLOCO já cortado (ex: 06_block1_bubbles_mapped.jpg)
    - ID do gabarito
    - Número do bloco (1-4)

SAÍDA:
    - Imagem com grid sobreposto em calibration_output/
"""

import cv2
import numpy as np
import json
import sys
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List

# Adicionar o diretório raiz ao path
script_dir = Path(__file__).parent.parent
sys.path.insert(0, str(script_dir))

from app import create_app
from app.models.answerSheetGabarito import AnswerSheetGabarito
from app import db

# ============================================================================
# 🎯 CONSTANTES DE CALIBRAÇÃO - AJUSTE AQUI!
# ============================================================================

# Valores atuais (copie de correction_new_grid.py)
CALIBRATION_ROW_HEIGHT_PX = 51.97
CALIBRATION_BUBBLE_RADIUS_PX = 25
CALIBRATION_BUBBLE_WIDTH_PX = 15  # Largura CSS da bolha
CALIBRATION_BUBBLE_GAP_PX = 4
CALIBRATION_BUBBLE_SPACING_PX = 19  # 15 (largura) + 4 (gap) - BASE INICIAL
CALIBRATION_BLOCK_OFFSET_X = 31  # 2 (borda) + 4 (padding) + 25 (num)
CALIBRATION_BLOCK_OFFSET_Y = 10  # 2 (borda) + 8 (padding)

# 🧪 TESTES INCREMENTAIS - AJUSTE ESSES VALORES!
TEST_ROW_HEIGHT_OFFSET = 0   # +/- pixels para ajustar altura da linha
TEST_RADIUS_OFFSET = 0       # +/- pixels para ajustar raio
TEST_BUBBLE_SPACING_ADJUST = 42  # +/- pixels para espaçamento entre bolhas (aumentar se coladas)
TEST_OFFSET_X_ADJUST = 84     # +/- pixels para ajustar offset X
TEST_OFFSET_Y_ADJUST = 30    # +/- pixels para ajustar offset Y

# ============================================================================

class BlockCalibrator:
    """Calibrador visual SIMPLIFICADO para um bloco"""
    
    def __init__(self, output_dir: str = "calibration_output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Aplicar ajustes
        self.row_height = CALIBRATION_ROW_HEIGHT_PX + TEST_ROW_HEIGHT_OFFSET
        self.bubble_radius = int(CALIBRATION_BUBBLE_RADIUS_PX + TEST_RADIUS_OFFSET)
        self.bubble_width = CALIBRATION_BUBBLE_WIDTH_PX
        self.bubble_gap = CALIBRATION_BUBBLE_GAP_PX
        self.bubble_spacing = CALIBRATION_BUBBLE_SPACING_PX + TEST_BUBBLE_SPACING_ADJUST
        self.offset_x = CALIBRATION_BLOCK_OFFSET_X + TEST_OFFSET_X_ADJUST
        self.offset_y = CALIBRATION_BLOCK_OFFSET_Y + TEST_OFFSET_Y_ADJUST
        
        print("=" * 80)
        print("🎯 CALIBRADOR VISUAL DE BLOCO OMR (SIMPLIFICADO)")
        print("=" * 80)
        print(f"📐 Parâmetros de calibração:")
        print(f"   Row height: {self.row_height:.2f}px (base: {CALIBRATION_ROW_HEIGHT_PX:.2f} + {TEST_ROW_HEIGHT_OFFSET})")
        print(f"   Bubble radius: {self.bubble_radius}px (base: {CALIBRATION_BUBBLE_RADIUS_PX} + {TEST_RADIUS_OFFSET})")
        print(f"   Bubble spacing: {self.bubble_spacing:.2f}px (base: {CALIBRATION_BUBBLE_SPACING_PX} + {TEST_BUBBLE_SPACING_ADJUST})")
        print(f"   Offset X: {self.offset_x}px (base: {CALIBRATION_BLOCK_OFFSET_X} + {TEST_OFFSET_X_ADJUST})")
        print(f"   Offset Y: {self.offset_y}px (base: {CALIBRATION_BLOCK_OFFSET_Y} + {TEST_OFFSET_Y_ADJUST})")
        print(f"📁 Output: {self.output_dir}")
        print("=" * 80)
    
    def load_image(self, image_path: str) -> np.ndarray:
        """Carrega imagem do bloco"""
        img = cv2.imread(image_path)
        if img is None:
            raise FileNotFoundError(f"Imagem não encontrada: {image_path}")
        print(f"✅ Imagem carregada: {img.shape}")
        return img
    
    def get_topology_block(self, gabarito_id: str, block_num: int) -> Dict:
        """Busca topologia do bloco específico"""
        from sqlalchemy.orm import Session
        gabarito = db.session.get(AnswerSheetGabarito, gabarito_id)
        if not gabarito:
            raise ValueError(f"Gabarito não encontrado: {gabarito_id}")
        
        # Reconstruir topologia a partir de blocks_config e correct_answers
        blocks_config = gabarito.blocks_config or {}
        correct_answers = gabarito.correct_answers or {}
        
        # Se blocks_config já tem a topologia completa
        if "topology" in blocks_config and "blocks" in blocks_config["topology"]:
            blocks = blocks_config["topology"]["blocks"]
            for block in blocks:
                if block.get("block_id") == block_num:
                    print(f"✅ Topologia do bloco {block_num} carregada: {len(block.get('questions', []))} questões")
                    return block
        
        # Fallback: reconstruir a partir de correct_answers
        num_blocks = blocks_config.get("num_blocks", 4)
        questions_per_block = gabarito.num_questions // num_blocks
        
        # Calcular questões do bloco
        start_q = ((block_num - 1) * questions_per_block) + 1
        end_q = min(block_num * questions_per_block, gabarito.num_questions)
        
        # Reconstruir bloco
        questions = []
        for q_num in range(start_q, end_q + 1):
            # Assumir 4 alternativas (A, B, C, D) por padrão
            questions.append({
                "q": q_num,
                "alternatives": ["A", "B", "C", "D"]
            })
        
        print(f"✅ Topologia do bloco {block_num} reconstruída: {len(questions)} questões")
        return {"block_id": block_num, "questions": questions}
    
    def draw_calibration_grid(self, block_img: np.ndarray, 
                             topology_block: Dict,
                             block_num: int) -> np.ndarray:
        """Desenha grid de calibração sobre o bloco"""
        
        debug_img = block_img.copy()
        h, w = debug_img.shape[:2]
        
        questions = topology_block.get("questions", [])
        num_questions = len(questions)
        
        print(f"\n📦 BLOCO {block_num}: {num_questions} questões")
        print(f"   Dimensões da imagem: {w}x{h}px")
        print(f"   Primeira questão: Q{questions[0]['q']} - {questions[0]['alternatives']}")
        
        # Desenhar linhas horizontais (entre questões)
        for i in range(num_questions + 1):
            y = int(self.offset_y + (self.row_height * i))
            if 0 <= y < h:
                cv2.line(debug_img, (0, y), (w, y), (0, 255, 255), 2)  # Amarelo
                if i < num_questions and i < 3:  # Mostrar label das primeiras 3
                    cv2.putText(debug_img, f"Q{questions[i]['q']}", 
                               (5, y + 25), cv2.FONT_HERSHEY_SIMPLEX, 
                               0.5, (0, 255, 255), 1)
        
        # Desenhar linha vertical do offset X
        if 0 <= self.offset_x < w:
            cv2.line(debug_img, (self.offset_x, 0), (self.offset_x, h), (255, 0, 255), 1)  # Magenta
        
        # Desenhar bolhas calculadas
        bubble_count = 0
        for row_idx, question in enumerate(questions):
            q_num = question.get("q")
            alternatives = question.get("alternatives", [])
            
            # Calcular cy (centro vertical da linha)
            cy = int(self.offset_y + (self.row_height * row_idx) + (self.row_height / 2))
            
            for col_idx, alt_letter in enumerate(alternatives):
                # Calcular cx (centro horizontal da bolha)
                # Usar bubble_spacing ajustável ao invés de calcular fixo
                cx = int(self.offset_x + (col_idx * self.bubble_spacing) + (self.bubble_width / 2))
                
                # Verificar se está dentro da imagem
                if 0 <= cx < w and 0 <= cy < h:
                    # Desenhar círculo verde (calculado)
                    cv2.circle(debug_img, (cx, cy), self.bubble_radius, (0, 255, 0), 2)
                    cv2.circle(debug_img, (cx, cy), 2, (0, 0, 255), -1)  # Centro vermelho
                    
                    # Label (apenas primeiras questões para não poluir)
                    if row_idx < 5:
                        cv2.putText(debug_img, f"{alt_letter}", (cx - 5, cy - self.bubble_radius - 5),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 0, 0), 1)
                    
                    bubble_count += 1
        
        print(f"   ✅ {bubble_count} bolhas desenhadas")
        
        # Adicionar informações na imagem
        info_y = 20
        cv2.putText(debug_img, f"BLOCO {block_num} | {num_questions} questoes", 
                   (10, info_y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        info_y += 25
        cv2.putText(debug_img, f"row_h={self.row_height:.1f}px radius={self.bubble_radius}px spacing={self.bubble_spacing:.1f}px", 
                   (10, info_y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
        info_y += 20
        cv2.putText(debug_img, f"offset_x={self.offset_x}px offset_y={self.offset_y}px", 
                   (10, info_y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
        
        # Legenda
        legend_y = h - 60
        cv2.putText(debug_img, "Legenda: Amarelo=Linhas | Verde=Bolhas calc | Vermelho=Centros", 
                   (10, legend_y), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
        legend_y += 20
        cv2.putText(debug_img, "Magenta=Offset X | Ajuste constantes no script!", 
                   (10, legend_y), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
        
        return debug_img
    
    def save_image(self, img: np.ndarray, name: str):
        """Salva imagem"""
        filename = f"{self.timestamp}_{name}"
        filepath = self.output_dir / filename
        cv2.imwrite(str(filepath), img)
        print(f"💾 Salvo: {filepath}")
        return filepath
    
    def run(self, block_image_path: str, gabarito_id: str, block_num: int):
        """Executa calibração"""
        try:
            # 1. Carregar imagem do bloco
            block_img = self.load_image(block_image_path)
            
            # 2. Buscar topologia
            topology_block = self.get_topology_block(gabarito_id, block_num)
            
            # 3. Desenhar grid de calibração
            calibrated = self.draw_calibration_grid(block_img, topology_block, block_num)
            
            # 4. Salvar resultado
            output_path = self.save_image(calibrated, f"block{block_num}_calibrated.jpg")
            
            print("\n" + "=" * 80)
            print("✅ CALIBRAÇÃO CONCLUÍDA!")
            print("=" * 80)
            print(f"📁 Imagem salva: {output_path}")
            print("\n🔍 COMO ANALISAR:")
            print("   ✅ Linhas amarelas devem passar ENTRE as linhas de questões")
            print("   ✅ Círculos verdes devem COBRIR as bolhas roxas")
            print("   ✅ Centros vermelhos devem estar NO CENTRO das bolhas")
            print("\n🎯 SE DESALINHADO, AJUSTE:")
            print("   No arquivo: scripts/calibrate_block_simple.py")
            print(f"   - TEST_ROW_HEIGHT_OFFSET = {TEST_ROW_HEIGHT_OFFSET}  (linhas muito juntas/separadas)")
            print(f"   - TEST_RADIUS_OFFSET = {TEST_RADIUS_OFFSET}  (círculos pequenos/grandes)")
            print(f"   - TEST_BUBBLE_SPACING_ADJUST = {TEST_BUBBLE_SPACING_ADJUST}  (bolhas coladas/espaçadas demais)")
            print(f"   - TEST_OFFSET_X_ADJUST = {TEST_OFFSET_X_ADJUST}  (círculos à esquerda/direita)")
            print(f"   - TEST_OFFSET_Y_ADJUST = {TEST_OFFSET_Y_ADJUST}  (círculos acima/abaixo)")
            print("\n💡 DICA: Se bolhas estão coladas, aumente TEST_BUBBLE_SPACING_ADJUST (+10, +20, etc)")
            print("   Execute novamente até alinhar perfeitamente!")
            print("=" * 80)
            
        except Exception as e:
            print(f"❌ ERRO: {e}")
            import traceback
            traceback.print_exc()


def main():
    parser = argparse.ArgumentParser(
        description="Calibração visual SIMPLIFICADA de bloco OMR"
    )
    parser.add_argument("--block_image", required=True, help="Caminho da imagem do bloco")
    parser.add_argument("--gabarito_id", required=True, help="UUID do gabarito")
    parser.add_argument("--block_num", type=int, required=True, help="Número do bloco (1-4)")
    parser.add_argument("--output", default="calibration_output", help="Diretório de saída")
    
    args = parser.parse_args()
    
    # Validar block_num
    if not 1 <= args.block_num <= 4:
        print("❌ ERRO: block_num deve ser entre 1 e 4")
        return
    
    # Criar app Flask
    app = create_app()
    
    with app.app_context():
        calibrator = BlockCalibrator(output_dir=args.output)
        calibrator.run(args.block_image, args.gabarito_id, args.block_num)


if __name__ == "__main__":
    main()
