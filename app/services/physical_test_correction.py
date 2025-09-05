# -*- coding: utf-8 -*-
"""
Serviço para correção automática de gabaritos físicos
Baseado no projeto.py original, mas adaptado para integrar com o banco de dados
"""

import numpy as np
import cv2
import qrcode
from PIL import Image
import io
import base64
import logging
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime
import os

class PhysicalTestCorrection:
    """
    Serviço para correção automática de gabaritos físicos
    Usa OpenCV para detectar QR Code e marcações das respostas
    """
    
    def __init__(self):
        self.alternativas_validas = {"A", "B", "C", "D", "E"}
        self.opcoes = {"A": 0, "B": 1, "C": 2, "D": 3, "E": 4}
        
        # Coordenadas base das alternativas (baseado no sistema original)
        self.coordenadas_base = [
            (198, 14, 20, 20), (238, 14, 20, 20), (278, 14, 20, 20), (318, 14, 20, 20), (358, 14, 20, 20),
            (198, 42, 20, 20), (238, 42, 20, 20), (278, 42, 20, 20), (318, 42, 20, 20), (358, 42, 20, 20),
            (198, 70, 20, 20), (238, 70, 20, 20), (278, 70, 20, 20), (318, 70, 20, 20), (358, 70, 20, 20),
            (198, 98, 20, 20), (238, 98, 20, 20), (278, 98, 20, 20), (318, 98, 20, 20), (358, 98, 20, 20),
            (198, 126, 20, 20), (238, 126, 20, 20), (278, 126, 20, 20), (318, 126, 20, 20), (358, 126, 20, 20),
            (198, 154, 20, 20), (238, 154, 20, 20), (278, 154, 20, 20), (318, 154, 20, 20), (358, 154, 20, 20),
            (198, 182, 20, 20), (238, 182, 20, 20), (278, 182, 20, 20), (318, 182, 20, 20), (358, 182, 20, 20),
            (198, 210, 20, 20), (238, 210, 20, 20), (278, 210, 20, 20), (318, 210, 20, 20), (358, 210, 20, 20),
            (198, 238, 20, 20), (238, 238, 20, 20), (278, 238, 20, 20), (318, 238, 20, 20), (358, 238, 20, 20),
            (198, 266, 20, 20), (238, 266, 20, 20), (278, 266, 20, 20), (318, 266, 20, 20), (358, 266, 20, 20),
            (479, 14, 20, 20), (519, 14, 20, 20), (559, 14, 20, 20), (599, 14, 20, 20), (639, 14, 20, 20),
            (479, 42, 20, 20), (519, 42, 20, 20), (559, 42, 20, 20), (599, 42, 20, 20), (639, 42, 20, 20),
            (479, 70, 20, 20), (519, 70, 20, 20), (559, 70, 20, 20), (599, 70, 20, 20), (639, 70, 20, 20),
            (479, 98, 20, 20), (519, 98, 20, 20), (559, 98, 20, 20), (599, 98, 20, 20), (639, 98, 20, 20),
            (479, 126, 20, 20), (519, 126, 20, 20), (559, 126, 20, 20), (599, 126, 20, 20), (639, 126, 20, 20),
            (479, 154, 20, 20), (519, 154, 20, 20), (559, 154, 20, 20), (599, 154, 20, 20), (639, 154, 20, 20),
            (479, 182, 20, 20), (519, 182, 20, 20), (278, 182, 20, 20), (318, 182, 20, 20), (358, 182, 20, 20),
            (479, 210, 20, 20), (519, 210, 20, 20), (559, 210, 20, 20), (599, 210, 20, 20), (639, 210, 20, 20),
            (479, 238, 20, 20), (519, 238, 20, 20), (559, 238, 20, 20), (599, 238, 20, 20), (639, 238, 20, 20),
            (479, 266, 20, 20), (519, 266, 20, 20), (559, 266, 20, 20), (599, 266, 20, 20), (639, 266, 20, 20)
        ]

    def process_correction(self, image_data: bytes, test_id: str, questions_data: List[Dict]) -> Dict[str, Any]:
        """
        Processa correção de gabarito físico
        
        Args:
            image_data: Dados da imagem do gabarito preenchido
            test_id: ID da prova
            questions_data: Lista de questões com respostas corretas
            
        Returns:
            Dicionário com resultados da correção
        """
        try:
            # Converter bytes para imagem OpenCV
            nparr = np.frombuffer(image_data, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            
            if img is None:
                raise ValueError("Não foi possível decodificar a imagem")
            
            # Redimensionar imagem para o tamanho padrão
            img = cv2.resize(img, (720, 320))
            img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Detectar QR Code
            student_id = self._detect_qr_code(img_gray)
            if not student_id:
                raise ValueError("QR Code não detectado na imagem")
            
            # Processar marcações das respostas
            marked_answers = self._detect_marked_answers(img_gray, len(questions_data))
            
            # Comparar com gabarito e calcular resultados
            correction_results = self._calculate_correction_results(
                marked_answers, questions_data, student_id
            )
            
            # Gerar imagem corrigida
            corrected_image = self._generate_corrected_image(
                img, marked_answers, questions_data
            )
            
            return {
                'success': True,
                'student_id': student_id,
                'marked_answers': marked_answers,
                'correction_results': correction_results,
                'corrected_image': corrected_image,
                'total_questions': len(questions_data),
                'correct_answers': correction_results['correct_answers'],
                'incorrect_answers': correction_results['incorrect_answers'],
                'unanswered': correction_results['unanswered']
            }
            
        except Exception as e:
            logging.error(f"Erro no processamento de correção: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'student_id': None,
                'marked_answers': [],
                'correction_results': None,
                'corrected_image': None
            }

    def _detect_qr_code(self, img_gray: np.ndarray) -> Optional[str]:
        """
        Detecta QR Code na imagem e retorna o ID do aluno
        """
        try:
            # Converter para RGB para detecção de QR Code
            img_color = cv2.cvtColor(img_gray, cv2.COLOR_GRAY2BGR)
            
            # Detectar QR Code
            detector = cv2.QRCodeDetector()
            data, _, _ = detector.detectAndDecode(img_color)
            
            if data:
                # Extrair student_id do formato "test_id_student_id"
                parts = data.split('_')
                if len(parts) >= 2:
                    return parts[-1]  # Última parte é o student_id
            
            return None
            
        except Exception as e:
            logging.error(f"Erro ao detectar QR Code: {str(e)}")
            return None

    def _detect_marked_answers(self, img_gray: np.ndarray, num_questions: int) -> List[Dict]:
        """
        Detecta respostas marcadas no gabarito
        """
        try:
            # Aplicar threshold adaptativo
            blurred = cv2.GaussianBlur(img_gray, (5, 5), 0)
            binary = cv2.adaptiveThreshold(
                blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                cv2.THRESH_BINARY_INV, 11, 2
            )
            
            # Aplicar operações morfológicas
            kernel = np.ones((3, 3), np.uint8)
            opening = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
            
            # Obter coordenadas das alternativas para o número de questões
            coordenadas = self.coordenadas_base[:num_questions * 5]
            
            marked_answers = []
            
            for i, (x, y, w, h) in enumerate(coordenadas):
                # Extrair região de interesse
                roi = opening[y:y + h, x:x + w]
                
                # Criar máscara circular
                mask = np.zeros((h, w), dtype=np.uint8)
                centro_x = w // 2
                centro_y = h // 2
                raio = min(w, h) // 2
                cv2.circle(mask, (centro_x, centro_y), raio, 255, -1)
                
                # Aplicar máscara
                roi_masked = cv2.bitwise_and(roi, roi, mask=mask)
                
                # Contar pixels brancos
                total_pixels = cv2.countNonZero(mask)
                white_pixels = cv2.countNonZero(roi_masked)
                
                if total_pixels > 0:
                    percentage = (white_pixels / total_pixels) * 100
                    
                    # Considerar marcado se mais de 70% dos pixels estiverem brancos
                    if percentage >= 70:
                        question_num = (i // 5) + 1
                        alternative = list(self.opcoes.keys())[i % 5]
                        
                        marked_answers.append({
                            'question_number': question_num,
                            'alternative': alternative,
                            'confidence': percentage,
                            'coordinates': (x, y, w, h)
                        })
            
            return marked_answers
            
        except Exception as e:
            logging.error(f"Erro ao detectar respostas marcadas: {str(e)}")
            return []

    def _calculate_correction_results(self, marked_answers: List[Dict], 
                                   questions_data: List[Dict], student_id: str) -> Dict[str, Any]:
        """
        Calcula resultados da correção comparando com o gabarito
        """
        try:
            # Criar dicionário de respostas marcadas por questão
            answers_by_question = {}
            for answer in marked_answers:
                q_num = answer['question_number']
                if q_num not in answers_by_question:
                    answers_by_question[q_num] = []
                answers_by_question[q_num].append(answer)
            
            correct_answers = 0
            incorrect_answers = 0
            unanswered = 0
            detailed_results = []
            
            for i, question in enumerate(questions_data, 1):
                correct_answer = question.get('correct_answer', '')
                marked_for_question = answers_by_question.get(i, [])
                
                if not marked_for_question:
                    # Questão não respondida
                    unanswered += 1
                    detailed_results.append({
                        'question_number': i,
                        'correct_answer': correct_answer,
                        'marked_answer': None,
                        'is_correct': False,
                        'confidence': 0
                    })
                else:
                    # Pegar a resposta com maior confiança
                    best_answer = max(marked_for_question, key=lambda x: x['confidence'])
                    marked_answer = best_answer['alternative']
                    
                    is_correct = marked_answer.upper() == correct_answer.upper()
                    
                    if is_correct:
                        correct_answers += 1
                    else:
                        incorrect_answers += 1
                    
                    detailed_results.append({
                        'question_number': i,
                        'correct_answer': correct_answer,
                        'marked_answer': marked_answer,
                        'is_correct': is_correct,
                        'confidence': best_answer['confidence']
                    })
            
            return {
                'correct_answers': correct_answers,
                'incorrect_answers': incorrect_answers,
                'unanswered': unanswered,
                'total_questions': len(questions_data),
                'detailed_results': detailed_results
            }
            
        except Exception as e:
            logging.error(f"Erro ao calcular resultados: {str(e)}")
            return {
                'correct_answers': 0,
                'incorrect_answers': 0,
                'unanswered': len(questions_data),
                'total_questions': len(questions_data),
                'detailed_results': []
            }

    def _generate_corrected_image(self, original_img: np.ndarray, marked_answers: List[Dict], 
                                questions_data: List[Dict]) -> Optional[bytes]:
        """
        Gera imagem corrigida com marcações visuais (verde = correto, vermelho = incorreto)
        """
        try:
            # Criar cópia da imagem original
            corrected_img = original_img.copy()
            
            # Criar dicionário de respostas por questão
            answers_by_question = {}
            for answer in marked_answers:
                q_num = answer['question_number']
                if q_num not in answers_by_question:
                    answers_by_question[q_num] = []
                answers_by_question[q_num].append(answer)
            
            # Desenhar marcações coloridas
            for i, question in enumerate(questions_data, 1):
                correct_answer = question.get('correct_answer', '')
                marked_for_question = answers_by_question.get(i, [])
                
                if marked_for_question:
                    # Pegar a resposta com maior confiança
                    best_answer = max(marked_for_question, key=lambda x: x['confidence'])
                    marked_answer = best_answer['alternative']
                    coordinates = best_answer['coordinates']
                    
                    # Determinar cor baseada na correção
                    is_correct = marked_answer.upper() == correct_answer.upper()
                    color = (0, 255, 0) if is_correct else (0, 0, 255)  # Verde ou Vermelho
                    
                    # Desenhar círculo colorido
                    x, y, w, h = coordinates
                    centro_x = x + w // 2
                    centro_y = y + h // 2
                    raio = min(w, h) // 2
                    cv2.circle(corrected_img, (centro_x, centro_y), raio, color, 3)
            
            # Adicionar texto com nota
            nota_texto = f"Nota: {len([r for r in answers_by_question.values() if r])}/{len(questions_data)}"
            cv2.putText(corrected_img, nota_texto, (50, corrected_img.shape[0] - 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 0), 2)
            
            # Converter para bytes
            _, buffer = cv2.imencode('.jpg', corrected_img)
            return buffer.tobytes()
            
        except Exception as e:
            logging.error(f"Erro ao gerar imagem corrigida: {str(e)}")
            return None

    def _order_points(self, points: np.ndarray) -> np.ndarray:
        """
        Ordena pontos para transformação de perspectiva
        Baseado no sistema original
        """
        points = points.reshape((4, 2))
        soma = points.sum(axis=1)
        diff = np.diff(points, axis=1)

        topo_esq = points[np.argmin(soma)]
        baixo_dir = points[np.argmax(soma)]
        topo_dir = points[np.argmin(diff)]
        baixo_esq = points[np.argmax(diff)]

        return np.array([topo_esq, topo_dir, baixo_dir, baixo_esq], dtype="float32")

    def _apply_perspective_transform(self, img: np.ndarray, contour: np.ndarray, 
                                   width: int = 688, height: int = 301) -> Optional[np.ndarray]:
        """
        Aplica transformação de perspectiva para corrigir inclinação
        Baseado no sistema original
        """
        try:
            epsilon = 0.02 * cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, epsilon, True)

            if len(approx) == 4:
                ordered_points = self._order_points(approx)

                destination = np.array([
                    [0, 0],
                    [width - 1, 0],
                    [width - 1, height - 1],
                    [0, height - 1]
                ], dtype="float32")

                matrix = cv2.getPerspectiveTransform(ordered_points, destination)
                corrected = cv2.warpPerspective(img, matrix, (width, height))
                return corrected
            else:
                return img
        except Exception as e:
            logging.error(f"Erro na transformação de perspectiva: {str(e)}")
            return img
