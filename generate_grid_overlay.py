#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para gerar visualizações da grade esperada vs. real
Cria imagens com overlay da grade para comparação visual
"""

import cv2
import numpy as np
import json
from pathlib import Path
from typing import Dict, List

class GridOverlayGenerator:
    def __init__(self, block_image_path: str, block_num: int = 1):
        self.image_path = block_image_path
        self.block_num = block_num
        self.image = None
        self.image_display = None
        
        # Carregar configurações
        self.load_config()
    
    def load_config(self):
        """Carrega arquivo de configuração do bloco"""
        config_file = f"app/services/cartao_resposta/block_{self.block_num:02d}_coordinates_adjustment.json"
        
        if Path(config_file).exists():
            with open(config_file, 'r') as f:
                self.config = json.load(f)
            print(f"✅ Configuração carregada: {config_file}")
        else:
            # Valores padrão
            self.config = {
                'start_x': 32,
                'start_y': 15,
                'line_height': 14,
                'bubble_size': 15,
                'bubble_gap': 4
            }
            print(f"⚠️  Usando valores padrão (arquivo não encontrado)")
    
    def load_image(self) -> bool:
        """Carrega a imagem do bloco"""
        if not Path(self.image_path).exists():
            print(f"❌ Erro: Arquivo não encontrado: {self.image_path}")
            return False
        
        self.image = cv2.imread(self.image_path)
        if self.image is None:
            print(f"❌ Erro: Não foi possível carregar: {self.image_path}")
            return False
        
        self.image_display = self.image.copy()
        print(f"✅ Imagem carregada: {self.image.shape}")
        return True
    
    def draw_grid(self, line_height: int, color: tuple, thickness: int = 1, alpha: float = 0.5):
        """Desenha a grade esperada na imagem"""
        if self.image_display is None:
            return
        
        h, w = self.image_display.shape[:2]
        start_x = self.config['start_x']
        start_y = self.config['start_y']
        bubble_size = self.config['bubble_size']
        bubble_gap = self.config['bubble_gap']
        bubble_spacing = bubble_size + bubble_gap
        
        # Overlay para transparência
        overlay = self.image_display.copy()
        
        # Desenhar linhas horizontais para cada questão
        for q_idx in range(26):
            y = start_y + q_idx * line_height
            
            if 0 <= y < h:
                # Linha horizontal (Y da questão)
                cv2.line(overlay, (0, y), (w, y), color, thickness)
                
                # Texto com número da questão
                q_num = q_idx + 1
                cv2.putText(overlay, f"Q{q_num}", (5, y-3), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)
                
                # Desenhar círculos para as bolhas esperadas (até 4 alternativas)
                for alt_idx in range(4):
                    x = start_x + alt_idx * bubble_spacing + bubble_size // 2
                    radius = bubble_size // 2
                    
                    if 0 <= x < w:
                        cv2.circle(overlay, (x, y), radius, color, thickness)
        
        # Aplicar transparência
        cv2.addWeighted(overlay, alpha, self.image_display, 1 - alpha, 0, self.image_display)
    
    def generate_comparison(self):
        """Gera imagens de comparação com os dois line_heights"""
        if not self.load_image():
            return False
        
        h, w = self.image.shape[:2]
        output_dir = Path("debug_corrections/grid_overlay")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Imagem 1: Com line_height = 14px
        print("\n📊 Gerando overlay com line_height=14px (ORIGINAL)...")
        self.image_display = self.image.copy()
        self.draw_grid(14, (0, 255, 0), thickness=1, alpha=0.4)  # Verde
        output_path_14 = output_dir / f"block_{self.block_num:02d}_grid_14px.jpg"
        cv2.imwrite(str(output_path_14), self.image_display)
        print(f"✅ Salvo: {output_path_14}")
        
        # Imagem 2: Com line_height = 18px
        print("\n📊 Gerando overlay com line_height=18px (AJUSTADO)...")
        self.image_display = self.image.copy()
        self.draw_grid(18, (0, 0, 255), thickness=1, alpha=0.4)  # Vermelho
        output_path_18 = output_dir / f"block_{self.block_num:02d}_grid_18px.jpg"
        cv2.imwrite(str(output_path_18), self.image_display)
        print(f"✅ Salvo: {output_path_18}")
        
        # Imagem 3: Comparação lado a lado (ambas as grades)
        print("\n📊 Gerando comparação lado a lado...")
        self.image_display = self.image.copy()
        self.draw_grid(14, (0, 255, 0), thickness=1, alpha=0.3)   # Verde (14px)
        self.draw_grid(18, (0, 0, 255), thickness=1, alpha=0.3)   # Vermelho (18px)
        output_path_both = output_dir / f"block_{self.block_num:02d}_grid_comparison.jpg"
        cv2.imwrite(str(output_path_both), self.image_display)
        print(f"✅ Salvo: {output_path_both}")
        
        # Criar imagem com legenda
        print("\n📋 Gerando legenda...")
        self.create_legend_image(output_dir)
        
        return True
    
    def create_legend_image(self, output_dir: Path):
        """Cria uma imagem com legenda das cores"""
        width, height = 600, 400
        image = np.ones((height, width, 3), dtype=np.uint8) * 255
        
        y_pos = 40
        line_spacing = 60
        
        # Título
        cv2.putText(image, "LEGENDA DO GRID OVERLAY", (50, y_pos), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)
        y_pos += line_spacing
        
        # Verde (14px)
        cv2.line(image, (50, y_pos), (150, y_pos), (0, 255, 0), 3)
        cv2.putText(image, "= line_height 14px (ORIGINAL - JSON)", (170, y_pos+5), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 1)
        y_pos += line_spacing
        
        # Vermelho (18px)
        cv2.line(image, (50, y_pos), (150, y_pos), (0, 0, 255), 3)
        cv2.putText(image, "= line_height 18px (AJUSTADO - DINÂMICO)", (170, y_pos+5), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 1)
        y_pos += line_spacing
        
        # Informação
        cv2.putText(image, "Se as bolhas alinham com verde: usar 14px", (50, y_pos), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 150, 0), 1)
        y_pos += 30
        cv2.putText(image, "Se as bolhas alinham com vermelho: usar 18px", (50, y_pos), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 150), 1)
        
        output_path = output_dir / "00_LEGENDA.jpg"
        cv2.imwrite(str(output_path), image)
        print(f"✅ Salvo: {output_path}")


def main():
    print("\n" + "="*70)
    print("🎨 GERADOR DE GRID OVERLAY")
    print("="*70)
    
    # Procurar imagens de debug
    debug_dir = Path("debug_corrections")
    
    if not debug_dir.exists():
        print(f"\n⚠️  Diretório não encontrado: {debug_dir}")
        
        import sys
        if len(sys.argv) > 1:
            image_path = sys.argv[1]
            block_num = int(sys.argv[2]) if len(sys.argv) > 2 else 1
            
            generator = GridOverlayGenerator(image_path, block_num)
            generator.generate_comparison()
        return
    
    block_files = sorted(debug_dir.glob("*block_*real*.jpg"))
    
    if not block_files:
        print(f"⚠️  Nenhuma imagem encontrada em {debug_dir}")
        return
    
    print(f"\n✅ Encontrados {len(block_files)} arquivos\n")
    
    for block_file in block_files:
        import re
        match = re.search(r'block_(\d+)', block_file.name)
        block_num = int(match.group(1)) if match else 1
        
        print(f"\n{'='*70}")
        print(f"📸 Processando: {block_file.name}")
        print(f"{'='*70}")
        
        generator = GridOverlayGenerator(str(block_file), block_num)
        generator.generate_comparison()

if __name__ == "__main__":
    main()
