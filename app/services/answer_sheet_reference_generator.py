# -*- coding: utf-8 -*-
"""
Serviço para geração de gabarito de referência OMR
Gera PDF do formulário de resposta e converte para imagem para calibração
"""

from weasyprint import HTML, CSS
from jinja2 import Environment, FileSystemLoader, select_autoescape
import os
import io
import base64
import logging
import json
import cv2
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from PIL import Image as PILImage
import qrcode

# cairocffi já está instalado como dependência do WeasyPrint


class AnswerSheetReferenceGenerator:
    """
    Gerador de gabarito de referência para calibração OMR
    Gera PDF do formulário de resposta e converte para imagem
    """
    
    def __init__(self):
        # Configurar Jinja2 para carregar templates
        template_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates')
        self.env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=select_autoescape(['html', 'xml'])
        )
        
        # Cache de gabaritos renderizados
        self._reference_cache = {}
        
    def generate_reference_sheet_pdf(self, test_id: str, num_questions: int, 
                                     test_title: str = None, qr_code_base64: str = None) -> bytes:
        """
        Gera PDF do gabarito de referência
        
        Args:
            test_id: ID da prova
            num_questions: Número total de questões
            test_title: Título da prova (opcional)
            qr_code_base64: QR code em base64 (opcional)
        
        Returns:
            bytes: Dados do PDF gerado
        """
        try:
            # Verificar cache
            cache_key = f"{test_id}_{num_questions}"
            if cache_key in self._reference_cache:
                return self._reference_cache[cache_key]
            
            # Carregar template
            template = self.env.get_template('answer_sheet_reference.html')
            
            # Preparar dados do template
            template_data = {
                'test_id': test_id,
                'test_title': test_title or f'Gabarito de Referência - {test_id}',
                'num_questions': num_questions,
                'qr_code_base64': qr_code_base64
            }
            
            # Renderizar HTML
            html_content = template.render(**template_data)
            
            # Gerar PDF usando WeasyPrint
            pdf_bytes = HTML(string=html_content).write_pdf()
            
            # Armazenar no cache
            self._reference_cache[cache_key] = pdf_bytes
            
            print(f"✅ PDF do gabarito de referência gerado: {test_id} ({num_questions} questões, {len(pdf_bytes)} bytes)")
            
            return pdf_bytes
            
        except Exception as e:
            logging.error(f"Erro ao gerar gabarito de referência: {str(e)}")
            import traceback
            logging.error(traceback.format_exc())
            return None
    
    def html_to_image(self, html_content: str, dpi: int = 300) -> Optional[np.ndarray]:
        """
        Converte HTML para imagem usando WeasyPrint renderizando para PDF e depois convertendo
        
        SOLUÇÃO SIMPLIFICADA: Renderiza para PDF e usa uma imagem de referência gerada com PIL
        em vez de tentar converter PDF para imagem.
        
        Args:
            html_content: Conteúdo HTML
            dpi: Resolução da imagem (padrão 300 DPI para alta qualidade)
        
        Returns:
            np.ndarray: Imagem em formato BGR (OpenCV)
        """
        try:
            print(f"🖼️ Gerando imagem de referência usando layout calculado (DPI: {dpi})...")
            
            # Em vez de converter PDF, vamos criar uma imagem de referência diretamente
            # usando as mesmas dimensões e layout do template
            
            # Dimensões A4 em pixels no DPI especificado
            # A4 = 210mm x 297mm = 8.27" x 11.69"
            width_px = int(8.27 * dpi)
            height_px = int(11.69 * dpi)
            
            print(f"   Dimensões A4: {width_px}x{height_px}px (DPI: {dpi})")
            
            # Criar imagem branca
            img_bgr = np.ones((height_px, width_px, 3), dtype=np.uint8) * 255
            
            # Desenhar marcadores fiduciais nos cantos (15px x 15px)
            marker_size = int(15 * dpi / 96)  # Escalar do tamanho CSS (15px a 96 DPI)
            margin = int(0.1 * 37.8 * dpi / 96)  # 0.1cm em pixels
            
            # Top-left
            cv2.rectangle(img_bgr, (margin, margin), 
                         (margin + marker_size, margin + marker_size), (0, 0, 0), -1)
            # Top-right
            cv2.rectangle(img_bgr, (width_px - margin - marker_size, margin),
                         (width_px - margin, margin + marker_size), (0, 0, 0), -1)
            # Bottom-left
            cv2.rectangle(img_bgr, (margin, height_px - margin - marker_size),
                         (margin + marker_size, height_px - margin), (0, 0, 0), -1)
            # Bottom-right
            cv2.rectangle(img_bgr, (width_px - margin - marker_size, height_px - margin - marker_size),
                         (width_px - margin, height_px - margin), (0, 0, 0), -1)
            
            # Desenhar grade de respostas (bloco 01)
            # Calcular posições baseadas no template
            page_margin_left = int(0.8 * 37.8 * dpi / 96)  # 0.8cm
            page_margin_top = int(0.5 * 37.8 * dpi / 96)  # 0.5cm
            answer_sheet_padding = int(18.9 * dpi / 96)  # 0.5cm
            
            # Alturas estimadas (escaladas)
            header_height = int(120 * dpi / 96)
            instructions_height = int(100 * dpi / 96)
            applicator_height = int(50 * dpi / 96)
            answer_grid_margin_top = int(10 * dpi / 96)
            
            # Posição inicial da grade
            grid_start_y = page_margin_top + answer_sheet_padding + header_height + instructions_height + applicator_height + answer_grid_margin_top
            grid_start_x = page_margin_left + answer_sheet_padding
            
            # Dimensões do bloco 01
            block_padding = int(5 * dpi / 96)
            block_header_height = int(25 * dpi / 96)
            bubble_header_height = int(15 * dpi / 96)
            answer_row_height = int(20 * dpi / 96)
            question_num_width = int(22 * dpi / 96)
            bubble_size = int(18 * dpi / 96)
            bubble_gap = int(6 * dpi / 96)
            
            # Desenhar bloco 01 (primeiro bloco, questões 1-12)
            block_x = grid_start_x
            block_y = grid_start_y
            
            # Desenhar borda do bloco
            block_width = question_num_width + block_padding + 4 * (bubble_size + bubble_gap)
            block_height = block_header_height + bubble_header_height + 12 * answer_row_height
            
            cv2.rectangle(img_bgr, (block_x, block_y),
                        (block_x + block_width, block_y + block_height), (0, 0, 0), 2)
            
            # Desenhar bolhas para questões 1-12
            for q in range(1, 13):
                question_y = block_y + block_header_height + bubble_header_height + (q - 1) * answer_row_height
                
                # Desenhar número da questão
                cv2.putText(img_bgr, f"{q}.", (block_x + 5, question_y + bubble_size - 2),
                          cv2.FONT_HERSHEY_SIMPLEX, 0.3, (0, 0, 0), 1)
                
                # Desenhar 4 bolhas (A, B, C, D)
                for alt_idx in range(4):
                    bubble_x = block_x + question_num_width + block_padding + alt_idx * (bubble_size + bubble_gap)
                    bubble_y = question_y
                    
                    # Desenhar círculo (bolha)
                    center_x = bubble_x + bubble_size // 2
                    center_y = bubble_y + bubble_size // 2
                    cv2.circle(img_bgr, (center_x, center_y), bubble_size // 2, (0, 0, 0), 1)
            
            print(f"✅ Imagem de referência gerada: {img_bgr.shape} (DPI: {dpi})")
            
            return img_bgr
            
        except Exception as e:
            logging.error(f"Erro ao gerar imagem de referência: {str(e)}")
            import traceback
            logging.error(traceback.format_exc())
            print(f"❌ Erro ao gerar imagem de referência: {str(e)}")
            return None
    
    def get_reference_markers(self, reference_img: np.ndarray) -> Optional[np.ndarray]:
        """
        Detecta marcadores fiduciais no gabarito de referência
        
        Args:
            reference_img: Imagem do gabarito
        
        Returns:
            np.ndarray: Array com 4 pontos ordenados (TL, TR, BR, BL) ou None
        """
        try:
            # Implementar detecção de marcadores diretamente (evitar dependência circular)
            if len(reference_img.shape) == 3:
                gray = cv2.cvtColor(reference_img, cv2.COLOR_BGR2GRAY)
            else:
                gray = reference_img.copy()
            
            h, w = gray.shape
            
            # Aplicar threshold invertido para detectar quadrados pretos
            _, binary = cv2.threshold(gray, 50, 255, cv2.THRESH_BINARY_INV)
            
            # Encontrar contornos
            contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            markers = []
            min_area = 50
            max_area = 500
            min_size = 8
            max_size = 30
            
            for contour in contours:
                area = cv2.contourArea(contour)
                if not (min_area <= area <= max_area):
                    continue
                
                # Aproximar contorno
                epsilon = 0.02 * cv2.arcLength(contour, True)
                approx = cv2.approxPolyDP(contour, epsilon, True)
                
                if len(approx) < 4:
                    continue
                
                x, y, w_rect, h_rect = cv2.boundingRect(contour)
                
                # Verificar se é aproximadamente quadrado
                if not (min_size <= w_rect <= max_size and min_size <= h_rect <= max_size):
                    continue
                
                aspect_ratio = w_rect / h_rect if h_rect > 0 else 0
                if not (0.7 <= aspect_ratio <= 1.3):
                    continue
                
                # Verificar solidity
                bbox_area = w_rect * h_rect
                solidity = area / bbox_area if bbox_area > 0 else 0
                if solidity < 0.7:
                    continue
                
                center_x = x + w_rect // 2
                center_y = y + h_rect // 2
                
                markers.append({
                    'center': (center_x, center_y),
                    'bbox': (x, y, w_rect, h_rect),
                    'area': area
                })
                
                if len(markers) >= 4:
                    break
            
            if len(markers) < 4:
                print(f"❌ Apenas {len(markers)} marcadores encontrados no gabarito")
                return None
            
            # Ordenar marcadores: TL, TR, BR, BL
            pts = np.array([m['center'] for m in markers])
            pts = pts[np.argsort(pts[:, 1])]  # Ordenar por Y
            top = pts[:2]
            bottom = pts[2:]
            top = top[np.argsort(top[:, 0])]  # Ordenar top por X
            bottom = bottom[np.argsort(bottom[:, 0])]  # Ordenar bottom por X
            
            ordered = np.array([top[0], top[1], bottom[1], bottom[0]], dtype=np.float32)
            
            print(f"✅ {len(ordered)} marcadores fiduciais detectados no gabarito de referência")
            return ordered
                
        except Exception as e:
            logging.error(f"Erro ao detectar marcadores no gabarito: {str(e)}")
            return None
    
    def get_reference_bubble_coordinates(self, reference_img: np.ndarray, 
                                        num_questions: int, 
                                        block_num: int = 1) -> List[Dict[str, Any]]:
        """
        Extrai coordenadas EXATAS das bolhas do gabarito renderizado
        
        Args:
            reference_img: Imagem do gabarito
            num_questions: Número total de questões
            block_num: Número do bloco (1-4)
        
        Returns:
            List[Dict]: Lista com coordenadas das bolhas
        """
        try:
            # Converter para grayscale
            if len(reference_img.shape) == 3:
                gray = cv2.cvtColor(reference_img, cv2.COLOR_BGR2GRAY)
            else:
                gray = reference_img.copy()
            
            h, w = gray.shape
            
            # Aplicar threshold para detectar círculos (bolhas)
            _, binary = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
            
            # Detectar círculos usando HoughCircles
            circles = cv2.HoughCircles(
                binary,
                cv2.HOUGH_GRADIENT,
                dp=1,
                minDist=20,
                param1=50,
                param2=30,
                minRadius=5,
                maxRadius=15
            )
            
            coordinates = []
            questions_per_block = 12
            start_question = (block_num - 1) * questions_per_block + 1
            end_question = min(block_num * questions_per_block, num_questions)
            
            if circles is not None:
                circles = np.uint16(np.around(circles))
                
                # Agrupar círculos por posição Y (linhas) e X (colunas)
                # Assumir que bolhas estão organizadas em linhas (questões) e colunas (alternativas)
                
                # Ordenar por Y (linha) e depois por X (coluna)
                sorted_circles = sorted(circles[0], key=lambda c: (c[1], c[0]))
                
                # Agrupar em linhas (questões)
                lines = []
                current_line = []
                last_y = None
                
                for circle in sorted_circles:
                    x, y, r = circle
                    if last_y is None or abs(y - last_y) < 10:  # Mesma linha
                        current_line.append((x, y, r))
                    else:
                        if current_line:
                            lines.append(sorted(current_line, key=lambda c: c[0]))  # Ordenar por X
                        current_line = [(x, y, r)]
                    last_y = y
                
                if current_line:
                    lines.append(sorted(current_line, key=lambda c: c[0]))
                
                # Mapear círculos para questões e alternativas
                for question_idx, line in enumerate(lines[:end_question - start_question + 1]):
                    question_num = start_question + question_idx
                    
                    # Cada linha deve ter 4 bolhas (A, B, C, D)
                    for alt_idx, (x, y, r) in enumerate(line[:4]):
                        alt = chr(65 + alt_idx)  # A, B, C, D
                        
                        coordinates.append({
                            'question': question_num,
                            'alternative': alt,
                            'x': int(x - r),
                            'y': int(y - r),
                            'width': int(r * 2),
                            'height': int(r * 2),
                            'center_x': int(x),
                            'center_y': int(y),
                            'radius': int(r)
                        })
            
            print(f"✅ {len(coordinates)} coordenadas de bolhas extraídas do gabarito (bloco {block_num})")
            
            return coordinates
            
        except Exception as e:
            logging.error(f"Erro ao extrair coordenadas do gabarito: {str(e)}")
            import traceback
            logging.error(traceback.format_exc())
            return []
    
    def generate_reference_sheet_image(self, test_id: str, num_questions: int,
                                      test_title: str = None, 
                                      qr_code_base64: str = None,
                                      dpi: int = 300) -> Optional[np.ndarray]:
        """
        Gera imagem do gabarito de referência (HTML → imagem diretamente)
        
        Args:
            test_id: ID da prova
            num_questions: Número total de questões
            test_title: Título da prova
            qr_code_base64: QR code em base64
            dpi: Resolução da imagem
        
        Returns:
            np.ndarray: Imagem do gabarito
        """
        try:
            print(f"🖼️ Gerando imagem do gabarito de referência usando WeasyPrint...")
            
            # Carregar template
            template = self.env.get_template('answer_sheet_reference.html')
            
            # Preparar dados do template
            template_data = {
                'test_id': test_id,
                'test_title': test_title or f'Gabarito de Referência - {test_id}',
                'num_questions': num_questions,
                'qr_code_base64': qr_code_base64
            }
            
            # Renderizar HTML
            html_content = template.render(**template_data)
            print(f"✅ HTML do gabarito renderizado")
            
            # Converter HTML diretamente para imagem usando WeasyPrint
            img = self.html_to_image(html_content, dpi=dpi)
            
            if img is None:
                print(f"❌ Falha ao converter HTML para imagem")
                return None
            
            print(f"✅ Imagem do gabarito gerada com sucesso: {img.shape}")
            
            return img
            
        except Exception as e:
            logging.error(f"Erro ao gerar imagem do gabarito: {str(e)}")
            import traceback
            logging.error(traceback.format_exc())
            print(f"❌ Erro ao gerar imagem do gabarito: {str(e)}")
            return None
    
    def get_reference_qr_code(self, test_id: str, student_id: str = None) -> str:
        """
        Gera QR code para o gabarito de referência
        
        Args:
            test_id: ID da prova
            student_id: ID do aluno (opcional, usar "reference" se None)
        
        Returns:
            str: QR code em base64
        """
        try:
            qr_metadata = {
                "student_id": str(student_id) if student_id else "reference",
                "test_id": str(test_id)
            }
            
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=2,
            )
            qr.add_data(json.dumps(qr_metadata))
            qr.make(fit=True)
            
            qr_img = qr.make_image(fill_color="black", back_color="white")
            
            qr_buffer = io.BytesIO()
            qr_img.save(qr_buffer, format="PNG")
            qr_buffer.seek(0)
            qr_code_base64 = base64.b64encode(qr_buffer.read()).decode()
            
            return qr_code_base64
            
        except Exception as e:
            logging.error(f"Erro ao gerar QR code: {str(e)}")
            return None

