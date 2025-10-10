# -*- coding: utf-8 -*-
"""
Visualizador temporário para debug de correção física
TEMPORÁRIO: Será removido após ajustes
"""

import cv2
import numpy as np
import os
from datetime import datetime
from typing import Dict, Any, Tuple, Optional
import logging

class PhysicalCorrectionVisualizer:
    """
    Classe temporária para visualizar comparação entre gabarito e resposta do aluno
    TEMPORÁRIO: Será removida após ajustes
    """
    
    def __init__(self):
        self.debug_dir = "debug_corrections"
        if not os.path.exists(self.debug_dir):
            os.makedirs(self.debug_dir)
            print(f"📁 Pasta de debug criada: {os.path.abspath(self.debug_dir)}")
        else:
            print(f"📁 Pasta de debug já existe: {os.path.abspath(self.debug_dir)}")
    
    def generate_correction_comparison(self, 
                                     gabarito_image: np.ndarray,
                                     user_image: np.ndarray, 
                                     test_id: str,
                                     student_id: str,
                                     detected_answers: Dict[int, str],
                                     correct_answers: Dict[int, str],
                                     gabarito_coords: Optional[Dict] = None,
                                     detection_areas: Optional[np.ndarray] = None) -> str:
        """
        Gera comparação visual entre gabarito e resposta do aluno
        
        Args:
            gabarito_image: Imagem do gabarito de referência
            user_image: Imagem da resposta do aluno
            test_id: ID da prova
            student_id: ID do aluno
            detected_answers: Respostas detectadas pelo sistema
            correct_answers: Respostas corretas do gabarito
            gabarito_coords: Coordenadas das bolhas no gabarito (opcional)
        
        Returns:
            Caminho do arquivo salvo
        """
        try:
            print(f"🔍 GERANDO COMPARAÇÃO VISUAL DE DEBUG...")
            print(f"📊 Respostas detectadas: {detected_answers}")
            print(f"📊 Respostas corretas: {correct_answers}")
            
            # Verificar se as imagens são válidas
            if gabarito_image is None:
                print(f"❌ Gabarito é None")
                return None
            if user_image is None:
                print(f"❌ User image é None")
                return None
            
            # Converter imagens PIL para OpenCV se necessário
            if hasattr(gabarito_image, 'convert'):  # É imagem PIL
                print(f"🔄 Convertendo gabarito de PIL para OpenCV")
                gabarito_cv = cv2.cvtColor(np.array(gabarito_image), cv2.COLOR_RGB2BGR)
            else:
                gabarito_cv = gabarito_image
                
            # Usar imagem com áreas de detecção se fornecida, senão usar imagem original
            if detection_areas is not None:
                print(f"🔍 Usando imagem com áreas de detecção")
                user_cv = detection_areas.copy()
            elif hasattr(user_image, 'convert'):  # É imagem PIL
                print(f"🔄 Convertendo user image de PIL para OpenCV")
                user_cv = cv2.cvtColor(np.array(user_image), cv2.COLOR_RGB2BGR)
            else:
                user_cv = user_image
            
            # Obter dimensões das imagens
            gabarito_h, gabarito_w = gabarito_cv.shape[:2]
            user_h, user_w = user_cv.shape[:2]
            
            print(f"📏 Gabarito: {gabarito_w}x{gabarito_h}")
            print(f"📏 Usuário: {user_w}x{user_h}")
            
            # Converter para BGR se necessário
            if len(gabarito_cv.shape) == 2:
                gabarito_bgr = cv2.cvtColor(gabarito_cv, cv2.COLOR_GRAY2BGR)
            else:
                gabarito_bgr = gabarito_cv.copy()
                
            if len(user_cv.shape) == 2:
                user_bgr = cv2.cvtColor(user_cv, cv2.COLOR_GRAY2BGR)
            else:
                user_bgr = user_cv.copy()
            
            # Redimensionar para tamanho padrão para comparação
            target_height = 800
            gabarito_scale = target_height / gabarito_h
            user_scale = target_height / user_h
            
            gabarito_resized = cv2.resize(gabarito_bgr, 
                                        (int(gabarito_w * gabarito_scale), target_height))
            user_resized = cv2.resize(user_bgr, 
                                    (int(user_w * user_scale), target_height))
            
            # Definir margens e espaçamento
            left_margin = 25
            right_margin = 25
            top_margin = 100
            gap = 50  # separação entre as imagens
            
            # Criar canvas para comparação lado a lado com margens corretas
            canvas_width = left_margin + gabarito_resized.shape[1] + gap + user_resized.shape[1] + right_margin
            canvas_height = max(gabarito_resized.shape[0], user_resized.shape[0]) + top_margin + 300  # Mais espaço para tabela de comparação
            
            canvas = np.ones((canvas_height, canvas_width, 3), dtype=np.uint8) * 255  # Fundo branco
            
            # Calcular posições de colagem
            g_x1 = left_margin
            g_y1 = top_margin
            g_x2 = g_x1 + gabarito_resized.shape[1]
            g_y2 = g_y1 + gabarito_resized.shape[0]
            
            u_x1 = g_x2 + gap
            u_y1 = top_margin
            u_x2 = u_x1 + user_resized.shape[1]
            u_y2 = u_y1 + user_resized.shape[0]
            
            # Garantir que as posições estão dentro do canvas
            g_x2 = min(g_x2, canvas_width)
            u_x2 = min(u_x2, canvas_width)
            g_y2 = min(g_y2, canvas_height)
            u_y2 = min(u_y2, canvas_height)
            
            # Colocar imagens lado a lado
            canvas[g_y1:g_y2, g_x1:g_x2] = gabarito_resized[0:(g_y2-g_y1), 0:(g_x2-g_x1)]
            canvas[u_y1:u_y2, u_x1:u_x2] = user_resized[0:(u_y2-u_y1), 0:(u_x2-u_x1)]
            
            # Adicionar títulos
            cv2.putText(canvas, "GABARITO DE REFERENCIA", (left_margin, 50), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)
            cv2.putText(canvas, "RESPOSTA DO ALUNO", (u_x1, 50), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)
            
            # Adicionar informações das respostas
            y_offset = g_y2 + 30
            
            # Cabeçalho da tabela
            cv2.putText(canvas, "COMPARACAO DE RESPOSTAS:", (left_margin, y_offset), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)
            
            y_offset += 30
            
            # Cabeçalhos das colunas
            cv2.putText(canvas, "Questao", (left_margin, y_offset), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)
            cv2.putText(canvas, "Detectada", (left_margin + 95, y_offset), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)
            cv2.putText(canvas, "Correta", (left_margin + 195, y_offset), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)
            cv2.putText(canvas, "Status", (left_margin + 295, y_offset), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)
            
            y_offset += 25
            
            # Linha separadora
            cv2.line(canvas, (left_margin, y_offset), (left_margin + 375, y_offset), (0, 0, 0), 1)
            y_offset += 20
            
            # Dados das respostas
            for question_num in sorted(detected_answers.keys()):
                detected = detected_answers.get(question_num, 'N/A')
                correct = correct_answers.get(question_num, 'N/A')
                status = "✓" if detected == correct else "✗"
                color = (0, 255, 0) if detected == correct else (0, 0, 255)  # Verde ou vermelho
                
                cv2.putText(canvas, f"Q{question_num}", (left_margin, y_offset), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
                cv2.putText(canvas, f"{detected}", (left_margin + 95, y_offset), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
                cv2.putText(canvas, f"{correct}", (left_margin + 195, y_offset), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
                cv2.putText(canvas, f"{status}", (left_margin + 295, y_offset), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
                
                y_offset += 25
            
            # Adicionar informações de debug
            debug_info = [
                f"Test ID: {test_id[:8]}...",
                f"Student ID: {student_id[:8]}...",
                f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            ]
            
            y_offset += 20
            for info in debug_info:
                cv2.putText(canvas, info, (left_margin, y_offset), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.4, (100, 100, 100), 1)
                y_offset += 20
            
            # Salvar arquivo
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"correction_debug_{test_id[:8]}_{student_id[:8]}_{timestamp}.png"
            filepath = os.path.join(self.debug_dir, filename)
            
            cv2.imwrite(filepath, canvas)
            
            print(f"✅ Comparação visual salva: {filepath}")
            print(f"📊 Respostas detectadas: {detected_answers}")
            print(f"📊 Respostas corretas: {correct_answers}")
            
            return filepath
            
        except Exception as e:
            logging.error(f"Erro ao gerar comparação visual: {str(e)}")
            return None
    
    def save_detected_bubbles(self, user_image: np.ndarray, coordinates: Dict, 
                            detected_answers: Dict[int, str], test_id: str, student_id: str) -> str:
        """
        Salva as regiões das bolhas detectadas como imagens separadas
        
        Args:
            user_image: Imagem do usuário
            coordinates: Coordenadas das bolhas
            detected_answers: Respostas detectadas
            test_id: ID da prova
            student_id: ID do aluno
        
        Returns:
            Caminho da pasta onde as imagens foram salvas
        """
        try:
            import os
            from datetime import datetime
            
            # Criar pasta específica para as bolhas desta correção
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            bubbles_dir = os.path.join(self.debug_dir, f"bubbles_{test_id[:8]}_{student_id[:8]}_{timestamp}")
            if not os.path.exists(bubbles_dir):
                os.makedirs(bubbles_dir)
            
            print(f"🔍 Salvando bolhas detectadas em: {bubbles_dir}")
            
            # Converter para OpenCV se necessário
            if hasattr(user_image, 'convert'):  # É imagem PIL
                user_cv = cv2.cvtColor(np.array(user_image), cv2.COLOR_RGB2BGR)
            else:
                user_cv = user_image
            
            # Converter para grayscale se necessário
            if len(user_cv.shape) == 3:
                user_gray = cv2.cvtColor(user_cv, cv2.COLOR_BGR2GRAY)
            else:
                user_gray = user_cv
            
            # Obter coordenadas
            x_positions = coordinates.get('x_positions', [])
            y_positions = coordinates.get('y_positions', [])
            
            if not x_positions or not y_positions:
                print(f"❌ Coordenadas não encontradas")
                return bubbles_dir
            
            # Salvar cada bolha detectada
            for question_num, detected_answer in detected_answers.items():
                if question_num <= len(y_positions):
                    y = y_positions[question_num - 1]
                    
                    # Encontrar índice da resposta detectada
                    answer_index = ord(detected_answer) - ord('A')  # A=0, B=1, C=2, D=3
                    
                    if answer_index < len(x_positions):
                        x = x_positions[answer_index]
                        
                        # Extrair região da bolha (mesma lógica do detector)
                        w = h = 60  # Tamanho fixo para visualização
                        x1 = max(0, x - w//2)
                        y1 = max(0, y - h//2)
                        x2 = min(user_gray.shape[1], x + w//2)
                        y2 = min(user_gray.shape[0], y + h//2)
                        
                        if x2 > x1 and y2 > y1:
                            bubble_region = user_gray[y1:y2, x1:x2]
                            
                            # Salvar imagem da bolha
                            bubble_filename = f"Q{question_num}_{detected_answer}_({x},{y}).png"
                            bubble_path = os.path.join(bubbles_dir, bubble_filename)
                            cv2.imwrite(bubble_path, bubble_region)
                            
                            print(f"  💾 Bolha Q{question_num} {detected_answer} salva: {bubble_filename}")
                        else:
                            print(f"  ❌ Região inválida para Q{question_num} {detected_answer}")
            
            # Salvar também todas as alternativas de cada questão detectada
            print(f"🔍 Salvando todas as alternativas das questões detectadas...")
            for question_num in detected_answers.keys():
                if question_num <= len(y_positions):
                    y = y_positions[question_num - 1]
                    
                    for i, alt in enumerate(['A', 'B', 'C', 'D']):
                        if i < len(x_positions):
                            x = x_positions[i]
                            
                            # Extrair região da bolha
                            w = h = 60
                            x1 = max(0, x - w//2)
                            y1 = max(0, y - h//2)
                            x2 = min(user_gray.shape[1], x + w//2)
                            y2 = min(user_gray.shape[0], y + h//2)
                            
                            if x2 > x1 and y2 > y1:
                                bubble_region = user_gray[y1:y2, x1:x2]
                                
                                # Marcar se é a resposta detectada
                                marker = "✓" if alt == detected_answers[question_num] else ""
                                bubble_filename = f"Q{question_num}_{alt}{marker}_({x},{y}).png"
                                bubble_path = os.path.join(bubbles_dir, bubble_filename)
                                cv2.imwrite(bubble_path, bubble_region)
            
            print(f"✅ Bolhas salvas em: {bubbles_dir}")
            return bubbles_dir
            
        except Exception as e:
            logging.error(f"Erro ao salvar bolhas detectadas: {str(e)}")
            return None

    def mark_bubbles_on_image(self, image: np.ndarray, coordinates: Dict, 
                            question_answers: Dict[int, str]) -> np.ndarray:
        """
        Marca as bolhas detectadas na imagem
        
        Args:
            image: Imagem base
            coordinates: Coordenadas das bolhas
            question_answers: Respostas por questão
        
        Returns:
            Imagem com bolhas marcadas
        """
        try:
            marked_image = image.copy()
            
            if len(marked_image.shape) == 2:
                marked_image = cv2.cvtColor(marked_image, cv2.COLOR_GRAY2BGR)
            
            # Marcar bolhas detectadas
            for question_num, answer in question_answers.items():
                if answer in coordinates.get('x_positions', []):
                    answer_index = coordinates['x_positions'].index(answer)
                    x = coordinates['x_positions'][answer_index]
                    y = coordinates['y_positions'][question_num - 1]
                    
                    # Desenhar círculo na resposta detectada
                    cv2.circle(marked_image, (x, y), 15, (0, 0, 255), 3)  # Vermelho
                    cv2.putText(marked_image, f"Q{question_num}", (x-20, y-25), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
            
            return marked_image
            
        except Exception as e:
            logging.error(f"Erro ao marcar bolhas: {str(e)}")
            return image
