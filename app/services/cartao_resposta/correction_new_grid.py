# -*- coding: utf-8 -*-
"""
Pipeline OMR Robusto e Determinístico
Baseado em Template Fixo + JSON de Topologia

PRINCÍPIO FUNDAMENTAL:
    "O template define o espaço.
     O JSON define a topologia.
     A imagem só confirma o preenchimento."

PROIBIÇÕES:
    ❌ NÃO usar ML
    ❌ NÃO usar OCR
    ❌ NÃO tentar inferir layout pela imagem
    ❌ NÃO assumir números fixos de questões/alternativas
"""

import cv2
import numpy as np
import json
import logging
import uuid
import re
from typing import Dict, List, Optional, Tuple, Any
from collections import defaultdict
from datetime import datetime
from app import db


class AnswerSheetCorrectionNewGrid:
    """
    Pipeline OMR Robusto - 9 Etapas Determinísticas
    
    Etapas:
        1. Pré-processamento
        2. Detectar âncoras A4 (4 quadrados)
        3. Normalizar para A4 lógico (2480x3508)
        4. Detectar triângulos do grid (4 triângulos)
        5. Detectar blocos de resposta
        6. Mapear JSON → Grid (CRÍTICO)
        7. Calcular centros das bolhas
        8. Detectar marcações
        9. Construir resultado
    """
    
    # Constantes de normalização A4 (300 DPI)
    A4_WIDTH_PX = 2480   # 21cm × 11.811 px/cm
    A4_HEIGHT_PX = 3508  # 29.7cm × 11.811 px/cm
    
    # Threshold de detecção de marcação
    FILL_THRESHOLD = 0.45  # 45% da área preenchida
    
    # =========================================================================
    # CONSTANTES CALIBRADAS EMPIRICAMENTE (answer_sheet.html)
    # =========================================================================
    # ✅ VALORES FINAIS CALIBRADOS com calibrate_block_simple.py
    # A4 normalizado a 300 DPI: 1cm = 118.11px
    # ⚠️ CSS pixels ≠ DPI pixels na normalização!
    
    # Altura da linha (0.44cm CSS → 51.97px na normalização)
    ROW_HEIGHT_PX = 51.97
    
    # Raio da bolha (15px CSS → 25px calibrado na imagem normalizada)
    BUBBLE_RADIUS_PX = 25
    
    # Espaçamento entre bolhas horizontalmente (bubble + gap)
    # ⚠️ CRÍTICO: 15px + 4px CSS → 61px calibrado na imagem normalizada!
    BUBBLE_SPACING_PX = 61  # Calibrado empiricamente
    
    # Offsets iniciais (compensam borda + padding + número da questão)
    # ⚠️ CRÍTICO: Valores calibrados empiricamente!
    BLOCK_OFFSET_X = 115  # Calibrado: 31 base + 84 ajuste
    BLOCK_OFFSET_Y = 40   # Calibrado: 10 base + 30 ajuste
    
    # Valores CSS de referência (apenas documentação, não usados diretamente)
    BUBBLE_WIDTH_PX = 15           # CSS: width: 15px
    BUBBLE_HEIGHT_PX = 15          # CSS: height: 15px
    BUBBLE_GAP_PX = 4              # CSS: gap: 4px
    QUESTION_NUM_WIDTH_PX = 25     # CSS: width: 25px
    BLOCK_BORDER_WIDTH_PX = 2      # CSS: border: 2px
    BLOCK_PADDING_TOP_PX = 8       # CSS: padding-top: 8px
    BLOCK_PADDING_LEFT_PX = 4      # CSS: padding-left: 4px
    
    def __init__(self, debug: bool = False):
        """
        Inicializa o serviço de correção
        
        Args:
            debug: Se True, salva imagens de debug
        """
        self.debug = debug
        self.logger = logging.getLogger(__name__)
        self.debug_dir = "debug_corrections_new"
        
        if self.debug:
            import os
            if not os.path.exists(self.debug_dir):
                os.makedirs(self.debug_dir)
            self.debug_timestamp = ""
            abspath = os.path.abspath(self.debug_dir)
            self.logger.info(f"🐛 Debug OMR ativado — imagens em: {abspath}")
        
        self.logger.info("✅ Pipeline OMR Robusto inicializado")
    
    # =========================================================================
    # DETECÇÃO DE QR CODE
    # =========================================================================
    
    def _detectar_qr_code(self, img: np.ndarray) -> Optional[Dict[str, str]]:
        """
        Detecta e decodifica QR Code no cartão resposta
        Usa múltiplas estratégias para aumentar taxa de sucesso
        
        Returns:
            Dict com gabarito_id, student_id, test_id ou None
        """
        import json as json_module
        
        self.logger.info("🔍 Iniciando detecção de QR Code...")
        
        # Converter para grayscale se necessário
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            gray = img.copy()
        
        qr_data_str = None
        
        # ========================================
        # ESTRATÉGIA 1: pyzbar (mais confiável)
        # ========================================
        try:
            from pyzbar.pyzbar import decode
            
            self.logger.debug("Tentando pyzbar na imagem original...")
            qr_codes = decode(img)
            
            if qr_codes:
                qr_data_str = qr_codes[0].data.decode('utf-8')
                self.logger.info("✅ QR Code detectado com pyzbar (imagem original)")
            
            if not qr_data_str:
                self.logger.debug("Tentando pyzbar em grayscale...")
                qr_codes = decode(gray)
                if qr_codes:
                    qr_data_str = qr_codes[0].data.decode('utf-8')
                    self.logger.info("✅ QR Code detectado com pyzbar (grayscale)")
            
            # Tentar com imagem aumentada (para QR codes pequenos)
            if not qr_data_str:
                self.logger.debug("Tentando pyzbar com imagem aumentada (2x)...")
                h, w = gray.shape
                enlarged = cv2.resize(gray, (w*2, h*2), interpolation=cv2.INTER_CUBIC)
                qr_codes = decode(enlarged)
                if qr_codes:
                    qr_data_str = qr_codes[0].data.decode('utf-8')
                    self.logger.info("✅ QR Code detectado com pyzbar (aumentado)")
            
            # Tentar com equalização de histograma
            if not qr_data_str:
                self.logger.debug("Tentando pyzbar com equalização...")
                equalized = cv2.equalizeHist(gray)
                qr_codes = decode(equalized)
                if qr_codes:
                    qr_data_str = qr_codes[0].data.decode('utf-8')
                    self.logger.info("✅ QR Code detectado com pyzbar (equalizado)")
                    
        except ImportError:
            self.logger.warning("⚠️ pyzbar não disponível, tentando OpenCV...")
        except Exception as e:
            self.logger.warning(f"⚠️ Erro ao usar pyzbar: {str(e)}")
        
        # ========================================
        # ESTRATÉGIA 2: OpenCV QRCodeDetector (fallback)
        # ========================================
        if not qr_data_str:
            try:
                self.logger.debug("Tentando OpenCV QRCodeDetector...")
                qr_detector = cv2.QRCodeDetector()
                
                # Tentar na imagem original
                data, bbox, _ = qr_detector.detectAndDecode(img)
                if data:
                    qr_data_str = data
                    self.logger.info("✅ QR Code detectado com OpenCV (imagem original)")
                
                # Tentar em grayscale
                if not qr_data_str:
                    data, bbox, _ = qr_detector.detectAndDecode(gray)
                    if data:
                        qr_data_str = data
                        self.logger.info("✅ QR Code detectado com OpenCV (grayscale)")
                
                # Tentar com threshold
                if not qr_data_str:
                    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                    data, bbox, _ = qr_detector.detectAndDecode(thresh)
                    if data:
                        qr_data_str = data
                        self.logger.info("✅ QR Code detectado com OpenCV (threshold)")
                        
            except Exception as e:
                self.logger.warning(f"⚠️ Erro ao usar OpenCV QRCodeDetector: {str(e)}")
        
        # ========================================
        # PROCESSAR DADOS DO QR CODE
        # ========================================
        if not qr_data_str:
            self.logger.error("❌ QR Code não encontrado após todas as tentativas")
            self.logger.error("Dicas:")
            self.logger.error("  - Verifique se o QR code está visível na imagem")
            self.logger.error("  - Aumente a resolução da imagem (mínimo 1000x1400)")
            self.logger.error("  - Certifique-se que o QR code tem pelo menos 100x100px")
            return None
        
        try:
            # Decodificar JSON
            qr_data = json_module.loads(qr_data_str)
            
            gabarito_id = qr_data.get('gabarito_id')
            student_id = qr_data.get('student_id')
            test_id = qr_data.get('test_id')
            
            # ✅ ACEITAR gabarito_id OU test_id
            if not gabarito_id and not test_id:
                self.logger.error("❌ Nem gabarito_id nem test_id encontrados no QR Code")
                self.logger.error(f"Dados do QR Code: {qr_data_str[:100]}...")
                return None
            
            # Se tem test_id mas não gabarito_id, buscar gabarito pela prova
            if test_id and not gabarito_id:
                # ✅ MODIFICADO: Para provas físicas, não buscar gabarito_id
                # O QR Code de provas físicas usa apenas test_id (não gabarito_id)
                # Os dados de correção serão buscados em PhysicalTestForm no corrigir_cartao_resposta
                self.logger.info(f"🔍 QR Code com test_id (prova física): {test_id[:8]}...")
                # Nota: gabarito_id ficará None, será tratado no corrigir_cartao_resposta buscando em PhysicalTestForm
            
            self.logger.info(f"✅ QR Code decodificado com sucesso!")
            if gabarito_id:
                self.logger.info(f"   Gabarito: {gabarito_id[:8]}...")
            if student_id:
                self.logger.info(f"   Aluno: {student_id[:8]}...")
            if test_id:
                self.logger.info(f"   Test: {test_id[:8]}...")
            
            return {
                'gabarito_id': gabarito_id,
                'student_id': student_id,
                'test_id': test_id
            }
            
        except json_module.JSONDecodeError as e:
            self.logger.error(f"❌ Erro ao decodificar JSON do QR Code: {str(e)}")
            self.logger.error(f"Dados recebidos: {qr_data_str[:200]}...")
            return None
        except Exception as e:
            self.logger.error(f"❌ Erro ao processar QR Code: {str(e)}")
            return None
    
    def _criar_gabarito_de_test(self, test_id: str):
        """
        Cria gabarito temporário a partir dos dados da prova (Test).
        Usado quando prova física foi corrigida sem ter gabarito gerado antes.
        
        Args:
            test_id: ID da prova
        
        Returns:
            Objeto temporário com atributos: id, correct_answers, blocks_config, num_questions, use_blocks
            ou None se falhar
        """
        try:
            from app.models.test import Test
            from app.models.testQuestion import TestQuestion
            from app.models.question import Question
            
            # Buscar prova
            test = Test.query.get(test_id)
            if not test:
                self.logger.error(f"❌ Prova {test_id} não encontrada")
                return None
            
            # Buscar questões ordenadas
            test_questions = TestQuestion.query.filter_by(
                test_id=test_id
            ).order_by(TestQuestion.order).all()
            
            if not test_questions:
                self.logger.error(f"❌ Prova {test_id} não tem questões")
                return None
            
            # Montar correct_answers
            correct_answers = {}
            for i, tq in enumerate(test_questions, start=1):
                question = Question.query.get(tq.question_id)
                if question:
                    correct_answers[str(i)] = question.correct_answer
                else:
                    self.logger.warning(f"⚠️ Questão {tq.question_id} não encontrada")
                    correct_answers[str(i)] = 'A'  # Fallback
            
            num_questions = len(correct_answers)
            self.logger.info(f"📝 Gabarito montado com {num_questions} questões")
            
            # Criar topology padrão (4 blocos de 26 questões)
            blocks_config = {
                'use_blocks': True,
                'num_blocks': 4,
                'questions_per_block': 26,
                'topology': {
                    'blocks': []
                }
            }
            
            # Montar topology
            for block_num in range(1, 5):
                start_q = (block_num - 1) * 26 + 1
                end_q = min(block_num * 26, num_questions)
                
                block_questions = []
                for q_num in range(start_q, end_q + 1):
                    block_questions.append({
                        'q': q_num,
                        'alternatives': ['A', 'B', 'C', 'D']
                    })
                
                blocks_config['topology']['blocks'].append({
                    'block_id': block_num,
                    'questions': block_questions
                })
            
            # Criar objeto temporário (não salva no banco)
            class GabaritoTemp:
                def __init__(self):
                    self.id = f"temp_{test_id}"
                    self.correct_answers = correct_answers
                    self.blocks_config = blocks_config
                    self.num_questions = num_questions
                    self.use_blocks = True
            
            self.logger.info(f"✅ Gabarito temporário criado para test_id {test_id[:8]}...")
            return GabaritoTemp()
            
        except Exception as e:
            self.logger.error(f"❌ Erro ao criar gabarito de test: {str(e)}")
            return None
    
    # =========================================================================
    # ETAPA 1: PRÉ-PROCESSAMENTO
    # =========================================================================
    
    def _preprocess_image(self, img: np.ndarray) -> Dict[str, np.ndarray]:
        """
        Pré-processamento padrão da imagem
        
        Args:
            img: Imagem colorida (BGR)
        
        Returns:
            Dict com: gray, blur, thresh, edges
        """
        # Converter para grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Gaussian blur para reduzir ruído
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        
        # Threshold adaptativo (melhor para iluminação irregular)
        thresh = cv2.adaptiveThreshold(
            blur, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV,
            11, 2
        )
        
        # Detecção de bordas
        edges = cv2.Canny(blur, 50, 150)
        
        return {
            "gray": gray,
            "blur": blur,
            "thresh": thresh,
            "edges": edges
        }
    
    # =========================================================================
    # ETAPA 2: DETECTAR ÂNCORAS A4
    # =========================================================================
    
    def _detect_a4_anchors(self, img: np.ndarray, edges: np.ndarray) -> Optional[Dict]:
        """
        Detecta 4 quadrados pretos nos cantos do cartão resposta (âncoras A4)
        
        Implementação robusta baseada no código testado:
        - RETR_TREE para hierarquia de contornos
        - Área RELATIVA à imagem (não fixa)
        - Aspect ratio restritivo (0.9-1.1)
        - Filtro de proximidade à borda
        - Garantia de 1 quadrado por canto
        - Extração do vértice correto (não o centro)
        
        Args:
            img: Imagem original
            edges: Bordas detectadas (não usado, usa threshold direto)
        
        Returns:
            Dict com coordenadas dos 4 quadrados ordenados (TL, TR, BR, BL) ou None
        """
        try:
            # Converter para grayscale
            if len(img.shape) == 3:
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            else:
                gray = img.copy()
            
            img_height, img_width = gray.shape[:2]
            img_area = img_width * img_height
            
            # Aplicar threshold para detectar quadrados pretos
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            
            # ✅ CORREÇÃO 1: Usar RETR_TREE para hierarquia de contornos
            contours, hierarchy = cv2.findContours(binary, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
            
            # ✅ CORREÇÃO 2: Área RELATIVA à imagem (nunca fixa)
            min_area = img_area * 0.0001   # ~0.01% da imagem
            max_area = img_area * 0.002    # ~0.2% da imagem
            
            # ✅ CORREÇÃO 3: Margem para filtro de proximidade à borda
            margin_x = img_width * 0.1   # 10% da largura
            margin_y = img_height * 0.1  # 10% da altura
            
            squares = []
            
            for i, cnt in enumerate(contours):
                # Aproximar contorno
                peri = cv2.arcLength(cnt, True)
                approx = cv2.approxPolyDP(cnt, 0.04 * peri, True)
                
                # Verificar se é um quadrado (4 vértices)
                if len(approx) != 4:
                    continue
                
                area = cv2.contourArea(approx)
                
                # Filtrar por área relativa
                if not (min_area < area < max_area):
                    continue
                
                # Verificar aspect ratio
                x, y, w, h = cv2.boundingRect(approx)
                aspect_ratio = w / float(h) if h > 0 else 0
                
                # Aspect ratio mais restritivo (quadrado real)
                if not (0.9 < aspect_ratio < 1.1):
                    continue
                
                # Calcular centro do quadrado
                M = cv2.moments(approx)
                if M["m00"] == 0:
                    continue
                
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])
                
                # ✅ CORREÇÃO 4: FILTRO DE PROXIMIDADE À BORDA (ESSENCIAL)
                # Quadrados A4 SEMPRE estão perto dos cantos
                is_near_edge = (
                    cx < margin_x or
                    cx > img_width - margin_x or
                    cy < margin_y or
                    cy > img_height - margin_y
                )
                
                if not is_near_edge:
                    continue
                
                squares.append({
                    'contour': approx,
                    'center': (cx, cy),
                    'area': area
                })
            
            if len(squares) < 4:
                self.logger.warning(f"❌ Apenas {len(squares)} quadrados detectados (necessário 4)")
                self.logger.info(f"   Área mínima: {min_area:.0f}px², máxima: {max_area:.0f}px²")
                self.logger.info(f"   Margens: X={margin_x:.0f}px, Y={margin_y:.0f}px")
                return None
            
            # ✅ CORREÇÃO 5: GARANTIR 1 QUADRADO POR CANTO
            corners = {
                "TL": [],  # Top-Left
                "TR": [],  # Top-Right
                "BR": [],  # Bottom-Right
                "BL": []   # Bottom-Left
            }
            
            for s in squares:
                cx, cy = s["center"]
                # Classificar por quadrante
                if cx < img_width / 2 and cy < img_height / 2:
                    corners["TL"].append(s)
                elif cx >= img_width / 2 and cy < img_height / 2:
                    corners["TR"].append(s)
                elif cx >= img_width / 2 and cy >= img_height / 2:
                    corners["BR"].append(s)
                else:
                    corners["BL"].append(s)
            
            # Verificar se todos os cantos têm pelo menos 1 quadrado
            missing_corners = [corner for corner, items in corners.items() if not items]
            if missing_corners:
                self.logger.warning(f"❌ Quadrados ausentes nos cantos: {missing_corners}")
                return None
            
            # Para cada canto, pegar o maior quadrado (mais confiável) e extrair o vértice correto
            ordered_squares = {}
            for corner, items in corners.items():
                if not items:
                    self.logger.warning(f"❌ Quadrado ausente no canto {corner}")
                    return None
                # Pegar o maior quadrado do canto
                best_square = max(items, key=lambda x: x["area"])
                
                # ✅ CORREÇÃO 6: Extrair o vértice correto do quadrado ao invés do centro
                # O vértice correto é aquele que está mais próximo do canto real do documento
                contour = best_square["contour"]  # approx com 4 vértices
                vertices = contour.reshape(-1, 2)  # Converter para array de pontos (x, y)
                
                # Selecionar o vértice correto baseado no canto
                if corner == "TL":  # Top-Left: menor x E menor y
                    # Encontrar vértice com menor distância ao canto (0, 0)
                    distances = vertices[:, 0] + vertices[:, 1]
                    corner_vertex = vertices[np.argmin(distances)]
                elif corner == "TR":  # Top-Right: maior x E menor y
                    # Encontrar vértice com maior x e menor y (mais próximo de (width, 0))
                    scores = vertices[:, 0] - vertices[:, 1]
                    corner_vertex = vertices[np.argmax(scores)]
                elif corner == "BR":  # Bottom-Right: maior x E maior y
                    # Encontrar vértice com maior distância ao canto (0, 0)
                    distances = vertices[:, 0] + vertices[:, 1]
                    corner_vertex = vertices[np.argmax(distances)]
                else:  # BL - Bottom-Left: menor x E maior y
                    # Encontrar vértice com menor x e maior y (mais próximo de (0, height))
                    scores = vertices[:, 0] - vertices[:, 1]
                    corner_vertex = vertices[np.argmin(scores)]
                
                ordered_squares[corner] = [float(corner_vertex[0]), float(corner_vertex[1])]
            
            # Salvar debug
            if self.debug:
                img_debug = img.copy()
                for label, vertex in ordered_squares.items():
                    vx, vy = int(vertex[0]), int(vertex[1])
                    cv2.circle(img_debug, (vx, vy), 15, (0, 255, 0), -1)
                    cv2.putText(img_debug, label, (vx+20, vy), 
                              cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 3)
                self._save_debug_image("01_a4_anchors_detected.jpg", img_debug)
            
            self.logger.info(f"✅ 4 quadrados A4 detectados (vértices)")
            self.logger.info(f"   TL={ordered_squares['TL']}, TR={ordered_squares['TR']}")
            self.logger.info(f"   BR={ordered_squares['BR']}, BL={ordered_squares['BL']}")
            
            return ordered_squares
            
        except Exception as e:
            self.logger.error(f"❌ Erro ao detectar quadrados A4: {str(e)}", exc_info=True)
            return None
    
    # =========================================================================
    # ETAPA 3: NORMALIZAR PARA A4
    # =========================================================================
    
    def _normalize_to_a4(self, img: np.ndarray, anchors: Dict) -> np.ndarray:
        """
        Normaliza imagem para A4 lógico FIXO (2480x3508 pixels a 300 DPI)
        
        Args:
            img: Imagem original
            anchors: Dict {"TL": [x,y], "TR": [x,y], "BR": [x,y], "BL": [x,y]}
        
        Returns:
            Imagem normalizada com tamanho FIXO
        """
        # Pontos de origem (4 vértices dos quadrados detectados)
        src_pts = np.float32([
            anchors["TL"],  # Top-Left
            anchors["TR"],  # Top-Right
            anchors["BR"],  # Bottom-Right
            anchors["BL"]   # Bottom-Left
        ])
        
        # Pontos de destino (A4 lógico)
        dst_pts = np.float32([
            [0, 0],                                # TL
            [self.A4_WIDTH_PX, 0],                # TR
            [self.A4_WIDTH_PX, self.A4_HEIGHT_PX], # BR
            [0, self.A4_HEIGHT_PX]                 # BL
        ])
        
        # Calcular matriz de transformação
        matrix = cv2.getPerspectiveTransform(src_pts, dst_pts)
        
        # Aplicar warp
        warped = cv2.warpPerspective(img, matrix, (self.A4_WIDTH_PX, self.A4_HEIGHT_PX))
        
        self.logger.info(f"✅ Imagem normalizada para A4 lógico ({self.A4_WIDTH_PX}x{self.A4_HEIGHT_PX})")
        
        if self.debug:
            self._save_debug_image("03_normalized_a4.jpg", warped)
        
        return warped
    
    # =========================================================================
    # ETAPA 4: ÁREA DO GRID (BASEADA NO TEMPLATE FIXO)
    # =========================================================================
    
    def _get_grid_area_from_template(self, img_a4: np.ndarray) -> Dict:
        """
        Calcula área do grid baseada nas coordenadas FIXAS do template HTML
        
        TEMPLATE HTML (.answer-grid-wrapper):
            - padding: 0.3cm 0.6cm 1.5cm 0.6cm (top right bottom left)
            - height: 13.5cm
            - Posição: após header, instruções, bloco aplicador
        
        .answer-sheet padding: 1.2cm 2cm 2.2cm 2cm
        
        A4 normalizado: 2480x3508px @ 300 DPI
        1cm = 11.811 pixels @ 300 DPI
        
        Returns:
            Dict com x, y, w, h da área do grid
        """
        # Conversão: 1cm = 11.811px @ 300 DPI
        CM_TO_PX = 11.811
        
        # answer-sheet padding
        sheet_padding_top = 1.2 * CM_TO_PX     # 14.17px
        sheet_padding_right = 2.0 * CM_TO_PX   # 23.62px
        sheet_padding_left = 2.0 * CM_TO_PX    # 23.62px
        
        # Cálculo baseado no template:
        # Top: sheet_padding_top + header(~6.4cm) + instruções(~3.8cm) + aplicador(~2.6cm)
        # Aproximadamente: 1.2 + 6.4 + 3.8 + 2.6 = 14cm
        grid_top = 14.0 * CM_TO_PX  # ~165px
        
        # answer-grid-wrapper dimensions
        wrapper_padding_top = 0.3 * CM_TO_PX      # 3.54px
        wrapper_padding_right = 0.6 * CM_TO_PX    # 7.09px
        wrapper_padding_bottom = 1.5 * CM_TO_PX   # 17.72px
        wrapper_padding_left = 0.6 * CM_TO_PX     # 7.09px
        
        wrapper_height = 13.5 * CM_TO_PX  # 159.45px
        
        # Largura do wrapper: A4 width - sheet padding left/right - wrapper padding left/right
        wrapper_width = self.A4_WIDTH_PX - sheet_padding_left - sheet_padding_right - wrapper_padding_left - wrapper_padding_right
        
        # Área útil do grid (dentro do wrapper, excluindo padding)
        grid_x = int(sheet_padding_left + wrapper_padding_left)
        grid_y = int(grid_top + wrapper_padding_top)
        grid_w = int(wrapper_width)
        grid_h = int(wrapper_height - wrapper_padding_top - wrapper_padding_bottom)
        
        self.logger.info(f"✅ Área do grid calculada do template: x={grid_x}, y={grid_y}, w={grid_w}, h={grid_h}")
        
        return {
            "x": grid_x,
            "y": grid_y,
            "w": grid_w,
            "h": grid_h
        }
    
    def _detect_grid_triangles(self, img_a4: np.ndarray, edges: np.ndarray) -> Optional[List[Dict]]:
        """
        Detecta 4 triângulos pretos delimitando o grid
        
        Estratégia robusta:
            - Detecta TODOS os triângulos (pode ser mais de 4)
            - Remove duplicatas (triângulos muito próximos)
            - Seleciona os 4 MAIORES
        
        Returns:
            Lista [TL, TR, BR, BL] ou None se inválido
        """
        # Converter para grayscale se necessário
        if len(img_a4.shape) == 3:
            gray = cv2.cvtColor(img_a4, cv2.COLOR_BGR2GRAY)
        else:
            gray = img_a4.copy()
        
        all_triangles = []
        
        # ========================================
        # ESTRATÉGIA 1: Threshold Otsu padrão
        # ========================================
        self.logger.info("   Tentando threshold Otsu...")
        _, binary1 = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        if self.debug:
            self._save_debug_image("04a_triangles_binary_otsu.jpg", binary1)
        triangles1 = self._extract_triangles_from_binary(binary1)
        self.logger.info(f"   Otsu: {len(triangles1)} triângulos")
        all_triangles.extend(triangles1)
        
        # ========================================
        # ESTRATÉGIA 2: Adaptive threshold
        # ========================================
        self.logger.info("   Tentando adaptive threshold...")
        binary2 = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                       cv2.THRESH_BINARY_INV, 11, 2)
        if self.debug:
            self._save_debug_image("04b_triangles_binary_adaptive.jpg", binary2)
        triangles2 = self._extract_triangles_from_binary(binary2)
        self.logger.info(f"   Adaptive: {len(triangles2)} triângulos")
        all_triangles.extend(triangles2)
        
        # ========================================
        # ESTRATÉGIA 3: Otsu com blur
        # ========================================
        self.logger.info("   Tentando Otsu com blur...")
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        _, binary3 = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        if self.debug:
            self._save_debug_image("04c_triangles_binary_otsu_blur.jpg", binary3)
        triangles3 = self._extract_triangles_from_binary(binary3)
        self.logger.info(f"   Otsu+Blur: {len(triangles3)} triângulos")
        all_triangles.extend(triangles3)
        
        self.logger.info(f"   {len(all_triangles)} triângulos detectados (antes de filtrar duplicatas)")
        
        # Remove duplicatas (triângulos muito próximos)
        candidates = self._remove_duplicate_triangles(all_triangles, min_dist=20)
        
        self.logger.info(f"   {len(candidates)} triângulos após remover duplicatas")
        
        # Validar quantidade mínima
        if len(candidates) < 4:
            self.logger.error(f"❌ REJEIÇÃO: Apenas {len(candidates)} triângulos detectados (necessário pelo menos 4)")
            return None
        
        # Se detectou mais de 4, pegar os 4 MAIORES
        if len(candidates) > 4:
            self.logger.info(f"   Selecionando os 4 maiores de {len(candidates)} triângulos")
            candidates = sorted(candidates, key=lambda t: t["area"], reverse=True)[:4]
        
        # Ordenar: TL, TR, BR, BL
        centers = np.array([(t["cx"], t["cy"]) for t in candidates], dtype="float32")
        soma = centers.sum(axis=1)
        diff = np.diff(centers, axis=1).flatten()
        
        tl_idx = np.argmin(soma)
        br_idx = np.argmax(soma)
        tr_idx = np.argmin(diff)
        bl_idx = np.argmax(diff)
        
        # Garantir índices diferentes
        if len(set([tl_idx, tr_idx, br_idx, bl_idx])) != 4:
            # Fallback: ordenar manualmente
            centers_list = centers.tolist()
            tl = min(centers_list, key=lambda p: p[0] + p[1])
            br = max(centers_list, key=lambda p: p[0] + p[1])
            remaining = [p for p in centers_list if p != tl and p != br]
            tr = min(remaining, key=lambda p: p[0] - p[1])
            bl = [p for p in remaining if p != tr][0]
            
            # Encontrar os triângulos correspondentes
            ordered = []
            for target in [tl, tr, br, bl]:
                for t in candidates:
                    if abs(t["cx"] - target[0]) < 1 and abs(t["cy"] - target[1]) < 1:
                        ordered.append(t)
                        break
        else:
            ordered = [
                candidates[tl_idx],
                candidates[tr_idx],
                candidates[br_idx],
                candidates[bl_idx]
            ]
        
        self.logger.info("✅ 4 triângulos detectados e ordenados")
        
        if self.debug:
            img_debug = img_a4.copy()
            labels = ["TL", "TR", "BR", "BL"]
            for i, (t, label) in enumerate(zip(ordered, labels)):
                cx, cy = t["cx"], t["cy"]
                cv2.circle(img_debug, (cx, cy), 15, (0, 255, 0), -1)
                cv2.putText(img_debug, label, (cx+20, cy), 
                          cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 3)
            self._save_debug_image("04_grid_triangles_detected.jpg", img_debug)
        
        return ordered
    
    def _extract_triangles_from_binary(self, binary: np.ndarray) -> List[Dict]:
        """
        Extrai triângulos de uma imagem binária
        
        Args:
            binary: Imagem binária (threshold aplicado)
        
        Returns:
            Lista de triângulos detectados
        """
        triangles = []
        min_triangle_area = 100  # Área mínima
        max_triangle_area = 800  # Área máxima
        
        # Usar RETR_TREE para pegar todos os contornos
        contours, _ = cv2.findContours(binary, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        
        count_3vertices = 0
        count_area_ok = 0
        
        for cnt in contours:
            # Aproximar contorno
            epsilon = 0.04 * cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, epsilon, True)
            
            # Filtro 1: Exatamente 3 vértices
            if len(approx) != 3:
                continue
            
            count_3vertices += 1
            area = cv2.contourArea(approx)
            
            # Filtro 2: Área dentro do intervalo
            if not (min_triangle_area < area < max_triangle_area):
                continue
            
            count_area_ok += 1
            
            # Calcular centro
            M = cv2.moments(approx)
            if M["m00"] != 0:
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])
                triangles.append({
                    'contour': approx,
                    'cx': cx,
                    'cy': cy,
                    'area': area
                })
        
        self.logger.debug(f"      Contornos totais: {len(contours)}, 3 vértices: {count_3vertices}, área OK: {count_area_ok}, final: {len(triangles)}")
        
        return triangles
    
    def _remove_duplicate_triangles(self, triangles: List[Dict], min_dist: int = 20) -> List[Dict]:
        """
        Remove triângulos duplicados com base na proximidade dos centros
        
        Args:
            triangles: Lista de triângulos detectados
            min_dist: Distância mínima em pixels para considerar triângulos distintos
        
        Returns:
            Lista de triângulos únicos (mantém o de maior área em caso de duplicata)
        """
        if len(triangles) <= 1:
            return triangles
        
        unique = []
        
        for tri in triangles:
            cx, cy = tri['cx'], tri['cy']
            found_duplicate = False
            duplicate_idx = -1
            
            # Verificar se já existe um triângulo muito próximo
            for idx, u in enumerate(unique):
                ux, uy = u['cx'], u['cy']
                # Calcular distância euclidiana
                dist = np.hypot(cx - ux, cy - uy)
                
                if dist < min_dist:
                    # Triângulos muito próximos - manter o de maior área
                    if tri['area'] > u['area']:
                        duplicate_idx = idx
                    found_duplicate = True
                    break
            
            if found_duplicate:
                # Substituir o duplicado pelo novo (se tiver maior área)
                if duplicate_idx >= 0:
                    unique[duplicate_idx] = tri
            else:
                # Triângulo único, adicionar
                unique.append(tri)
        
        return unique
    
    # =========================================================================
    # ETAPA 5: DETECTAR BLOCOS
    # =========================================================================
    
    def _calculate_grid_area(self, triangles: List[Dict]) -> Dict:
        """Calcula área do grid baseado nos 4 triângulos"""
        min_x = min(t["cx"] for t in triangles)
        max_x = max(t["cx"] for t in triangles)
        min_y = min(t["cy"] for t in triangles)
        max_y = max(t["cy"] for t in triangles)
        
        margin = 20
        
        return {
            "x": min_x - margin,
            "y": min_y - margin,
            "w": (max_x - min_x) + (2 * margin),
            "h": (max_y - min_y) + (2 * margin)
        }
    
    def _detect_answer_blocks_in_full_a4(self, img_a4: np.ndarray,
                                         num_blocks_expected: int) -> Optional[List[Dict]]:
        """
        Detecta blocos com bordas pretas grossas em TODA a imagem A4 normalizada
        
        Mais simples e robusto: não precisa calcular área do grid,
        apenas procura retângulos com bordas de 2px em toda a imagem.
        
        Args:
            img_a4: Imagem A4 normalizada (2480x3508)
            num_blocks_expected: Número de blocos esperado do JSON
        
        Returns:
            Lista de blocos detectados ou None
        """
        h, w = img_a4.shape[:2]
        
        self.logger.info(f"   Procurando blocos na imagem completa: {w}x{h}px")
        
        # Converter para grayscale
        if len(img_a4.shape) == 3:
            gray = cv2.cvtColor(img_a4, cv2.COLOR_BGR2GRAY)
        else:
            gray = img_a4.copy()
        
        # Aplicar blur para suavizar
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        
        # Threshold binário invertido para destacar bordas pretas
        _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        
        if self.debug:
            self._save_debug_image("05a_blocks_threshold.jpg", thresh)
        
        # Dilatação mínima para conectar bordas quebradas
        kernel_small = np.ones((3, 3), np.uint8)
        dilated = cv2.dilate(thresh, kernel_small, iterations=1)
        
        if self.debug:
            self._save_debug_image("05b_blocks_dilated.jpg", dilated)
        
        # Usar RETR_TREE para hierarquia de contornos
        contours, hierarchy = cv2.findContours(dilated.copy(), cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        
        self.logger.info(f"   {len(contours)} contornos detectados")
        
        # Filtrar contornos que são blocos
        # Cada bloco deve ter uma área significativa (pelo menos 3% da imagem)
        # e uma largura razoável (15% a 30% da largura total para 4 blocos lado a lado)
        img_area = w * h
        min_block_area = img_area * 0.02  # 2% da imagem (mais flexível)
        max_block_area = img_area * 0.15  # 15% da imagem (bloco individual)
        min_block_width = w * 0.10  # Pelo menos 10% da largura
        max_block_width = w * 0.30  # No máximo 30% da largura
        min_block_height = h * 0.10  # Pelo menos 10% da altura
        
        self.logger.info(f"   Área: {min_block_area:.0f} - {max_block_area:.0f}px²")
        self.logger.info(f"   Largura: {min_block_width:.0f} - {max_block_width:.0f}px")
        self.logger.info(f"   Altura mínima: {min_block_height:.0f}px")
        
        candidates = []
        
        # Filtrar apenas contornos EXTERNOS usando hierarquia
        for idx, cnt in enumerate(contours):
            # Verificar se é contorno externo (sem pai)
            if hierarchy is not None and len(hierarchy) > 0:
                if hierarchy[0][idx][3] != -1:  # Tem pai = contorno interno, pular
                    continue
            
            area = cv2.contourArea(cnt)
            
            # Filtrar por área
            if area < min_block_area or area > max_block_area:
                continue
            
            # Aproximar contorno
            peri = cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
            
            # Procurar por retângulos (4 ou mais vértices)
            if len(approx) < 4:
                continue
            
            bx, by, bw, bh = cv2.boundingRect(approx)
            
            # Filtrar por largura
            if bw < min_block_width or bw > max_block_width:
                continue
            
            # Filtrar por altura
            if bh < min_block_height:
                continue
            
            aspect_ratio = bw / float(bh) if bh > 0 else 0
            
            # Verificar se é um retângulo razoável
            # Aspect ratio entre 0.3 e 2.0 (mais flexível)
            if not (0.3 < aspect_ratio < 2.0):
                continue
            
            candidates.append({
                "contour": approx,
                "x": bx,
                "y": by,
                "w": bw,
                "h": bh,
                "area": area,
                "aspect_ratio": aspect_ratio
            })
            
            self.logger.debug(f"   Bloco: x={bx}, y={by}, w={bw}, h={bh}, area={area:.0f}, aspect={aspect_ratio:.2f}")
        
        # Ordenar por X (esquerda para direita) - blocos lado a lado
        candidates.sort(key=lambda b: b["x"])
        
        self.logger.info(f"   {len(candidates)} blocos candidatos após filtros")
        
        # VALIDAÇÃO
        if len(candidates) != num_blocks_expected:
            self.logger.error(
                f"❌ REJEIÇÃO: Esperava {num_blocks_expected} blocos (JSON), "
                f"encontrou {len(candidates)}"
            )
            
            # Debug: mostrar por que falhou
            if len(candidates) == 0:
                self.logger.error("   Nenhum bloco detectado! Possíveis causas:")
                self.logger.error("   - Bordas dos blocos muito finas ou ausentes")
                self.logger.error("   - Área ou largura fora dos limites esperados")
                self.logger.error("   - Verifique as imagens de debug (05a, 05b)")
            elif len(candidates) > num_blocks_expected:
                self.logger.error(f"   Detectou {len(candidates) - num_blocks_expected} blocos a mais")
                self.logger.error("   Possível duplicação ou detecção de bordas internas")
            
            return None
        
        self.logger.info(f"✅ {num_blocks_expected} blocos detectados e ordenados")
        
        if self.debug:
            img_debug = img_a4.copy()
            if len(img_debug.shape) == 2:
                img_debug = cv2.cvtColor(img_debug, cv2.COLOR_GRAY2BGR)
            for i, block in enumerate(candidates):
                bx, by, bw, bh = block["x"], block["y"], block["w"], block["h"]
                cv2.rectangle(img_debug, (bx, by), (bx+bw, by+bh), (0, 255, 0), 3)
                cv2.putText(img_debug, f"B{i+1}", (bx+10, by+30),
                          cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)
            self._save_debug_image("05_blocks_detected.jpg", img_debug)
        
        return candidates
    
    def _detect_answer_blocks(self, img_a4: np.ndarray, grid_area: Dict,
                              num_blocks_expected: int) -> Optional[List[Dict]]:
        """
        Detecta blocos com bordas pretas grossas
        
        Implementação robusta baseada no código testado:
            - Usa área RELATIVA (não fixa)
            - Filtra apenas contornos EXTERNOS (usando hierarquia)
            - Aceita 4 ou mais vértices (não exatamente 4)
            - Aspect ratio flexível (0.3 a 3.0)
        
        VALIDAÇÃO:
            - Número de blocos DEVE ser == num_blocks_expected
            - Se diferente → REJEITAR imagem
        """
        # Crop área do grid
        x, y, w, h = grid_area["x"], grid_area["y"], grid_area["w"], grid_area["h"]
        grid_roi = img_a4[y:y+h, x:x+w]
        
        self.logger.info(f"   Área do grid: {w}x{h}px")
        
        # Converter para grayscale
        if len(grid_roi.shape) == 3:
            gray = cv2.cvtColor(grid_roi, cv2.COLOR_BGR2GRAY)
        else:
            gray = grid_roi.copy()
        
        # Aplicar blur para suavizar
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        
        # Threshold binário invertido para destacar bordas pretas
        _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        
        if self.debug:
            self._save_debug_image("05a_blocks_threshold.jpg", thresh)
        
        # Dilatação mínima para conectar bordas quebradas SEM conectar blocos adjacentes
        kernel_small = np.ones((3, 3), np.uint8)
        dilated = cv2.dilate(thresh, kernel_small, iterations=1)
        
        if self.debug:
            self._save_debug_image("05b_blocks_dilated.jpg", dilated)
        
        # ✅ CORREÇÃO: Usar RETR_TREE para hierarquia de contornos
        contours, hierarchy = cv2.findContours(dilated.copy(), cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        
        self.logger.info(f"   {len(contours)} contornos detectados")
        
        # Filtrar contornos que são blocos individuais
        # Cada bloco deve ter ~20-25% da largura total (4 blocos lado a lado)
        min_block_area = (w * h) * 0.03  # 3% da área (mais flexível)
        max_block_area = (w * h) * 0.30  # 30% da área (bloco individual)
        min_block_width = w * 0.15  # Cada bloco tem pelo menos 15% da largura
        max_block_width = w * 0.30  # Cada bloco tem no máximo 30% da largura
        
        self.logger.info(f"   Área: {min_block_area:.0f} - {max_block_area:.0f}px²")
        self.logger.info(f"   Largura: {min_block_width:.0f} - {max_block_width:.0f}px")
        
        candidates = []
        
        # ✅ CORREÇÃO CRÍTICA: Filtrar apenas contornos EXTERNOS usando hierarquia
        for idx, cnt in enumerate(contours):
            # Verificar se é contorno externo (sem pai)
            # hierarchy estrutura: [next, previous, first_child, parent]
            if hierarchy is not None and len(hierarchy) > 0:
                if hierarchy[0][idx][3] != -1:  # Tem pai = contorno interno, pular
                    continue
            
            area = cv2.contourArea(cnt)
            
            # Filtrar por área
            if area < min_block_area or area > max_block_area:
                continue
            
            # Aproximar contorno
            peri = cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
            
            # Procurar por retângulos (4 ou mais vértices - mais flexível)
            if len(approx) < 4:
                continue
            
            bx, by, bw, bh = cv2.boundingRect(approx)
            
            # Filtrar por largura
            if bw < min_block_width or bw > max_block_width:
                continue
            
            aspect_ratio = bw / float(bh) if bh > 0 else 0
            
            # Verificar se é um retângulo razoável (não muito alongado)
            # Aspect ratio entre 0.3 e 3.0 (mais flexível)
            if not (0.3 < aspect_ratio < 3.0):
                continue
            
            candidates.append({
                "contour": approx,
                "x": x + bx,  # Coordenadas no A4 completo
                "y": y + by,
                "w": bw,
                "h": bh,
                "area": area,
                "aspect_ratio": aspect_ratio
            })
            
            self.logger.debug(f"   Bloco externo: x={bx}, y={by}, w={bw}, h={bh}, area={area:.0f}, aspect={aspect_ratio:.2f}")
        
        # Ordenar por X (esquerda para direita) - blocos lado a lado  
        candidates.sort(key=lambda b: b["x"])
        
        self.logger.info(f"   {len(candidates)} blocos candidatos após filtros")
        
        # VALIDAÇÃO RIGOROSA
        if len(candidates) != num_blocks_expected:
            self.logger.error(
                f"❌ REJEIÇÃO: Esperava {num_blocks_expected} blocos (JSON), "
                f"encontrou {len(candidates)}"
            )
            
            # Debug: mostrar por que falhou
            if len(candidates) == 0:
                self.logger.error("   Nenhum bloco detectado! Possíveis causas:")
                self.logger.error("   - Bordas dos blocos muito finas ou ausentes")
                self.logger.error("   - Área ou largura fora dos limites esperados")
                self.logger.error("   - Verifique as imagens de debug (05a, 05b)")
            
            return None
        
        self.logger.info(f"✅ {num_blocks_expected} blocos detectados e ordenados")
        
        if self.debug:
            img_debug = grid_roi.copy()
            if len(img_debug.shape) == 2:
                img_debug = cv2.cvtColor(img_debug, cv2.COLOR_GRAY2BGR)
            for i, block in enumerate(candidates):
                bx, by = block["x"] - x, block["y"] - y  # Converter para coordenadas do ROI
                bw, bh = block["w"], block["h"]
                cv2.rectangle(img_debug, (bx, by), (bx+bw, by+bh), (0, 255, 0), 3)
                cv2.putText(img_debug, f"B{i+1}", (bx+10, by+30),
                          cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)
            self._save_debug_image("05_blocks_detected.jpg", img_debug)
        
        return candidates
    
    # =========================================================================
    # ETAPA 6: MAPEAR JSON → GRID (🔴 CRÍTICA)
    # =========================================================================
    
    def _map_topology_to_grid(self, block_roi: np.ndarray, block_config: Dict) -> Optional[Dict]:
        """
        🔴 FUNÇÃO MAIS IMPORTANTE DO SISTEMA
        
        Mapeia topologia do JSON para um grid matemático
        
        A IMAGEM NÃO DEFINE NADA
        O JSON DEFINE TUDO
        
        Args:
            block_roi: ROI do bloco (apenas para dimensões)
            block_config: {
                "block_id": 1,
                "questions": [
                    {"q": 1, "alternatives": ["A","B","C"]},
                    {"q": 2, "alternatives": ["A","B","C","D"]},
                    ...
                ]
            }
        
        Returns:
            Grid completo com posições calculadas
        """
        block_height, block_width = block_roi.shape[:2]
        
        # Obter questões do JSON
        questions = block_config.get("questions", [])
        num_rows = len(questions)
        
        # 🔍 DEBUG: Mostrar topologia recebida
        block_id = block_config.get("block_id", "?")
        self.logger.info(f"🔍 Bloco {block_id} - Topologia JSON:")
        for q in questions[:3]:  # Mostrar primeiras 3 questões
            self.logger.info(f"   Q{q.get('q')}: {q.get('alternatives')}")
        if len(questions) > 3:
            self.logger.info(f"   ... (total: {len(questions)} questões)")
        
        if num_rows == 0:
            self.logger.error("❌ Nenhuma questão no bloco")
            return None
        
        # ⚠️ VALORES FIXOS DO CSS - NÃO CALCULAR PELA IMAGEM!
        row_height = self.ROW_HEIGHT_PX  # FIXO: 51.97px (0.44cm a 300 DPI)
        
        # 🔍 DEBUG: Logs detalhados das dimensões
        self.logger.info(f"📐 Dimensões do bloco ROI: {block_width}x{block_height}px")
        self.logger.info(f"📐 row_height (CALIBRADO): {row_height:.2f}px")
        self.logger.info(f"📐 Offsets (CALIBRADOS): X={self.BLOCK_OFFSET_X}px, Y={self.BLOCK_OFFSET_Y}px")
        self.logger.info(f"📐 Bolha radius: {self.BUBBLE_RADIUS_PX}px, spacing: {self.BUBBLE_SPACING_PX}px (CALIBRADOS)")
        
        grid_map = {
            "num_rows": num_rows,
            "row_height": row_height,
            "block_width": block_width,
            "block_height": block_height,
            "questions": []
        }
        
        for row_idx, question in enumerate(questions):
            q_num = question.get("q")
            alternatives = question.get("alternatives", [])
            num_cols = len(alternatives)
            
            if num_cols == 0:
                self.logger.warning(f"⚠️ Questão {q_num} sem alternativas, pulando")
                continue
            
            # ⚠️ FÓRMULA CSS: cy = OFFSET_Y + (row_height * row_idx) + (row_height / 2)
            # Centro vertical da linha (meio da altura da linha)
            cy = self.BLOCK_OFFSET_Y + (row_height * row_idx) + (row_height / 2)
            
            # 🔍 DEBUG: Log detalhado da primeira questão
            if row_idx == 0:
                self.logger.info(f"📐 Primeira questão (Q{q_num}): {num_cols} alternativas")
                self.logger.info(f"   cy: {cy:.2f}px (offset={self.BLOCK_OFFSET_Y} + row={row_idx} * {row_height:.2f})")
            
            question_map = {
                "q_num": q_num,
                "row_idx": row_idx,
                "cy": cy,
                "num_cols": num_cols,
                "alternatives": []
            }
            
            for col_idx, alt_letter in enumerate(alternatives):
                # ⚠️ FÓRMULA CALIBRADA: cx = OFFSET_X + (col_idx * BUBBLE_SPACING) + (bubble_width / 2)
                # Centro horizontal de cada bolha (espaçamento calibrado empiricamente)
                cx = self.BLOCK_OFFSET_X + (col_idx * self.BUBBLE_SPACING_PX) + (self.BUBBLE_WIDTH_PX / 2)
                
                # 🔍 DEBUG: Log da primeira alternativa da primeira questão
                if row_idx == 0 and col_idx == 0:
                    self.logger.info(f"   Primeira alternativa ({alt_letter}):")
                    self.logger.info(f"   cx: {cx:.2f}px (offset={self.BLOCK_OFFSET_X} + col={col_idx} * spacing={self.BUBBLE_SPACING_PX})")
                
                question_map["alternatives"].append({
                    "letter": alt_letter,
                    "col_idx": col_idx,
                    "cx": cx
                })
            
            grid_map["questions"].append(question_map)
        
        self.logger.info(
            f"✅ Grid mapeado: {num_rows} questões, "
            f"larguras de coluna variáveis"
        )
        
        if self.debug:
            self.logger.debug(f"   Row height (CSS FIXO): {row_height:.2f}px")
            bubble_spacing = self.BUBBLE_WIDTH_PX + self.BUBBLE_GAP_PX
            for q in grid_map["questions"][:3]:
                self.logger.debug(
                    f"   Q{q['q_num']}: {q['num_cols']} alternativas, "
                    f"espaçamento={bubble_spacing}px ({self.BUBBLE_WIDTH_PX}px + {self.BUBBLE_GAP_PX}px gap)"
                )
        
        # ✅ VALIDAÇÃO: Verificar se cálculo está consistente com CSS
        if len(grid_map["questions"]) >= 2:
            q1_cy = grid_map["questions"][0]["cy"]
            q2_cy = grid_map["questions"][1]["cy"]
            calculado_row_height = q2_cy - q1_cy
            esperado_row_height = self.ROW_HEIGHT_PX  # CSS FIXO
            
            diff = abs(calculado_row_height - esperado_row_height)
            if diff > 0.1:  # Margem de erro 0.1px (float)
                self.logger.warning(
                    f"⚠️ Espaçamento vertical inconsistente! "
                    f"CSS esperado: {esperado_row_height:.2f}px, "
                    f"Calculado: {calculado_row_height:.2f}px"
                )
            else:
                self.logger.debug(f"✓ Espaçamento vertical OK (CSS: {esperado_row_height:.2f}px)")
        
        return grid_map
    
    # =========================================================================
    # ETAPA 7: CALCULAR CENTROS DAS BOLHAS
    # =========================================================================
    
    def _calculate_bubble_centers(self, grid_map: Dict) -> List[Dict]:
        """
        Calcula centros e raios de TODAS as bolhas matematicamente
        
        Returns:
            Lista de bolhas com cx, cy, r
        """
        # ⚠️ RAIO FIXO DO CSS - NÃO CALCULAR DINAMICAMENTE!
        # .bubble { width: 15px; height: 15px; }
        bubble_radius = int(self.BUBBLE_RADIUS_PX)
        
        self.logger.info(f"🔍 Raio das bolhas (CSS FIXO): {bubble_radius}px")
        
        bubbles = []
        
        for question in grid_map["questions"]:
            q_num = question["q_num"]
            cy = int(question["cy"])
            
            for alt in question["alternatives"]:
                cx = int(alt["cx"])
                letter = alt["letter"]
                
                bubbles.append({
                    "q_num": q_num,
                    "alternative": letter,
                    "cx": cx,
                    "cy": cy,
                    "r": bubble_radius
                })
        
        self.logger.info(f"✅ {len(bubbles)} centros de bolhas calculados")
        return bubbles
    
    # =========================================================================
    # ETAPA 8: DETECTAR MARCAÇÕES
    # =========================================================================
    
    def _detect_marked_bubbles(self, block_roi: np.ndarray, bubbles: List[Dict],
                               block_id: int = None) -> Dict[int, str]:
        """
        Detecta quais bolhas estão marcadas
        
        Para cada bolha:
            1. Criar máscara circular
            2. Contar pixels escuros
            3. Calcular fill_ratio
        
        Para cada questão:
            - Se 1 alternativa > THRESHOLD → marcada
            - Se 0 alternativas > THRESHOLD → em branco
            - Se 2+ alternativas > THRESHOLD → INVÁLIDA
        
        Returns:
            {1: "C", 2: None, 3: "INVALID", ...}
        """
        # Pré-processar bloco
        gray = cv2.cvtColor(block_roi, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        
        # Threshold: pixels escuros (marcações) ficam BRANCOS (255)
        # ⚠️ Usar BINARY_INV para que marcações pretas virem brancas
        _, thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        
        # 🔍 DEBUG: Salvar threshold e centros das bolhas
        if self.debug and block_id:
            # Salvar threshold
            self._save_debug_image(f"06_block{block_id}_threshold.jpg", thresh)
            
            # Criar imagem mostrando centros das bolhas E grid de referência
            debug_img = block_roi.copy()
            h, w = debug_img.shape[:2]
            
            # Desenhar grid de linhas horizontais (questões) usando ROW_HEIGHT CSS FIXO
            # Agrupar para contar questões
            temp_questions = defaultdict(list)
            for b in bubbles:
                temp_questions[b["q_num"]].append(b)
            num_questions = len(temp_questions)
            
            if num_questions > 0:
                # ⚠️ Usar ROW_HEIGHT_PX fixo do CSS!
                for i in range(num_questions + 1):
                    y = int(self.BLOCK_OFFSET_Y + (self.ROW_HEIGHT_PX * i))
                    if 0 <= y < h:
                        cv2.line(debug_img, (0, y), (w, y), (255, 255, 0), 1)  # Linhas amarelas
            
            # Desenhar bolhas calculadas
            for bubble in bubbles:
                cx, cy, r = bubble["cx"], bubble["cy"], bubble["r"]
                letter = bubble["alternative"]
                q_num = bubble["q_num"]
                
                # Desenhar círculo e letra
                cv2.circle(debug_img, (cx, cy), r, (0, 255, 0), 2)
                cv2.circle(debug_img, (cx, cy), 3, (0, 0, 255), -1)  # Centro
                cv2.putText(debug_img, f"Q{q_num}{letter}", (cx-15, cy-r-5),
                          cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 0, 0), 1)
            
            # Adicionar informação dos valores CSS na imagem
            cv2.putText(debug_img, f"CSS: row={self.ROW_HEIGHT_PX:.1f}px, bubble={self.BUBBLE_WIDTH_PX}px+{self.BUBBLE_GAP_PX}px", 
                       (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1)
            cv2.putText(debug_img, f"Offset: X={self.BLOCK_OFFSET_X}px, Y={self.BLOCK_OFFSET_Y}px", 
                       (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1)
            
            self._save_debug_image(f"06_block{block_id}_bubbles_mapped.jpg", debug_img)
        
        # Agrupar bolhas por questão
        questions_dict = defaultdict(list)
        for bubble in bubbles:
            q_num = bubble["q_num"]
            questions_dict[q_num].append(bubble)
        
        answers = {}
        all_fill_ratios = []  # Para log resumido
        
        for q_num, q_bubbles in questions_dict.items():
            fill_ratios = []
            
            for bubble in q_bubbles:
                cx, cy, r = bubble["cx"], bubble["cy"], bubble["r"]
                letter = bubble["alternative"]
                
                # Criar máscara circular
                mask = np.zeros_like(thresh)
                cv2.circle(mask, (cx, cy), r, 255, -1)
                
                # Aplicar máscara ao threshold
                masked = cv2.bitwise_and(thresh, mask)
                
                # 🔍 DEBUG: Salvar máscara das primeiras bolhas
                if self.debug and block_id and q_num == 12:  # Questão 12 para debug
                    mask_debug = np.zeros((thresh.shape[0], thresh.shape[1], 3), dtype=np.uint8)
                    mask_debug[:, :, 0] = thresh  # Canal azul = threshold
                    mask_debug[:, :, 1] = mask    # Canal verde = máscara
                    mask_debug[:, :, 2] = masked  # Canal vermelho = resultado
                    self._save_debug_image(f"07_block{block_id}_Q{q_num}{letter}_mask.jpg", mask_debug)
                
                # Contar pixels
                black_pixels = cv2.countNonZero(masked)
                total_pixels = cv2.countNonZero(mask)
                
                # Calcular taxa de preenchimento
                fill_ratio = black_pixels / total_pixels if total_pixels > 0 else 0
                
                fill_ratios.append({
                    "letter": letter,
                    "fill_ratio": fill_ratio
                })
                
                all_fill_ratios.append(fill_ratio)
                
                # 🔍 DEBUG DETALHADO: Logar apenas em modo debug
                if self.debug and q_num <= 13:  # Primeiras questões para debug
                    self.logger.info(
                        f"   Q{q_num}{letter}: cx={cx}, cy={cy}, r={r} → "
                        f"pixels_brancos={black_pixels}/{total_pixels} → "
                        f"fill_ratio={fill_ratio:.3f} "
                        f"({'✅MARCADA' if fill_ratio > self.FILL_THRESHOLD else '⚪vazia'})"
                    )
            
            # Ordenar por fill_ratio (maior primeiro)
            fill_ratios.sort(key=lambda x: x["fill_ratio"], reverse=True)
            
            # Contar quantas estão acima do threshold
            marked_count = sum(1 for fr in fill_ratios if fr["fill_ratio"] > self.FILL_THRESHOLD)
            
            if marked_count == 0:
                # Nenhuma marcada → em branco
                answers[q_num] = None
                if self.debug:
                    self.logger.debug(f"   Q{q_num}: EM BRANCO")
            
            elif marked_count == 1:
                # Exatamente uma marcada
                answers[q_num] = fill_ratios[0]["letter"]
                if self.debug:
                    self.logger.debug(f"   Q{q_num}: MARCADO {fill_ratios[0]['letter']}")
            
            else:
                # Múltiplas marcadas → inválida
                answers[q_num] = "INVALID"
                marked_letters = [fr["letter"] for fr in fill_ratios if fr["fill_ratio"] > self.FILL_THRESHOLD]
                if self.debug:
                    self.logger.warning(f"   Q{q_num}: INVÁLIDA ({marked_letters})")
        
        self.logger.info(
            f"✅ {len(answers)} respostas detectadas "
            f"({sum(1 for a in answers.values() if a and a != 'INVALID')} marcadas, "
            f"{sum(1 for a in answers.values() if a is None)} em branco, "
            f"{sum(1 for a in answers.values() if a == 'INVALID')} inválidas)"
        )
        
        # 🔍 DEBUG: Estatísticas dos fill_ratios
        if all_fill_ratios:
            arr = np.array(all_fill_ratios)
            self.logger.info(
                f"📊 Fill ratios: min={arr.min():.3f}, max={arr.max():.3f}, "
                f"mean={arr.mean():.3f}, median={np.median(arr):.3f}"
            )
            self.logger.info(f"🎯 Threshold atual: {self.FILL_THRESHOLD}")
            above_threshold = sum(1 for fr in all_fill_ratios if fr > self.FILL_THRESHOLD)
            self.logger.info(f"   {above_threshold}/{len(all_fill_ratios)} bolhas acima do threshold")
        
        return answers
    
    # =========================================================================
    # ETAPA 9: CONSTRUIR RESULTADO
    # =========================================================================
    
    def _build_result(self, answers: Dict[int, str], gabarito: Dict[int, str]) -> Dict:
        """
        Constrói resultado final comparando com gabarito
        
        Returns:
            Resultado completo com estatísticas
        """
        total_questions = len(gabarito)
        correct = 0
        wrong = 0
        blank = 0
        invalid = 0
        
        detailed_answers = []
        
        for q_num in sorted(gabarito.keys()):
            marked = answers.get(q_num)
            correct_answer = gabarito[q_num]
            
            if marked == "INVALID":
                invalid += 1
                is_correct = False
            elif marked is None:
                blank += 1
                is_correct = False
            elif marked == correct_answer:
                correct += 1
                is_correct = True
            else:
                wrong += 1
                is_correct = False
            
            detailed_answers.append({
                "question": q_num,
                "marked": marked,
                "correct": correct_answer,
                "is_correct": is_correct
            })
        
        score = (correct / total_questions * 100) if total_questions > 0 else 0
        
        # Converter chaves para strings para serialização JSON
        student_answers_str = {str(q): answers.get(q) for q in sorted(gabarito.keys())}
        answer_key_str = {str(q): gabarito[q] for q in sorted(gabarito.keys())}
        
        return {
            "success": True,
            "total_questions": total_questions,
            "correct_answers": correct,  # Contador de corretas
            "wrong_answers": wrong,
            "blank_answers": blank,
            "invalid_answers": invalid,
            "score": round(score, 2),
            "detailed_answers": detailed_answers,  # Lista detalhada: [{question, marked, correct, is_correct}, ...]
            "student_answers": student_answers_str,  # Dicionário: {"1": "A", "2": "B", ...}
            "answer_key": answer_key_str  # Gabarito oficial: {"1": "A", "2": "C", ...}
        }
    
    # =========================================================================
    # FORMATAÇÃO DE ERROS AMIGÁVEIS
    # =========================================================================
    
    def _format_user_friendly_error(self, technical_error: str, context: Dict = None) -> str:
        """
        Converte mensagens de erro técnicas em mensagens amigáveis para o usuário final
        
        Args:
            technical_error: Mensagem de erro técnica original
            context: Dicionário com contexto adicional (ex: num_blocks_expected, num_blocks_found)
        
        Returns:
            Mensagem de erro amigável
        """
        if context is None:
            context = {}
        
        # Verificar primeiro se é erro de quantidade de blocos (precisa de contexto)
        blocks_pattern = r"Esperava\s+(\d+)\s+blocos.*encontrou\s+(\d+)|Esperava\s+(\d+)\s+blocos.*encontrou.*diferente"
        blocks_match = re.search(blocks_pattern, technical_error, re.IGNORECASE)
        if blocks_match:
            # Se não temos contexto, tentar extrair dos números na mensagem
            if not context or 'num_blocks_expected' not in context:
                try:
                    expected = int(blocks_match.group(1)) if blocks_match.group(1) else int(blocks_match.group(3))
                    found = context.get('num_blocks_found', 0)
                    context = {
                        'num_blocks_expected': expected,
                        'num_blocks_found': found
                    }
                except:
                    pass
            return self._format_blocks_quantity_error(context)
        
        # Mapeamento de padrões técnicos para mensagens amigáveis
        error_patterns = [
            # Detecção de elementos
            (r"âncoras\s+A4|Âncoras\s+A4|quadrados\s+A4", "Não foi possível identificar os marcadores nos cantos da folha. Verifique se a imagem está completa e os cantos estão visíveis."),
            (r"triângulos", "Não foi possível identificar os marcadores de alinhamento. Certifique-se de que a imagem está nítida e os triângulos estão visíveis."),
            (r"blocos.*detectado|Nenhum bloco", "Não foi possível identificar as áreas de resposta. Verifique se a imagem está bem iluminada e as bordas dos blocos estão visíveis."),
            (r"QR\s+Code.*não\s+detectado|QR\s+Code.*inválido|QR\s+Code.*não\s+encontrado", "Não foi possível ler o código QR do cartão. Verifique se o código está visível, não está danificado e a imagem está nítida."),
            
            # Processamento
            (r"decodificar\s+imagem|Falha ao carregar imagem", "Não foi possível processar a imagem. Verifique se o arquivo está em um formato válido (JPG, PNG)."),
            (r"normalizar.*A4", "Não foi possível ajustar a imagem. Tente escanear novamente com a folha bem posicionada e os cantos visíveis."),
            (r"crop.*área", "Não foi possível identificar a área de respostas. Verifique se a imagem está completa e bem alinhada."),
            
            # Dados
            (r"Aluno.*não\s+encontrado", "Aluno não encontrado no sistema. Verifique se o código QR está correto."),
            (r"Gabarito.*não\s+encontrado", "Gabarito não encontrado. Verifique se a prova está cadastrada corretamente."),
            (r"Prova.*não\s+encontrada", "Prova não encontrada. Verifique se a prova está cadastrada corretamente."),
            (r"topology_json.*obrigatório|gabarito.*obrigatório", "Configuração da prova incompleta. Entre em contato com o suporte técnico."),
        ]
        
        # Buscar padrão correspondente
        for pattern, friendly_msg in error_patterns:
            if re.search(pattern, technical_error, re.IGNORECASE):
                return friendly_msg
        
        # Se não encontrou padrão específico, retornar mensagem genérica
        return "Não foi possível processar a imagem. Por favor, verifique se a imagem está nítida e completa, e tente novamente."
    
    def _format_blocks_quantity_error(self, context: Dict) -> str:
        """Formata erro específico de quantidade de blocos"""
        expected = context.get('num_blocks_expected', None)
        found = context.get('num_blocks_found', 0)
        
        if expected is None:
            return "A quantidade de blocos de resposta não corresponde ao esperado. Verifique se a imagem está completa e todas as áreas de resposta estão visíveis."
        
        if found == 0:
            return "Nenhuma área de resposta foi identificada. Verifique se a imagem está completa e as bordas dos blocos estão visíveis."
        elif found < expected:
            return f"Foram identificadas apenas {found} área(s) de resposta, mas esperava-se {expected}. Verifique se a imagem está completa e todas as áreas estão visíveis."
        else:
            return f"Foram identificadas {found} áreas de resposta, mas esperava-se {expected}. Verifique se há elementos extras na imagem que possam estar sendo confundidos com áreas de resposta."
    
    # =========================================================================
    # PIPELINE PRINCIPAL
    # =========================================================================
    
    def _execute_omr_pipeline(self, img: np.ndarray, topology_json: Dict) -> Dict[str, Any]:
        """
        Pipeline de 9 etapas - Execução sequencial
        
        Returns:
            {"success": True, "answers": {...}} ou
            {"success": False, "error": "..."}
        """
        # ETAPA 1: Pré-processamento
        self.logger.info("🔄 Etapa 1: Pré-processamento")
        processed = self._preprocess_image(img)
        edges = processed["edges"]
        
        # ETAPA 2: Detectar âncoras A4
        self.logger.info("🔄 Etapa 2: Detectar âncoras A4")
        anchors = self._detect_a4_anchors(img, edges)
        if anchors is None:
            error_msg = self._format_user_friendly_error("Âncoras A4 não detectadas")
            return {"success": False, "error": error_msg}
        
        # ETAPA 3: Normalizar para A4 lógico
        self.logger.info("🔄 Etapa 3: Normalizar para A4")
        img_a4 = self._normalize_to_a4(img, anchors)
        
        # ETAPA 4-5: Detectar blocos diretamente na imagem A4 normalizada
        # Os blocos têm bordas pretas de 2px, então são facilmente detectáveis
        self.logger.info("🔄 Etapa 4-5: Detectar blocos na imagem A4 completa")
        num_blocks_expected = topology_json.get("num_blocks", 4)
        blocks = self._detect_answer_blocks_in_full_a4(img_a4, num_blocks_expected)
        if blocks is None:
            context = {
                'num_blocks_expected': num_blocks_expected,
                'num_blocks_found': 0
            }
            error_msg = self._format_user_friendly_error(
                f"Esperava {num_blocks_expected} blocos, encontrou quantidade diferente",
                context
            )
            return {
                "success": False,
                "error": error_msg
            }
        
        # ETAPAS 6-9: Processar cada bloco
        self.logger.info("🔄 Etapas 6-9: Processar blocos")
        all_answers = {}
        
        blocks_topology = topology_json.get("topology", {}).get("blocks", [])
        
        for idx, block in enumerate(blocks):
            block_num = idx + 1
            self.logger.info(f"  📦 Processando bloco {block_num}")
            
            # Extrair ROI do bloco
            x, y, w, h = block["x"], block["y"], block["w"], block["h"]
            block_roi = img_a4[y:y+h, x:x+w]
            
            # Obter configuração do bloco do JSON
            if block_num - 1 >= len(blocks_topology):
                self.logger.error(f"❌ Bloco {block_num} não encontrado no JSON")
                continue
            
            block_config = blocks_topology[block_num - 1]
            
            # ETAPA 6: Mapear topologia → grid
            grid_map = self._map_topology_to_grid(block_roi, block_config)
            if not grid_map:
                continue
            
            # ETAPA 7: Calcular centros das bolhas
            bubbles = self._calculate_bubble_centers(grid_map)
            
            # ETAPA 8: Detectar marcações
            block_id = block_config.get('block_id', block_num)
            block_answers = self._detect_marked_bubbles(block_roi, bubbles, block_id)
            
            # Adicionar ao resultado geral
            all_answers.update(block_answers)
        
        # ETAPA 9: Construir resultado (feito externamente)
        return {
            "success": True,
            "answers": all_answers
        }
    
    # =========================================================================
    # FUNÇÃO PRINCIPAL PÚBLICA
    # =========================================================================
    
    def corrigir_cartao_resposta(self, image_path: str = None, image_data: bytes = None,
                                 topology_json: Dict = None, gabarito: Dict[int, str] = None,
                                 auto_detect_qr: bool = True) -> Dict[str, Any]:
        """
        Função principal - Corrige um cartão-resposta completo
        
        Args:
            image_path: Caminho da imagem (opcional se image_data for fornecido)
            image_data: Bytes da imagem (opcional se image_path for fornecido)
            topology_json: JSON com estrutura do cartão (opcional se auto_detect_qr=True)
            gabarito: Respostas corretas {1: "A", 2: "C", ...} (opcional se auto_detect_qr=True)
            auto_detect_qr: Se True, detecta QR code e carrega gabarito automaticamente
        
        Returns:
            Resultado completo com estatísticas
        """
        try:
            if self.debug:
                import os
                if not os.path.exists(self.debug_dir):
                    os.makedirs(self.debug_dir)
                self.debug_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                self.logger.info(f"🐛 Debug: run_id={self.debug_timestamp}")

            # Carregar imagem
            if image_path:
                self.logger.info(f"🎯 Iniciando correção: {image_path}")
                img = cv2.imread(image_path)
            elif image_data:
                self.logger.info(f"🎯 Iniciando correção de bytes")
                import numpy as np
                nparr = np.frombuffer(image_data, np.uint8)
                img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            else:
                error_msg = self._format_user_friendly_error("Nenhuma imagem fornecida")
                return {"success": False, "error": error_msg}
            
            if img is None:
                error_msg = self._format_user_friendly_error("Falha ao carregar imagem")
                return {"success": False, "error": error_msg}
            
            # Salvar imagem de entrada para debug
            if self.debug:
                self._save_debug_image("00_input_image.jpg", img)
            
            # Se auto_detect_qr, detectar QR code e carregar dados
            if auto_detect_qr:
                qr_data = self._detectar_qr_code(img)
                if not qr_data:
                    error_msg = self._format_user_friendly_error("QR Code não encontrado no cartão")
                    return {"success": False, "error": error_msg}
                
                gabarito_id = qr_data.get('gabarito_id')
                student_id = qr_data.get('student_id')
                test_id = qr_data.get('test_id')
                
                # Carregar gabarito do banco
                from app.models.answerSheetGabarito import AnswerSheetGabarito
                from app.models.test import Test
                from app.models.testQuestion import TestQuestion
                from app.models.question import Question
                
                gabarito_obj = None
                
                # ✅ BUSCAR por gabarito_id OU por test_id
                if gabarito_id:
                    gabarito_obj = AnswerSheetGabarito.query.get(gabarito_id)
                    if not gabarito_obj:
                        error_msg = self._format_user_friendly_error(f"Gabarito {gabarito_id[:8]}... não encontrado")
                        return {"success": False, "error": error_msg}
                
                elif test_id:
                    # ✅ MODIFICADO: Buscar PRIMEIRO em AnswerSheetGabarito (fonte central)
                    # Fallback: PhysicalTestForm (compatibilidade com provas antigas)
                    gabarito_obj = AnswerSheetGabarito.query.filter_by(test_id=test_id).first()
                    
                    if gabarito_obj:
                        self.logger.info(f"✅ Gabarito encontrado em AnswerSheetGabarito (fonte central) para test_id: {gabarito_obj.id[:8]}...")
                    else:
                        # Fallback: buscar em PhysicalTestForm (compatibilidade com provas antigas)
                        from app.models.physicalTestForm import PhysicalTestForm
                        
                        physical_form = PhysicalTestForm.query.filter_by(test_id=test_id).first()
                        
                        if physical_form and physical_form.blocks_config and physical_form.correct_answers:
                            # Criar objeto temporário compatível com a interface esperada
                            class GabaritoTemp:
                                def __init__(self, form):
                                    self.id = f"physical_{form.test_id}"
                                    self.test_id = form.test_id
                                    self.num_questions = form.num_questions
                                    self.use_blocks = form.use_blocks
                                    self.blocks_config = form.blocks_config
                                    self.correct_answers = form.correct_answers
                            
                            gabarito_obj = GabaritoTemp(physical_form)
                            self.logger.info(f"✅ Dados de correção encontrados em PhysicalTestForm (fallback) para test_id: {test_id[:8]}...")
                        else:
                            # Último recurso: criar temporário a partir do Test
                            self.logger.warning(f"⚠️ Dados de correção não encontrados para test_id {test_id[:8]}..., montando dinamicamente")
                            gabarito_obj = self._criar_gabarito_de_test(test_id)
                            
                            if not gabarito_obj:
                                error_msg = self._format_user_friendly_error(f"Prova {test_id[:8]}... não encontrada ou sem questões")
                                return {"success": False, "error": error_msg}
                else:
                    error_msg = self._format_user_friendly_error("QR Code sem gabarito_id ou test_id")
                    return {"success": False, "error": error_msg}
                
                if not gabarito_obj:
                    error_msg = self._format_user_friendly_error("Gabarito não encontrado")
                    return {"success": False, "error": error_msg}
                
                # Construir topology_json
                topology_json = {
                    "num_blocks": gabarito_obj.blocks_config.get('num_blocks', 1),
                    "use_blocks": gabarito_obj.use_blocks,
                    "total_questions": gabarito_obj.num_questions,
                    "topology": gabarito_obj.blocks_config.get('topology', {})
                }
                
                # Validar topology
                if not topology_json.get('topology') or not topology_json['topology'].get('blocks'):
                    error_msg = self._format_user_friendly_error("Gabarito não possui estrutura de topologia. Regenere os cartões.")
                    return {
                        "success": False,
                        "error": error_msg
                    }
                
                # Usar respostas corretas do gabarito
                # ⚠️ CRÍTICO: Converter chaves de string para int
                gabarito_raw = gabarito_obj.correct_answers or {}
                gabarito = {}
                for key, value in gabarito_raw.items():
                    try:
                        gabarito[int(key)] = value
                    except (ValueError, TypeError):
                        self.logger.warning(f"⚠️ Chave de gabarito inválida: {key}")
                
                self.logger.info(f"✅ Gabarito carregado: {len(gabarito)} questões")
                
                # 🔍 DEBUG: Mostrar primeiras questões do gabarito
                if self.debug and len(gabarito) > 0:
                    sample_questions = sorted(list(gabarito.keys()))[:5]
                    sample_str = ", ".join([f"Q{q}={gabarito[q]}" for q in sample_questions])
                    self.logger.info(f"   Amostra gabarito: {sample_str}")
            
            # Validar parâmetros
            if not topology_json:
                error_msg = self._format_user_friendly_error("topology_json é obrigatório")
                return {"success": False, "error": error_msg}
            if not gabarito:
                error_msg = self._format_user_friendly_error("gabarito é obrigatório ou está vazio")
                return {"success": False, "error": error_msg}
            
            # Executar pipeline
            result = self._execute_omr_pipeline(img, topology_json)
            
            if not result["success"]:
                return result
            
            # Comparar com gabarito
            answers = result["answers"]
            correction = self._build_result(answers, gabarito)
            
            # ============================================
            # IMPRIMIR RESUMO DETALHADO NO TERMINAL
            # ============================================
            self._print_correction_summary(topology_json, answers, gabarito, correction)
            
            # Adicionar informações extras se auto_detect_qr
            if auto_detect_qr and qr_data:
                correction['gabarito_id'] = qr_data.get('gabarito_id') or gabarito_obj.id if hasattr(gabarito_obj, 'id') else None
                correction['student_id'] = qr_data.get('student_id')
                correction['test_id'] = qr_data.get('test_id')
            
            self.logger.info(
                f"✅ Correção finalizada: "
                f"{correction['correct_answers']}/{correction['total_questions']} corretas "
                f"({correction['score']:.1f}%)"
            )
            
            # Salvar resultado no banco automaticamente
            saved_result = None
            if correction.get('student_id') and (correction.get('gabarito_id') or correction.get('test_id')):
                saved_result = self.salvar_resultado(correction)
                if saved_result:
                    correction['answer_sheet_result_id'] = saved_result.get('id')
                    correction['evaluation_result_id'] = saved_result.get('id')
            
            return correction
            
        except Exception as e:
            self.logger.error(f"❌ Erro ao corrigir cartão: {str(e)}", exc_info=True)
            error_msg = self._format_user_friendly_error(f"Erro interno: {str(e)}")
            return {
                "success": False,
                "error": error_msg
            }
    
    # =========================================================================
    # FUNÇÕES AUXILIARES
    # =========================================================================
    
    def _print_correction_summary(self, topology_json: Dict, answers: Dict,
                                  gabarito: Dict, correction: Dict):
        """
        Imprime resumo detalhado da correção no terminal
        
        Args:
            topology_json: JSON com topologia dos blocos
            answers: Respostas detectadas {1: "A", 2: "B", ...}
            gabarito: Respostas corretas {1: "A", 2: "C", ...}
            correction: Resultado da correção
        """
        print("\n" + "="*80)
        print("📊 RESUMO DA CORREÇÃO - PIPELINE OMR ROBUSTO")
        print("="*80)
        
        # Informações gerais
        print(f"\n🎯 RESULTADO GERAL:")
        print(f"   Total de questões: {correction['total_questions']}")
        print(f"   ✅ Corretas: {correction['correct_answers']}")
        print(f"   ❌ Erradas: {correction['wrong_answers']}")
        print(f"   ⭕ Em branco: {correction['blank_answers']}")
        print(f"   ⚠️  Inválidas: {correction['invalid_answers']}")
        print(f"   📈 Nota: {correction['score']:.2f}%")
        
        # Detalhes por bloco
        if topology_json.get('use_blocks') and topology_json.get('topology', {}).get('blocks'):
            blocks = topology_json['topology']['blocks']
            
            print(f"\n📦 BLOCOS DETECTADOS: {len(blocks)}")
            print("-" * 80)
            
            for block_data in blocks:
                block_id = block_data.get('block_id', '?')
                questions = block_data.get('questions', [])
                
                print(f"\n🔹 BLOCO {block_id} - {len(questions)} questões")
                print("   " + "-" * 75)
                
                # Agrupar questões em linhas de 4 para não ficar muito longo
                for i in range(0, len(questions), 4):
                    line_questions = questions[i:i+4]
                    line_parts = []
                    
                    for q_data in line_questions:
                        q_num = q_data.get('q')
                        student_answer = answers.get(q_num, "___")
                        correct_answer = gabarito.get(q_num, "?")
                        
                        # Determinar símbolo
                        if student_answer == "___":
                            symbol = "⭕"  # Em branco
                            color = ""
                        elif student_answer == "INVALID":
                            symbol = "⚠️"  # Inválida
                            color = ""
                        elif student_answer == correct_answer:
                            symbol = "✅"  # Correta
                            color = ""
                        else:
                            symbol = "❌"  # Errada
                            color = ""
                        
                        # Formatar questão
                        if student_answer == correct_answer:
                            line_parts.append(f"Q{q_num:02d}:{student_answer}{symbol}")
                        else:
                            line_parts.append(f"Q{q_num:02d}:{student_answer}≠{correct_answer}{symbol}")
                    
                    print(f"   {' | '.join(line_parts)}")
        
        else:
            # Sem blocos - mostrar todas as questões
            print(f"\n📝 TODAS AS QUESTÕES:")
            print("-" * 80)
            
            all_questions = sorted(answers.keys())
            for i in range(0, len(all_questions), 5):
                line_questions = all_questions[i:i+5]
                line_parts = []
                
                for q_num in line_questions:
                    student_answer = answers.get(q_num, "___")
                    correct_answer = gabarito.get(q_num, "?")
                    
                    if student_answer == "___":
                        symbol = "⭕"
                    elif student_answer == "INVALID":
                        symbol = "⚠️"
                    elif student_answer == correct_answer:
                        symbol = "✅"
                    else:
                        symbol = "❌"
                    
                    if student_answer == correct_answer:
                        line_parts.append(f"Q{q_num:02d}:{student_answer}{symbol}")
                    else:
                        line_parts.append(f"Q{q_num:02d}:{student_answer}≠{correct_answer}{symbol}")
                
                print(f"   {' | '.join(line_parts)}")
        
        print("\n" + "="*80)
        print("✨ FIM DO RESUMO")
        print("="*80 + "\n")
    
    def _save_debug_image(self, filename: str, img: np.ndarray):
        """Salva imagem de debug"""
        if not self.debug:
            return
        
        import os
        filepath = os.path.join(self.debug_dir, f"{self.debug_timestamp}_{filename}")
        cv2.imwrite(filepath, img)
        self.logger.debug(f"💾 Debug: {filepath}")
    
    # =========================================================================
    # PERSISTÊNCIA - SALVAMENTO NO BANCO
    # =========================================================================
    
    def _calcular_proficiencia_classificacao(self, correct_answers: int, total_questions: int,
                                             gabarito_obj) -> Tuple[float, str]:
        """
        Calcula proficiência e classificação baseado no gabarito
        
        Args:
            correct_answers: Número de acertos
            total_questions: Total de questões
            gabarito_obj: Objeto AnswerSheetGabarito
            
        Returns:
            Tuple: (proficiência, classificação)
        """
        try:
            from app.services.evaluation_calculator import EvaluationCalculator
            
            # Inferir nome do curso (string) baseado no grade_name
            grade_name = gabarito_obj.grade_name or ''
            course_name = 'Anos Iniciais'  # Padrão
            
            if any(x in grade_name.lower() for x in ['infantil', 'pré', 'pre']):
                course_name = 'Educação Infantil'
            elif any(x in grade_name.lower() for x in ['1º', '2º', '3º', '4º', '5º', 'anos iniciais']):
                course_name = 'Anos Iniciais'
            elif any(x in grade_name.lower() for x in ['6º', '7º', '8º', '9º', 'anos finais']):
                course_name = 'Anos Finais'
            elif any(x in grade_name.lower() for x in ['1º médio', '2º médio', '3º médio', 'ensino médio']):
                course_name = 'Ensino Médio'
            elif 'especial' in grade_name.lower():
                course_name = 'Educação Especial'
            elif 'eja' in grade_name.lower():
                course_name = 'EJA'
            
            # Inferir nome da disciplina (string) baseado no title
            title = gabarito_obj.title or ''
            subject_name = 'Outras'  # Padrão
            
            if 'matemática' in title.lower() or 'matematica' in title.lower():
                subject_name = 'Matemática'
            
            # Calcular proficiência usando os parâmetros corretos
            proficiency = EvaluationCalculator.calculate_proficiency(
                correct_answers=correct_answers,
                total_questions=total_questions,
                course_name=course_name,
                subject_name=subject_name
            )
            
            # Calcular classificação usando os parâmetros corretos
            classification = EvaluationCalculator.determine_classification(
                proficiency=proficiency,
                course_name=course_name,
                subject_name=subject_name
            )
            
            return proficiency, classification
            
        except Exception as e:
            self.logger.error(f"Erro ao calcular proficiência/classificação: {str(e)}", exc_info=True)
            return 0.0, "Não calculado"
    
    def _salvar_respostas_no_banco(self, test_id: str, student_id: str,
                                  respostas_detectadas: Dict[int, Optional[str]],
                                  gabarito: Dict[int, str]) -> List[Dict[str, Any]]:
        """
        Salva respostas detectadas no banco de dados (StudentAnswer)
        Necessário para que EvaluationResultService possa calcular o resultado
        """
        try:
            from app.models.testQuestion import TestQuestion
            from app.models.question import Question
            from app.models.studentAnswer import StudentAnswer
            
            # Buscar questões do teste
            test_questions = TestQuestion.query.filter_by(test_id=test_id).order_by(TestQuestion.order).all()
            
            if not test_questions:
                self.logger.warning(f"Nenhuma questão encontrada para test_id={test_id}")
                return []
            
            # Criar mapeamento: índice sequencial -> test_question
            questions_by_index = {}
            for idx, tq in enumerate(test_questions, start=1):
                questions_by_index[idx] = tq
            
            saved_answers = []
            
            for q_num, detected_answer in respostas_detectadas.items():
                if q_num not in questions_by_index:
                    continue
                
                test_question = questions_by_index[q_num]
                question_id = test_question.question_id
                correct_answer = gabarito.get(q_num, '')
                
                # Verificar se está correta
                is_correct = None
                if detected_answer and correct_answer:
                    is_correct = (detected_answer.upper() == correct_answer.upper())
                
                # Verificar se já existe resposta
                existing_answer = StudentAnswer.query.filter_by(
                    student_id=student_id,
                    test_id=test_id,
                    question_id=question_id
                ).first()
                
                if existing_answer:
                    # Atualizar resposta existente
                    existing_answer.answer = detected_answer if detected_answer else ''
                    existing_answer.is_correct = is_correct
                    existing_answer.answered_at = datetime.utcnow()
                    student_answer = existing_answer
                else:
                    # Criar nova resposta
                    student_answer = StudentAnswer(
                        student_id=student_id,
                        test_id=test_id,
                        question_id=question_id,
                        answer=detected_answer if detected_answer else '',
                        is_correct=is_correct
                    )
                    db.session.add(student_answer)
                
                saved_answers.append({
                    'question_number': q_num,
                    'question_id': question_id,
                    'detected_answer': detected_answer,
                    'correct_answer': correct_answer,
                    'is_correct': is_correct
                })
            
            # Commit
            db.session.commit()
            self.logger.info(f"✅ {len(saved_answers)} respostas salvas em StudentAnswer")
            
            return saved_answers
            
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Erro ao salvar respostas no banco: {str(e)}", exc_info=True)
            return []
    
    def _criar_sessao_minima_para_evaluation_result(self, test_id: str, student_id: str) -> Optional[str]:
        """
        Cria uma sessão mínima apenas para satisfazer a foreign key do EvaluationResult
        Não é uma sessão real de teste, apenas um registro técnico
        
        Args:
            test_id: ID da prova
            student_id: ID do aluno
            
        Returns:
            session_id: ID da sessão criada ou None se erro
        """
        try:
            from app.models.testSession import TestSession
            
            # Verificar se já existe uma sessão para esta correção física
            existing_session = TestSession.query.filter_by(
                test_id=test_id,
                student_id=student_id,
                status='corrigida',
                user_agent='Physical Test Correction (NewGrid)'
            ).first()
            
            if existing_session:
                self.logger.info(f"Sessão existente encontrada: {existing_session.id}")
                return existing_session.id
            
            # Criar nova sessão mínima para correção física
            session = TestSession(
                id=str(uuid.uuid4()),
                student_id=student_id,
                test_id=test_id,
                time_limit_minutes=None,
                ip_address=None,
                user_agent='Physical Test Correction (NewGrid)',
                status='corrigida',
                started_at=datetime.utcnow(),
                submitted_at=datetime.utcnow()
            )
            
            session_id = session.id
            db.session.add(session)
            db.session.commit()
            
            self.logger.info(f"✅ Sessão mínima criada: {session_id}")
            return session_id
            
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Erro ao criar sessão mínima: {str(e)}", exc_info=True)
            return None
    
    def _salvar_resultado_answer_sheet(self, gabarito_id: str, student_id: str,
                                      detected_answers: Dict[int, Optional[str]],
                                      correction: Dict[str, Any],
                                      grade: float, proficiency: float,
                                      classification: str,
                                      proficiency_by_subject: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """Salva resultado em AnswerSheetResult (cartões resposta)"""
        try:
            from app.models.answerSheetResult import AnswerSheetResult
            
            # Verificar se já existe resultado
            existing_result = AnswerSheetResult.query.filter_by(
                gabarito_id=gabarito_id,
                student_id=student_id
            ).first()
            
            if existing_result:
                # Atualizar
                existing_result.detected_answers = detected_answers
                existing_result.correct_answers = correction.get('correct_answers', 0)
                existing_result.total_questions = correction.get('total_questions', 0)
                existing_result.incorrect_answers = correction.get('wrong_answers', 0)
                existing_result.unanswered_questions = correction.get('blank_answers', 0)
                existing_result.answered_questions = correction.get('total_questions', 0) - correction.get('blank_answers', 0)
                existing_result.score_percentage = correction.get('score', 0.0)
                existing_result.grade = grade
                existing_result.proficiency = proficiency
                existing_result.classification = classification
                existing_result.proficiency_by_subject = proficiency_by_subject
                existing_result.corrected_at = datetime.utcnow()
                existing_result.detection_method = 'new_grid'
                
                db.session.flush()
                payload = existing_result.to_dict()
                db.session.commit()
                self.logger.info(f"✅ AnswerSheetResult atualizado: {payload['id']}")
                try:
                    from app.report_analysis.answer_sheet_aggregate_service import (
                        invalidate_answer_sheet_report_cache_after_result,
                    )

                    invalidate_answer_sheet_report_cache_after_result(
                        gabarito_id, student_id, commit=True
                    )
                except Exception as inv_err:
                    self.logger.warning("Invalidate answer_sheet report cache: %s", inv_err)
                return payload
            else:
                # Criar novo
                result = AnswerSheetResult(
                    gabarito_id=gabarito_id,
                    student_id=student_id,
                    detected_answers=detected_answers,
                    correct_answers=correction.get('correct_answers', 0),
                    total_questions=correction.get('total_questions', 0),
                    incorrect_answers=correction.get('wrong_answers', 0),
                    unanswered_questions=correction.get('blank_answers', 0),
                    answered_questions=correction.get('total_questions', 0) - correction.get('blank_answers', 0),
                    score_percentage=correction.get('score', 0.0),
                    grade=grade,
                    proficiency=proficiency,
                    classification=classification,
                    proficiency_by_subject=proficiency_by_subject,
                    detection_method='new_grid'
                )
                
                db.session.add(result)
                db.session.flush()
                payload = result.to_dict()
                db.session.commit()
                self.logger.info(f"✅ AnswerSheetResult criado: {payload['id']}")
                try:
                    from app.report_analysis.answer_sheet_aggregate_service import (
                        invalidate_answer_sheet_report_cache_after_result,
                    )

                    invalidate_answer_sheet_report_cache_after_result(
                        gabarito_id, student_id, commit=True
                    )
                except Exception as inv_err:
                    self.logger.warning("Invalidate answer_sheet report cache: %s", inv_err)
                return payload
                
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Erro ao salvar resultado em answer_sheet_results: {str(e)}", exc_info=True)
            return None
    
    def _salvar_resultado_evaluation(self, test_id: str, student_id: str,
                                    detected_answers: Dict[int, Optional[str]],
                                    correction: Dict[str, Any],
                                    grade: float, proficiency: float,
                                    classification: str) -> Optional[Dict[str, Any]]:
        """
        Salva resultado em evaluation_results (provas físicas)
        Primeiro salva respostas em StudentAnswer, depois calcula EvaluationResult
        """
        try:
            # ✅ MODIFICADO: Buscar PRIMEIRO em AnswerSheetGabarito (fonte central)
            # Fallback: PhysicalTestForm (compatibilidade com provas antigas)
            from app.models.answerSheetGabarito import AnswerSheetGabarito
            
            # 1. Buscar AnswerSheetGabarito (fonte central)
            gabarito_obj = AnswerSheetGabarito.query.filter_by(test_id=test_id).first()
            
            if gabarito_obj and gabarito_obj.correct_answers:
                correct_answers = gabarito_obj.correct_answers
                self.logger.info(f"✅ Dados de correção obtidos de AnswerSheetGabarito (fonte central)")
            else:
                # Fallback: buscar em PhysicalTestForm (compatibilidade com provas antigas)
                from app.models.physicalTestForm import PhysicalTestForm
                physical_form = PhysicalTestForm.query.filter_by(test_id=test_id).first()
                
                if physical_form and physical_form.correct_answers:
                    correct_answers = physical_form.correct_answers
                    self.logger.info(f"✅ Dados de correção obtidos de PhysicalTestForm (fallback)")
                else:
                    self.logger.error(f"Gabarito não encontrado para test_id={test_id}")
                    return None
            
            # Converter correct_answers para dict
            if isinstance(correct_answers, str):
                correct_answers = json.loads(correct_answers)
            
            gabarito = {}
            for key, value in correct_answers.items():
                try:
                    q_num = int(key)
                    gabarito[q_num] = str(value).upper() if value else None
                except (ValueError, TypeError):
                    continue
            
            # 2. Salvar respostas do aluno em StudentAnswer
            saved_answers = self._salvar_respostas_no_banco(
                test_id=test_id,
                student_id=student_id,
                respostas_detectadas=detected_answers,
                gabarito=gabarito
            )
            
            if not saved_answers:
                self.logger.warning(f"Nenhuma resposta salva para test_id={test_id}, student_id={student_id}")
            
            # 3. Criar sessão mínima para EvaluationResult
            session_id = self._criar_sessao_minima_para_evaluation_result(
                test_id=test_id,
                student_id=student_id
            )
            
            if not session_id:
                self.logger.warning("Não foi possível criar sessão mínima, continuando sem EvaluationResult")
                return {
                    'id': None,
                    'test_id': test_id,
                    'student_id': student_id,
                    'saved_answers': saved_answers
                }
            
            # 4. Calcular e salvar EvaluationResult usando EvaluationResultService
            from app.services.evaluation_result_service import EvaluationResultService
            
            evaluation_result = EvaluationResultService.calculate_and_save_result(
                test_id=test_id,
                student_id=student_id,
                session_id=session_id
            )
            
            if evaluation_result:
                self.logger.info(f"✅ EvaluationResult criado/atualizado: {evaluation_result.get('id')}")
                
                # Marcar formulário físico como corrigido
                self._marcar_formulario_como_corrigido(test_id, student_id)
                
                return {
                    'id': evaluation_result.get('id'),
                    'test_id': test_id,
                    'student_id': student_id,
                    'session_id': session_id,
                    'correct_answers': evaluation_result.get('correct_answers', correction.get('correct_answers', 0)),
                    'total_questions': evaluation_result.get('total_questions', correction.get('total_questions', 0)),
                    'score_percentage': evaluation_result.get('score_percentage', correction.get('score', 0.0)),
                    'grade': evaluation_result.get('grade', grade),
                    'proficiency': evaluation_result.get('proficiency', proficiency),
                    'classification': evaluation_result.get('classification', classification),
                    'saved_answers': saved_answers
                }
            else:
                self.logger.warning("EvaluationResultService não retornou resultado")
                
                # Mesmo sem EvaluationResult, marcar formulário como corrigido
                self._marcar_formulario_como_corrigido(test_id, student_id)
                
                return {
                    'id': None,
                    'test_id': test_id,
                    'student_id': student_id,
                    'saved_answers': saved_answers
                }
                
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Erro ao salvar resultado em evaluation_results: {str(e)}", exc_info=True)
            return None
    
    def _marcar_formulario_como_corrigido(self, test_id: str, student_id: str) -> bool:
        """
        Marca o PhysicalTestForm como corrigido após processar a correção
        
        Args:
            test_id: ID da prova física
            student_id: ID do aluno
            
        Returns:
            True se marcado com sucesso, False caso contrário
        """
        try:
            from app.models.physicalTestForm import PhysicalTestForm
            
            # Buscar formulário físico do aluno para esta prova
            form = PhysicalTestForm.query.filter_by(
                test_id=test_id,
                student_id=student_id
            ).first()
            
            if not form:
                self.logger.warning(f"Formulário físico não encontrado para test_id={test_id}, student_id={student_id}")
                return False
            
            # Marcar como enviado (se ainda não foi marcado)
            if not form.answer_sheet_sent_at:
                form.answer_sheet_sent_at = datetime.utcnow()
            
            # Marcar como corrigido
            form.is_corrected = True
            form.corrected_at = datetime.utcnow()
            form.status = 'corrigido'
            
            db.session.commit()
            
            self.logger.info(f"✅ Formulário físico marcado como corrigido: {form.id}")
            return True
            
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Erro ao marcar formulário como corrigido: {str(e)}", exc_info=True)
            return False
    
    def salvar_resultado(self, correction: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Salva resultado detectando automaticamente o tipo:
        - Se tem gabarito_id → salva em AnswerSheetResult (cartões resposta)
        - Se tem test_id → salva em EvaluationResult (provas físicas)
        
        Args:
            correction: Dicionário com resultado da correção
            
        Returns:
            Dicionário com informações do registro salvo ou None se erro
        """
        try:
            from app.models.answerSheetGabarito import AnswerSheetGabarito
            
            gabarito_id = correction.get('gabarito_id')
            student_id = correction.get('student_id')
            test_id = correction.get('test_id')
            
            if not student_id:
                self.logger.error("student_id não encontrado no resultado da correção")
                return None
            
            # Preparar respostas detectadas (converter de student_answers)
            detected_answers = {}
            if 'student_answers' in correction:
                for key, value in correction['student_answers'].items():
                    try:
                        q_num = int(key)
                        detected_answers[q_num] = value
                    except (ValueError, TypeError):
                        continue
            
            # Calcular grade (0-10)
            grade = correction.get('score', 0.0) / 10.0
            
            # Calcular proficiência por disciplina e média geral (cartão resposta)
            proficiency = 0.0
            classification = "Não calculado"
            proficiency_by_subject = None
            gabarito_obj = None
            
            if gabarito_id:
                gabarito_obj = AnswerSheetGabarito.query.get(gabarito_id)
            elif test_id:
                gabarito_obj = AnswerSheetGabarito.query.filter_by(test_id=test_id).first()
            
            if gabarito_obj:
                blocks_config = getattr(gabarito_obj, 'blocks_config', None) or {}
                correct_answers_json = gabarito_obj.correct_answers
                if isinstance(correct_answers_json, str):
                    import json
                    correct_answers_json = json.loads(correct_answers_json)
                gabarito_dict = {}
                for k, v in (correct_answers_json or {}).items():
                    try:
                        gabarito_dict[int(k)] = str(v).upper() if v else ''
                    except (ValueError, TypeError):
                        pass
                from app.services.cartao_resposta.proficiency_by_subject import calcular_proficiencia_por_disciplina
                proficiency_by_subject, proficiency, classification = calcular_proficiencia_por_disciplina(
                    blocks_config=blocks_config,
                    validated_answers=detected_answers,
                    gabarito_dict=gabarito_dict,
                    grade_name=gabarito_obj.grade_name or '',
                )
            
            # Decidir onde salvar
            if gabarito_id and not test_id:
                # Cartão resposta: salvar em AnswerSheetResult
                self.logger.info(f"💾 Salvando resultado em AnswerSheetResult (gabarito_id={gabarito_id})")
                return self._salvar_resultado_answer_sheet(
                    gabarito_id=gabarito_id,
                    student_id=student_id,
                    detected_answers=detected_answers,
                    correction=correction,
                    grade=grade,
                    proficiency=proficiency,
                    classification=classification,
                    proficiency_by_subject=proficiency_by_subject
                )
            elif test_id:
                # Prova física: salvar em EvaluationResult (proficiency única, sem proficiency_by_subject)
                self.logger.info(f"💾 Salvando resultado em EvaluationResult (test_id={test_id})")
                return self._salvar_resultado_evaluation(
                    test_id=test_id,
                    student_id=student_id,
                    detected_answers=detected_answers,
                    correction=correction,
                    grade=grade,
                    proficiency=proficiency,
                    classification=classification
                )
            else:
                self.logger.error("Nem gabarito_id nem test_id encontrados no resultado da correção")
                return None
                
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Erro ao salvar resultado: {str(e)}", exc_info=True)
            return None


# =============================================================================
# EXEMPLO DE USO
# =============================================================================

if __name__ == "__main__":
    # Configurar logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # JSON de topologia (exemplo)
    topology_json = {
        "num_blocks": 4,
        "use_blocks": True,
        "total_questions": 48,
        "topology": {
            "blocks": [
                {
                    "block_id": 1,
                    "questions": [
                        {"q": 1, "alternatives": ["A", "B", "C", "D"]},
                        {"q": 2, "alternatives": ["A", "B", "C", "D"]},
                        {"q": 3, "alternatives": ["A", "B", "C"]},
                        {"q": 4, "alternatives": ["A", "B", "C", "D", "E"]},
                        # ... mais questões
                    ]
                },
                # ... mais blocos
            ]
        }
    }
    
    # Gabarito (exemplo)
    gabarito = {
        1: "A",
        2: "C",
        3: "B",
        4: "D",
        # ... mais respostas
    }
    
    # Criar instância (debug desativado por padrão)
    corrector = AnswerSheetCorrectionNewGrid(debug=False)
    
    # Corrigir cartão
    result = corrector.corrigir_cartao_resposta(
        image_path="test_images/cartao_001.jpg",
        topology_json=topology_json,
        gabarito=gabarito
    )
    
    # Exibir resultado
    if result["success"]:
        print(f"\n✅ CORREÇÃO FINALIZADA")
        print(f"Total de questões: {result['total_questions']}")
        print(f"Respostas corretas: {result['correct_answers']}")
        print(f"Respostas erradas: {result['wrong_answers']}")
        print(f"Em branco: {result['blank_answers']}")
        print(f"Inválidas: {result['invalid_answers']}")
        print(f"Nota: {result['score']:.2f}%")
    else:
        print(f"\n❌ ERRO: {result['error']}")
