# -*- coding: utf-8 -*-
"""
Script de calibração visual do grid OMR (NÃO-INTERATIVO)

USO:
    1. Ajuste as constantes CALIBRATION_* abaixo
    2. Execute: python scripts/calibrate_grid_visual.py --image path/to/image.jpg --gabarito_id UUID
    3. Veja as imagens geradas em calibration_output/
    4. Ajuste as constantes até alinhar perfeitamente
    5. Copie os valores finais para correction_new_grid.py

OBJETIVO:
    Gerar visualizações do grid calculado vs. bolhas reais
    para ajustar empiricamente as constantes do pipeline OMR
"""

import cv2
import numpy as np
import json
import sys
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple

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
CALIBRATION_BUBBLE_GAP_PX = 4
CALIBRATION_BLOCK_OFFSET_X = 31  # 2 (borda) + 4 (padding) + 25 (num)
CALIBRATION_BLOCK_OFFSET_Y = 10  # 2 (borda) + 8 (padding)

# Testes incrementais (ajuste esses valores)
TEST_ROW_HEIGHT_OFFSET = 10  # +/- pixels para ajustar altura da linha
TEST_RADIUS_OFFSET = 0      # +/- pixels para ajustar raio
TEST_OFFSET_X_ADJUST = 20    # +/- pixels para ajustar offset X
TEST_OFFSET_Y_ADJUST = 100    # +/- pixels para ajustar offset Y

# ============================================================================
# CLASSE PRINCIPAL
# ============================================================================

