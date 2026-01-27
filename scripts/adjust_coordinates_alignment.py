# -*- coding: utf-8 -*-
"""
Script para ajustar manualmente start_x, start_y e line_height das coordenadas do JSON
Permite ajustar as coordenadas fixas usadas no método determinístico (com JSON)
"""

import cv2
import numpy as np
import json
import os
import sys
import argparse
from pathlib import Path
from typing import Optional, Dict, List

# Adicionar o diretório raiz ao path para importar módulos do app
script_dir = Path(__file__).parent.parent
sys.path.insert(0, str(script_dir))

# Importar apenas quando necessário
try:
    from app import create_app
    from app.models.answerSheetGabarito import AnswerSheetGabarito
    from app import db
    from app.services.cartao_resposta.correction_n import AnswerSheetCorrectionN
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False
    print("[AVISO] Flask não disponível - algumas funcionalidades desabilitadas")


class CoordinatesAlignmentAdjuster:
    """
    Ajustador de alinhamento das coordenadas fixas (start_x, start_y, line_height).
    Usa coordenadas do JSON ao invés de ratios.
    """
    
    def __init__(self, img_real_path: str, block_num: int, 
                 gabarito_id: str = None, coordinates_json: Dict = None,
                 num_questions: int = None):
        """
        Inicializa o ajustador de coordenadas.
        
        Args:
            img_real_path: Caminho para imagem real do bloco
            block_num: Número do bloco (1-4)
            gabarito_id: ID do gabarito (opcional)
            coordinates_json: JSON de coordenadas (opcional, se não fornecido tenta carregar do gabarito)
            num_questions: Número de questões no bloco (padrão: 11, usado quando não há JSON)
        """
        self.img_real_path = img_real_path
        self.block_num = block_num
        self.gabarito_id = gabarito_id
        self.num_questions_default = num_questions or 11  # Padrão: 11 questões por bloco
        
        # Carregar imagem real
        self.img_real = cv2.imread(img_real_path)
        if self.img_real is None:
            raise ValueError(f"Não foi possível carregar a imagem: {img_real_path}")
        
        # Converter para grayscale se necessário
        if len(self.img_real.shape) == 3:
            self.img_real = cv2.cvtColor(self.img_real, cv2.COLOR_BGR2GRAY)
        
        self.h, self.w = self.img_real.shape[:2]
        print(f"[INFO] Imagem carregada: {self.w}x{self.h}px")
        
        # Carregar coordenadas do JSON
        self.coordinates_json = coordinates_json
        self.block_json = None
        if not self.coordinates_json and FLASK_AVAILABLE:
            self._load_coordinates_from_gabarito()
        
        if self.coordinates_json:
            # Buscar bloco correspondente
            blocks_json = self.coordinates_json.get('blocks', [])
            for b in blocks_json:
                if b.get('block_number') == block_num:
                    self.block_json = b
                    break
            
            if self.block_json:
                # Valores atuais do JSON
                self.start_x = self.block_json.get('start_x', 35)
                self.start_y = self.block_json.get('start_y', 13)
                self.line_height = self.block_json.get('line_height', 16)
                self.bubble_size = self.block_json.get('bubble_size', 15)
                self.bubble_gap = self.block_json.get('bubble_gap', 4)
                print(f"[INFO] Coordenadas carregadas do JSON:")
                print(f"   start_x: {self.start_x}px")
                print(f"   start_y: {self.start_y}px")
                print(f"   line_height: {self.line_height}px")
            else:
                print(f"[AVISO] Bloco {block_num} não encontrado no JSON de coordenadas")
                # Valores padrão
                self.start_x = 35
                self.start_y = 13
                self.line_height = 16
                self.bubble_size = 15
                self.bubble_gap = 4
        else:
            print(f"[AVISO] JSON de coordenadas não disponível, usando valores padrão")
            self.start_x = 35
            self.start_y = 13
            self.line_height = 16
            self.bubble_size = 15
            self.bubble_gap = 4
    
    def _load_coordinates_from_gabarito(self):
        """Carrega coordenadas do gabarito"""
        if not FLASK_AVAILABLE:
            return
        
        try:
            app = create_app()
            with app.app_context():
                # Buscar gabarito
                gabarito_obj = None
                
                if self.gabarito_id:
                    gabarito_obj = AnswerSheetGabarito.query.get(self.gabarito_id)
                else:
                    # Buscar o mais recente com coordinates
                    gabarito_obj = AnswerSheetGabarito.query.filter(
                        AnswerSheetGabarito.coordinates.isnot(None)
                    ).order_by(AnswerSheetGabarito.created_at.desc()).first()
                
                if not gabarito_obj:
                    print(f"[AVISO] Gabarito não encontrado")
                    return
                
                # Carregar coordinates
                coordinates = gabarito_obj.coordinates
                if isinstance(coordinates, str):
                    self.coordinates_json = json.loads(coordinates)
                else:
                    self.coordinates_json = coordinates
                
                print(f"[OK] Coordenadas carregadas do gabarito {gabarito_obj.id}")
                
        except Exception as e:
            print(f"[ERRO] Erro ao carregar coordenadas: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def _gerar_grid_com_coordenadas(self) -> List[Dict]:
        """Gera grid usando coordenadas fixas (start_x, start_y, line_height)"""
        grid = []
        
        # Calcular line_height ajustado baseado no tamanho real da imagem para evitar erro acumulado
        # Se a imagem é 142x473px (novo padrão), ajustar line_height para distribuir melhor o espaço
        PADDING_TOP = 8  # Padding interno superior (do CSS)
        PADDING_BOTTOM = 8  # Padding interno inferior (do CSS)
        total_padding = PADDING_TOP + PADDING_BOTTOM
        
        # Se temos JSON do bloco, usar as questões dele
        if self.block_json:
            questions_json = self.block_json.get('questions', [])
            num_questions = len(questions_json)
            
            # Calcular line_height ideal baseado no tamanho real da imagem
            # Altura útil = altura total - padding
            usable_height = self.h - total_padding
            
            # Se temos altura suficiente e número de questões, calcular line_height mais preciso
            if num_questions > 0 and usable_height > 0:
                # Calcular line_height ideal (pode ser decimal)
                ideal_line_height = usable_height / num_questions
                
                # Se o line_height atual difere muito do ideal, usar um ajuste progressivo
                # Para evitar erro acumulado, usar cálculo mais preciso
                if abs(self.line_height - ideal_line_height) > 0.5:
                    # Usar line_height calculado, arredondado para evitar erro muito grande
                    adjusted_line_height = round(ideal_line_height)
                    if adjusted_line_height != self.line_height:
                        print(f"[INFO] Ajustando line_height de {self.line_height}px para {adjusted_line_height}px (ideal: {ideal_line_height:.2f}px) baseado no tamanho real {self.w}x{self.h}px")
                        # Não alterar self.line_height aqui, mas usar no cálculo
                        use_line_height = adjusted_line_height
                    else:
                        use_line_height = self.line_height
                else:
                    use_line_height = self.line_height
            else:
                use_line_height = self.line_height
            
            for question_json in questions_json:
                q_num = question_json.get('number')
                bubbles = question_json.get('bubbles', [])
                
                if q_num is None:
                    continue
                
                # Recalcular coordenadas usando start_x, start_y e line_height ajustados
                q_idx = questions_json.index(question_json)
                # Usar cálculo mais preciso para evitar erro acumulado
                line_y = int(self.start_y + q_idx * use_line_height)
                
                for alt_idx, bubble in enumerate(bubbles):
                    option = bubble.get('option')
                    # Recalcular X: start_x + alt_idx * (bubble_size + bubble_gap) + bubble_size/2
                    bubble_x = self.start_x + alt_idx * (self.bubble_size + self.bubble_gap) + (self.bubble_size // 2)
                    
                    grid.append({
                        "question": q_num,
                        "letter": option,
                        "x": bubble_x,
                        "y": line_y,
                        "question_index": q_idx,
                        "alternative_index": alt_idx
                    })
        else:
            # Se não temos JSON, gerar grid padrão: num_questions questões, 4 alternativas (A, B, C, D)
            # Baseado no padrão comum de cartões resposta
            num_questions = self.num_questions_default
            options = ['A', 'B', 'C', 'D']  # 4 alternativas padrão
            
            # Calcular line_height ajustado baseado no tamanho real da imagem
            PADDING_TOP = 8  # Padding interno superior (do CSS)
            PADDING_BOTTOM = 8  # Padding interno inferior (do CSS)
            total_padding = PADDING_TOP + PADDING_BOTTOM
            usable_height = self.h - total_padding
            
            # Calcular line_height ideal baseado no tamanho real
            if num_questions > 0 and usable_height > 0:
                ideal_line_height = usable_height / num_questions
                adjusted_line_height = round(ideal_line_height)
                if abs(self.line_height - ideal_line_height) > 0.5:
                    print(f"[INFO] Ajustando line_height de {self.line_height}px para {adjusted_line_height}px (ideal: {ideal_line_height:.2f}px) baseado no tamanho real {self.w}x{self.h}px")
                    use_line_height = adjusted_line_height
                else:
                    use_line_height = self.line_height
            else:
                use_line_height = self.line_height
            
            for q_idx in range(num_questions):
                q_num = q_idx + 1
                # Usar cálculo mais preciso para evitar erro acumulado
                line_y = int(self.start_y + q_idx * use_line_height)
                
                for alt_idx, option in enumerate(options):
                    # Recalcular X: start_x + alt_idx * (bubble_size + bubble_gap) + bubble_size/2
                    bubble_x = self.start_x + alt_idx * (self.bubble_size + self.bubble_gap) + (self.bubble_size // 2)
                    
                    grid.append({
                        "question": q_num,
                        "letter": option,
                        "x": bubble_x,
                        "y": line_y,
                        "question_index": q_idx,
                        "alternative_index": alt_idx
                    })
        
        return grid
    
    def create_visualization_image(self) -> np.ndarray:
        """Cria imagem de visualização com grid sobreposto"""
        # Converter para BGR para desenho
        img_bgr = cv2.cvtColor(self.img_real, cv2.COLOR_GRAY2BGR)
        
        # Gerar grid usando coordenadas ajustadas
        grid = self._gerar_grid_com_coordenadas()
        
        # Raio da bolha para visualização
        bubble_radius = self.bubble_size // 2  # 15px / 2 = 7.5px ≈ 7-8px
        
        # Cores
        COLOR_GRID = (0, 0, 255)  # Vermelho para grid
        COLOR_INFO = (0, 255, 0)  # Verde para informações
        
        # Desenhar grid
        for item in grid:
            x = item['x']
            y = item['y']
            
            # Desenhar círculo do grid
            cv2.circle(img_bgr, (x, y), bubble_radius, COLOR_GRID, 1)
            
            # Desenhar centro
            cv2.circle(img_bgr, (x, y), 2, COLOR_GRID, -1)
        
        # Adicionar informações no topo
        num_questions = len(set(item['question'] for item in grid)) if grid else 0
        info_lines = [
            f"BLOCO {self.block_num:02d} - Coordenadas Fixas",
            f"Tamanho: {self.w}x{self.h}px",
            f"start_x: {self.start_x}px",
            f"start_y: {self.start_y}px",
            f"line_height: {self.line_height}px",
            f"bubble_size: {self.bubble_size}px",
            f"bubble_gap: {self.bubble_gap}px",
            f"Questões: {num_questions}",
            f"Bolhas: {len(grid)} posições"
        ]
        
        y_offset = 20
        for i, line in enumerate(info_lines):
            cv2.putText(img_bgr, line, (10, y_offset + i * 20),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, COLOR_INFO, 1)
        
        return img_bgr
    
    def save_adjustment(self, output_path: str):
        """Salva ajuste de coordenadas"""
        adjustment = {
            'block_num': self.block_num,
            'start_x': self.start_x,
            'start_y': self.start_y,
            'line_height': self.line_height,
            'block_width_ref': self.w,
            'block_height_ref': self.h,
            'img_real_path': self.img_real_path,
            'bubble_size': self.bubble_size,
            'bubble_gap': self.bubble_gap
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(adjustment, f, indent=2, ensure_ascii=False)
        
        print(f"\n[OK] Ajuste salvo em: {output_path}")
        print(f"   start_x: {self.start_x}px")
        print(f"   start_y: {self.start_y}px")
        print(f"   line_height: {self.line_height}px")
        print(f"   Tamanho do bloco (referência): {self.w}x{self.h}px")


def find_image_by_filename(debug_dir: str, filename: str):
    """Encontra uma imagem específica pelo nome do arquivo"""
    if not os.path.isabs(debug_dir):
        script_dir = Path(__file__).parent.parent
        possible_paths = [
            Path(debug_dir),
            script_dir / debug_dir,
            Path.cwd() / debug_dir,
        ]
        
        for path in possible_paths:
            if path.exists():
                debug_dir = str(path.resolve())
                break
        else:
            debug_dir = str(Path(debug_dir).resolve())
    
    debug_path = Path(debug_dir)
    if not debug_path.exists():
        return None
    
    if not filename.endswith(('.jpg', '.jpeg', '.png')):
        patterns = [f"*{filename}*.jpg", f"*{filename}*.jpeg", f"*{filename}*.png"]
    else:
        patterns = [f"*{filename}*"]
    
    for pattern in patterns:
        files = list(debug_path.glob(pattern))
        if files:
            return str(max(files, key=os.path.getmtime).resolve())
    
    return None


def main():
    parser = argparse.ArgumentParser(
        description='Ajuste manual de start_x, start_y e line_height das coordenadas fixas',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  # Ajustar coordenadas manualmente
  python scripts/adjust_coordinates_alignment.py --block 1 --real-filename 20260120_184149_478_04_block_01_real_only --start-x 40 --start-y 15 --line-height 18 --save
  
  # Apenas visualizar com valores atuais
  python scripts/adjust_coordinates_alignment.py --block 1 --real-filename 20260120_184149_478_04_block_01_real_only
        """
    )
    parser.add_argument('--real', '-i', type=str, default=None,
                       help='Caminho para imagem real do bloco')
    parser.add_argument('--real-filename', type=str, default=None,
                       help='Nome específico da imagem real (ex: 20260120_184149_478_04_block_01_real_only.jpg)')
    parser.add_argument('--block', '-b', type=int, required=True,
                       help='Número do bloco (1-4)')
    parser.add_argument('--gabarito-id', type=str, default=None,
                       help='ID do gabarito (opcional)')
    parser.add_argument('--start-x', type=int, default=None,
                       help='start_x em pixels')
    parser.add_argument('--start-y', type=int, default=None,
                       help='start_y em pixels')
    parser.add_argument('--line-height', type=int, default=None,
                       help='line_height em pixels')
    parser.add_argument('--num-questions', type=int, default=None,
                       help='Número de questões no bloco (padrão: 11, usado quando não há JSON)')
    parser.add_argument('--debug-dir', type=str, default='debug_corrections',
                       help='Diretório de debug')
    parser.add_argument('--save', action='store_true',
                       help='Salvar ajuste')
    
    args = parser.parse_args()
    
    # Buscar imagem real por nome específico se fornecido
    if args.real_filename:
        print(f"[BUSCA] Buscando imagem real por nome: '{args.real_filename}'...")
        real_path = find_image_by_filename(args.debug_dir, args.real_filename)
        if real_path:
            args.real = real_path
            print(f"   [OK] Imagem real encontrada: {Path(real_path).name}")
        else:
            print(f"   [ERRO] Imagem real não encontrada: '{args.real_filename}'")
            return 1
    
    if not args.real:
        print("[ERRO] É necessário fornecer --real ou --real-filename")
        parser.print_help()
        return 1
    
    # Criar ajustador
    try:
        adjuster = CoordinatesAlignmentAdjuster(
            args.real,
            args.block,
            gabarito_id=args.gabarito_id,
            num_questions=args.num_questions
        )
        
        # Aplicar valores da linha de comando
        if args.start_x is not None:
            adjuster.start_x = args.start_x
            print(f"[PARAM] start_x da linha de comando: {adjuster.start_x}px")
        if args.start_y is not None:
            adjuster.start_y = args.start_y
            print(f"[PARAM] start_y da linha de comando: {adjuster.start_y}px")
        if args.line_height is not None:
            adjuster.line_height = args.line_height
            print(f"[PARAM] line_height da linha de comando: {adjuster.line_height}px")
        
        # Salvar se solicitado
        if args.save:
            script_dir = Path(__file__).parent.parent
            alignment_dir = script_dir / "app" / "services" / "cartao_resposta"
            alignment_dir.mkdir(parents=True, exist_ok=True)
            
            output_path = str(alignment_dir / f"block_{args.block:02d}_coordinates_adjustment.json")
            adjuster.save_adjustment(output_path)
            
            # Salvar imagem de visualização
            img = adjuster.create_visualization_image()
            debug_dir = script_dir / "debug_corrections"
            debug_dir.mkdir(parents=True, exist_ok=True)
            viz_path = debug_dir / f"block_{args.block:02d}_coordinates_alignment.jpg"
            cv2.imwrite(str(viz_path), img)
            print(f"[OK] Imagem de visualização salva: {viz_path}")
        else:
            # Apenas gerar visualização
            script_dir = Path(__file__).parent.parent
            debug_dir = script_dir / "debug_corrections"
            debug_dir.mkdir(parents=True, exist_ok=True)
            
            img = adjuster.create_visualization_image()
            viz_path = debug_dir / f"block_{args.block:02d}_coordinates_alignment.jpg"
            cv2.imwrite(str(viz_path), img)
            print(f"\n[OK] Imagem de visualização salva: {viz_path}")
            print(f"\n[DICA] Para salvar o ajuste, use --save:")
            print(f"   python scripts/adjust_coordinates_alignment.py --block {args.block} --real-filename {args.real_filename} --start-x {adjuster.start_x} --start-y {adjuster.start_y} --line-height {adjuster.line_height} --save")
            
    except Exception as e:
        print(f"[ERRO] Erro: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
