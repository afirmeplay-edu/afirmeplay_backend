# -*- coding: utf-8 -*-
"""
Construção de gráficos Excel usando openpyxl
"""

from openpyxl.chart import BarChart, LineChart, Reference
from openpyxl.chart.series import DataPoint
from openpyxl.utils.cell import coordinate_from_string
from openpyxl.utils import column_index_from_string
from typing import List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


def _parse_range_string(range_string: str) -> Tuple[int, int, int, int]:
    """
    Converte range string (ex: "B12:C12") em coordenadas numéricas
    
    Args:
        range_string: String no formato "A1:B2" ou "B12:C12"
        
    Returns:
        Tuple (min_col, min_row, max_col, max_row)
    """
    try:
        if ':' in range_string:
            start, end = range_string.split(':')
        else:
            start = end = range_string
        
        start_col_str, start_row = coordinate_from_string(start)
        end_col_str, end_row = coordinate_from_string(end)
        
        min_col = column_index_from_string(start_col_str)
        min_row = start_row
        max_col = column_index_from_string(end_col_str)
        max_row = end_row
        
        return (min_col, min_row, max_col, max_row)
    except Exception as e:
        logger.error(f"Erro ao parsear range {range_string}: {e}")
        raise

# Cores para gráficos
COLOR_BAR = "7C3AED"  # Roxo
COLOR_LINE_INCREASE = "00C853"  # Verde
COLOR_LINE_DECREASE = "FF1744"  # Vermelho
COLOR_LINE_STABLE = "9E9E9E"    # Cinza


