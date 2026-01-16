# -*- coding: utf-8 -*-
"""
Script interativo para ajustar manualmente os offsets X e Y dos blocos
Permite visualizar e ajustar o alinhamento entre referência e real
"""

import cv2
import numpy as np
import json
import os
import sys
import argparse
from pathlib import Path


class AlignmentAdjuster:
    def __init__(self, img_ref_path: str, img_real_path: str, block_num: int = None):
        self.img_ref_path = img_ref_path
        self.img_real_path = img_real_path
        self.block_num = block_num
        
        # Carregar imagens
        self.img_ref = cv2.imread(img_ref_path)
        self.img_real = cv2.imread(img_real_path)
        
        if self.img_ref is None or self.img_real is None:
            raise ValueError("Não foi possível carregar as imagens")
        
        # Converter para grayscale se necessário
        if len(self.img_ref.shape) == 3:
            self.img_ref = cv2.cvtColor(self.img_ref, cv2.COLOR_BGR2GRAY)
        if len(self.img_real.shape) == 3:
            self.img_real = cv2.cvtColor(self.img_real, cv2.COLOR_BGR2GRAY)
        
        # Redimensionar para mesmo tamanho (usar referência como base)
        h_ref, w_ref = self.img_ref.shape[:2]
        h_real, w_real = self.img_real.shape[:2]
        
        if (w_real, h_real) != (w_ref, h_ref):
            self.img_real = cv2.resize(self.img_real, (w_ref, h_ref), interpolation=cv2.INTER_AREA)
        
        self.h, self.w = self.img_ref.shape[:2]
        
        # Offsets ajustáveis
        self.offset_x = 0
        self.offset_y = 0
        
        # Estado
        self.show_overlay = True
        self.alpha = 0.5  # Transparência do overlay
        
    def create_comparison_image(self):
        """Cria imagem de comparação com overlay"""
        # Converter para BGR para desenho
        img_ref_bgr = cv2.cvtColor(self.img_ref, cv2.COLOR_GRAY2BGR)
        img_real_bgr = cv2.cvtColor(self.img_real, cv2.COLOR_GRAY2BGR)
        
        if self.show_overlay:
            # Criar overlay com transparência
            overlay = img_ref_bgr.copy()
            
            # Aplicar offset na imagem real
            M = np.float32([[1, 0, self.offset_x], [0, 1, self.offset_y]])
            img_real_offset = cv2.warpAffine(img_real_bgr, M, (self.w, self.h))
            
            # Criar máscara para área válida
            mask = np.ones((self.h, self.w), dtype=np.uint8) * 255
            
            # Combinar com transparência
            result = cv2.addWeighted(overlay, 1.0 - self.alpha, img_real_offset, self.alpha, 0)
            
            # Desenhar linhas de referência (verde)
            cv2.line(result, (0, self.h // 2), (self.w, self.h // 2), (0, 255, 0), 1)
            cv2.line(result, (self.w // 2, 0), (self.w // 2, self.h), (0, 255, 0), 1)
            
            # Desenhar linhas de offset (azul)
            center_x = self.w // 2 + self.offset_x
            center_y = self.h // 2 + self.offset_y
            cv2.line(result, (center_x - 20, center_y), (center_x + 20, center_y), (255, 0, 0), 2)
            cv2.line(result, (center_x, center_y - 20), (center_x, center_y + 20), (255, 0, 0), 2)
        else:
            # Lado a lado
            result = np.zeros((self.h, self.w * 2 + 50, 3), dtype=np.uint8)
            result.fill(255)
            result[0:self.h, 0:self.w] = img_ref_bgr
            result[0:self.h, self.w+50:self.w*2+50] = img_real_bgr
            
            # Aplicar offset na imagem real
            M = np.float32([[1, 0, self.offset_x], [0, 1, self.offset_y]])
            img_real_offset = cv2.warpAffine(img_real_bgr, M, (self.w, self.h))
            result[0:self.h, self.w+50:self.w*2+50] = img_real_offset
        
        # Adicionar informações
        info_text = f"Offset: X={self.offset_x:+d}, Y={self.offset_y:+d}"
        cv2.putText(result, info_text, (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        
        if self.block_num:
            block_text = f"BLOCO {self.block_num:02d}"
            cv2.putText(result, block_text, (10, 60),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
        
        help_text = "Setas: ajustar | Espaço: toggle overlay | S: salvar | Q: sair"
        cv2.putText(result, help_text, (10, self.h - 20),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (128, 128, 128), 1)
        
        return result
    
    def save_config(self, output_path: str):
        """
        Salva configuração de offset
        
        NOTA IMPORTANTE: O offset salvo aqui representa o deslocamento da imagem REAL
        para alinhar com a REFERÊNCIA. O sistema de correção irá INVERTER o sinal
        ao aplicar, pois precisa ajustar as posições esperadas para encontrar as bolhas reais.
        
        Exemplo:
        - Se offset_x = -25: a imagem real precisa ser movida 25px à esquerda para alinhar
        - Na correção: as posições esperadas serão ajustadas +25px (sinal invertido)
        """
        config = {
            'block_num': self.block_num,
            'offset_x': int(self.offset_x),
            'offset_y': int(self.offset_y),
            'img_ref_path': self.img_ref_path,
            'img_real_path': self.img_real_path
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        print(f"[OK] Configuracao salva em: {output_path}")
        print(f"   Offset X: {self.offset_x:+d}px")
        print(f"   Offset Y: {self.offset_y:+d}px")
        print(f"   [INFO] O sistema de correcao ira inverter o sinal ao aplicar estes offsets")
    
    def run(self, interactive: bool = True):
        """Executa o ajuste interativo ou não-interativo"""
        if interactive:
            try:
                return self._run_interactive()
            except cv2.error as e:
                if "not implemented" in str(e) or "GUI" in str(e):
                    print("\n[AVISO] OpenCV sem suporte a GUI detectado.")
                    print("   Mudando para modo nao-interativo (salva imagens)...")
                    return self._run_non_interactive()
                else:
                    raise
        else:
            return self._run_non_interactive()
    
    def _run_interactive(self):
        """Executa o ajuste interativo com janelas"""
        print("=" * 60)
        print("Ajuste Manual de Alinhamento de Blocos")
        print("=" * 60)
        print("\nControles:")
        print("  ← → : Ajustar offset X (-1 / +1)")
        print("  ↑ ↓ : Ajustar offset Y (-1 / +1)")
        print("  Shift + ← → : Ajustar offset X (-10 / +10)")
        print("  Shift + ↑ ↓ : Ajustar offset Y (-10 / +10)")
        print("  Espaço: Alternar entre overlay e lado a lado")
        print("  +/- : Ajustar transparência do overlay")
        print("  S: Salvar configuração")
        print("  Q: Sair sem salvar")
        print("\nPressione qualquer tecla para começar...")
        
        window_name = f"Ajuste de Alinhamento - Bloco {self.block_num or 'N/A'}"
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(window_name, 1200, 800)
        
        while True:
            img = self.create_comparison_image()
            cv2.imshow(window_name, img)
            
            key = cv2.waitKey(0) & 0xFF
            
            if key == ord('q') or key == 27:  # Q ou ESC
                print("\n[X] Sair sem salvar")
                break
            el            if key == ord('s'):  # S - Salvar
                # Salvar na pasta app/services/cartao_resposta/
                script_dir = Path(__file__).parent.parent  # Voltar um nível do scripts/
                alignment_dir = script_dir / "app" / "services" / "cartao_resposta"
                alignment_dir.mkdir(parents=True, exist_ok=True)
                
                if self.block_num:
                    output_path = str(alignment_dir / f"block_{self.block_num:02d}_alignment.json")
                else:
                    output_path = str(alignment_dir / "block_alignment.json")
                self.save_config(output_path)
                print("\n[OK] Configuracao salva! Pressione Q para sair.")
            elif key == ord(' '):  # Espaço - Toggle overlay
                self.show_overlay = not self.show_overlay
                print(f"   Modo: {'Overlay' if self.show_overlay else 'Lado a lado'}")
            elif key == ord('+') or key == ord('='):  # + - Aumentar transparência
                self.alpha = min(1.0, self.alpha + 0.1)
                print(f"   Transparência: {self.alpha:.1f}")
            elif key == ord('-') or key == ord('_'):  # - - Diminuir transparência
                self.alpha = max(0.0, self.alpha - 0.1)
                print(f"   Transparência: {self.alpha:.1f}")
            elif key == 81 or key == 2:  # ← (Linux/Windows)
                self.offset_x -= 1
                print(f"   Offset X: {self.offset_x:+d}")
            elif key == 83 or key == 3:  # → (Linux/Windows)
                self.offset_x += 1
                print(f"   Offset X: {self.offset_x:+d}")
            elif key == 82 or key == 0:  # ↑ (Linux/Windows)
                self.offset_y -= 1
                print(f"   Offset Y: {self.offset_y:+d}")
            elif key == 84 or key == 1:  # ↓ (Linux/Windows)
                self.offset_y += 1
                print(f"   Offset Y: {self.offset_y:+d}")
        
        cv2.destroyAllWindows()
        return True
    
    def _run_non_interactive(self):
        """Executa o ajuste não-interativo (salva imagens)"""
        print("=" * 60)
        print("Ajuste Manual de Alinhamento de Blocos (Modo Não-Interativo)")
        print("=" * 60)
        print("\nEste modo salva imagens de comparação para você ajustar os offsets.")
        print("Use os parâmetros --offset-x e --offset-y para ajustar.")
        print("\nOffset atual: X={:+d}, Y={:+d}".format(self.offset_x, self.offset_y))
        
        # Salvar imagens de comparação
        output_dir = Path.cwd()
        if self.block_num:
            output_prefix = f"block_{self.block_num:02d}_alignment"
        else:
            output_prefix = "block_alignment"
        
        # Modo overlay
        self.show_overlay = True
        img_overlay = self.create_comparison_image()
        overlay_path = output_dir / f"{output_prefix}_overlay.jpg"
        cv2.imwrite(str(overlay_path), img_overlay)
        print(f"\n[OK] Imagem overlay salva: {overlay_path}")
        
        # Modo lado a lado
        self.show_overlay = False
        img_side = self.create_comparison_image()
        side_path = output_dir / f"{output_prefix}_side_by_side.jpg"
        cv2.imwrite(str(side_path), img_side)
        print(f"[OK] Imagem lado a lado salva: {side_path}")
        
        print(f"\n[DICA] Para ajustar os offsets, use:")
        print(f"   python scripts/adjust_block_alignment.py --block {self.block_num or 1} --auto --offset-x <valor> --offset-y <valor>")
        print(f"\n[DICA] Para salvar a configuracao:")
        print(f"   python scripts/adjust_block_alignment.py --block {self.block_num or 1} --auto --offset-x <valor> --offset-y <valor> --save")
        
        return True


def find_latest_debug_images(debug_dir: str = "debug_corrections", block_num: int = None):
    """Encontra automaticamente as imagens mais recentes"""
    # Resolver caminho absoluto para funcionar de qualquer diretório
    if not os.path.isabs(debug_dir):
        # Se for relativo, tentar encontrar a partir do diretório do script ou diretório atual
        script_dir = Path(__file__).parent.parent  # Voltar um nível do scripts/
        possible_paths = [
            Path(debug_dir),  # Diretório atual
            script_dir / debug_dir,  # Relativo ao projeto
            Path.cwd() / debug_dir,  # Relativo ao diretório de trabalho atual
        ]
        
        for path in possible_paths:
            if path.exists():
                debug_dir = str(path.resolve())
                break
        else:
            # Se não encontrou, usar o diretório atual
            debug_dir = str(Path(debug_dir).resolve())
    
    # Resolver caminho
    if os.path.isabs(debug_dir):
        debug_path = Path(debug_dir)
    else:
        # Tentar vários caminhos possíveis
        current_dir = Path.cwd()
        script_dir = Path(__file__).parent.parent if '__file__' in globals() else Path.cwd()
        
        possible_paths = [
            current_dir / debug_dir,  # Relativo ao diretório atual
            current_dir if current_dir.name == debug_dir else None,  # Se já estamos no diretório
            script_dir / debug_dir,  # Relativo ao projeto
            Path(debug_dir),  # Caminho relativo simples
        ]
        
        debug_path = None
        for path in possible_paths:
            if path and path.exists() and path.is_dir():
                debug_path = path
                break
        
        if debug_path is None:
            # Última tentativa: usar diretório atual se o nome corresponder
            if current_dir.name == debug_dir or current_dir.name == "debug_corrections":
                debug_path = current_dir
            else:
                debug_path = Path(debug_dir)
    
    if not debug_path.exists():
        print(f"   [AVISO] Diretorio nao encontrado: {debug_path}")
        return None, None
    
    print(f"   [DIR] Buscando em: {debug_path.resolve()}")
    
    # Listar todos os arquivos para debug
    all_files = list(debug_path.glob("*.jpg"))
    if all_files:
        print(f"   [INFO] Encontrados {len(all_files)} arquivos .jpg no diretorio")
        if block_num:
            block_files = [f for f in all_files if f"block_{block_num:02d}" in f.name]
            if block_files:
                print(f"   [INFO] {len(block_files)} arquivos do bloco {block_num}:")
                for f in block_files[:5]:  # Mostrar até 5
                    print(f"      - {f.name}")
    
    # Buscar referência
    ref_pattern = f"*_block_{block_num:02d}_reference.jpg" if block_num else "*_block_*_reference.jpg"
    ref_files = list(debug_path.glob(ref_pattern))
    if not ref_files:
        ref_files = list(debug_path.glob("*_block_*_reference.jpg"))
    
    # Buscar real
    # Prioridade: usar a imagem original do bloco (04_block_XX_original.jpg)
    # que é a mesma usada na correção, garantindo consistência
    if block_num:
        patterns = [
            f"*_block_{block_num:02d}_original.jpg",  # Imagem original do bloco (prioridade)
            f"*_block_{block_num:02d}_roi.jpg",  # Alternativa
            f"*_block_{block_num:02d}_threshold.jpg",  # Alternativa
            f"*_block_{block_num:02d}_first_bubble_alignment.jpg",  # Fallback (imagem de debug)
            f"*_block_{block_num:02d}_comparison.jpg"  # Fallback (imagem de debug)
        ]
    else:
        patterns = [
            "*_block_*_original.jpg",  # Imagem original do bloco (prioridade)
            "*_block_*_roi.jpg",  # Alternativa
            "*_block_*_threshold.jpg",  # Alternativa
            "*_block_*_first_bubble_alignment.jpg",  # Fallback (imagem de debug)
            "*_block_*_comparison.jpg"  # Fallback (imagem de debug)
        ]
    
    real_files = []
    for pattern in patterns:
        files = list(debug_path.glob(pattern))
        if files:
            real_files = files
            break
    
    ref_path = max(ref_files, key=os.path.getmtime) if ref_files else None
    real_path = max(real_files, key=os.path.getmtime) if real_files else None
    
    if ref_path:
        print(f"   [REF] Referencia: {ref_path.name}")
    if real_path:
        print(f"   [REAL] Real: {real_path.name}")
    
    return str(ref_path.resolve()) if ref_path else None, str(real_path.resolve()) if real_path else None


def load_alignment_config(config_path: str) -> dict:
    """Carrega configuração de alinhamento salva"""
    if not os.path.exists(config_path):
        return None
    
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser(
        description='Ajuste manual de offsets X e Y para alinhamento de blocos',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  # Buscar automaticamente imagens do bloco 1
  python scripts/adjust_block_alignment.py --block 1 --auto
  
  # Usar imagens específicas
  python scripts/adjust_block_alignment.py -r ref.jpg -i real.jpg --block 1
  
  # Carregar configuração existente
  python scripts/adjust_block_alignment.py --block 1 --auto --load-config
        """
    )
    parser.add_argument('--reference', '-r', type=str, default=None,
                       help='Caminho para imagem de referência')
    parser.add_argument('--real', '-i', type=str, default=None,
                       help='Caminho para imagem real')
    parser.add_argument('--auto', '-a', action='store_true',
                       help='Buscar imagens automaticamente')
    parser.add_argument('--block', '-b', type=int, default=None,
                       help='Número do bloco')
    parser.add_argument('--load-config', action='store_true',
                       help='Carregar configuração existente se disponível')
    parser.add_argument('--debug-dir', type=str, default='debug_corrections',
                       help='Diretório de debug')
    parser.add_argument('--offset-x', type=int, default=None,
                       help='Offset X para aplicar (em pixels)')
    parser.add_argument('--offset-y', type=int, default=None,
                       help='Offset Y para aplicar (em pixels)')
    parser.add_argument('--save', action='store_true',
                       help='Salvar configuração com os offsets especificados')
    parser.add_argument('--no-interactive', action='store_true',
                       help='Forçar modo não-interativo (salva imagens)')
    
    args = parser.parse_args()
    
    # Buscar imagens automaticamente
    if args.auto:
        print(f"[BUSCA] Buscando imagens no diretorio '{args.debug_dir}'...")
        
        # Se o diretório atual é debug_corrections, usar ele diretamente
        current_dir = Path.cwd()
        if current_dir.name == "debug_corrections" or current_dir.name == args.debug_dir:
            # Estamos dentro do diretório de debug
            args.debug_dir = str(current_dir)
            print(f"   [INFO] Detectado: executando de dentro do diretorio de debug")
        
        ref_path, real_path = find_latest_debug_images(args.debug_dir, args.block)
        
        if ref_path:
            args.reference = ref_path
            print(f"   [OK] Referencia encontrada")
        else:
            block_pattern = f"{args.block:02d}" if args.block else "*"
            print(f"   [ERRO] Referencia nao encontrada")
            print(f"      Procurando por: *_block_{block_pattern}_reference.jpg")
        
        if real_path:
            args.real = real_path
            print(f"   [OK] Real encontrada")
        else:
            block_pattern = f"{args.block:02d}" if args.block else "*"
            print(f"   [ERRO] Real nao encontrada")
            print(f"      Procurando por: *_block_{block_pattern}_original.jpg ou *_roi.jpg")
        
        if not ref_path or not real_path:
            print("\n[ERRO] Nao foi possivel encontrar as imagens")
            print("\n[DICA] Dicas:")
            print("   - Verifique se voce executou uma correcao primeiro (para gerar as imagens)")
            print("   - Ou especifique os caminhos manualmente:")
            print(f"     python scripts/adjust_block_alignment.py -r <ref.jpg> -i <real.jpg> --block {args.block or 1}")
            return 1
    
    # Validar
    if not args.reference or not args.real:
        print("[ERRO] E necessario fornecer --reference e --real, ou usar --auto")
        parser.print_help()
        return 1
    
    # Carregar configuração existente se solicitado
    initial_offset_x = 0
    initial_offset_y = 0
    
    if args.load_config and args.block:
        # Buscar na pasta app/services/cartao_resposta/
        script_dir = Path(__file__).parent.parent  # Voltar um nível do scripts/
        alignment_dir = script_dir / "app" / "services" / "cartao_resposta"
        config_path = str(alignment_dir / f"block_{args.block:02d}_alignment.json")
        config = load_alignment_config(config_path)
        if config:
            initial_offset_x = config.get('offset_x', 0)
            initial_offset_y = config.get('offset_y', 0)
            print(f"[CONFIG] Configuracao carregada: X={initial_offset_x:+d}, Y={initial_offset_y:+d}")
    
    # Aplicar offsets da linha de comando (têm prioridade)
    if args.offset_x is not None:
        initial_offset_x = args.offset_x
        print(f"[OFFSET] Offset X da linha de comando: {initial_offset_x:+d}")
    if args.offset_y is not None:
        initial_offset_y = args.offset_y
        print(f"[OFFSET] Offset Y da linha de comando: {initial_offset_y:+d}")
    
    # Criar ajustador
    try:
        adjuster = AlignmentAdjuster(args.reference, args.real, args.block)
        adjuster.offset_x = initial_offset_x
        adjuster.offset_y = initial_offset_y
        
        # Se --save foi especificado, salvar diretamente
        if args.save:
            # Salvar na pasta app/services/cartao_resposta/
            script_dir = Path(__file__).parent.parent  # Voltar um nível do scripts/
            alignment_dir = script_dir / "app" / "services" / "cartao_resposta"
            alignment_dir.mkdir(parents=True, exist_ok=True)
            
            if args.block:
                output_path = str(alignment_dir / f"block_{args.block:02d}_alignment.json")
            else:
                output_path = str(alignment_dir / "block_alignment.json")
            adjuster.save_config(output_path)
            print(f"\n[OK] Configuracao salva!")
            
            # Também gerar imagens de visualização
            adjuster._run_non_interactive()
        else:
            # Executar modo interativo ou não-interativo
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
