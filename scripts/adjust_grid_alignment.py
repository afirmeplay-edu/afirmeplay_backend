# -*- coding: utf-8 -*-
"""
Script interativo para ajustar manualmente a posição do grid virtual
Permite ajustar LEFT_MARGIN_RATIO, TOP_PADDING_RATIO e BUBBLE_SPACING_RATIO
para alinhar o grid virtual com as bolhas reais detectadas
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


class GridAlignmentAdjuster:
    """
    Ajustador de alinhamento do grid virtual.
    Permite ajustar os ratios de posicionamento do grid para alinhar com bolhas reais.
    """
    
    def __init__(self, img_real_path: str, block_num: int, 
                 gabarito_id: str = None, test_id: str = None,
                 scale_info: Optional[Dict] = None):
        """
        Inicializa o ajustador de grid.
        
        Args:
            img_real_path: Caminho para imagem real do bloco
            block_num: Número do bloco (1-4)
            gabarito_id: ID do gabarito (opcional)
            test_id: ID do teste (opcional)
            scale_info: Informações de escala do A4 (opcional)
        """
        self.img_real_path = img_real_path
        self.block_num = block_num
        self.gabarito_id = gabarito_id
        self.test_id = test_id
        self.scale_info = scale_info
        
        # Carregar imagem real
        self.img_real = cv2.imread(img_real_path)
        if self.img_real is None:
            raise ValueError(f"Não foi possível carregar a imagem: {img_real_path}")
        
        # Converter para grayscale se necessário
        if len(self.img_real.shape) == 3:
            self.img_real = cv2.cvtColor(self.img_real, cv2.COLOR_BGR2GRAY)
        
        self.h, self.w = self.img_real.shape[:2]
        print(f"[INFO] Imagem carregada: {self.w}x{self.h}px")
        
        # Carregar configuração do bloco da topology
        self.block_config = None
        self.questions_config = []
        if FLASK_AVAILABLE:
            self._load_block_config()
        
        # Ratios ajustáveis (valores padrão do código)
        self.left_margin_ratio = 0.18  # 18% da largura
        self.top_padding_ratio = 0.05  # 5% da altura
        self.bubble_spacing_ratio = 0.16  # 16% da largura entre bolhas
        
        # Line height (será calculado dinamicamente)
        self.line_height = None
        
        # Estado para visualização
        self.show_grid = True
        self.show_bubbles = True  # Mostrar bolhas detectadas (se disponível)
        
    def _load_block_config(self):
        """Carrega configuração do bloco da topology do gabarito"""
        if not FLASK_AVAILABLE:
            return
        
        try:
            app = create_app()
            with app.app_context():
                # Buscar gabarito
                gabarito_obj = None
                
                if self.gabarito_id:
                    gabarito_obj = AnswerSheetGabarito.query.get(self.gabarito_id)
                elif self.test_id:
                    gabarito_obj = AnswerSheetGabarito.query.filter_by(test_id=self.test_id).first()
                else:
                    # Buscar o mais recente com blocks_config
                    gabarito_obj = AnswerSheetGabarito.query.filter(
                        AnswerSheetGabarito.blocks_config.isnot(None)
                    ).order_by(AnswerSheetGabarito.created_at.desc()).first()
                
                if not gabarito_obj:
                    print(f"[AVISO] Gabarito não encontrado - grid será gerado sem topology")
                    return
                
                # Carregar blocks_config
                blocks_config_dict = gabarito_obj.blocks_config
                if isinstance(blocks_config_dict, str):
                    blocks_config_dict = json.loads(blocks_config_dict)
                
                # Buscar topology
                blocks_structure = blocks_config_dict.get('topology') if blocks_config_dict else None
                if not blocks_structure:
                    blocks_structure = blocks_config_dict.get('structure') if blocks_config_dict else None
                
                if not blocks_structure:
                    print(f"[AVISO] Topology não encontrada - grid será gerado sem estrutura")
                    return
                
                # Encontrar o bloco correspondente
                blocks = blocks_structure.get('blocks', [])
                for block in blocks:
                    if block.get('block_id') == self.block_num:
                        self.block_config = block
                        self.questions_config = block.get('questions', [])
                        print(f"[OK] Topology carregada: {len(self.questions_config)} questões no bloco {self.block_num}")
                        return
                
                print(f"[AVISO] Bloco {self.block_num} não encontrado na topology")
                
        except Exception as e:
            print(f"[ERRO] Erro ao carregar block_config: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def _calcular_line_height(self) -> int:
        """Calcula line_height dinamicamente"""
        if not FLASK_AVAILABLE:
            # Fallback: estimar baseado na altura
            if self.questions_config:
                return int(self.h / len(self.questions_config))
            return 20
        
        try:
            correction_service = AnswerSheetCorrectionN(debug=False)
            line_height = correction_service._calcular_line_height_dinamico(
                self.img_real, 
                len(self.questions_config) if self.questions_config else 26,
                self.block_num
            )
            
            if line_height is None:
                # Fallback
                line_height = int(self.h / len(self.questions_config)) if self.questions_config else 20
            
            return line_height
        except Exception as e:
            print(f"[AVISO] Erro ao calcular line_height: {str(e)}, usando fallback")
            return int(self.h / len(self.questions_config)) if self.questions_config else 20
    
    def _gerar_grid_virtual(self) -> List[Dict]:
        """Gera grid virtual com os ratios atuais"""
        if not self.questions_config:
            print(f"[AVISO] Sem questões configuradas, usando 26 questões padrão")
            # Criar questões padrão
            self.questions_config = [
                {'q': i + 1 + (self.block_num - 1) * 26, 'alternatives': ['A', 'B', 'C', 'D']}
                for i in range(26)
            ]
        
        # Calcular line_height se necessário (sempre calcular para garantir que está correto)
        calculated_line_height = self._calcular_line_height()
        if self.line_height is None:
            self.line_height = calculated_line_height
            print(f"[INFO] Line height calculado: {self.line_height}px")
        elif self.line_height != calculated_line_height:
            # Se o line_height foi fornecido mas difere do calculado, avisar
            print(f"[AVISO] Line height fornecido ({self.line_height}px) difere do calculado ({calculated_line_height}px)")
            print(f"[INFO] Usando line_height calculado: {calculated_line_height}px")
            self.line_height = calculated_line_height
        
        # Calcular valores em pixels
        left_margin = int(self.w * self.left_margin_ratio)
        bubble_spacing = int(self.w * self.bubble_spacing_ratio)
        top_padding = int(self.h * self.top_padding_ratio)
        # TOP_PADDING_RATIO pode ser negativo, garantir que y_start não seja negativo
        y_start = max(0, top_padding) + self.line_height // 2
        
        grid = []
        
        for i, question_config in enumerate(self.questions_config):
            q_num = question_config.get('q')
            alternatives = question_config.get('alternatives', ['A', 'B', 'C', 'D'])
            
            if q_num is None:
                continue
            
            # Calcular Y da linha
            y = y_start + int(i * self.line_height)
            
            # Gerar posições para cada alternativa
            for j, letter in enumerate(alternatives):
                x = left_margin + int(j * bubble_spacing)
                
                grid.append({
                    "question": q_num,
                    "letter": letter,
                    "x": x,
                    "y": y,
                    "question_index": i,
                    "alternative_index": j
                })
        
        return grid
    
    def _calcular_raio_bolha(self) -> int:
        """Calcula raio da bolha baseado no template"""
        if FLASK_AVAILABLE:
            try:
                correction_service = AnswerSheetCorrectionN(debug=False)
                return correction_service._calcular_raio_bolha_template(self.img_real, self.scale_info)
            except:
                pass
        
        # Fallback: 4% da largura
        return max(5, int(self.w * 0.04))
    
    def create_visualization_image(self) -> np.ndarray:
        """Cria imagem de visualização com grid virtual sobreposto"""
        # Converter para BGR para desenho
        img_bgr = cv2.cvtColor(self.img_real, cv2.COLOR_GRAY2BGR)
        
        # Gerar grid virtual
        grid = self._gerar_grid_virtual()
        
        # Calcular raio da bolha (15px para medição)
        bubble_radius = self._calcular_raio_bolha()
        
        # Raio maior para visualização do grid (16px diâmetro = 8px raio)
        # Usar raio maior apenas para desenho, manter raio original para cálculos
        grid_radius = int(bubble_radius * (16.0 / 15.0))  # Proporcional: 16px / 15px
        
        # Cores
        COLOR_GRID = (0, 0, 255)  # Vermelho para grid virtual
        COLOR_INFO = (0, 255, 0)  # Verde para informações
        
        # Desenhar grid virtual
        if self.show_grid:
            for item in grid:
                x = item['x']
                y = item['y']
                
                # Desenhar círculo do grid (usar grid_radius de 16px para visualização)
                cv2.circle(img_bgr, (x, y), grid_radius, COLOR_GRID, 1)
                
                # Desenhar centro
                cv2.circle(img_bgr, (x, y), 2, COLOR_GRID, -1)
        
        # Adicionar informações no topo
        top_padding_px = int(self.h * self.top_padding_ratio) if self.top_padding_ratio is not None else 0
        top_padding_str = f"{self.top_padding_ratio:.3f}" if self.top_padding_ratio is not None else "null (auto)"
        
        info_lines = [
            f"BLOCO {self.block_num:02d} - Grid Virtual",
            f"Tamanho: {self.w}x{self.h}px",
            f"LEFT_MARGIN_RATIO: {self.left_margin_ratio:.3f} ({int(self.w * self.left_margin_ratio)}px)",
            f"TOP_PADDING_RATIO: {top_padding_str} ({top_padding_px}px)",
            f"BUBBLE_SPACING_RATIO: {self.bubble_spacing_ratio:.3f} ({int(self.w * self.bubble_spacing_ratio)}px)",
            f"LINE_HEIGHT: {self.line_height}px",
            f"Bolhas: {len(grid)} posições, {len(self.questions_config)} questões"
        ]
        
        y_offset = 20
        for i, line in enumerate(info_lines):
            cv2.putText(img_bgr, line, (10, y_offset + i * 20),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, COLOR_INFO, 1)
        
        # Adicionar ajuda
        help_text = "Setas: ajustar ratios | A/D: left_margin | W/S: top_padding | E/Q: bubble_spacing | I/K: line_height | Espaço: toggle grid | S: salvar | Q: sair"
        cv2.putText(img_bgr, help_text, (10, self.h - 20),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, (128, 128, 128), 1)
        
        return img_bgr
    
    def save_config(self, output_path: str):
        """Salva configuração do grid"""
        # Garantir que line_height seja calculado se ainda não foi
        if self.line_height is None:
            self.line_height = self._calcular_line_height()
        
        config = {
            'block_num': self.block_num,
            'left_margin_ratio': self.left_margin_ratio,
            'top_padding_ratio': self.top_padding_ratio,
            'bubble_spacing_ratio': self.bubble_spacing_ratio,
            'line_height': self.line_height,
            'block_width_ref': self.w,
            'block_height_ref': self.h,
            'img_real_path': self.img_real_path
        }
        
        # Adicionar scale_info se disponível
        if self.scale_info:
            config['scale_info'] = self.scale_info
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        print(f"\n[OK] Configuração salva em: {output_path}")
        print(f"   LEFT_MARGIN_RATIO: {self.left_margin_ratio:.3f} ({int(self.w * self.left_margin_ratio)}px)")
        if self.top_padding_ratio is not None:
            top_padding_px = int(self.h * self.top_padding_ratio)
            print(f"   TOP_PADDING_RATIO: {self.top_padding_ratio:.3f} ({top_padding_px}px)")
        else:
            print(f"   TOP_PADDING_RATIO: null (será calculado automaticamente)")
        print(f"   BUBBLE_SPACING_RATIO: {self.bubble_spacing_ratio:.3f} ({int(self.w * self.bubble_spacing_ratio)}px)")
        print(f"   LINE_HEIGHT: {self.line_height}px")
        print(f"   Tamanho do bloco (referência): {self.w}x{self.h}px")
    
    def run(self, interactive: bool = True):
        """Executa o ajuste interativo ou não-interativo"""
        if interactive:
            try:
                return self._run_interactive()
            except cv2.error as e:
                if "not implemented" in str(e) or "GUI" in str(e):
                    print("\n[AVISO] OpenCV sem suporte a GUI detectado.")
                    print("   Mudando para modo não-interativo...")
                    return self._run_non_interactive()
                else:
                    raise
        else:
            return self._run_non_interactive()
    
    def _run_interactive(self):
        """Executa o ajuste interativo com janelas"""
        print("=" * 60)
        print("Ajuste Manual de Alinhamento do Grid Virtual")
        print("=" * 60)
        print("\nControles:")
        print("  TECLADO:")
        print("    a/d : Ajustar LEFT_MARGIN_RATIO (-0.001 / +0.001)")
        print("    A/D : Ajustar LEFT_MARGIN_RATIO (-0.01 / +0.01) [Shift]")
        print("    w/x : Ajustar TOP_PADDING_RATIO (-0.001 / +0.001)")
        print("    W/X : Ajustar TOP_PADDING_RATIO (-0.01 / +0.01) [Shift]")
        print("    e/r : Ajustar BUBBLE_SPACING_RATIO (-0.001 / +0.001)")
        print("    E/R : Ajustar BUBBLE_SPACING_RATIO (-0.01 / +0.01) [Shift]")
        print("    i/k : Ajustar LINE_HEIGHT (-1 / +1)")
        print("    Espaço: Alternar exibição do grid")
        print("    S: Salvar configuração")
        print("    Q: Sair sem salvar")
        print(f"\nRatios iniciais:")
        print(f"   LEFT_MARGIN_RATIO: {self.left_margin_ratio:.3f}")
        print(f"   TOP_PADDING_RATIO: {self.top_padding_ratio:.3f}")
        print(f"   BUBBLE_SPACING_RATIO: {self.bubble_spacing_ratio:.3f}")
        print(f"   LINE_HEIGHT: {self.line_height}px")
        print("\nAbrindo janela de ajuste...")
        
        window_name = f"Ajuste de Grid - Bloco {self.block_num:02d}"
        try:
            cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(window_name, 1200, 800)
        except Exception as e:
            print(f"[ERRO] Erro ao criar janela: {e}")
            raise
        
        print("[INFO] Janela aberta. Use as teclas para ajustar. Pressione Q para sair.\n")
        
        while True:
            img = self.create_visualization_image()
            cv2.imshow(window_name, img)
            
            key = cv2.waitKey(0) & 0xFF
            
            # Verificar se janela ainda está aberta
            try:
                if cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1:
                    print("\n[X] Janela fechada")
                    break
            except:
                print("\n[X] Janela fechada")
                break
            
            if key == ord('q') or key == 27:  # Q ou ESC
                print("\n[X] Sair sem salvar")
                break
            elif key == ord('s'):  # S - Salvar
                script_dir = Path(__file__).parent.parent
                alignment_dir = script_dir / "app" / "services" / "cartao_resposta"
                alignment_dir.mkdir(parents=True, exist_ok=True)
                
                output_path = str(alignment_dir / f"block_{self.block_num:02d}_grid_alignment.json")
                self.save_config(output_path)
                
                # Salvar imagem de visualização
                debug_dir = script_dir / "debug_corrections"
                debug_dir.mkdir(parents=True, exist_ok=True)
                viz_path = debug_dir / f"block_{self.block_num:02d}_grid_alignment.jpg"
                cv2.imwrite(str(viz_path), img)
                print(f"[OK] Imagem de visualização salva: {viz_path}")
                print("\nPressione Q para sair.")
            elif key == ord(' '):  # Espaço - Toggle grid
                self.show_grid = not self.show_grid
                print(f"   Grid: {'ON' if self.show_grid else 'OFF'}")
            elif key == ord('a'):  # A - Diminuir left_margin (0.001)
                self.left_margin_ratio = max(0.0, self.left_margin_ratio - 0.001)
                print(f"   LEFT_MARGIN_RATIO: {self.left_margin_ratio:.3f} ({int(self.w * self.left_margin_ratio)}px)")
            elif key == ord('A'):  # Shift+A - Diminuir left_margin (0.01)
                self.left_margin_ratio = max(0.0, self.left_margin_ratio - 0.01)
                print(f"   LEFT_MARGIN_RATIO: {self.left_margin_ratio:.3f} ({int(self.w * self.left_margin_ratio)}px)")
            elif key == ord('d'):  # D - Aumentar left_margin (0.001)
                self.left_margin_ratio = min(0.5, self.left_margin_ratio + 0.001)
                print(f"   LEFT_MARGIN_RATIO: {self.left_margin_ratio:.3f} ({int(self.w * self.left_margin_ratio)}px)")
            elif key == ord('D'):  # Shift+D - Aumentar left_margin (0.01)
                self.left_margin_ratio = min(0.5, self.left_margin_ratio + 0.01)
                print(f"   LEFT_MARGIN_RATIO: {self.left_margin_ratio:.3f} ({int(self.w * self.left_margin_ratio)}px)")
            elif key == ord('w'):  # W - Diminuir top_padding (0.001)
                self.top_padding_ratio = max(0.0, self.top_padding_ratio - 0.001)
                print(f"   TOP_PADDING_RATIO: {self.top_padding_ratio:.3f} ({int(self.h * self.top_padding_ratio)}px)")
            elif key == ord('W'):  # Shift+W - Diminuir top_padding (0.01)
                self.top_padding_ratio = max(0.0, self.top_padding_ratio - 0.01)
                print(f"   TOP_PADDING_RATIO: {self.top_padding_ratio:.3f} ({int(self.h * self.top_padding_ratio)}px)")
            elif key == ord('x'):  # X - Aumentar top_padding (0.001) - mudado de 's' para evitar conflito
                self.top_padding_ratio = min(0.3, self.top_padding_ratio + 0.001)
                print(f"   TOP_PADDING_RATIO: {self.top_padding_ratio:.3f} ({int(self.h * self.top_padding_ratio)}px)")
            elif key == ord('X'):  # Shift+X - Aumentar top_padding (0.01)
                self.top_padding_ratio = min(0.3, self.top_padding_ratio + 0.01)
                print(f"   TOP_PADDING_RATIO: {self.top_padding_ratio:.3f} ({int(self.h * self.top_padding_ratio)}px)")
            elif key == ord('e'):  # E - Diminuir bubble_spacing (0.001)
                self.bubble_spacing_ratio = max(0.05, self.bubble_spacing_ratio - 0.001)
                print(f"   BUBBLE_SPACING_RATIO: {self.bubble_spacing_ratio:.3f} ({int(self.w * self.bubble_spacing_ratio)}px)")
            elif key == ord('E'):  # Shift+E - Diminuir bubble_spacing (0.01)
                self.bubble_spacing_ratio = max(0.05, self.bubble_spacing_ratio - 0.01)
                print(f"   BUBBLE_SPACING_RATIO: {self.bubble_spacing_ratio:.3f} ({int(self.w * self.bubble_spacing_ratio)}px)")
            elif key == ord('r'):  # R - Aumentar bubble_spacing (0.001) - mudado de 'q' para evitar conflito
                self.bubble_spacing_ratio = min(0.3, self.bubble_spacing_ratio + 0.001)
                print(f"   BUBBLE_SPACING_RATIO: {self.bubble_spacing_ratio:.3f} ({int(self.w * self.bubble_spacing_ratio)}px)")
            elif key == ord('R'):  # Shift+R - Aumentar bubble_spacing (0.01)
                self.bubble_spacing_ratio = min(0.3, self.bubble_spacing_ratio + 0.01)
                print(f"   BUBBLE_SPACING_RATIO: {self.bubble_spacing_ratio:.3f} ({int(self.w * self.bubble_spacing_ratio)}px)")
            elif key == ord('i') or key == ord('I'):  # I - Aumentar line_height
                self.line_height = max(10, self.line_height + 1)
                print(f"   LINE_HEIGHT: {self.line_height}px")
            elif key == ord('k') or key == ord('K'):  # K - Diminuir line_height
                self.line_height = max(10, self.line_height - 1)
                print(f"   LINE_HEIGHT: {self.line_height}px")
        
        cv2.destroyAllWindows()
        return True
    
    def _run_non_interactive(self):
        """Executa o ajuste não-interativo (salva imagens)"""
        print("=" * 60)
        print("Ajuste Manual de Alinhamento do Grid Virtual (Modo Não-Interativo)")
        print("=" * 60)
        print("\nEste modo salva imagens de visualização para você ajustar os ratios.")
        print("Use os parâmetros --left-margin, --top-padding, --bubble-spacing para ajustar.")
        print(f"\nRatios atuais:")
        print(f"   LEFT_MARGIN_RATIO: {self.left_margin_ratio:.3f}")
        print(f"   TOP_PADDING_RATIO: {self.top_padding_ratio:.3f}")
        print(f"   BUBBLE_SPACING_RATIO: {self.bubble_spacing_ratio:.3f}")
        print(f"   LINE_HEIGHT: {self.line_height}px")
        
        script_dir = Path(__file__).parent.parent
        debug_dir = script_dir / "debug_corrections"
        debug_dir.mkdir(parents=True, exist_ok=True)
        
        # Salvar imagem de visualização
        img = self.create_visualization_image()
        viz_path = debug_dir / f"block_{self.block_num:02d}_grid_alignment.jpg"
        cv2.imwrite(str(viz_path), img)
        print(f"\n[OK] Imagem de visualização salva: {viz_path}")
        
        print(f"\n[DICA] Para ajustar os ratios, use:")
        print(f"   python scripts/adjust_grid_alignment.py --block {self.block_num} --real-filename <nome> --left-margin <valor> --top-padding <valor> --bubble-spacing <valor> --save")
        
        return True


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


def load_grid_alignment_config(config_path: str) -> dict:
    """Carrega configuração de alinhamento do grid salva"""
    if not os.path.exists(config_path):
        return None
    
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser(
        description='Ajuste manual dos ratios do grid virtual para alinhamento',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  # Modo interativo: ajustar ratios visualmente
  python scripts/adjust_grid_alignment.py --block 1 --real-filename 20260119_182714_166_04_block_01_real_only
  
  # Modo manual: ajustar ratios via linha de comando
  python scripts/adjust_grid_alignment.py --block 1 --real-filename <nome> --left-margin 0.20 --top-padding 0.06 --bubble-spacing 0.15 --save
  
  # Carregar configuração existente e ajustar
  python scripts/adjust_grid_alignment.py --block 1 --real-filename <nome> --load-config --left-margin 0.21 --save
        """
    )
    parser.add_argument('--real', '-i', type=str, default=None,
                       help='Caminho para imagem real do bloco')
    parser.add_argument('--real-filename', type=str, default=None,
                       help='Nome específico da imagem real (ex: 20260119_182714_166_04_block_01_real_only.jpg)')
    parser.add_argument('--block', '-b', type=int, required=True,
                       help='Número do bloco (1-4)')
    parser.add_argument('--gabarito-id', type=str, default=None,
                       help='ID do gabarito (opcional)')
    parser.add_argument('--test-id', type=str, default=None,
                       help='ID do teste (opcional)')
    parser.add_argument('--load-config', action='store_true',
                       help='Carregar configuração existente se disponível')
    parser.add_argument('--debug-dir', type=str, default='debug_corrections',
                       help='Diretório de debug')
    parser.add_argument('--left-margin', type=float, default=None,
                       help='LEFT_MARGIN_RATIO (0.0-0.5)')
    parser.add_argument('--top-padding', type=float, default=None,
                       help='TOP_PADDING_RATIO (0.0-0.3)')
    parser.add_argument('--bubble-spacing', type=float, default=None,
                       help='BUBBLE_SPACING_RATIO (0.05-0.3)')
    parser.add_argument('--line-height', type=int, default=None,
                       help='LINE_HEIGHT em pixels')
    parser.add_argument('--save', action='store_true',
                       help='Salvar configuração com os ratios especificados')
    parser.add_argument('--no-interactive', action='store_true',
                       help='Forçar modo não-interativo (salva imagens)')
    
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
    
    # Carregar configuração existente se solicitado
    initial_left_margin = 0.18
    initial_top_padding = None  # None = calcular automaticamente
    initial_bubble_spacing = 0.16
    initial_line_height = None
    
    if args.load_config:
        script_dir = Path(__file__).parent.parent
        alignment_dir = script_dir / "app" / "services" / "cartao_resposta"
        config_path = str(alignment_dir / f"block_{args.block:02d}_grid_alignment.json")
        config = load_grid_alignment_config(config_path)
        if config:
            initial_left_margin = config.get('left_margin_ratio', 0.18)
            # Se top_padding_ratio for None no JSON, manter None para calcular automaticamente
            top_padding_config = config.get('top_padding_ratio')
            if top_padding_config is not None:
                initial_top_padding = top_padding_config
            initial_bubble_spacing = config.get('bubble_spacing_ratio', 0.16)
            initial_line_height = config.get('line_height', None)
            print(f"[CONFIG] Configuração carregada:")
            print(f"   LEFT_MARGIN_RATIO: {initial_left_margin:.3f}")
            if initial_top_padding is not None:
                print(f"   TOP_PADDING_RATIO: {initial_top_padding:.3f}")
            else:
                print(f"   TOP_PADDING_RATIO: null (será calculado)")
            print(f"   BUBBLE_SPACING_RATIO: {initial_bubble_spacing:.3f}")
            if initial_line_height:
                print(f"   LINE_HEIGHT: {initial_line_height}px")
            else:
                print(f"   LINE_HEIGHT: null (será calculado)")
    
    # Aplicar valores da linha de comando (têm prioridade)
    if args.left_margin is not None:
        initial_left_margin = args.left_margin
        print(f"[PARAM] LEFT_MARGIN_RATIO da linha de comando: {initial_left_margin:.3f}")
    if args.top_padding is not None:
        initial_top_padding = args.top_padding
        print(f"[PARAM] TOP_PADDING_RATIO da linha de comando: {initial_top_padding:.3f}")
    if args.bubble_spacing is not None:
        initial_bubble_spacing = args.bubble_spacing
        print(f"[PARAM] BUBBLE_SPACING_RATIO da linha de comando: {initial_bubble_spacing:.3f}")
    if args.line_height is not None:
        initial_line_height = args.line_height
        print(f"[PARAM] LINE_HEIGHT da linha de comando: {initial_line_height}px")
    
    # Criar ajustador
    try:
        adjuster = GridAlignmentAdjuster(
            args.real,
            args.block,
            gabarito_id=args.gabarito_id,
            test_id=args.test_id,
            scale_info=None  # Pode ser carregado do config se necessário
        )
        
        # Calcular line_height PRIMEIRO (é necessário para visualização correta)
        # Isso deve ser feito antes de aplicar os ratios
        if initial_line_height:
            adjuster.line_height = initial_line_height
            print(f"[INFO] Line height fornecido: {adjuster.line_height}px")
        else:
            # Calcular automaticamente se não fornecido
            calculated = adjuster._calcular_line_height()
            if calculated:
                adjuster.line_height = calculated
                print(f"[INFO] Line height calculado automaticamente: {adjuster.line_height}px")
            else:
                print(f"[AVISO] Não foi possível calcular line_height automaticamente")
                print(f"[INFO] Usando estimativa baseada na altura do bloco")
                adjuster.line_height = int(adjuster.h / len(adjuster.questions_config)) if adjuster.questions_config else 20
        
        # Aplicar valores iniciais (após calcular line_height)
        adjuster.left_margin_ratio = initial_left_margin
        adjuster.top_padding_ratio = initial_top_padding
        adjuster.bubble_spacing_ratio = initial_bubble_spacing
        
        # Se --save foi especificado, salvar diretamente
        if args.save:
            script_dir = Path(__file__).parent.parent
            alignment_dir = script_dir / "app" / "services" / "cartao_resposta"
            alignment_dir.mkdir(parents=True, exist_ok=True)
            
            output_path = str(alignment_dir / f"block_{args.block:02d}_grid_alignment.json")
            adjuster.save_config(output_path)
            
            # Salvar imagem de visualização
            img = adjuster.create_visualization_image()
            debug_dir = script_dir / "debug_corrections"
            debug_dir.mkdir(parents=True, exist_ok=True)
            viz_path = debug_dir / f"block_{args.block:02d}_grid_alignment.jpg"
            cv2.imwrite(str(viz_path), img)
            print(f"[OK] Imagem de visualização salva: {viz_path}")
        else:
            # Executar ajuste
            interactive = not args.no_interactive
            adjuster.run(interactive=interactive)
            
    except Exception as e:
        print(f"[ERRO] Erro: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
