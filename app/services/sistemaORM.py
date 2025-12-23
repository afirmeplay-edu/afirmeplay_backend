# -*- coding: utf-8 -*-
"""
Sistema OMR (Optical Mark Recognition) - Baseado em projeto.py
Adaptado para template institutional_test.html

ETAPAS:
1. Detectar borda grossa (5px) ao redor dos blocos de resposta (.answer-grid-container)
2. Aplicar correção de perspectiva
3. Detectar QR Code
4. Calcular coordenadas dinamicamente baseado no CSS do template
5. Processar imagem binária (adaptiveThreshold invertido)
6. Detectar bolhas preenchidas (>= 70% pixels brancos)
7. Comparar com gabarito e salvar
"""

import cv2
import numpy as np
import json
import logging
from typing import Dict, List, Tuple, Optional, Any
from pyzbar.pyzbar import decode as pyzbar_decode
import os
from datetime import datetime


class SistemaORM:
    """
    Sistema OMR baseado em projeto.py
    Adaptado para template institutional_test.html
    """
    
    # Threshold para detecção de bolinha preenchida (mesmo do projeto.py)
    BUBBLE_FILL_THRESHOLD = 0.70  # 70% de pixels brancos = preenchida
    
    def __init__(self, debug: bool = False):
        """
        Inicializa o sistema OMR
        
        Args:
            debug: Se True, gera logs detalhados e imagens de debug
        """
        self.debug = debug
        self.debug_dir = "debug_corrections"
        if self.debug:
            os.makedirs(self.debug_dir, exist_ok=True)
    
    def process_exam(self, image_path: str = None, image_data: str = None, 
                     answer_key: Dict[int, str] = None, 
                     num_questions: int = None,
                     coordinates_config: Dict = None) -> Dict[str, Any]:
        """
        Pipeline principal: processa uma prova completa
        
        Args:
            image_path: Caminho para a imagem (opcional)
            image_data: Dados da imagem em base64 (opcional)
            answer_key: Gabarito {questão: resposta_correta}
            num_questions: Número total de questões
            coordinates_config: Configuração de coordenadas das bolhas (não usado, calculado dinamicamente)
        
        Returns:
            Dict com test_id, student_id, answers, score, correct, total
        """
        try:
            print(f"🎯 INICIANDO PROCESSAMENTO OMR")
            
            # 1. Carregar imagem
            img = self._load_image(image_path, image_data)
            if img is None:
                return {"success": False, "error": "Erro ao carregar imagem"}
            
            print(f"📏 Imagem carregada: {img.shape}")
            
            # 2. Detectar borda grossa (5px) ao redor dos blocos de resposta
            print(f"\n🔍 ETAPA 1: DETECTANDO BORDA GROSSA AO REDOR DOS BLOCOS...")
            border_corners = self._detect_answer_grid_border(img)
            if border_corners is None or len(border_corners) != 4:
                return {"success": False, "error": f"Borda dos blocos não detectada (encontrados: {len(border_corners) if border_corners else 0}/4 cantos)"}
            
            print(f"✅ Borda dos blocos detectada (4 cantos)")
            
            # 3. Aplicar correção de perspectiva
            print(f"\n🔍 ETAPA 2: APLICANDO CORREÇÃO DE PERSPECTIVA...")
            aligned = self._warp_perspective_border(img, border_corners)
            if aligned is None:
                return {"success": False, "error": "Falha ao aplicar correção de perspectiva"}
            
            print(f"✅ Perspectiva corrigida: {aligned.shape}")
            
            if self.debug:
                debug_path = os.path.join(self.debug_dir, f"warped_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
                cv2.imwrite(debug_path, aligned)
                print(f"💾 Imagem retificada salva: {debug_path}")
            
            # 4. Detectar QR Code
            print(f"\n🔍 ETAPA 3: DETECTANDO QR CODE...")
            qr_data = self._read_qr_code(aligned)
            if not qr_data:
                print(f"⚠️ QR Code não detectado na imagem retificada, tentando na imagem original...")
                qr_data = self._read_qr_code(img)
                if not qr_data:
                    return {"success": False, "error": "QR Code não detectado"}
            
            test_id = qr_data.get('test_id')
            student_id = qr_data.get('student_id')
            
            print(f"✅ QR Code lido: test_id={test_id[:8] if test_id else 'N/A'}..., student_id={student_id[:8] if student_id else 'N/A'}...")
            
            # Obter número de questões se não fornecido
            if num_questions is None:
                num_questions = self._get_num_questions_from_db(test_id)
                if num_questions is None:
                    return {"success": False, "error": "Número de questões não encontrado"}
            
            print(f"📊 Número de questões: {num_questions}")
            
            # Obter gabarito se não fornecido
            if answer_key is None:
                answer_key = self._get_answer_key_from_db(test_id)
                if not answer_key:
                    return {"success": False, "error": "Gabarito não encontrado no banco"}
            
            # 5. Calcular coordenadas dinamicamente baseado no CSS do template
            print(f"\n🔍 ETAPA 4: CALCULANDO COORDENADAS DINAMICAMENTE...")
            coordinates = self._calculate_bubble_coordinates(aligned, num_questions)
            if not coordinates:
                return {"success": False, "error": "Falha ao calcular coordenadas"}
            
            print(f"✅ {len(coordinates)} coordenadas calculadas")
            
            # 6. Processar imagem binária e detectar bolhas
            print(f"\n🔍 ETAPA 5: DETECTANDO BOLHAS...")
            detected_answers = self._detect_bubbles(aligned, coordinates, num_questions)
            
            print(f"✅ Respostas detectadas: {len(detected_answers)}/{num_questions}")
            
            # 7. Gerar imagem de debug se habilitado
            if self.debug:
                self._generate_debug_image(aligned, coordinates, detected_answers, answer_key, test_id, student_id)
            
            # 8. Calcular score
            score_data = self._calculate_score(detected_answers, answer_key)
            
            # 9. Salvar respostas no banco de dados
            saved_answers = self._save_answers_to_db(test_id, student_id, detected_answers, answer_key)
            
            # 10. Calcular resultado da avaliação
            evaluation_result = self._calculate_evaluation_result(test_id, student_id)
            
            # 11. Montar resultado final
            result = {
                "success": True,
                "test_id": test_id,
                "student_id": student_id,
                "answers": detected_answers,
                "score": score_data['score'],
                "correct": score_data['correct'],
                "total": score_data['total'],
                "percentage": score_data['percentage'],
                "saved_answers": saved_answers,
                "evaluation_result": evaluation_result
            }
            
            print(f"✅ Processamento concluído: {score_data['correct']}/{score_data['total']} acertos ({score_data['percentage']:.1f}%)")
            print(f"💾 Respostas salvas no banco: {len(saved_answers)}")
            
            return result
            
        except Exception as e:
            logging.error(f"Erro no processamento OMR: {str(e)}")
            import traceback
            logging.error(traceback.format_exc())
            return {"success": False, "error": f"Erro no processamento: {str(e)}"}
    
    def _load_image(self, image_path: str = None, image_data: str = None) -> Optional[np.ndarray]:
        """
        Carrega imagem de arquivo ou base64
        """
        try:
            if image_path:
                img = cv2.imread(image_path)
                if img is None:
                    print(f"❌ Erro ao ler imagem: {image_path}")
                    return None
                return img
            
            elif image_data:
                import base64
                # Remover prefixo data:image se presente
                if ',' in image_data:
                    image_data = image_data.split(',')[1]
                
                img_bytes = base64.b64decode(image_data)
                nparr = np.frombuffer(img_bytes, np.uint8)
                img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                return img
            
            return None
            
        except Exception as e:
            logging.error(f"Erro ao carregar imagem: {str(e)}")
            return None
    
    def _detect_answer_grid_border(self, img: np.ndarray) -> Optional[np.ndarray]:
        """
        Detecta a borda grossa (5px) ao redor dos blocos de respostas
        Baseado no projeto.py - detecta maior contorno retangular
        
        Returns:
            Array com 4 pontos ordenados (TL, TR, BR, BL) ou None
        """
        try:
            # Converter para grayscale
            if len(img.shape) == 3:
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            else:
                gray = img.copy()
            
            h, w = gray.shape
            print(f"🔍 Detectando borda em imagem {w}x{h}px")
            
            # Aplicar blur gaussiano (mesmo do projeto.py)
            borrada = cv2.GaussianBlur(gray, (5, 5), 0)
            
            # Threshold adaptativo invertido (mesmo do projeto.py)
            binario = cv2.adaptiveThreshold(borrada, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                           cv2.THRESH_BINARY_INV, 11, 2)
            
            # Aplicar morfologia OPEN para limpar ruído (mesmo do projeto.py)
            kernel = np.ones((3, 3), np.uint8)
            opening = cv2.morphologyEx(binario, cv2.MORPH_OPEN, kernel)
            
            # Encontrar contornos (mesmo do projeto.py)
            contornos, _ = cv2.findContours(opening, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if not contornos:
                print(f"❌ Nenhum contorno encontrado")
                return None
            
            # Pegar maior contorno (mesmo do projeto.py)
            maior_contorno = max(contornos, key=cv2.contourArea)
            
            # Aproximar contorno para retângulo
            epsilon = 0.02 * cv2.arcLength(maior_contorno, True)
            aproximado = cv2.approxPolyDP(maior_contorno, epsilon, True)
            
            if len(aproximado) < 4:
                print(f"❌ Contorno não tem 4 vértices (encontrados: {len(aproximado)})")
                return None
            
            # Ordenar pontos (TL, TR, BR, BL)
            pontos_ordenados = self._ordenar_pontos(aproximado)
            
            print(f"✅ Borda detectada:")
            print(f"   TL: {pontos_ordenados[0]}")
            print(f"   TR: {pontos_ordenados[1]}")
            print(f"   BR: {pontos_ordenados[2]}")
            print(f"   BL: {pontos_ordenados[3]}")
            
            return pontos_ordenados
            
        except Exception as e:
            logging.error(f"Erro ao detectar borda: {str(e)}")
            print(f"❌ Erro ao detectar borda: {e}")
            import traceback
            logging.error(traceback.format_exc())
            return None
    
    def _ordenar_pontos(self, pontos: np.ndarray) -> np.ndarray:
        """
        Ordena os 4 pontos como TL, TR, BR, BL
        Mesmo método do projeto.py
        """
        pontos = pontos.reshape((4, 2))
        soma = pontos.sum(axis=1)
        diff = np.diff(pontos, axis=1)
        
        topo_esq = pontos[np.argmin(soma)]
        baixo_dir = pontos[np.argmax(soma)]
        topo_dir = pontos[np.argmin(diff)]
        baixo_esq = pontos[np.argmax(diff)]
        
        return np.array([topo_esq, topo_dir, baixo_dir, baixo_esq], dtype="float32")
    
    def _warp_perspective_border(self, img: np.ndarray, border_corners: np.ndarray) -> Optional[np.ndarray]:
        """
        Aplica correção de perspectiva usando a borda detectada
        Baseado no projeto.py - usa tamanho fixo baseado no template
        
        Args:
            img: Imagem original
            border_corners: 4 cantos da borda detectada (TL, TR, BR, BL)
        
        Returns:
            Imagem retificada ou None
        """
        try:
            # Calcular dimensões baseadas no template
            # Template típico: largura ~688px, altura ~301px (para área de respostas)
            # Mas vamos calcular dinamicamente baseado na proporção dos cantos
            width_top = np.linalg.norm(border_corners[1] - border_corners[0])
            width_bottom = np.linalg.norm(border_corners[2] - border_corners[3])
            largura = int(max(width_top, width_bottom))
            
            height_left = np.linalg.norm(border_corners[3] - border_corners[0])
            height_right = np.linalg.norm(border_corners[2] - border_corners[1])
            altura = int(max(height_left, height_right))
            
            # Pontos de destino
            destino = np.array([
                [0, 0],
                [largura - 1, 0],
                [largura - 1, altura - 1],
                [0, altura - 1]
            ], dtype="float32")
            
            # Calcular matriz de transformação
            matriz = cv2.getPerspectiveTransform(border_corners, destino)
            
            # Aplicar warp
            corrigido = cv2.warpPerspective(img, matriz, (largura, altura))
            
            print(f"✅ Imagem retificada: {corrigido.shape}")
            
            return corrigido
            
        except Exception as e:
            logging.error(f"Erro ao aplicar warp: {str(e)}")
            print(f"❌ Warp error: {e}")
            return None
    
    def _read_qr_code(self, img: np.ndarray) -> Optional[Dict[str, str]]:
        """
        Lê QR Code da imagem usando cv2.QRCodeDetector (mesmo do projeto.py)
        
        Returns:
            Dict com test_id e student_id ou None
        """
        try:
            # Converter para grayscale se necessário
            if len(img.shape) == 3:
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            else:
                gray = img.copy()
            
            # Usar cv2.QRCodeDetector (mesmo do projeto.py)
            detector = cv2.QRCodeDetector()
            dados, _, _ = detector.detectAndDecode(gray)
            
            if not dados:
                return None
            
            print(f"📱 QR Code detectado: {dados[:50]}...")
            
            # Tentar formato ultra-compacto primeiro: s12345678t87654321
            if dados.startswith('s') and 't' in dados[1:]:
                t_index = dados.find('t', 1)
                if t_index > 1:
                    short_student_id = dados[1:t_index]
                    short_test_id = dados[t_index+1:]
                    
                    # Buscar IDs completos no banco
                    student_id = self._buscar_id_completo_por_sufixo('student', short_student_id)
                    test_id = self._buscar_id_completo_por_sufixo('test', short_test_id)
                    
                    if student_id and test_id:
                        return {
                            'test_id': test_id,
                            'student_id': student_id
                        }
                    else:
                        logging.warning(f"Não foi possível encontrar IDs completos: "
                                      f"student_suffix={short_student_id}, test_suffix={short_test_id}")
                        # Fallback: retornar os sufixos mesmo assim
                        return {
                            'test_id': short_test_id,
                            'student_id': short_student_id
                        }
            
            # Tentar formato compacto com dois pontos: s:xxx t:xxx
            if dados.startswith('s:') and ' t:' in dados:
                parts = dados.split(' t:')
                if len(parts) == 2:
                    student_id = parts[0].replace('s:', '').strip()
                    test_id = parts[1].strip()
                    return {
                        'test_id': test_id,
                        'student_id': student_id
                    }
            
            # Tentar parsear como JSON (compatibilidade com formato antigo)
            try:
                qr_json = json.loads(dados)
                return {
                    'test_id': qr_json.get('test_id'),
                    'student_id': qr_json.get('student_id')
                }
            except json.JSONDecodeError:
                # Se não for JSON, tratar como string simples (student_id)
                return {
                    'test_id': None,
                    'student_id': dados.strip()
                }
                
        except Exception as e:
            logging.error(f"Erro ao ler QR Code: {str(e)}")
            return None
    
    def _buscar_id_completo_por_sufixo(self, table_name: str, suffix: str) -> Optional[str]:
        """
        Busca ID completo no banco usando sufixo (últimos caracteres)
        """
        try:
            from sqlalchemy import func
            from app import db
            
            if table_name == 'student':
                from app.models.student import Student
                student = Student.query.filter(
                    func.replace(Student.id, '-', '').like(f'%{suffix}')
                ).first()
                return student.id if student else None
            elif table_name == 'test':
                from app.models.test import Test
                test = Test.query.filter(
                    func.replace(Test.id, '-', '').like(f'%{suffix}')
                ).first()
                return test.id if test else None
            return None
        except Exception as e:
            logging.error(f"Erro ao buscar ID completo para {table_name} com sufixo {suffix}: {str(e)}")
            return None
    
    def _calculate_bubble_coordinates(self, aligned_img: np.ndarray, num_questions: int) -> List[Dict]:
        """
        Calcula coordenadas das bolhas dinamicamente baseado no CSS do template
        
        Estrutura do template:
        - .answer-grid-container: border 5px, padding 5px, gap 8px, grid 4 colunas
        - .answer-block: border 1px, padding 5px
        - .bubble: 18px x 18px, gap 6px entre bolhas
        - 12 questões por bloco
        - 4 alternativas por questão (A, B, C, D)
        
        Args:
            aligned_img: Imagem retificada
            num_questions: Número total de questões
        
        Returns:
            Lista de coordenadas [{question, alternative, x, y, width, height}, ...]
        """
        try:
            h, w = aligned_img.shape[:2]
            
            # Valores CSS do template (em pixels a 96 DPI)
            CSS_BORDER_WIDTH = 5
            CSS_PADDING = 5
            CSS_GRID_GAP = 8
            CSS_BLOCK_PADDING = 5
            CSS_BLOCK_HEADER_HEIGHT = 18  # Aproximado
            CSS_BUBBLE_HEADER_HEIGHT = 15  # Aproximado
            CSS_ANSWER_ROW_HEIGHT = 24  # Aproximado
            CSS_QUESTION_NUM_WIDTH = 22
            CSS_BUBBLE_SIZE = 18
            CSS_BUBBLE_GAP = 6
            
            questions_per_block = 12
            num_blocks = ((num_questions - 1) // questions_per_block) + 1
            if num_blocks == 0:
                num_blocks = 1
            
            # Calcular dimensões disponíveis
            available_width = w - (CSS_BORDER_WIDTH * 2) - (CSS_PADDING * 2)
            available_height = h - (CSS_BORDER_WIDTH * 2) - (CSS_PADDING * 2)
            
            # Calcular largura de cada bloco
            block_width = (available_width - (CSS_GRID_GAP * (num_blocks - 1))) // num_blocks if num_blocks > 0 else available_width
            
            # Calcular escala baseada no tamanho real da imagem
            # Template típico: ~688px largura total
            template_expected_width = CSS_BORDER_WIDTH * 2 + CSS_PADDING * 2 + num_blocks * block_width + (num_blocks - 1) * CSS_GRID_GAP
            scale = w / template_expected_width if template_expected_width > 0 else 1.0
            
            # Escalar valores
            border_width = int(CSS_BORDER_WIDTH * scale)
            padding = int(CSS_PADDING * scale)
            grid_gap = int(CSS_GRID_GAP * scale)
            block_padding = int(CSS_BLOCK_PADDING * scale)
            block_header_height = int(CSS_BLOCK_HEADER_HEIGHT * scale)
            bubble_header_height = int(CSS_BUBBLE_HEADER_HEIGHT * scale)
            answer_row_height = int(CSS_ANSWER_ROW_HEIGHT * scale)
            question_num_width = int(CSS_QUESTION_NUM_WIDTH * scale)
            bubble_size = int(CSS_BUBBLE_SIZE * scale)
            bubble_gap = int(CSS_BUBBLE_GAP * scale)
            
            # Recalcular block_width com valores escalados
            available_width_scaled = w - (border_width * 2) - (padding * 2)
            block_width = (available_width_scaled - (grid_gap * (num_blocks - 1))) // num_blocks if num_blocks > 0 else available_width_scaled
            
            coordinates = []
            
            # Posição base (dentro da borda e padding)
            base_x = border_width + padding
            base_y = border_width + padding
            
            # Processar cada bloco
            for block_idx in range(num_blocks):
                block_x = base_x + block_idx * (block_width + grid_gap) + block_padding
                block_y_start = base_y + block_header_height + bubble_header_height
                
                # Processar questões do bloco
                for q_in_block in range(1, 13):
                    question_num = block_idx * questions_per_block + q_in_block
                    if question_num > num_questions:
                        break
                    
                    # Calcular Y da questão
                    question_y = block_y_start + (q_in_block - 1) * answer_row_height
                    
                    # Calcular posições X das alternativas
                    alt_x_base = block_x + question_num_width
                    
                    # Processar cada alternativa (A, B, C, D)
                    for alt_idx in range(4):
                        alt = chr(65 + alt_idx)  # A, B, C, D
                        
                        # Calcular posição X da bolha
                        bubble_x = alt_x_base + alt_idx * (bubble_size + bubble_gap)
                        bubble_y = question_y
                        
                        # Validar coordenadas
                        if bubble_x < 0 or bubble_y < 0 or bubble_x + bubble_size > w or bubble_y + bubble_size > h:
                            continue
                        
                        coordinates.append({
                            'question': question_num,
                            'alternative': alt,
                            'x': int(bubble_x),
                            'y': int(bubble_y),
                            'width': bubble_size,
                            'height': bubble_size
                        })
            
            print(f"✅ {len(coordinates)} coordenadas calculadas")
            if self.debug and coordinates:
                print(f"   Exemplo Q1A: ({coordinates[0]['x']}, {coordinates[0]['y']}) - {coordinates[0]['width']}x{coordinates[0]['height']}")
            
            return coordinates
            
        except Exception as e:
            logging.error(f"Erro ao calcular coordenadas: {str(e)}")
            import traceback
            logging.error(traceback.format_exc())
            return []
    
    def _detect_bubbles(self, aligned_img: np.ndarray, coordinates: List[Dict], num_questions: int) -> Dict[int, str]:
        """
        Detecta bolhas preenchidas usando o mesmo método do projeto.py
        
        Método:
        1. Aplicar blur gaussiano
        2. Threshold adaptativo invertido
        3. Morfologia OPEN
        4. Para cada bolha: criar máscara circular e contar pixels brancos
        5. Se >= 70% pixels brancos = preenchida
        
        Args:
            aligned_img: Imagem retificada
            coordinates: Lista de coordenadas das bolhas
            num_questions: Número total de questões
        
        Returns:
            Dict {questão: resposta_detectada}
        """
        try:
            # Converter para grayscale
            if len(aligned_img.shape) == 3:
                gray = cv2.cvtColor(aligned_img, cv2.COLOR_BGR2GRAY)
            else:
                gray = aligned_img.copy()
            
            # Aplicar blur gaussiano (mesmo do projeto.py)
            borrada = cv2.GaussianBlur(gray, (5, 5), 0)
            
            # Threshold adaptativo invertido (mesmo do projeto.py)
            binario = cv2.adaptiveThreshold(borrada, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                           cv2.THRESH_BINARY_INV, 11, 2)
            
            # Aplicar morfologia OPEN para limpar ruído (mesmo do projeto.py)
            kernel = np.ones((3, 3), np.uint8)
            opening = cv2.morphologyEx(binario, cv2.MORPH_OPEN, kernel)
            
            if self.debug:
                debug_path = os.path.join(self.debug_dir, f"binary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
                cv2.imwrite(debug_path, opening)
                print(f"💾 Imagem binária salva: {debug_path}")
            
            # Agrupar coordenadas por questão
            questions_data = {}
            for coord in coordinates:
                q = coord['question']
                if q not in questions_data:
                    questions_data[q] = []
                questions_data[q].append(coord)
            
            detected_answers = {}
            
            # Processar cada questão
            for question_num in range(1, num_questions + 1):
                if question_num not in questions_data:
                    continue
                
                question_coords = questions_data[question_num]
                fill_ratios = {}
                
                # Verificar cada alternativa
                for coord in question_coords:
                    alt = coord['alternative']
                    x = coord['x']
                    y = coord['y']
                    w = coord['width']
                    h = coord['height']
                    
                    # Validar coordenadas
                    img_h, img_w = opening.shape[:2]
                    if x < 0 or y < 0 or x + w > img_w or y + h > img_h:
                        fill_ratios[alt] = 0.0
                        continue
                    
                    # Extrair ROI da bolha (mesmo do projeto.py)
                    interesse = opening[y:y + h, x:x + w]
                    
                    if interesse.size == 0:
                        fill_ratios[alt] = 0.0
                        continue
                    
                    # Criar máscara circular (mesmo do projeto.py)
                    mascara = np.zeros((h, w), dtype=np.uint8)
                    centro_x = w // 2
                    centro_y = h // 2
                    raio = min(w, h) // 2
                    cv2.circle(mascara, (centro_x, centro_y), raio, 255, -1)
                    
                    # Aplicar máscara e contar pixels brancos (mesmo do projeto.py)
                    interesse_mascarado = cv2.bitwise_and(interesse, interesse, mask=mascara)
                    total_pixels = cv2.countNonZero(mascara)
                    pixels_brancos = cv2.countNonZero(interesse_mascarado)
                    porcentagem_branco = (pixels_brancos / total_pixels * 100) if total_pixels > 0 else 0.0
                    
                    fill_ratios[alt] = porcentagem_branco / 100.0
                    
                    if self.debug and question_num <= 2:
                        print(f"   Q{question_num}{alt}: {porcentagem_branco:.1f}% preenchido ({pixels_brancos}/{total_pixels} pixels brancos)")
                
                # Escolher alternativa com maior fill ratio
                if fill_ratios:
                    max_alt = max(fill_ratios, key=fill_ratios.get)
                    max_ratio = fill_ratios[max_alt]
                    
                    if max_ratio >= self.BUBBLE_FILL_THRESHOLD:
                        detected_answers[question_num] = max_alt
                        if self.debug or question_num <= 5:
                            print(f"   ✅ Q{question_num}: {max_alt} ({max_ratio:.1%})")
                    else:
                        if self.debug:
                            print(f"   ⚪ Q{question_num}: Nenhuma acima do threshold ({max_ratio:.1%} < {self.BUBBLE_FILL_THRESHOLD:.1%})")
            
            return detected_answers
            
        except Exception as e:
            logging.error(f"Erro ao detectar bolhas: {str(e)}")
            import traceback
            logging.error(traceback.format_exc())
            return {}
    
    def _generate_debug_image(self, aligned_img: np.ndarray, coordinates: List[Dict],
                             detected_answers: Dict[int, str], answer_key: Dict[int, str],
                             test_id: str, student_id: str) -> None:
        """
        Gera imagem de debug mostrando as detecções
        """
        try:
            debug_img = aligned_img.copy()
            
            # Garantir que é BGR
            if len(debug_img.shape) == 2:
                debug_img = cv2.cvtColor(debug_img, cv2.COLOR_GRAY2BGR)
            
            # Desenhar cada bolha
            for coord in coordinates:
                question_num = coord['question']
                alt = coord['alternative']
                x = coord['x']
                y = coord['y']
                w = coord['width']
                h = coord['height']
                
                # Determinar cor baseado no resultado
                detected_answer = detected_answers.get(question_num)
                correct_answer = answer_key.get(question_num, '')
                
                if detected_answer == alt:
                    # Bolha detectada como marcada
                    if alt == correct_answer:
                        color = (0, 255, 0)  # Verde - correta
                    else:
                        color = (0, 0, 255)  # Vermelho - incorreta
                else:
                    # Bolha não detectada
                    if alt == correct_answer:
                        color = (0, 165, 255)  # Laranja - deveria estar marcada
                    else:
                        color = (128, 128, 128)  # Cinza - não marcada (ok)
                
                # Desenhar retângulo
                cv2.rectangle(debug_img, (x, y), (x + w, y + h), color, 2)
                
                # Desenhar texto (apenas para primeiras questões)
                if question_num <= 10:
                    text = f"Q{question_num}{alt}"
                    cv2.putText(debug_img, text, (x, y - 2),
                              cv2.FONT_HERSHEY_SIMPLEX, 0.3, color, 1)
            
            # Adicionar informações no topo
            info_text = [
                f"Test ID: {test_id[:8] if test_id else 'N/A'}...",
                f"Student ID: {student_id[:8] if student_id else 'N/A'}...",
                f"Detectadas: {len(detected_answers)}/{len(answer_key)}",
                f"Threshold: {self.BUBBLE_FILL_THRESHOLD:.0%}"
            ]
            
            # Adicionar espaço no topo
            h, w = debug_img.shape[:2]
            info_height = 80
            debug_final = np.ones((h + info_height, w, 3), dtype=np.uint8) * 255
            debug_final[info_height:, :] = debug_img
            
            y_offset = 20
            for i, text in enumerate(info_text):
                cv2.putText(debug_final, text, (10, y_offset + i * 18),
                          cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2)
                cv2.putText(debug_final, text, (10, y_offset + i * 18),
                          cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            # Salvar imagem
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            debug_filename = f"orm_debug_{test_id[:8] if test_id else 'unknown'}_{student_id[:8] if student_id else 'unknown'}_{timestamp}.png"
            debug_path = os.path.join(self.debug_dir, debug_filename)
            
            cv2.imwrite(debug_path, debug_final)
            print(f"💾 Imagem de debug salva: {debug_path}")
            
        except Exception as e:
            logging.error(f"Erro ao gerar imagem de debug: {str(e)}")
    
    def _calculate_score(self, detected_answers: Dict[int, str], 
                        answer_key: Dict[int, str]) -> Dict[str, Any]:
        """
        Calcula score comparando respostas detectadas com gabarito
        """
        try:
            total = len(answer_key)
            correct = 0
            
            for question_num, correct_answer in answer_key.items():
                detected = detected_answers.get(question_num)
                
                if detected and str(detected).upper() == str(correct_answer).upper():
                    correct += 1
            
            score = correct
            percentage = (correct / total * 100) if total > 0 else 0.0
            
            return {
                'score': score,
                'correct': correct,
                'total': total,
                'percentage': percentage
            }
            
        except Exception as e:
            logging.error(f"Erro ao calcular score: {str(e)}")
            return {'score': 0, 'correct': 0, 'total': 0, 'percentage': 0.0}
    
    def _save_answers_to_db(self, test_id: str, student_id: str, 
                           detected_answers: Dict[int, str],
                           answer_key: Dict[int, str]) -> List[Dict[str, Any]]:
        """
        Salva respostas detectadas no banco de dados
        """
        try:
            from app import db
            from app.models.studentAnswer import StudentAnswer
            from app.models.testQuestion import TestQuestion
            from datetime import datetime
            
            # Buscar questões da prova ordenadas
            test_questions = TestQuestion.query.filter_by(test_id=test_id).order_by(TestQuestion.order).all()
            
            if not test_questions:
                print(f"⚠️ Nenhuma questão encontrada para a prova {test_id}")
                return []
            
            saved_answers = []
            
            # Mapear questões por ordem sequencial
            questions_by_order = {}
            for idx, tq in enumerate(test_questions, start=1):
                questions_by_order[idx] = tq
            
            # Salvar cada resposta detectada
            for question_order, detected_answer in detected_answers.items():
                if question_order not in questions_by_order:
                    print(f"⚠️ Questão {question_order} não encontrada na prova")
                    continue
                
                test_question = questions_by_order[question_order]
                question_id = test_question.question_id
                correct_answer = answer_key.get(question_order, '')
                
                # Verificar se já existe resposta
                existing_answer = StudentAnswer.query.filter_by(
                    student_id=student_id,
                    test_id=test_id,
                    question_id=question_id
                ).first()
                
                if existing_answer:
                    # Atualizar resposta existente
                    existing_answer.answer = str(detected_answer)
                    existing_answer.answered_at = datetime.utcnow()
                    student_answer = existing_answer
                else:
                    # Criar nova resposta
                    student_answer = StudentAnswer(
                        student_id=student_id,
                        test_id=test_id,
                        question_id=question_id,
                        answer=str(detected_answer)
                    )
                    db.session.add(student_answer)
                
                # Verificar se está correta
                is_correct = (str(detected_answer).upper() == str(correct_answer).upper()) if correct_answer else None
                student_answer.is_correct = is_correct
                
                saved_answers.append({
                    'question_id': question_id,
                    'question_order': question_order,
                    'answer': str(detected_answer),
                    'correct_answer': correct_answer,
                    'is_correct': is_correct
                })
            
            # Commit das mudanças
            db.session.commit()
            
            print(f"💾 {len(saved_answers)} respostas salvas no banco de dados")
            
            return saved_answers
            
        except Exception as e:
            logging.error(f"Erro ao salvar respostas no banco: {str(e)}")
            import traceback
            logging.error(traceback.format_exc())
            db.session.rollback()
            return []
    
    def _calculate_evaluation_result(self, test_id: str, student_id: str) -> Optional[Dict[str, Any]]:
        """
        Calcula resultado da avaliação usando EvaluationResultService
        """
        try:
            from app.services.evaluation_result_service import EvaluationResultService
            import uuid
            
            # Gerar session_id temporário para correções físicas
            session_id = f"physical_correction_{uuid.uuid4().hex[:8]}"
            
            evaluation_result = EvaluationResultService.calculate_and_save_result(
                test_id=test_id,
                student_id=student_id,
                session_id=session_id
            )
            
            if evaluation_result:
                print(f"📊 Resultado calculado:")
                print(f"   Nota: {evaluation_result.get('grade', 'N/A')}")
                print(f"   Proficiência: {evaluation_result.get('proficiency', 'N/A')}")
                print(f"   Classificação: {evaluation_result.get('classification', 'N/A')}")
            
            return evaluation_result
            
        except Exception as e:
            logging.error(f"Erro ao calcular resultado da avaliação: {str(e)}")
            return None
    
    def _get_num_questions_from_db(self, test_id: str) -> Optional[int]:
        """
        Busca número de questões do banco de dados
        """
        try:
            from app.models.testQuestion import TestQuestion
            num = TestQuestion.query.filter_by(test_id=test_id).count()
            return num if num > 0 else None
        except Exception as e:
            logging.error(f"Erro ao buscar número de questões: {str(e)}")
            return None
    
    def _get_answer_key_from_db(self, test_id: str) -> Dict[int, str]:
        """
        Busca gabarito do banco de dados
        """
        try:
            from app.models.testQuestion import TestQuestion
            from app.models.question import Question
            
            test_questions = TestQuestion.query.filter_by(test_id=test_id).order_by(TestQuestion.order).all()
            
            answer_key = {}
            for idx, tq in enumerate(test_questions, start=1):
                question = Question.query.get(tq.question_id)
                if question and question.correct_answer:
                    answer_key[idx] = question.correct_answer
            
            return answer_key
            
        except Exception as e:
            logging.error(f"Erro ao buscar gabarito: {str(e)}")
            return {}


# Função de conveniência para uso direto
def processar_prova_orm(image_path: str = None, image_data: str = None, 
                        test_id: str = None, debug: bool = False) -> Dict[str, Any]:
    """
    Função de conveniência para processar uma prova usando o sistema OMR
    """
    sistema = SistemaORM(debug=debug)
    return sistema.process_exam(image_path=image_path, image_data=image_data)
