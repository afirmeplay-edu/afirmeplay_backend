# -*- coding: utf-8 -*-
"""
Construção de gráficos usando Matplotlib e exportação como imagens PNG
"""

import matplotlib
matplotlib.use('Agg')  # Backend sem interface gráfica
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)

# Cores para gráficos (mesmas do chart_builder.py)
COLOR_BAR = "#7C3AED"  # Roxo
COLOR_LINE_INCREASE = "#00C853"  # Verde
COLOR_LINE_DECREASE = "#FF1744"  # Vermelho
COLOR_LINE_STABLE = "#757575"  # Cinza


class MatplotlibChartBuilder:
    """Classe para construção de gráficos usando Matplotlib"""
    
    @staticmethod
    def create_composed_chart_image(
        labels: List[str],
        values: List[float],
        variations: List[float],
        directions: List[str],
        chart_title: str,
        y_axis_title: str = "Valor",
        y_axis_min: float = 0,
        y_axis_max: Optional[float] = None,
        output_path: str = None
    ) -> str:
        """
        Gera gráfico combinado (barras + linha) como PNG
        
        Args:
            labels: Lista de rótulos das avaliações (ex: ["Avaliação 1", "Avaliação 2"])
            values: Lista de valores das barras (ex: [7.5, 8.2])
            variations: Lista de variações percentuais entre avaliações (ex: [9.3, -3.7])
            directions: Lista de direções ['increase', 'decrease', 'stable']
            chart_title: Título do gráfico
            y_axis_title: Título do eixo Y
            y_axis_min: Valor mínimo do eixo Y
            y_axis_max: Valor máximo do eixo Y (None = automático)
            output_path: Caminho para salvar a imagem PNG
            
        Returns:
            Caminho da imagem gerada
        """
        try:
            # Filtrar valores None
            valid_indices = [i for i, v in enumerate(values) if v is not None]
            if len(valid_indices) < 2:
                logger.warning(f"Não há dados suficientes para criar gráfico: {len(valid_indices)} valores válidos")
                return None
            
            # Filtrar dados válidos
            valid_labels = [labels[i] for i in valid_indices]
            valid_values = [values[i] for i in valid_indices]
            
            # Criar figura (tamanho reduzido)
            fig, ax = plt.subplots(figsize=(8, 4))
            
            # Configurar eixo Y
            if y_axis_max is None:
                y_axis_max = max(valid_values) * 1.2 if valid_values else 10
            ax.set_ylim(y_axis_min, y_axis_max)
            ax.set_ylabel(y_axis_title, fontsize=10, fontweight='bold')
            
            # Criar barras
            bars = ax.bar(valid_labels, valid_values, color=COLOR_BAR, width=0.6, alpha=0.8)
            
            # Adicionar valores no topo das barras
            for bar, value in zip(bars, valid_values):
                if value is not None:
                    ax.text(
                        bar.get_x() + bar.get_width() / 2,
                        value,
                        f"{value:.1f}",
                        ha='center',
                        va='bottom',
                        fontsize=9,
                        fontweight='bold'
                    )
            
            # Criar linha conectando os topos das barras
            if len(valid_values) >= 2:
                # Coordenadas X dos centros das barras
                x_coords = [bar.get_x() + bar.get_width() / 2 for bar in bars]
                
                # Desenhar linha conectando os topos
                line_color = COLOR_LINE_STABLE
                if directions and len(directions) > 0:
                    # Usar a primeira direção para cor da linha
                    first_direction = directions[0]
                    if first_direction == 'increase':
                        line_color = COLOR_LINE_INCREASE
                    elif first_direction == 'decrease':
                        line_color = COLOR_LINE_DECREASE
                    else:
                        line_color = COLOR_LINE_STABLE
                
                # Desenhar linha
                line = ax.plot(x_coords, valid_values, color=line_color, linewidth=2.5, 
                              marker='o', markersize=6, zorder=10)
                
                # Adicionar porcentagem de variação no meio da linha (entre as barras)
                if variations and len(variations) > 0:
                    for i, (var, direction) in enumerate(zip(variations, directions)):
                        if i < len(x_coords) - 1:
                            # Posição X no meio entre duas barras
                            mid_x = (x_coords[i] + x_coords[i + 1]) / 2
                            # Posição Y no meio entre dois valores
                            mid_y = (valid_values[i] + valid_values[i + 1]) / 2
                            
                            # Cor do texto baseada na direção
                            text_color = COLOR_LINE_STABLE
                            if direction == 'increase':
                                text_color = COLOR_LINE_INCREASE
                            elif direction == 'decrease':
                                text_color = COLOR_LINE_DECREASE
                            
                            # Adicionar texto da porcentagem
                            ax.annotate(
                                f"{var:.1f}%",
                                xy=(mid_x, mid_y),
                                ha='center',
                                va='center',
                                fontsize=9,
                                fontweight='bold',
                                color=text_color,
                                bbox=dict(boxstyle='round,pad=0.2', facecolor='white', 
                                         edgecolor=text_color, linewidth=1.5),
                                zorder=11
                            )
            
            # Configurar título
            ax.set_title(chart_title, fontsize=12, fontweight='bold', pad=15)
            
            # Remover bordas desnecessárias
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            ax.spines['left'].set_color('#CCCCCC')
            ax.spines['bottom'].set_color('#CCCCCC')
            
            # Configurar grid
            ax.grid(True, axis='y', linestyle='--', alpha=0.3, color='#CCCCCC')
            ax.set_axisbelow(True)
            
            # Rotacionar labels do eixo X se necessário
            plt.xticks(rotation=15, ha='right')
            
            # Ajustar layout
            plt.tight_layout()
            
            # Salvar imagem (DPI reduzido para arquivo menor)
            plt.savefig(output_path, dpi=100, bbox_inches='tight', facecolor='white')
            plt.close()
            
            logger.info(f"Gráfico gerado com sucesso: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Erro ao gerar gráfico: {str(e)}", exc_info=True)
            if 'fig' in locals():
                plt.close()
            return None
    
    @staticmethod
    def create_bar_chart_image(
        labels: List[str],
        values: List[float],
        chart_title: str,
        y_axis_title: str = "Valor",
        y_axis_min: float = 0,
        y_axis_max: Optional[float] = None,
        output_path: str = None
    ) -> str:
        """
        Gera gráfico de barras simples como PNG
        
        Args:
            labels: Lista de rótulos
            values: Lista de valores
            chart_title: Título do gráfico
            y_axis_title: Título do eixo Y
            y_axis_min: Valor mínimo do eixo Y
            y_axis_max: Valor máximo do eixo Y (None = automático)
            output_path: Caminho para salvar a imagem PNG
            
        Returns:
            Caminho da imagem gerada
        """
        try:
            # Filtrar valores None
            valid_indices = [i for i, v in enumerate(values) if v is not None]
            if len(valid_indices) == 0:
                logger.warning("Não há dados válidos para criar gráfico")
                return None
            
            # Filtrar dados válidos
            valid_labels = [labels[i] for i in valid_indices]
            valid_values = [values[i] for i in valid_indices]
            
            # Criar figura (tamanho reduzido)
            fig, ax = plt.subplots(figsize=(8, 4))
            
            # Configurar eixo Y
            if y_axis_max is None:
                y_axis_max = max(valid_values) * 1.2 if valid_values else 10
            ax.set_ylim(y_axis_min, y_axis_max)
            ax.set_ylabel(y_axis_title, fontsize=10, fontweight='bold')
            
            # Criar barras
            bars = ax.bar(valid_labels, valid_values, color=COLOR_BAR, width=0.6, alpha=0.8)
            
            # Adicionar valores no topo das barras
            for bar, value in zip(bars, valid_values):
                if value is not None:
                    ax.text(
                        bar.get_x() + bar.get_width() / 2,
                        value,
                        f"{value:.1f}",
                        ha='center',
                        va='bottom',
                        fontsize=9,
                        fontweight='bold'
                    )
            
            # Configurar título
            ax.set_title(chart_title, fontsize=12, fontweight='bold', pad=15)
            
            # Remover bordas desnecessárias
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            ax.spines['left'].set_color('#CCCCCC')
            ax.spines['bottom'].set_color('#CCCCCC')
            
            # Configurar grid
            ax.grid(True, axis='y', linestyle='--', alpha=0.3, color='#CCCCCC')
            ax.set_axisbelow(True)
            
            # Rotacionar labels do eixo X se necessário
            plt.xticks(rotation=15, ha='right')
            
            # Ajustar layout
            plt.tight_layout()
            
            # Salvar imagem (DPI reduzido para arquivo menor)
            plt.savefig(output_path, dpi=100, bbox_inches='tight', facecolor='white')
            plt.close()
            
            logger.info(f"Gráfico de barras gerado com sucesso: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Erro ao gerar gráfico de barras: {str(e)}", exc_info=True)
            if 'fig' in locals():
                plt.close()
            return None