class GridCalibrator:
    """Calibrador visual de grid OMR"""
    
    def __init__(self, output_dir: str = "calibration_output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Aplicar ajustes de calibração
        self.row_height = CALIBRATION_ROW_HEIGHT_PX + TEST_ROW_HEIGHT_OFFSET
        self.bubble_radius = int(CALIBRATION_BUBBLE_RADIUS_PX + TEST_RADIUS_OFFSET)
        self.bubble_gap = CALIBRATION_BUBBLE_GAP_PX
        self.offset_x = CALIBRATION_BLOCK_OFFSET_X + TEST_OFFSET_X_ADJUST
        self.offset_y = CALIBRATION_BLOCK_OFFSET_Y + TEST_OFFSET_Y_ADJUST
        
        print("=" * 80)
        print("🎯 CALIBRADOR VISUAL DE GRID OMR")
        print("=" * 80)
        print(f"📐 Parâmetros atuais:")
        print(f"   Row height: {self.row_height:.2f}px")
        print(f"   Bubble radius: {self.bubble_radius}px")
        print(f"   Bubble gap: {self.bubble_gap}px")
        print(f"   Offset X: {self.offset_x}px")
        print(f"   Offset Y: {self.offset_y}px")
        print(f"📁 Output: {self.output_dir}")
        print("=" * 80)
    
    def load_image(self, image_path: str) -> np.ndarray:
        """Carrega imagem"""
        img = cv2.imread(image_path)
        if img is None:
            raise FileNotFoundError(f"Imagem não encontrada: {image_path}")
        print(f"✅ Imagem carregada: {img.shape}")
        return img
    
    def detect_a4_anchors(self, img: np.ndarray) -> Dict:
        """Detecta âncoras A4 (simplificado)"""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        contours, hierarchy = cv2.findContours(binary, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        
        squares = []
        h, w = img.shape[:2]
        min_area = (w * h) * 0.0001
        max_area = (w * h) * 0.001
        
        for i, cnt in enumerate(contours):
            area = cv2.contourArea(cnt)
            if not (min_area < area < max_area):
                continue
            
            peri = cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, 0.04 * peri, True)
            
            if len(approx) == 4:
                x, y, w_rect, h_rect = cv2.boundingRect(approx)
                aspect_ratio = float(w_rect) / h_rect if h_rect > 0 else 0
                
                if 0.8 <= aspect_ratio <= 1.2:
                    M = cv2.moments(cnt)
                    if M["m00"] > 0:
                        cx = int(M["m10"] / M["m00"])
                        cy = int(M["m01"] / M["m00"])
                        squares.append({"cx": cx, "cy": cy, "cnt": approx})
        
        if len(squares) < 4:
            raise ValueError(f"Apenas {len(squares)} âncoras detectadas (esperado: 4)")
        
        # Ordenar: TL, TR, BR, BL
        squares.sort(key=lambda s: s["cy"])
        top_two = sorted(squares[:2], key=lambda s: s["cx"])
        bottom_two = sorted(squares[-2:], key=lambda s: s["cx"])
        
        anchors = {
            "TL": top_two[0]["cnt"][0][0].tolist(),
            "TR": top_two[1]["cnt"][0][0].tolist(),
            "BR": bottom_two[1]["cnt"][0][0].tolist(),
            "BL": bottom_two[0]["cnt"][0][0].tolist()
        }
        
        print(f"✅ 4 âncoras A4 detectadas")
        return anchors
    
    def normalize_to_a4(self, img: np.ndarray, anchors: Dict) -> np.ndarray:
        """Normaliza para A4 (2480x3508 a 300 DPI)"""
        src_pts = np.float32([
            anchors["TL"], anchors["TR"],
            anchors["BR"], anchors["BL"]
        ])
        
        dst_pts = np.float32([
            [0, 0], [2480, 0],
            [2480, 3508], [0, 3508]
        ])
        
        M = cv2.getPerspectiveTransform(src_pts, dst_pts)
        normalized = cv2.warpPerspective(img, M, (2480, 3508))
        print(f"✅ Imagem normalizada: {normalized.shape}")
        return normalized
    
    def detect_blocks(self, img: np.ndarray) -> List[Dict]:
        """Detecta blocos de resposta (simplificado)"""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        _, binary = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        dilated = cv2.dilate(binary, kernel, iterations=2)
        
        contours, hierarchy = cv2.findContours(dilated, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        
        h, w = img.shape[:2]
        min_area = (w * h) * 0.02
        max_area = (w * h) * 0.15
        
        blocks = []
        for i, cnt in enumerate(contours):
            if hierarchy[0][i][3] != -1:  # Apenas contornos externos
                continue
            
            area = cv2.contourArea(cnt)
            if not (min_area < area < max_area):
                continue
            
            peri = cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
            
            if len(approx) >= 4:
                x, y, w_rect, h_rect = cv2.boundingRect(approx)
                aspect_ratio = float(h_rect) / w_rect if w_rect > 0 else 0
                
                if 0.3 <= aspect_ratio <= 2.0:
                    blocks.append({
                        "x": x, "y": y,
                        "w": w_rect, "h": h_rect,
                        "area": area
                    })
        
        # Ordenar por X (esquerda para direita)
        blocks.sort(key=lambda b: b["x"])
        print(f"✅ {len(blocks)} blocos detectados")
        return blocks
    
    def get_topology(self, gabarito_id: str) -> Dict:
        """Busca topologia do gabarito"""
        gabarito = AnswerSheetGabarito.query.get(gabarito_id)
        if not gabarito:
            raise ValueError(f"Gabarito não encontrado: {gabarito_id}")
        
        if isinstance(gabarito.topology_json, str):
            topology = json.loads(gabarito.topology_json)
        else:
            topology = gabarito.topology_json
        
        print(f"✅ Topologia carregada: {topology.get('num_blocks', 0)} blocos")
        return topology
    
    def draw_calibration_grid(self, block_img: np.ndarray, 
                             topology_block: Dict, 
                             block_num: int) -> np.ndarray:
        """Desenha grid de calibração sobre o bloco"""
        
        debug_img = block_img.copy()
        h, w = debug_img.shape[:2]
        
        questions = topology_block.get("questions", [])
        num_questions = len(questions)
        
        print(f"\n📦 BLOCO {block_num}: {num_questions} questões")
        print(f"   Dimensões: {w}x{h}px")
        
        # Desenhar linhas horizontais (questões)
        for i in range(num_questions + 1):
            y = int(self.offset_y + (self.row_height * i))
            if 0 <= y < h:
                cv2.line(debug_img, (0, y), (w, y), (0, 255, 255), 2)  # Amarelo
                if i < num_questions:
                    cv2.putText(debug_img, f"Q{questions[i]['q']}", 
                               (5, y + 25), cv2.FONT_HERSHEY_SIMPLEX, 
                               0.5, (0, 255, 255), 1)
        
        # Desenhar bolhas calculadas
        for row_idx, question in enumerate(questions):
            q_num = question.get("q")
            alternatives = question.get("alternatives", [])
            
            # Calcular cy
            cy = int(self.offset_y + (self.row_height * row_idx) + (self.row_height / 2))
            
            for col_idx, alt_letter in enumerate(alternatives):
                # Calcular cx
                bubble_spacing = 15 + self.bubble_gap  # 15px (largura CSS) + gap
                cx = int(self.offset_x + (col_idx * bubble_spacing) + (15 / 2))
                
                # Desenhar círculo verde (calculado)
                cv2.circle(debug_img, (cx, cy), self.bubble_radius, (0, 255, 0), 2)
                cv2.circle(debug_img, (cx, cy), 2, (0, 0, 255), -1)  # Centro vermelho
                
                # Label
                cv2.putText(debug_img, alt_letter, (cx - 5, cy - self.bubble_radius - 5),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 0, 0), 1)
        
        # Adicionar informações na imagem
        cv2.putText(debug_img, f"row_h={self.row_height:.1f} radius={self.bubble_radius} gap={self.bubble_gap}", 
                   (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
        cv2.putText(debug_img, f"offset_x={self.offset_x} offset_y={self.offset_y}", 
                   (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
        
        return debug_img
    
    def save_image(self, img: np.ndarray, name: str):
        """Salva imagem no diretório de output"""
        filename = f"{self.timestamp}_{name}"
        filepath = self.output_dir / filename
        cv2.imwrite(str(filepath), img)
        print(f"💾 Salvo: {filepath}")
    
    def run(self, image_path: str, gabarito_id: str):
        """Executa calibração"""
        try:
            # 1. Carregar imagem
            img = self.load_image(image_path)
            self.save_image(img, "01_original.jpg")
            
            # 2. Detectar âncoras A4
            anchors = self.detect_a4_anchors(img)
            
            # 3. Normalizar para A4
            normalized = self.normalize_to_a4(img, anchors)
            self.save_image(normalized, "02_normalized_a4.jpg")
            
            # 4. Detectar blocos
            blocks = self.detect_blocks(normalized)
            
            # 5. Buscar topologia
            topology = self.get_topology(gabarito_id)
            topology_blocks = topology.get("topology", {}).get("blocks", [])
            
            if len(blocks) != len(topology_blocks):
                print(f"⚠️  Blocos detectados ({len(blocks)}) != topologia ({len(topology_blocks)})")
            
            # 6. Processar cada bloco
            for i, block in enumerate(blocks[:len(topology_blocks)]):
                block_num = i + 1
                x, y, w, h = block["x"], block["y"], block["w"], block["h"]
                
                # Extrair ROI do bloco
                block_roi = normalized[y:y+h, x:x+w].copy()
                
                # Desenhar grid de calibração
                calibrated = self.draw_calibration_grid(
                    block_roi, 
                    topology_blocks[i],
                    block_num
                )
                
                self.save_image(calibrated, f"block{block_num}_calibrated.jpg")
            
            print("\n" + "=" * 80)
            print("✅ CALIBRAÇÃO CONCLUÍDA!")
            print("=" * 80)
            print(f"📁 Imagens salvas em: {self.output_dir}")
            print("\n🎯 PRÓXIMOS PASSOS:")
            print("1. Abra as imagens block*_calibrated.jpg")
            print("2. Verifique se os círculos verdes cobrem as bolhas roxas")
            print("3. Ajuste as constantes no topo deste script:")
            print(f"   - TEST_ROW_HEIGHT_OFFSET = {TEST_ROW_HEIGHT_OFFSET}")
            print(f"   - TEST_RADIUS_OFFSET = {TEST_RADIUS_OFFSET}")
            print(f"   - TEST_OFFSET_X_ADJUST = {TEST_OFFSET_X_ADJUST}")
            print(f"   - TEST_OFFSET_Y_ADJUST = {TEST_OFFSET_Y_ADJUST}")
            print("4. Execute novamente até alinhar perfeitamente")
            print("5. Copie os valores finais para correction_new_grid.py")
            print("=" * 80)
            
        except Exception as e:
            print(f"❌ ERRO: {e}")
            import traceback
            traceback.print_exc()


# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Calibração visual de grid OMR (não-interativo)"
    )
    parser.add_argument("--image", required=True, help="Caminho da imagem")
    parser.add_argument("--gabarito_id", required=True, help="UUID do gabarito")
    parser.add_argument("--output", default="calibration_output", help="Diretório de saída")
    
    args = parser.parse_args()
    
    # Criar app Flask
    app = create_app()
    
    with app.app_context():
        calibrator = GridCalibrator(output_dir=args.output)
        calibrator.run(args.image, args.gabarito_id)


if __name__ == "__main__":
    main()
