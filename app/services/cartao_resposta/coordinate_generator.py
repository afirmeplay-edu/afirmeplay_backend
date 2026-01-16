# -*- coding: utf-8 -*-
"""
Gerador de coordenadas fixas (ROIs) para bolhas de resposta
Gera coordenadas absolutas em pixels para área entre triângulos
"""

import logging
from typing import Dict, Any, Optional


class CoordinateGenerator:
    """
    Gera coordenadas fixas para ROIs de bolhas de resposta
    Coordenadas são em pixels absolutos para área warped entre triângulos
    """
    
    # Dimensões padrão do warp (fallback se não forem fornecidas)
    DEFAULT_WARPED_WIDTH_PX = 2200
    DEFAULT_WARPED_HEIGHT_PX = 2800
    
    # Constantes de layout (ajustadas para alinhamento correto)
    PAGE_HEADER_HEIGHT = 500  # Altura do cabeçalho (px)
    OFFSET_X = -10  # Offset horizontal inicial
    
    # Espaçamento entre elementos
    ANSWER_ROW_MIN_HEIGHT = 50  # Altura mínima de cada linha de resposta
    SPACING_Y_EXTRA = 0  # Espaçamento extra entre questões
    SPACING_X_BETWEEN_OPTIONS = 0  # Espaçamento extra entre alternativas
    
    # Tamanho das bolhas
    BUBBLE_WIDTH = 70  # Largura da bolha (px)
    BUBBLE_HEIGHT = 35  # Altura da bolha (px)
    
    # Margens e blocos
    BLOCK_MARGIN_LEFT = 50  # Margem esquerda do bloco
    BLOCK_GAP = 30  # Espaçamento entre blocos
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def generate_coordinates(self, num_questions: int, use_blocks: bool,
                           blocks_config: Dict, questions_options: Dict = None,
                           warped_dimensions: tuple = None) -> Dict[str, Any]:
        """
        Gera coordenadas fixas para ROIs de bolhas de resposta
        
        Args:
            num_questions: Número total de questões
            use_blocks: Se usa blocos ou não
            blocks_config: Configuração de blocos
            questions_options: Dict {question_num: [options]}
                              Ex: {1: ['A', 'B', 'C'], 2: ['A', 'B', 'C', 'D']}
            warped_dimensions: Tupla (width, height) das dimensões reais da área warped
                              Se None, usa dimensões padrão
        
        Returns:
            Dict com coordenadas no formato:
            {
                "warped_size": [width, height],
                "questions": {
                    "1": {
                        "A": {"x": 100, "y": 200, "w": 70, "h": 35},
                        "B": {"x": 180, "y": 200, "w": 70, "h": 35},
                        ...
                    },
                    "2": {...}
                }
            }
        """
        try:
            # Usar dimensões fornecidas ou padrão
            if warped_dimensions and len(warped_dimensions) == 2:
                WARPED_WIDTH_PX = warped_dimensions[0]
                WARPED_HEIGHT_PX = warped_dimensions[1]
                self.logger.info(f"✅ Usando dimensões reais fornecidas: {WARPED_WIDTH_PX}x{WARPED_HEIGHT_PX}px")
            else:
                WARPED_WIDTH_PX = self.DEFAULT_WARPED_WIDTH_PX
                WARPED_HEIGHT_PX = self.DEFAULT_WARPED_HEIGHT_PX
                self.logger.info(f"⚠️ Usando dimensões padrão (fallback): {WARPED_WIDTH_PX}x{WARPED_HEIGHT_PX}px")
            
            # Processar questions_options: garantir que seja dict {int: list}
            options_map = {}
            if questions_options:
                for key, value in questions_options.items():
                    try:
                        q_num = int(key)  # Converter "1" -> 1
                        if isinstance(value, list) and len(value) >= 2:
                            options_map[q_num] = value
                        else:
                            options_map[q_num] = ['A', 'B', 'C', 'D']  # Padrão
                    except (ValueError, TypeError):
                        continue
            
            # Se options_map vazio, preencher com padrão para todas questões
            if not options_map:
                for q in range(1, num_questions + 1):
                    options_map[q] = ['A', 'B', 'C', 'D']
            
            # Garantir que todas as questões de 1 a num_questions existam
            for q in range(1, num_questions + 1):
                if q not in options_map:
                    options_map[q] = ['A', 'B', 'C', 'D']
            
            # Organizar questões por blocos
            if use_blocks:
                blocks = self._organize_questions_by_blocks(
                    num_questions, blocks_config, options_map
                )
            else:
                # Sem blocos: um único bloco com todas questões
                blocks = [{
                    'block_number': 1,
                    'questions': [
                        {'question_number': q, 'options': options_map[q]}
                        for q in range(1, num_questions + 1)
                    ]
                }]
            
            # Calcular coordenadas
            coordinates = self._calculate_coordinates(
                blocks, WARPED_WIDTH_PX, WARPED_HEIGHT_PX
            )
            
            # Adicionar dimensões ao resultado
            coordinates['warped_size'] = [WARPED_WIDTH_PX, WARPED_HEIGHT_PX]
            
            self.logger.info(f"✅ Coordenadas geradas para {num_questions} questões")
            return coordinates
            
        except Exception as e:
            self.logger.error(f"Erro ao gerar coordenadas: {str(e)}", exc_info=True)
            raise
    
    def _organize_questions_by_blocks(self, num_questions: int,
                                     blocks_config: Dict,
                                     options_map: Dict) -> list:
        """
        Organiza questões por blocos
        
        Returns:
            Lista de blocos: [{block_number, questions: [{question_number, options}]}]
        """
        blocks = []
        num_blocks = blocks_config.get('num_blocks', 1)
        questions_per_block = blocks_config.get('questions_per_block', 12)
        
        for block_num in range(1, num_blocks + 1):
            start_question = (block_num - 1) * questions_per_block + 1
            end_question = min(block_num * questions_per_block, num_questions)
            
            questions = []
            for q_num in range(start_question, end_question + 1):
                questions.append({
                    'question_number': q_num,
                    'options': options_map.get(q_num, ['A', 'B', 'C', 'D'])
                })
            
            if questions:
                blocks.append({
                    'block_number': block_num,
                    'questions': questions
                })
        
        return blocks
    
    def _calculate_coordinates(self, blocks: list, width: int, height: int) -> Dict:
        """
        Calcula coordenadas absolutas (pixels) para cada bolha
        
        Args:
            blocks: Lista de blocos com questões
            width: Largura da área warped (px)
            height: Altura da área warped (px)
        
        Returns:
            Dict {"questions": {q_num: {opt: {x, y, w, h}}}}
        """
        questions_coords = {}
        
        # Calcular largura disponível por bloco
        total_blocks = len(blocks)
        if total_blocks == 0:
            return {"questions": {}}
        
        # Largura de cada bloco (dividindo igualmente a largura total)
        block_width = (width - (total_blocks + 1) * self.BLOCK_GAP) / total_blocks
        
        # Para cada bloco
        for block_idx, block in enumerate(blocks):
            # Posição X inicial do bloco
            block_x = self.BLOCK_GAP + block_idx * (block_width + self.BLOCK_GAP)
            
            # Para cada questão no bloco
            for q_idx, question in enumerate(block['questions']):
                q_num = question['question_number']
                options = question['options']
                
                # Calcular Y baseado no índice DENTRO DO BLOCO (não global)
                y_position = (
                    self.PAGE_HEADER_HEIGHT +
                    q_idx * (self.ANSWER_ROW_MIN_HEIGHT + self.SPACING_Y_EXTRA)
                )
                
                # Largura total necessária para todas as alternativas
                num_options = len(options)
                total_options_width = num_options * (self.BUBBLE_WIDTH + self.SPACING_X_BETWEEN_OPTIONS)
                
                # Posição X inicial das alternativas (centralizar no bloco)
                options_start_x = block_x + (block_width - total_options_width) / 2
                
                # Gerar coordenadas para cada alternativa
                question_coords = {}
                for opt_idx, option_letter in enumerate(options):
                    x_position = options_start_x + opt_idx * (self.BUBBLE_WIDTH + self.SPACING_X_BETWEEN_OPTIONS)
                    
                    question_coords[option_letter] = {
                        'x': int(x_position + self.OFFSET_X),
                        'y': int(y_position),
                        'w': self.BUBBLE_WIDTH,
                        'h': self.BUBBLE_HEIGHT
                    }
                
                # Salvar coordenadas da questão (usar string como chave)
                questions_coords[str(q_num)] = question_coords
        
        return {"questions": questions_coords}