class ChartBuilder:
    """Classe para construção de gráficos Excel"""
    
    @staticmethod
    def create_composed_chart(
        worksheet,
        bar_data_range: str,
        line_data_range: str,
        categories_range: str,
        chart_title: str,
        y_axis_title: str = "",
        y_axis_min: Optional[float] = None,
        y_axis_max: Optional[float] = None,
        bar_title: str = "Valores",
        line_title: str = "Variação (%)",
        directions: Optional[List[str]] = None,
        variation_percentages: Optional[List[float]] = None
    ):
        """
        Cria gráfico combinado (barras + linhas) com eixo Y secundário
        
        Args:
            worksheet: Worksheet do Excel
            bar_data_range: Range dos dados de barras (ex: "B2:B5")
            line_data_range: Range dos dados de linhas (ex: "C2:C5")
            categories_range: Range das categorias (ex: "A2:A5")
            chart_title: Título do gráfico
            y_axis_title: Título do eixo Y principal
            y_axis_min: Valor mínimo do eixo Y principal
            y_axis_max: Valor máximo do eixo Y principal
            bar_title: Título da série de barras
            line_title: Título da série de linhas
            directions: Lista de direções para colorir linhas por segmento
            
        Returns:
            Chart object
        """
        try:
            print(f"[CHART] Criando gráfico combinado: {chart_title}")
            print(f"[CHART] Bar data range: {bar_data_range}")
            print(f"[CHART] Line data range: {line_data_range}")
            print(f"[CHART] Categories range: {categories_range}")
            
            # Criar gráfico de barras (eixo Y principal)
            chart = BarChart()
            chart.type = "col"
            chart.style = 10
            chart.title = chart_title
            chart.y_axis.title = y_axis_title
            chart.x_axis.title = None
            
            # Configurar eixo Y principal
            if y_axis_min is not None:
                chart.y_axis.scaling.min = y_axis_min
            if y_axis_max is not None:
                chart.y_axis.scaling.max = y_axis_max
            
            # Adicionar série de barras - usar coordenadas numéricas
            bar_min_col, bar_min_row, bar_max_col, bar_max_row = _parse_range_string(bar_data_range)
            bar_data = Reference(worksheet, min_col=bar_min_col, max_col=bar_max_col, min_row=bar_min_row, max_row=bar_max_row)
            
            cat_min_col, cat_min_row, cat_max_col, cat_max_row = _parse_range_string(categories_range)
            categories = Reference(worksheet, min_col=cat_min_col, max_col=cat_max_col, min_row=cat_min_row, max_row=cat_max_row)
            print(f"[CHART] References criados com sucesso")
            
            chart.add_data(bar_data, titles_from_data=False)
            chart.set_categories(categories)
            # Não definir title diretamente - openpyxl não aceita string direta
            # O título pode ser definido via SeriesLabel se necessário, mas geralmente não é necessário
            chart.series[0].graphicalProperties.solidFill = COLOR_BAR
            
            # Criar gráfico de linhas - A linha conecta os topos das barras usando os mesmos valores
            # IMPORTANTE: A linha deve ser apenas UMA série conectando os topos das barras
            line_chart = LineChart()
            line_chart.title = None
            line_min_col, line_min_row, line_max_col, line_max_row = _parse_range_string(line_data_range)
            
            # Validar que o range de linha tenha pelo menos 2 colunas para renderizar corretamente
            if line_min_col == line_max_col:
                print(f"[CHART] Aviso: Range de linha tem apenas 1 coluna ({line_data_range}). Gráfico de linha pode não renderizar corretamente.")
            
            # A linha usa os MESMOS valores das barras para conectar os topos
            line_data = Reference(worksheet, min_col=line_min_col, max_col=line_max_col, min_row=line_min_row, max_row=line_max_row)
            line_chart.add_data(line_data, titles_from_data=False)
            line_chart.set_categories(categories)
            # Não definir title diretamente - openpyxl não aceita string direta
            
            # A linha usa o MESMO eixo Y das barras (não secundário)
            # Isso faz com que a linha conecte os topos das barras perfeitamente
            line_chart.y_axis.axId = 0  # Mesmo eixo Y das barras
            line_chart.y_axis.title = None  # Não precisa de título separado
            
            # Garantir que seja apenas uma série de linha (sem marcadores visíveis, apenas linha)
            line_chart.series[0].marker = None  # Sem marcadores
            
            # Colorir linhas por segmento baseado na direção
            if directions and len(directions) > 0:
                # Aplicar cor geral da linha baseada na primeira direção
                first_direction = directions[0]
                if first_direction == 'increase':
                    line_color = COLOR_LINE_INCREASE
                elif first_direction == 'decrease':
                    line_color = COLOR_LINE_DECREASE
                else:
                    line_color = COLOR_LINE_STABLE
                
                line_chart.series[0].graphicalProperties.line.solidFill = line_color
                line_chart.series[0].graphicalProperties.line.width = 30000  # 3pt - mais espessa para melhor visibilidade
                
                # Garantir que seja apenas uma linha (sem marcadores)
                line_chart.series[0].marker = None
                
                # Tentar adicionar labels de dados com variações percentuais
                # A porcentagem deve aparecer no meio da linha (no ponto médio entre as barras)
                try:
                    from openpyxl.chart.label import DataLabelList
                    line_chart.series[0].dLbls = DataLabelList()
                    # Mostrar apenas no ponto médio (segundo ponto se houver 2 barras)
                    if variation_percentages and len(variation_percentages) > 0:
                        # Mostrar label apenas no ponto médio da linha
                        line_chart.series[0].dLbls.showVal = True
                        # Tentar formatar como porcentagem
                        try:
                            line_chart.series[0].dLbls.numFmt = "0.0%"
                        except:
                            pass
                        print(f"[CHART] Labels de dados habilitados para linha (variações: {variation_percentages})")
                    else:
                        line_chart.series[0].dLbls.showVal = False
                except Exception as e:
                    print(f"[CHART] Aviso: Não foi possível adicionar labels de dados: {e}")
                
                # Tentar colorir pontos individuais (se suportado)
                try:
                    for i, direction in enumerate(directions):
                        if i < len(line_chart.series[0].dataPoints):
                            if direction == 'increase':
                                point_color = COLOR_LINE_INCREASE
                            elif direction == 'decrease':
                                point_color = COLOR_LINE_DECREASE
                            else:
                                point_color = COLOR_LINE_STABLE
                            
                            # Aplicar cor ao ponto
                            line_chart.series[0].dataPoints[i].graphicalProperties.solidFill = point_color
                            line_chart.series[0].dataPoints[i].graphicalProperties.line.solidFill = point_color
                except:
                    # Se não conseguir colorir pontos individuais, usar cor geral
                    pass
            
            # Combinar gráficos - A linha usa o mesmo eixo Y das barras
            chart += line_chart
            print(f"[CHART] Gráficos combinados. Séries: {len(chart.series)}")
            
            # Configurar a série de linha após combinar
            # Após combinar, a série de linha está no índice 1 (ou último índice)
            # IMPORTANTE: Garantir que seja apenas UMA linha conectando os topos das barras
            line_series_index = len(chart.series) - 1  # Última série adicionada (a linha)
            if line_series_index >= 0 and line_series_index < len(chart.series):
                try:
                    # Preservar propriedades visuais da linha
                    if hasattr(line_chart.series[0], 'graphicalProperties'):
                        chart.series[line_series_index].graphicalProperties.line.solidFill = line_chart.series[0].graphicalProperties.line.solidFill
                        chart.series[line_series_index].graphicalProperties.line.width = line_chart.series[0].graphicalProperties.line.width
                    
                    # Garantir que seja apenas uma linha (sem marcadores visíveis)
                    chart.series[line_series_index].marker = None
                    
                    # Preservar labels de dados se foram adicionados
                    if hasattr(line_chart.series[0], 'dLbls') and line_chart.series[0].dLbls:
                        chart.series[line_series_index].dLbls = line_chart.series[0].dLbls
                    
                    # A linha usa o mesmo eixo Y (não secundário)
                    # Isso faz com que a linha conecte os topos das barras perfeitamente
                    chart.series[line_series_index].y_axis.axId = 0  # Mesmo eixo Y das barras
                    print(f"[CHART] Linha configurada para usar o mesmo eixo Y das barras (índice: {line_series_index})")
                except Exception as e:
                    print(f"[CHART] Aviso: Não foi possível configurar série de linha: {e}")
                    pass
            
            # Configurar tamanho
            chart.width = 15
            chart.height = 10
            
            print(f"[CHART] Gráfico criado com sucesso")
            return chart
            
        except Exception as e:
            logger.error(f"Erro ao criar gráfico combinado: {str(e)}", exc_info=True)
            return None
    
    @staticmethod
    def create_bar_chart(
        worksheet,
        data_range: str,
        categories_range: str,
        chart_title: str,
        y_axis_title: str = "",
        y_axis_min: Optional[float] = None,
        y_axis_max: Optional[float] = None,
        series_title: str = "Valores"
    ):
        """
        Cria gráfico de barras simples
        
        Args:
            worksheet: Worksheet do Excel
            data_range: Range dos dados (ex: "B2:B5")
            categories_range: Range das categorias (ex: "A2:A5")
            chart_title: Título do gráfico
            y_axis_title: Título do eixo Y
            y_axis_min: Valor mínimo do eixo Y
            y_axis_max: Valor máximo do eixo Y
            series_title: Título da série
            
        Returns:
            Chart object
        """
        try:
            chart = BarChart()
            chart.type = "col"
            chart.style = 10
            chart.title = chart_title
            chart.y_axis.title = y_axis_title
            chart.x_axis.title = None
            
            if y_axis_min is not None:
                chart.y_axis.scaling.min = y_axis_min
            if y_axis_max is not None:
                chart.y_axis.scaling.max = y_axis_max
            
            data_min_col, data_min_row, data_max_col, data_max_row = _parse_range_string(data_range)
            data = Reference(worksheet, min_col=data_min_col, max_col=data_max_col, min_row=data_min_row, max_row=data_max_row)
            
            cat_min_col, cat_min_row, cat_max_col, cat_max_row = _parse_range_string(categories_range)
            categories = Reference(worksheet, min_col=cat_min_col, max_col=cat_max_col, min_row=cat_min_row, max_row=cat_max_row)
            
            chart.add_data(data, titles_from_data=False)
            chart.set_categories(categories)
            # Não definir title diretamente - openpyxl não aceita string direta
            chart.series[0].graphicalProperties.solidFill = COLOR_BAR
            
            chart.width = 15
            chart.height = 10
            
            return chart
            
        except Exception as e:
            logger.error(f"Erro ao criar gráfico de barras: {str(e)}", exc_info=True)
            return None
    
    @staticmethod
    def create_grouped_bar_chart(
        worksheet,
        data_ranges: List[str],
        categories_range: str,
        chart_title: str,
        y_axis_title: str = "",
        y_axis_min: Optional[float] = None,
        y_axis_max: Optional[float] = None,
        series_titles: Optional[List[str]] = None
    ):
        """
        Cria gráfico de barras agrupadas (múltiplas séries)
        
        Args:
            worksheet: Worksheet do Excel
            data_ranges: Lista de ranges dos dados
            categories_range: Range das categorias
            chart_title: Título do gráfico
            y_axis_title: Título do eixo Y
            y_axis_min: Valor mínimo do eixo Y
            y_axis_max: Valor máximo do eixo Y
            series_titles: Lista de títulos das séries
            
        Returns:
            Chart object
        """
        try:
            chart = BarChart()
            chart.type = "col"
            chart.style = 10
            chart.title = chart_title
            chart.y_axis.title = y_axis_title
            chart.x_axis.title = None
            
            if y_axis_min is not None:
                chart.y_axis.scaling.min = y_axis_min
            if y_axis_max is not None:
                chart.y_axis.scaling.max = y_axis_max
            
            cat_min_col, cat_min_row, cat_max_col, cat_max_row = _parse_range_string(categories_range)
            categories = Reference(worksheet, min_col=cat_min_col, max_col=cat_max_col, min_row=cat_min_row, max_row=cat_max_row)
            chart.set_categories(categories)
            
            colors = [COLOR_BAR, COLOR_LINE_INCREASE, COLOR_LINE_DECREASE, COLOR_LINE_STABLE]
            
            for i, data_range in enumerate(data_ranges):
                data_min_col, data_min_row, data_max_col, data_max_row = _parse_range_string(data_range)
                data = Reference(worksheet, min_col=data_min_col, max_col=data_max_col, min_row=data_min_row, max_row=data_max_row)
                chart.add_data(data, titles_from_data=False)
                
                series_index = len(chart.series) - 1
                # Não definir title diretamente - openpyxl não aceita string direta
                # Os títulos podem ser definidos via SeriesLabel se necessário, mas geralmente não é necessário
                
                chart.series[series_index].graphicalProperties.solidFill = colors[i % len(colors)]
            
            chart.width = 15
            chart.height = 10
            
            return chart
            
        except Exception as e:
            logger.error(f"Erro ao criar gráfico de barras agrupadas: {str(e)}", exc_info=True)
            return None

