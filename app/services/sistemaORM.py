# -*- coding: utf-8 -*-
"""
Sistema OMR (Optical Mark Recognition) Robusto
Pipeline completo para correção de provas físicas

ETAPAS OBRIGATÓRIAS:
1. LOCALIZAÇÃO DO CONTORNO DA PÁGINA - Usa 4 marcadores fiduciais (quadrados pretos nos cantos)
2. CORREÇÃO DE PERSPECTIVA - warpPerspective usando os 4 marcadores
3. PADRONIZAÇÃO DO RECORTE - Recorta bloco 01 usando proporções relativas
4. DETECÇÃO DAS BOLINHAS - Apenas dentro do bloco 01 recortado
5. MAPEAMENTO DAS QUESTÕES - Sobre o bloco 01 retificado
6. SOBREPOSIÇÃO DE RESULTADOS - Desenha apenas no bloco 01

IMPORTANTE: A imagem SEMPRE possui 4 marcadores fiduciais nos cantos.
Se não detectar, ampliar busca e aumentar tolerância.
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
    Sistema OMR robusto para correção de provas físicas
    """
    
    # Threshold para detecção de bolinha preenchida
    BUBBLE_FILL_THRESHOLD = 0.45  # 45% de pixels brancos = preenchida
    
    # NOTA: Não usamos mais canvas A4 fixo - trabalhamos diretamente com a imagem
    
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
            coordinates_config: Configuração de coordenadas das bolhas
        
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
            
            # ETAPA 1: DETECÇÃO DA BORDA GROSSA AO REDOR DOS BLOCOS DE RESPOSTAS
            print(f"\n🔍 ETAPA 1: DETECTANDO BORDA GROSSA AO REDOR DOS BLOCOS...")
            border_corners = self._detect_answer_grid_border(img)
            if border_corners is None or len(border_corners) != 4:
                return {"success": False, "error": f"Borda dos blocos não detectada (encontrados: {len(border_corners) if border_corners else 0}/4 cantos)"}
            
            print(f"✅ Borda dos blocos detectada (4 cantos)")
            
            # ETAPA 2: CORREÇÃO DE PERSPECTIVA BASEADA NA BORDA
            print(f"\n🔍 ETAPA 2: APLICANDO CORREÇÃO DE PERSPECTIVA...")
            aligned = self._warp_perspective_border(img, border_corners)
            if aligned is None:
                return {"success": False, "error": "Falha ao aplicar correção de perspectiva"}
            
            print(f"✅ Perspectiva corrigida: {aligned.shape}")
            
            # Ler QR Code (após warp, antes do recorte)
            # Se não detectar na imagem retificada, tentar na imagem original
            qr_data = self._read_qr_code(aligned)
            if not qr_data:
                print(f"⚠️ QR Code não detectado na imagem retificada, tentando na imagem original...")
                qr_data = self._read_qr_code(img)
                if not qr_data:
                    return {"success": False, "error": "QR Code não detectado (tentou na imagem retificada e original)"}
            
            test_id = qr_data.get('test_id')
            student_id = qr_data.get('student_id')
            
            print(f"✅ QR Code lido: test_id={test_id[:8]}..., student_id={student_id[:8]}...")
            
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
            
            # ETAPA 3: RECORTAR ROI (REGION OF INTEREST) - ÁREA DENTRO DA BORDA DETECTADA
            print(f"\n🔍 ETAPA 3: RECORTANDO ROI (ÁREA DENTRO DA BORDA)...")
            
            # Detectar a borda novamente na imagem alinhada para recortar o ROI
            roi_border = self._detect_answer_grid_border(aligned)
            if roi_border is None:
                return {"success": False, "error": "Borda não detectada na imagem alinhada para recorte do ROI"}
            
            # Recortar a região dentro da borda (ROI)
            answer_grid_roi = self._extract_roi_from_border(aligned, roi_border)
            if answer_grid_roi is None:
                return {"success": False, "error": "Falha ao recortar ROI da área de respostas"}
            
            print(f"✅ ROI recortado: {answer_grid_roi.shape}")
            
            # Calcular coordenadas das bolhas diretamente no ROI
            if coordinates_config is None:
                coordinates_config = self._calculate_bubble_coordinates_in_roi(
                    answer_grid_roi, num_questions
                )
            
            # Usar answer_grid_roi como ROI para detecção
            roi_for_detection = answer_grid_roi
            questions_to_process = coordinates_config.get('num_questions', num_questions)
            
            print(f"✅ ROI preparado para detecção: {roi_for_detection.shape}")
            
            # ETAPA 4 e 5: DETECÇÃO DAS BOLINHAS E MAPEAMENTO (no ROI completo)
            print(f"\n🔍 ETAPA 4-5: DETECTANDO BOLINHAS NO ROI...")
            
            print(f"📊 Processando {questions_to_process} questões (de {num_questions} totais)")
            
            # Tentar primeiro detecção automática (sem coordenadas fixas)
            print(f"\n🎯 Tentando detecção AUTOMÁTICA (sem coordenadas fixas)...")
            auto_results = self._detect_bubbles_automatic(roi_for_detection, questions_to_process)
            auto_detected = auto_results.get('answers', {})
            
            # Se a detecção automática encontrou pelo menos algumas respostas, usar ela
            if len(auto_detected) >= questions_to_process * 0.5:  # Pelo menos 50% das questões
                print(f"✅ Detecção automática bem-sucedida: {len(auto_detected)} respostas detectadas")
                detected_answers = auto_detected
                fill_ratios_all = auto_results.get('fill_ratios', {})
            else:
                print(f"⚠️ Detecção automática encontrou apenas {len(auto_detected)} respostas, usando método com coordenadas...")
                # Usar método tradicional com coordenadas
                detection_results = self._detect_bubbles_calibrated(
                    roi_for_detection, coordinates_config, questions_to_process
                )
                detected_answers = detection_results.get('answers', {})
                fill_ratios_all = detection_results.get('fill_ratios', {})
                
                # Combinar resultados se a auto-detecção encontrou algumas respostas que o método tradicional não encontrou
                for q_num, alt in auto_detected.items():
                    if q_num not in detected_answers:
                        detected_answers[q_num] = alt
                        if q_num in auto_results.get('fill_ratios', {}):
                            fill_ratios_all[q_num] = auto_results['fill_ratios'][q_num]
                        print(f"   ➕ Adicionada detecção automática: Q{q_num}: {alt}")
            
            print(f"✅ Respostas detectadas: {len(detected_answers)}/{num_questions}")
            
            # ETAPA 6: SOBREPOSIÇÃO DE RESULTADOS (no ROI)
            if self.debug:
                self._generate_debug_image_block01(roi_for_detection, aligned, coordinates_config, detected_answers, fill_ratios_all, answer_key, test_id, student_id)
            
            # 10. Calcular score
            score_data = self._calculate_score(detected_answers, answer_key)
            
            # 11. Salvar respostas no banco de dados
            saved_answers = self._save_answers_to_db(test_id, student_id, detected_answers, answer_key)
            
            # 12. Calcular resultado da avaliação
            evaluation_result = self._calculate_evaluation_result(test_id, student_id)
            
            # 13. Montar resultado final
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
        Detecta a borda grossa preta ao redor dos blocos de respostas
        
        A borda é um retângulo grosso (5px) que envolve todos os blocos de questões.
        Este método detecta os 4 cantos dessa borda para correção de perspectiva.
        
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
            
            # Aplicar threshold invertido para detectar borda preta grossa
            # A borda tem 5px de espessura, então precisamos detectar linhas grossas
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            
            # Aplicar morfologia para unir linhas quebradas e destacar a borda grossa
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
            binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=2)
            
            # Encontrar contornos externos
            contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if not contours:
                print(f"❌ Nenhum contorno encontrado")
                return None
            
            # Procurar o maior contorno retangular (a borda dos blocos)
            # A borda deve ser grande o suficiente para envolver todos os blocos
            min_area = (w * h) * 0.1  # Pelo menos 10% da imagem
            max_area = (w * h) * 0.9   # No máximo 90% da imagem
            
            best_contour = None
            best_score = 0
            
            for contour in contours:
                area = cv2.contourArea(contour)
                
                # Filtrar por área
                if not (min_area <= area <= max_area):
                    continue
                
                # Aproximar contorno para retângulo
                epsilon = 0.02 * cv2.arcLength(contour, True)
                approx = cv2.approxPolyDP(contour, epsilon, True)
                
                # Deve ter 4 vértices (retângulo)
                if len(approx) != 4:
                    continue
                
                # Calcular bounding box
                x, y, w_rect, h_rect = cv2.boundingRect(contour)
                
                # Verificar se é aproximadamente retangular (não muito distorcido)
                aspect_ratio = w_rect / h_rect if h_rect > 0 else 0
                if aspect_ratio < 0.3 or aspect_ratio > 3.0:
                    continue
                
                # Score baseado em quão retangular é (solidity) e tamanho
                bbox_area = w_rect * h_rect
                solidity = area / bbox_area if bbox_area > 0 else 0
                
                # Preferir contornos mais retangulares e maiores
                score = solidity * area
                
                if score > best_score:
                    best_score = score
                    best_contour = approx
            
            if best_contour is None:
                print(f"❌ Borda dos blocos não encontrada")
                return None
            
            # Extrair os 4 cantos do retângulo detectado
            corners = best_contour.reshape(-1, 2).astype(np.float32)
            
            if len(corners) != 4:
                print(f"❌ Borda não tem 4 cantos (encontrados: {len(corners)})")
                return None
            
            # Ordenar cantos: TL, TR, BR, BL
            # Ordenar por Y (altura)
            corners_sorted_y = corners[np.argsort(corners[:, 1])]
            top = corners_sorted_y[:2]  # 2 pontos com menor Y (topo)
            bottom = corners_sorted_y[2:]  # 2 pontos com maior Y (fundo)
            
            # Ordenar top por X (esquerda, direita)
            top = top[np.argsort(top[:, 0])]
            # Ordenar bottom por X (esquerda, direita)
            bottom = bottom[np.argsort(bottom[:, 0])]
            
            # TL = top esquerdo, TR = top direito, BR = bottom direito, BL = bottom esquerdo
            ordered = np.array([top[0], top[1], bottom[1], bottom[0]], dtype=np.float32)
            
            print(f"✅ Borda detectada:")
            print(f"   TL: {ordered[0]}")
            print(f"   TR: {ordered[1]}")
            print(f"   BR: {ordered[2]}")
            print(f"   BL: {ordered[3]}")
            
            return ordered
            
        except Exception as e:
            logging.error(f"Erro ao detectar borda dos blocos: {str(e)}")
            print(f"❌ Erro ao detectar borda: {e}")
            return None
    
    def _detect_fiducial_markers(self, img: np.ndarray) -> Optional[np.ndarray]:
        """
        [DEPRECATED] Método antigo - mantido para compatibilidade
        Agora usamos _detect_answer_grid_border
        """
        try:
            # Converter para grayscale
            if len(img.shape) == 3:
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            else:
                gray = img.copy()
            
            h, w = gray.shape
            
            # Aplicar threshold invertido para detectar quadrados pretos
            _, binary = cv2.threshold(gray, 50, 255, cv2.THRESH_BINARY_INV)
            
            # Tentar diferentes thresholds e kernels para detectar os 4 marcadores
            thresholds = [50, 70, 80, 100, 120, 150]
            kernels = [None, (3, 3), (5, 5)]  # Sem kernel, com kernel 3x3, com kernel 5x5
            all_markers = []
            
            for kernel_size in kernels:
                gray_processed = gray.copy()
                
                # Aplicar morfologia se necessário
                if kernel_size:
                    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, kernel_size)
                    gray_processed = cv2.morphologyEx(gray_processed, cv2.MORPH_CLOSE, kernel)
                
                for thresh_val in thresholds:
                    _, binary = cv2.threshold(gray_processed, thresh_val, 255, cv2.THRESH_BINARY_INV)
                    
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
                        all_markers = markers
                        kernel_str = f"kernel {kernel_size}" if kernel_size else "sem kernel"
                        print(f"✅ {len(markers)} marcadores encontrados com threshold {thresh_val} ({kernel_str})")
                        break
                
                if len(all_markers) >= 4:
                    break
            
            if len(all_markers) < 4:
                print(f"⚠️ Apenas {len(all_markers)} marcadores encontrados, tentando ampliar busca...")
                # Ampliar busca com tolerâncias maiores
                min_area = 30
                max_area = 800
                min_size = 5
                max_size = 40
                
                _, binary = cv2.threshold(gray, 80, 255, cv2.THRESH_BINARY_INV)
                contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                for contour in contours:
                    area = cv2.contourArea(contour)
                    if not (min_area <= area <= max_area):
                        continue
                    
                    x, y, w_rect, h_rect = cv2.boundingRect(contour)
                    if not (min_size <= w_rect <= max_size and min_size <= h_rect <= max_size):
                        continue
                    
                    center_x = x + w_rect // 2
                    center_y = y + h_rect // 2
                    
                    all_markers.append({
                        'center': (center_x, center_y),
                        'bbox': (x, y, w_rect, h_rect),
                        'area': area
                    })
                    
                    if len(all_markers) >= 4:
                        break
            
            if len(all_markers) < 4:
                print(f"❌ Não foi possível detectar 4 marcadores (encontrados: {len(all_markers)})")
                return None
            
            # Ordenar marcadores: TL, TR, BR, BL
            pts = np.array([m['center'] for m in all_markers])
            
            # DEBUG: Mostrar pontos antes da ordenação
            if self.debug:
                print(f"🔍 Pontos antes da ordenação:")
                for i, pt in enumerate(pts):
                    print(f"   P{i}: ({pt[0]:.1f}, {pt[1]:.1f})")
            
            # Ordenar por Y (altura)
            pts_sorted_y = pts[np.argsort(pts[:, 1])]
            top = pts_sorted_y[:2]  # 2 pontos com menor Y (topo)
            bottom = pts_sorted_y[2:]  # 2 pontos com maior Y (fundo)
            
            # Ordenar top por X (esquerda, direita)
            top = top[np.argsort(top[:, 0])]
            # Ordenar bottom por X (esquerda, direita)
            bottom = bottom[np.argsort(bottom[:, 0])]
            
            # TL = top esquerdo, TR = top direito, BR = bottom direito, BL = bottom esquerdo
            ordered = np.array([top[0], top[1], bottom[1], bottom[0]], dtype=np.float32)
            
            print(f"✅ 4 marcadores ordenados:")
            print(f"   TL: {ordered[0]} (top esquerdo)")
            print(f"   TR: {ordered[1]} (top direito)")
            print(f"   BR: {ordered[2]} (bottom direito)")
            print(f"   BL: {ordered[3]} (bottom esquerdo)")
            
            # Validação: Verificar se a ordenação faz sentido
            # TL deve ter menor X e menor Y que TR
            # BL deve ter menor X e maior Y que BR
            if ordered[0][0] >= ordered[1][0] or ordered[0][1] >= ordered[1][1]:
                print(f"⚠️ AVISO: Ordenação suspeita - TL não está à esquerda/acima de TR")
            if ordered[3][0] >= ordered[2][0] or ordered[3][1] <= ordered[2][1]:
                print(f"⚠️ AVISO: Ordenação suspeita - BL não está à esquerda/abaixo de BR")
            
            return ordered
            
        except Exception as e:
            logging.error(f"Erro ao detectar marcadores fiduciais: {str(e)}")
            return None
    
    def _warp_perspective_border(self, img: np.ndarray, border_corners: np.ndarray) -> Optional[np.ndarray]:
        """
        ETAPA 2: Aplica correção de perspectiva usando a borda detectada ao redor dos blocos
        
        IMPORTANTE: Usa tamanho FIXO A4 (200 DPI) para garantir alinhamento correto das coordenadas.
        
        Justificativa:
        - A detecção das bolhas depende de coordenadas de calibração fixas
        - Cada imagem warpada deve sempre sair com a mesma resolução exata
        - Se o tamanho variar, as bolhas ficam "escorregadas" para cima/baixo
        - O warp dinâmico distorce a relação entre coordenadas → ERRADO
        - Warp com tamanho fixo A4 → SEMPRE alinhamento correto
        
        Args:
            img: Imagem original
            border_corners: 4 cantos da borda detectada (TL, TR, BR, BL)
        
        Returns:
            Imagem retificada (retangular, sem inclinação) ou None
        """
        try:
            # Cantos da borda (TL, TR, BR, BL)
            tl, tr, br, bl = border_corners.astype(np.float32)
            
            # TAMANHO FIXO DA FOLHA A4 (200 DPI)
            # Este tamanho fixo garante que as coordenadas das bolhas sempre estejam alinhadas
            TARGET_WIDTH = 1654   # A4 200 DPI
            TARGET_HEIGHT = 2339  # A4 200 DPI
            
            # Pontos de destino (cantos da folha A4)
            dst_pts = np.array([
                [0, 0],                                    # TL
                [TARGET_WIDTH - 1, 0],                    # TR
                [TARGET_WIDTH - 1, TARGET_HEIGHT - 1],    # BR
                [0, TARGET_HEIGHT - 1]                    # BL
            ], dtype=np.float32)
            
            # Calcular matriz de transformação
            M = cv2.getPerspectiveTransform(border_corners, dst_pts)
            
            # Aplicar warp com tamanho fixo
            aligned = cv2.warpPerspective(
                img,
                M,
                (TARGET_WIDTH, TARGET_HEIGHT),
                flags=cv2.INTER_LINEAR,
                borderMode=cv2.BORDER_CONSTANT,
                borderValue=(255, 255, 255)
            )
            
            # Verificar se a imagem foi gerada corretamente
            if aligned.shape[0] < 100 or aligned.shape[1] < 100:
                print(f"❌ Imagem retificada muito pequena: {aligned.shape}")
                return None
            
            print(f"✅ Imagem retificada: {aligned.shape} (A4 fixo 200 DPI)")
            
            if self.debug:
                debug_path = os.path.join(self.debug_dir, f"warped_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
                cv2.imwrite(debug_path, aligned)
                print(f"💾 Imagem retificada salva: {debug_path}")
            
            return aligned
            
        except Exception as e:
            logging.error(f"Erro ao aplicar warp: {str(e)}")
            print(f"❌ Warp error: {e}")
            return None
    
    def _warp_perspective_markers(self, img: np.ndarray, markers: np.ndarray) -> Optional[np.ndarray]:
        """
        [DEPRECATED] Método antigo - mantido para compatibilidade
        Agora usamos _warp_perspective_border
        """
        return self._warp_perspective_border(img, markers)
    
    def _extract_roi_from_border(self, aligned_img: np.ndarray, border_corners: np.ndarray) -> Optional[np.ndarray]:
        """
        Recorta a região dentro da borda detectada (ROI - Region of Interest)
        
        Args:
            aligned_img: Imagem alinhada
            border_corners: 4 cantos da borda (TL, TR, BR, BL)
        
        Returns:
            Imagem do ROI recortado ou None
        """
        try:
            # Calcular bounding box da borda
            x_coords = border_corners[:, 0]
            y_coords = border_corners[:, 1]
            
            left = int(np.min(x_coords))
            right = int(np.max(x_coords))
            top = int(np.min(y_coords))
            bottom = int(np.max(y_coords))
            
            # Adicionar pequena margem para garantir que a borda não seja incluída
            margin = 5
            left += margin
            right -= margin
            top += margin
            bottom -= margin
            
            # Validar coordenadas
            h, w = aligned_img.shape[:2]
            left = max(0, left)
            top = max(0, top)
            right = min(w, right)
            bottom = min(h, bottom)
            
            if top >= bottom or left >= right:
                print(f"❌ Coordenadas inválidas do ROI: top={top}, bottom={bottom}, left={left}, right={right}")
                return None
            
            # Recortar ROI
            roi = aligned_img[top:bottom, left:right]
            
            if roi.size == 0:
                print(f"❌ ROI vazio após recorte")
                return None
            
            print(f"✅ ROI recortado: {roi.shape} (de {aligned_img.shape})")
            print(f"   Coordenadas: top={top}, bottom={bottom}, left={left}, right={right}")
            
            if self.debug:
                debug_path = os.path.join(self.debug_dir, f"roi_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
                cv2.imwrite(debug_path, roi)
                print(f"💾 ROI salvo: {debug_path}")
            
            return roi
            
        except Exception as e:
            logging.error(f"Erro ao recortar ROI: {str(e)}")
            return None
    
    def _extract_block01(self, aligned_img: np.ndarray) -> Optional[np.ndarray]:
        """
        ETAPA 3: Recorta o bloco 01 usando proporções relativas
        
        Bloco 01:
        - top = 0.58 * altura
        - bottom = 0.92 * altura
        - left = 0.05 * largura
        - right = 0.40 * largura
        
        Returns:
            Imagem do bloco 01 recortado ou None
        """
        try:
            h, w = aligned_img.shape[:2]
            
            # Calcular coordenadas do bloco 01
            top = int(0.58 * h)
            bottom = int(0.92 * h)
            left = int(0.05 * w)
            right = int(0.40 * w)
            
            # Validar coordenadas
            if top >= bottom or left >= right:
                print(f"❌ Coordenadas inválidas do bloco 01: top={top}, bottom={bottom}, left={left}, right={right}")
                return None
            
            # Recortar bloco 01
            block01 = aligned_img[top:bottom, left:right]
            
            if block01.size == 0:
                print(f"❌ Bloco 01 vazio após recorte")
                return None
            
            print(f"✅ Bloco 01 recortado: {block01.shape} (de {aligned_img.shape})")
            print(f"   Coordenadas: top={top}, bottom={bottom}, left={left}, right={right}")
            
            if self.debug:
                debug_path = os.path.join(self.debug_dir, f"block01_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
                cv2.imwrite(debug_path, block01)
                print(f"💾 Bloco 01 salvo: {debug_path}")
            
            return block01
            
        except Exception as e:
            logging.error(f"Erro ao recortar bloco 01: {str(e)}")
            return None
    
    def _read_qr_code(self, aligned_img: np.ndarray) -> Optional[Dict[str, str]]:
        """
        Lê QR Code da imagem alinhada usando pyzbar
        
        Tenta múltiplas estratégias: diferentes regiões, pré-processamentos, escalas
        
        Returns:
            Dict com test_id e student_id ou None
        """
        try:
            # Converter para grayscale se necessário
            if len(aligned_img.shape) == 3:
                gray = cv2.cvtColor(aligned_img, cv2.COLOR_BGR2GRAY)
            else:
                gray = aligned_img.copy()
            
            h, w = gray.shape
            print(f"🔍 Tentando detectar QR Code em imagem: {w}x{h}px")
            
            # ESTRATÉGIA 1: Região superior direita (onde geralmente está o QR code)
            roi_size = min(w, h) // 3
            if roi_size > 0:
                roi = gray[0:roi_size, w-roi_size:w]
                qr_codes = pyzbar_decode(roi)
                if qr_codes:
                    print(f"✅ QR Code detectado na região superior direita")
                    qr_data = qr_codes[0].data.decode('utf-8')
                    return self._parse_qr_data(qr_data)
            
            # ESTRATÉGIA 2: Região superior esquerda
            if roi_size > 0:
                roi = gray[0:roi_size, 0:roi_size]
                qr_codes = pyzbar_decode(roi)
                if qr_codes:
                    print(f"✅ QR Code detectado na região superior esquerda")
                    qr_data = qr_codes[0].data.decode('utf-8')
                    return self._parse_qr_data(qr_data)
            
            # ESTRATÉGIA 3: Imagem inteira
            qr_codes = pyzbar_decode(gray)
            if qr_codes:
                print(f"✅ QR Code detectado na imagem inteira")
                qr_data = qr_codes[0].data.decode('utf-8')
                return self._parse_qr_data(qr_data)
            
            # ESTRATÉGIA 4: Pré-processamento com threshold
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            qr_codes = pyzbar_decode(binary)
            if qr_codes:
                print(f"✅ QR Code detectado após threshold")
                qr_data = qr_codes[0].data.decode('utf-8')
                return self._parse_qr_data(qr_data)
            
            # ESTRATÉGIA 5: Upscale se imagem muito pequena
            if w < 500 or h < 500:
                print(f"⚠️ Imagem pequena ({w}x{h}), tentando upscale...")
                scale_factor = 2.0
                gray_upscaled = cv2.resize(gray, None, fx=scale_factor, fy=scale_factor, interpolation=cv2.INTER_CUBIC)
                qr_codes = pyzbar_decode(gray_upscaled)
                if qr_codes:
                    print(f"✅ QR Code detectado após upscale")
                    qr_data = qr_codes[0].data.decode('utf-8')
                    return self._parse_qr_data(qr_data)
            
            # ESTRATÉGIA 6: Usar cv2.QRCodeDetector como fallback
            try:
                qr_detector = cv2.QRCodeDetector()
                retval, decoded_info, points, straight_qrcode = qr_detector.detectAndDecodeMulti(gray)
                
                if retval and decoded_info and len(decoded_info) > 0:
                    qr_data = decoded_info[0]
                    if qr_data:
                        print(f"✅ QR Code detectado com cv2.QRCodeDetector")
                        return self._parse_qr_data(qr_data)
            except Exception as e:
                if self.debug:
                    print(f"⚠️ Erro ao usar cv2.QRCodeDetector: {str(e)}")
            
            print(f"❌ QR Code não detectado após todas as tentativas")
            return None
            
        except Exception as e:
            logging.error(f"Erro ao ler QR Code: {str(e)}")
            import traceback
            logging.error(traceback.format_exc())
            return None
            
    def _parse_qr_data(self, qr_data: str) -> Optional[Dict[str, str]]:
        """
        Parse dos dados do QR Code
        
        Args:
            qr_data: String com dados do QR Code
        
        Returns:
            Dict com test_id e student_id
        """
        try:
            print(f"📱 QR Code detectado: {qr_data[:50]}...")
            
            # Tentar parsear como JSON
            try:
                qr_json = json.loads(qr_data)
                return {
                    'test_id': qr_json.get('test_id'),
                    'student_id': qr_json.get('student_id')
                }
            except json.JSONDecodeError:
                # Se não for JSON, tratar como string simples (student_id)
                return {
                    'test_id': None,
                    'student_id': qr_data.strip()
                }
        except Exception as e:
            logging.error(f"Erro ao parsear dados do QR Code: {str(e)}")
            return None
            
        except Exception as e:
            logging.error(f"Erro ao ler QR Code: {str(e)}")
            import traceback
            logging.error(traceback.format_exc())
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
        
        Returns:
            Dict {questão: resposta_correta}
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
    
    def _calibrate_with_reference_template(self, aligned_img: np.ndarray, 
                                          test_id: str, num_questions: int) -> Optional[Dict[str, Any]]:
        """
        ETAPA 3: Calibra coordenadas usando gabarito de referência
        
        Args:
            aligned_img: Imagem física alinhada
            test_id: ID da prova
            num_questions: Número total de questões
        
        Returns:
            Dict com coordenadas calibradas ou None se falhar
        """
        try:
            from app.services.answer_sheet_reference_generator import AnswerSheetReferenceGenerator
            
            print(f"📋 Carregando gabarito de referência para {test_id}...")
            
            # Gerar gabarito de referência
            generator = AnswerSheetReferenceGenerator()
            
            # Obter título da prova
            from app.models.test import Test
            test = Test.query.get(test_id)
            test_title = test.title if test else None
            
            # Gerar QR code de referência
            qr_code_base64 = generator.get_reference_qr_code(test_id)
            
            # Gerar imagem do gabarito
            reference_img = generator.generate_reference_sheet_image(
                test_id, num_questions, test_title, qr_code_base64, dpi=300
            )
            
            if reference_img is None:
                print(f"❌ Falha ao gerar gabarito de referência")
                return None
            
            print(f"✅ Gabarito de referência gerado: {reference_img.shape}")
            
            # Detectar marcadores no gabarito
            ref_markers = generator.get_reference_markers(reference_img)
            if ref_markers is None:
                print(f"❌ Marcadores não detectados no gabarito")
                return None
            
            # Detectar marcadores na imagem física
            phys_markers = self._detect_answer_grid_border(aligned_img)
            if phys_markers is None:
                print(f"❌ Marcadores não detectados na imagem física")
                return None
            
            # Alinhar imagem física com gabarito usando marcadores
            aligned_to_ref = self._align_to_reference_template(
                aligned_img, phys_markers, reference_img, ref_markers
            )
            
            if aligned_to_ref is None:
                print(f"❌ Falha ao alinhar imagem física com gabarito")
                return None
            
            print(f"✅ Imagem física alinhada com gabarito: {aligned_to_ref.shape}")
            
            # Extrair coordenadas reais das bolhas do gabarito
            ref_coordinates = generator.get_reference_bubble_coordinates(
                reference_img, num_questions, block_num=1
            )
            
            if not ref_coordinates:
                print(f"❌ Falha ao extrair coordenadas do gabarito")
                return None
            
            print(f"✅ {len(ref_coordinates)} coordenadas extraídas do gabarito")
            
            # Ajustar coordenadas para o bloco 01 recortado
            # Calcular posição do bloco 01 no gabarito
            block01_coords = self._calculate_block01_position_in_reference(reference_img)
            
            if block01_coords is None:
                print(f"❌ Falha ao calcular posição do bloco 01 no gabarito")
                return None
            
            # Converter coordenadas absolutas do gabarito para relativas ao bloco 01
            calibrated_coords = []
            for coord in ref_coordinates:
                # Ajustar coordenadas para serem relativas ao bloco 01
                x_rel = coord['x'] - block01_coords['left']
                y_rel = coord['y'] - block01_coords['top']
                
                # Validar que está dentro do bloco 01
                if (0 <= x_rel <= block01_coords['width'] and 
                    0 <= y_rel <= block01_coords['height']):
                    calibrated_coords.append({
                        'question': coord['question'],
                        'alternative': coord['alternative'],
                        'x': int(x_rel),
                        'y': int(y_rel),
                        'width': coord['width'],
                        'height': coord['height']
                    })
            
            print(f"✅ {len(calibrated_coords)} coordenadas calibradas para o bloco 01")
            
            # Salvar imagem de debug se habilitado
            if self.debug:
                debug_path = os.path.join(
                    self.debug_dir, 
                    f"calibrated_{test_id[:8]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                )
                # Criar imagem comparativa
                h1, w1 = aligned_to_ref.shape[:2]
                h2, w2 = reference_img.shape[:2]
                h_max = max(h1, h2)
                w_combined = w1 + w2 + 50
                comparison = np.ones((h_max, w_combined, 3), dtype=np.uint8) * 255
                comparison[:h1, :w1] = aligned_to_ref
                comparison[:h2, w1+50:w1+50+w2] = reference_img
                cv2.imwrite(debug_path, comparison)
                print(f"💾 Imagem de calibração salva: {debug_path}")
            
            return {
                'coordinates': calibrated_coords,
                'bubble_size': 18,  # Tamanho padrão das bolhas
                'num_questions': min(num_questions, 12),
                'block01_coords': block01_coords
            }
            
        except Exception as e:
            logging.error(f"Erro na calibração com gabarito: {str(e)}")
            import traceback
            logging.error(traceback.format_exc())
            return None
    
    def _align_to_reference_template(self, phys_img: np.ndarray, phys_markers: np.ndarray,
                                    ref_img: np.ndarray, ref_markers: np.ndarray) -> Optional[np.ndarray]:
        """
        Alinha imagem física com gabarito de referência usando marcadores fiduciais
        
        Args:
            phys_img: Imagem física
            phys_markers: Marcadores da imagem física (TL, TR, BR, BL)
            ref_img: Gabarito de referência
            ref_markers: Marcadores do gabarito (TL, TR, BR, BL)
        
        Returns:
            Imagem física alinhada ao gabarito ou None
        """
        try:
            # Calcular matriz de transformação
            M = cv2.getPerspectiveTransform(phys_markers, ref_markers)
            
            # Aplicar transformação
            h, w = ref_img.shape[:2]
            aligned = cv2.warpPerspective(
                phys_img,
                M,
                (w, h),
                flags=cv2.INTER_LINEAR,
                borderMode=cv2.BORDER_CONSTANT,
                borderValue=(255, 255, 255)
            )
            
            return aligned
            
        except Exception as e:
            logging.error(f"Erro ao alinhar com gabarito: {str(e)}")
            return None
    
    def _calculate_block01_position_in_reference(self, reference_img: np.ndarray) -> Optional[Dict[str, int]]:
        """
        Calcula posição do bloco 01 no gabarito de referência
        
        Args:
            reference_img: Imagem do gabarito
        
        Returns:
            Dict com top, bottom, left, right do bloco 01 ou None
        """
        try:
            h, w = reference_img.shape[:2]
            
            # Usar proporções conhecidas do template
            # Bloco 01 está aproximadamente em:
            # top = 0.58 * altura
            # bottom = 0.92 * altura
            # left = 0.05 * largura
            # right = 0.40 * largura
            
            top = int(0.58 * h)
            bottom = int(0.92 * h)
            left = int(0.05 * w)
            right = int(0.40 * w)
            
            return {
                'top': top,
                'bottom': bottom,
                'left': left,
                'right': right,
                'width': right - left,
                'height': bottom - top
            }
            
        except Exception as e:
            logging.error(f"Erro ao calcular posição do bloco 01: {str(e)}")
            return None
    
    def _extract_block01_from_calibrated(self, aligned_img: np.ndarray, 
                                        coordinates_config: Dict) -> Optional[np.ndarray]:
        """
        Recorta bloco 01 usando coordenadas calibradas
        
        Args:
            aligned_img: Imagem alinhada
            coordinates_config: Configuração de coordenadas calibradas
        
        Returns:
            Imagem do bloco 01 recortado ou None
        """
        try:
            block01_coords = coordinates_config.get('block01_coords')
            if block01_coords is None:
                # Fallback para método tradicional
                return self._extract_block01(aligned_img)
            
            top = block01_coords['top']
            bottom = block01_coords['bottom']
            left = block01_coords['left']
            right = block01_coords['right']
            
            h, w = aligned_img.shape[:2]
            
            # Validar coordenadas
            if top < 0 or left < 0 or bottom > h or right > w:
                print(f"⚠️ Coordenadas do bloco 01 fora dos limites, usando método tradicional")
                return self._extract_block01(aligned_img)
            
            block01 = aligned_img[top:bottom, left:right]
            
            if block01.size == 0:
                print(f"❌ Bloco 01 vazio após recorte")
                return None
            
            return block01
            
        except Exception as e:
            logging.error(f"Erro ao recortar bloco 01 calibrado: {str(e)}")
            return None
    
    def _detect_bubbles_calibrated(self, block01_img: np.ndarray, coordinates_config: Dict,
                                  num_questions: int) -> Dict[str, Any]:
        """
        Detecta bolhas usando coordenadas calibradas com múltiplas estratégias
        
        Args:
            block01_img: Imagem do bloco 01
            coordinates_config: Configuração de coordenadas calibradas
            num_questions: Número de questões
        
        Returns:
            Dict com 'answers' e 'fill_ratios'
        """
        try:
            coordinates = coordinates_config.get('coordinates', [])
            if not coordinates:
                # Fallback para método tradicional
                return self._detect_bubbles_block01(block01_img, coordinates_config, num_questions)
            
            # Testar múltiplas estratégias de threshold
            strategies = [
                ('adaptive_inv', self._get_binary_adaptive_inv),
                ('adaptive', self._get_binary_adaptive),
                ('otsu_inv', self._get_binary_otsu_inv),
                ('otsu', self._get_binary_otsu),
                ('fixed_inv', self._get_binary_fixed_inv),
                ('fixed', self._get_binary_fixed)
            ]
            
            best_results = None
            best_score = 0
            
            for strategy_name, strategy_func in strategies:
                try:
                    binary = strategy_func(block01_img)
                    results = self._detect_bubbles_with_binary(
                        block01_img, binary, coordinates, num_questions
                    )
                    
                    # Calcular score (número de detecções com fill ratio > threshold)
                    score = sum(1 for q, ratios in results.get('fill_ratios', {}).items()
                               if ratios and max(ratios.values()) >= self.BUBBLE_FILL_THRESHOLD)
                    
                    if score > best_score:
                        best_score = score
                        best_results = results
                        print(f"   ✅ Estratégia '{strategy_name}': {score} detecções")
                    else:
                        print(f"   ⚪ Estratégia '{strategy_name}': {score} detecções")
                        
                except Exception as e:
                    if self.debug:
                        print(f"   ❌ Estratégia '{strategy_name}' falhou: {str(e)}")
                    continue
            
            if best_results is None:
                print(f"❌ Todas as estratégias falharam, usando método tradicional")
                return self._detect_bubbles_block01(block01_img, coordinates_config, num_questions)
            
            return best_results
            
        except Exception as e:
            logging.error(f"Erro ao detectar bolhas calibradas: {str(e)}")
            return self._detect_bubbles_block01(block01_img, coordinates_config, num_questions)
    
    def _get_binary_adaptive_inv(self, img: np.ndarray) -> np.ndarray:
        """Threshold adaptativo invertido"""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        gray_norm = clahe.apply(gray)
        return cv2.adaptiveThreshold(gray_norm, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                     cv2.THRESH_BINARY_INV, 11, 2)
    
    def _get_binary_adaptive(self, img: np.ndarray) -> np.ndarray:
        """Threshold adaptativo normal"""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        gray_norm = clahe.apply(gray)
        return cv2.adaptiveThreshold(gray_norm, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                     cv2.THRESH_BINARY, 11, 2)
    
    def _get_binary_otsu_inv(self, img: np.ndarray) -> np.ndarray:
        """OTSU invertido"""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        return binary
    
    def _get_binary_otsu(self, img: np.ndarray) -> np.ndarray:
        """OTSU normal"""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return binary
    
    def _get_binary_fixed_inv(self, img: np.ndarray) -> np.ndarray:
        """Threshold fixo invertido"""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
        _, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY_INV)
        return binary
    
    def _get_binary_fixed(self, img: np.ndarray) -> np.ndarray:
        """Threshold fixo normal"""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
        _, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
        return binary
    
    def _adaptive_line_search(self, block01_img: np.ndarray, question_coords: List[Dict],
                              question_num: int) -> Optional[Tuple[str, float]]:
        """
        Busca adaptativa por linha - busca todas as bolhas na linha e mapeia para alternativas
        
        Estratégia:
        1. Buscar todas as bolhas preenchidas na região Y da questão
        2. Mapear posições reais para alternativas (A, B, C, D) baseado na posição X
        3. Retornar a alternativa com maior fill ratio
        
        Args:
            block01_img: Imagem do ROI/bloco
            question_coords: Lista de coordenadas das alternativas da questão
            question_num: Número da questão
        
        Returns:
            Tupla (alternativa, fill_ratio) da melhor detecção ou None
        """
        try:
            block_h, block_w = block01_img.shape[:2]
            
            # Converter para grayscale
            if len(block01_img.shape) == 3:
                gray = cv2.cvtColor(block01_img, cv2.COLOR_BGR2GRAY)
            else:
                gray = block01_img.copy()
            
            # Aplicar CLAHE
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(3, 3))
            gray_normalized = clahe.apply(gray)
            
            # Calcular região Y da questão (média das coordenadas Y)
            y_coords = [coord['y'] + coord['height'] // 2 for coord in question_coords]
            y_center = int(np.mean(y_coords))
            y_tolerance = max(20, question_coords[0]['height'] * 2)  # Tolerância maior
            
            # Buscar bolhas na região Y da questão
            search_y_start = max(0, y_center - y_tolerance)
            search_y_end = min(block_h, y_center + y_tolerance)
            search_region = gray_normalized[search_y_start:search_y_end, :]
            
            if search_region.size == 0:
                return None
            
            # Detectar círculos na região
            bubble_size = question_coords[0]['width']
            estimated_radius = bubble_size // 2
            blurred = cv2.GaussianBlur(search_region, (5, 5), 0)
            
            circles = cv2.HoughCircles(
                blurred,
                cv2.HOUGH_GRADIENT,
                dp=1,
                minDist=int(estimated_radius * 2),
                param1=50,
                param2=30,
                minRadius=max(5, estimated_radius - 5),
                maxRadius=min(50, estimated_radius + 10)
            )
            
            if circles is None:
                return None
            
            circles = np.round(circles[0, :]).astype("int")
            
            # Analisar cada círculo e mapear para alternativa
            bubble_results = {}  # {alt: (x, fill_ratio)}
            
            for circle in circles:
                cx, cy, r = circle
                # Ajustar coordenadas para o ROI completo
                cy_roi = cy + search_y_start
                
                # Extrair região do círculo
                x = max(0, cx - r)
                y = max(0, cy_roi - r)
                w = min(block_w - x, r * 2)
                h = min(block_h - y, r * 2)
                
                if w <= 0 or h <= 0:
                    continue
                
                roi_bubble = gray_normalized[y:y+h, x:x+w]
                if roi_bubble.size == 0:
                    continue
                
                # Calcular fill ratio
                mean_brightness = np.mean(roi_bubble)
                median_brightness = np.median(roi_bubble)
                std_brightness = np.std(roi_bubble)
                
                threshold_value = max(50, median_brightness * 0.65)
                dark_pixels = np.sum(roi_bubble < threshold_value)
                total_pixels = roi_bubble.size
                fill_ratio = dark_pixels / total_pixels if total_pixels > 0 else 0.0
                
                # Validações
                if std_brightness < 15 and mean_brightness > 200:
                    fill_ratio = 0.0
                elif std_brightness < 20 and mean_brightness < 100:
                    fill_ratio = max(fill_ratio, 0.8)
                
                # Análise circular
                if fill_ratio > 0.2:
                    center_x, center_y = w // 2, h // 2
                    radius = min(w, h) // 2 - 2
                    mask = np.zeros((h, w), dtype=np.uint8)
                    cv2.circle(mask, (center_x, center_y), radius, 255, -1)
                    
                    masked_roi = cv2.bitwise_and(roi_bubble, mask)
                    dark_pixels_circle = np.sum(masked_roi < threshold_value)
                    total_pixels_circle = np.sum(mask > 0)
                    
                    if total_pixels_circle > 0:
                        fill_ratio_circle = dark_pixels_circle / total_pixels_circle
                        fill_ratio = max(fill_ratio, fill_ratio_circle)
                
                # Mapear posição X para alternativa
                # Comparar cx com as coordenadas calculadas
                for coord in question_coords:
                    calc_x_center = coord['x'] + coord['width'] // 2
                    distance = abs(cx - calc_x_center)
                    
                    # Se está próximo o suficiente (dentro de 1.5x o tamanho da bolha)
                    if distance <= bubble_size * 1.5:
                        alt = coord['alternative']
                        # Manter o maior fill ratio para cada alternativa
                        if alt not in bubble_results or fill_ratio > bubble_results[alt][1]:
                            bubble_results[alt] = (cx, fill_ratio)
                        break
            
            # Retornar a alternativa com maior fill ratio
            if bubble_results:
                best_alt = max(bubble_results, key=lambda a: bubble_results[a][1])
                best_ratio = bubble_results[best_alt][1]
                return (best_alt, best_ratio)
            
            return None
            
        except Exception as e:
            logging.error(f"Erro na busca adaptativa por linha: {str(e)}")
            return None
    
    def _adaptive_bubble_search(self, block01_img: np.ndarray, question_coords: List[Dict], 
                                question_num: int) -> Optional[Tuple[str, float]]:
        """
        Busca adaptativa para bolhas não detectadas
        
        Quando uma bolha não é detectada nas coordenadas exatas, busca em uma região expandida
        ao redor das coordenadas calculadas.
        
        Args:
            block01_img: Imagem do ROI/bloco
            question_coords: Lista de coordenadas das alternativas da questão
            question_num: Número da questão
        
        Returns:
            Tupla (alternativa, fill_ratio) da melhor detecção ou None
        """
        try:
            block_h, block_w = block01_img.shape[:2]
            
            # Converter para grayscale
            if len(block01_img.shape) == 3:
                gray = cv2.cvtColor(block01_img, cv2.COLOR_BGR2GRAY)
            else:
                gray = block01_img.copy()
            
            # Aplicar CLAHE
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(3, 3))
            gray_normalized = clahe.apply(gray)
            
            best_result = None
            best_ratio = 0.0
            
            # Para cada alternativa, buscar em região expandida
            for coord in question_coords:
                alt = coord['alternative']
                x_center = coord['x'] + coord['width'] // 2
                y_center = coord['y'] + coord['height'] // 2
                w = coord['width']
                h = coord['height']
                
                # Região de busca expandida (1.5x o tamanho original em cada direção)
                search_radius_x = int(w * 0.75)
                search_radius_y = int(h * 0.75)
                
                # Testar múltiplas posições em uma grade ao redor da posição original
                search_offsets = [
                    (0, 0),  # Posição original
                    (-search_radius_x, 0), (search_radius_x, 0),  # Esquerda, direita
                    (0, -search_radius_y), (0, search_radius_y),  # Acima, abaixo
                    (-search_radius_x // 2, -search_radius_y // 2),  # Diagonal
                    (search_radius_x // 2, -search_radius_y // 2),
                    (-search_radius_x // 2, search_radius_y // 2),
                    (search_radius_x // 2, search_radius_y // 2),
                ]
                
                for offset_x, offset_y in search_offsets:
                    x = x_center - w // 2 + offset_x
                    y = y_center - h // 2 + offset_y
                    
                    # Validar coordenadas
                    if x < 0 or y < 0 or x + w > block_w or y + h > block_h:
                        continue
                    
                    # Extrair ROI
                    roi_region = gray_normalized[y:y+h, x:x+w]
                    if roi_region.size == 0:
                        continue
                    
                    # Calcular fill ratio
                    mean_brightness = np.mean(roi_region)
                    median_brightness = np.median(roi_region)
                    std_brightness = np.std(roi_region)
                    
                    # Threshold adaptativo
                    threshold_value = max(50, median_brightness * 0.65)
                    dark_pixels = np.sum(roi_region < threshold_value)
                    total_pixels = roi_region.size
                    
                    fill_ratio = dark_pixels / total_pixels if total_pixels > 0 else 0.0
                    
                    # Validações adicionais
                    if std_brightness < 15 and mean_brightness > 200:
                        fill_ratio = 0.0
                    elif std_brightness < 20 and mean_brightness < 100:
                        fill_ratio = max(fill_ratio, 0.8)
                    
                    # Usar análise circular se tiver alguma detecção
                    if fill_ratio > 0.2:
                        center_x, center_y = w // 2, h // 2
                        radius = min(w, h) // 2 - 2
                        mask = np.zeros((h, w), dtype=np.uint8)
                        cv2.circle(mask, (center_x, center_y), radius, 255, -1)
                        
                        masked_roi = cv2.bitwise_and(roi_region, mask)
                        dark_pixels_circle = np.sum(masked_roi < threshold_value)
                        total_pixels_circle = np.sum(mask > 0)
                        
                        if total_pixels_circle > 0:
                            fill_ratio_circle = dark_pixels_circle / total_pixels_circle
                            fill_ratio = max(fill_ratio, fill_ratio_circle)
                    
                    # Atualizar melhor resultado
                    if fill_ratio > best_ratio:
                        best_ratio = fill_ratio
                        best_result = (alt, fill_ratio)
            
            return best_result if best_result and best_ratio > 0.1 else None
            
        except Exception as e:
            logging.error(f"Erro na busca adaptativa: {str(e)}")
            return None
    
    def _detect_bubbles_with_binary(self, block01_img: np.ndarray, binary: np.ndarray,
                                   coordinates: List[Dict], num_questions: int) -> Dict[str, Any]:
        """
        Detecta bolhas usando imagem binária e coordenadas
        
        IMPORTANTE: Para threshold NORMAL (não invertido), bolha preenchida = pixels PRETOS
        Para threshold INVERTIDO, bolha preenchida = pixels BRANCOS
        
        Args:
            block01_img: Imagem do bloco 01
            binary: Imagem binária processada
            coordinates: Lista de coordenadas das bolhas
            num_questions: Número de questões
        
        Returns:
            Dict com 'answers' e 'fill_ratios'
        """
        detected_answers = {}
        fill_ratios_all = {}
        
        # Agrupar coordenadas por questão
        questions_data = {}
        for coord in coordinates:
            q = coord['question']
            if q not in questions_data:
                questions_data[q] = []
            questions_data[q].append(coord)
        
        # Detectar para cada questão
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
                block_h, block_w = block01_img.shape[:2]
                if x < 0 or y < 0 or x + w > block_w or y + h > block_h:
                    fill_ratios[alt] = 0.0
                    continue
                
                # Extrair ROI da bolha da imagem ORIGINAL (não binária) para análise
                roi_original = block01_img[y:y+h, x:x+w]
                roi_binary = binary[y:y+h, x:x+w]
                
                if roi_binary.size == 0:
                    if self.debug and question_num <= 2:  # Debug apenas primeiras questões
                        print(f"   ⚠️ Q{question_num}{alt}: ROI vazio em ({x}, {y})")
                    fill_ratios[alt] = 0.0
                    continue
                
                # Estratégia: analisar a imagem original na região da bolha
                # Bolha preenchida = região mais escura (menos brilho)
                if len(roi_original.shape) == 3:
                    roi_gray = cv2.cvtColor(roi_original, cv2.COLOR_BGR2GRAY)
                else:
                    roi_gray = roi_original
                
                # Aplicar normalização de contraste local (CLAHE) para melhorar detecção
                clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(3, 3))
                roi_gray_normalized = clahe.apply(roi_gray)
                
                # Calcular média de brilho (bolha preenchida = mais escura = menor média)
                mean_brightness = np.mean(roi_gray_normalized)
                
                # Calcular desvio padrão (bolha preenchida = mais uniforme = menor desvio)
                std_brightness = np.std(roi_gray_normalized)
                
                # Calcular mediana (mais robusta que média para outliers)
                median_brightness = np.median(roi_gray_normalized)
                
                # Estratégia 1: Contar pixels escuros usando threshold adaptativo
                # Threshold baseado na mediana (mais robusto)
                threshold_value = max(50, median_brightness * 0.65)  # 65% da mediana, mínimo 50
                dark_pixels = np.sum(roi_gray_normalized < threshold_value)
                total_pixels = roi_gray_normalized.size
                
                # Fill ratio = proporção de pixels escuros
                fill_ratio = dark_pixels / total_pixels if total_pixels > 0 else 0.0
                
                # Estratégia 2: Se a região for muito clara e uniforme, provavelmente é fundo branco
                if std_brightness < 15 and mean_brightness > 200:
                    # Região muito clara e uniforme = provavelmente fundo branco
                    fill_ratio = 0.0
                
                # Estratégia 3: Se a região for muito escura e uniforme, provavelmente está preenchida
                elif std_brightness < 20 and mean_brightness < 100:
                    # Região muito escura e uniforme = provavelmente preenchida
                    fill_ratio = max(fill_ratio, 0.8)  # Garantir pelo menos 80%
                
                # Estratégia 4: Usar análise de contorno circular para validar
                # Se houver um círculo bem definido preenchido, aumentar confiança
                if fill_ratio > 0.3:  # Se já tem alguma detecção
                    # Criar máscara circular
                    center_x, center_y = w // 2, h // 2
                    radius = min(w, h) // 2 - 2
                    mask = np.zeros((h, w), dtype=np.uint8)
                    cv2.circle(mask, (center_x, center_y), radius, 255, -1)
                    
                    # Calcular fill ratio apenas dentro do círculo
                    masked_roi = cv2.bitwise_and(roi_gray_normalized, mask)
                    dark_pixels_circle = np.sum(masked_roi < threshold_value)
                    total_pixels_circle = np.sum(mask > 0)
                    
                    if total_pixels_circle > 0:
                        fill_ratio_circle = dark_pixels_circle / total_pixels_circle
                        # Usar o maior entre os dois métodos
                        fill_ratio = max(fill_ratio, fill_ratio_circle)
                
                fill_ratios[alt] = fill_ratio
                
                # Debug detalhado para primeiras questões
                if self.debug and question_num <= 2:
                    print(f"   Q{question_num}{alt}: {fill_ratio:.2%} preenchido (brilho médio: {mean_brightness:.1f}, desvio: {std_brightness:.1f})")
            
            fill_ratios_all[question_num] = fill_ratios
            
            # Escolher alternativa com maior fill ratio
            if fill_ratios:
                max_alt = max(fill_ratios, key=fill_ratios.get)
                max_ratio = fill_ratios[max_alt]
                
                # BUSCA ADAPTATIVA: Se não detectou e é uma das primeiras questões, tentar busca por linha
                if max_ratio < self.BUBBLE_FILL_THRESHOLD and question_num <= 2:
                    print(f"   🔍 Q{question_num}: Fill ratio baixo ({max_ratio:.1%}), tentando busca adaptativa por linha...")
                    
                    # Tentar busca por linha (mais inteligente - mapeia posições reais para alternativas)
                    adaptive_result = self._adaptive_line_search(
                        block01_img, question_coords, question_num
                    )
                    
                    if adaptive_result:
                        best_alt, best_ratio = adaptive_result
                        if best_ratio >= self.BUBBLE_FILL_THRESHOLD:
                            detected_answers[question_num] = best_alt
                            fill_ratios_all[question_num][best_alt] = best_ratio
                            print(f"   ✅ Q{question_num}: {best_alt} ({best_ratio:.1%}) - Detectado com busca adaptativa por linha")
                        else:
                            # Se ainda não passou, tentar busca expandida tradicional como fallback
                            print(f"   🔍 Q{question_num}: Busca por linha encontrou {best_alt} mas ratio baixo ({best_ratio:.1%}), tentando busca expandida...")
                            fallback_result = self._adaptive_bubble_search(
                                block01_img, question_coords, question_num
                            )
                            if fallback_result:
                                fallback_alt, fallback_ratio = fallback_result
                                if fallback_ratio >= self.BUBBLE_FILL_THRESHOLD:
                                    detected_answers[question_num] = fallback_alt
                                    fill_ratios_all[question_num][fallback_alt] = fallback_ratio
                                    print(f"   ✅ Q{question_num}: {fallback_alt} ({fallback_ratio:.1%}) - Detectado com busca expandida")
                                else:
                                    print(f"   ⚪ Q{question_num}: Busca expandida encontrou {fallback_alt} mas ratio ainda baixo ({fallback_ratio:.1%} < {self.BUBBLE_FILL_THRESHOLD:.1%})")
                            else:
                                print(f"   ⚪ Q{question_num}: Nenhuma acima do threshold ({max_ratio:.1%} < {self.BUBBLE_FILL_THRESHOLD:.1%})")
                    else:
                        # Fallback para busca expandida tradicional
                        print(f"   🔍 Q{question_num}: Busca por linha não encontrou, tentando busca expandida...")
                        fallback_result = self._adaptive_bubble_search(
                            block01_img, question_coords, question_num
                        )
                        if fallback_result:
                            fallback_alt, fallback_ratio = fallback_result
                            if fallback_ratio >= self.BUBBLE_FILL_THRESHOLD:
                                detected_answers[question_num] = fallback_alt
                                fill_ratios_all[question_num][fallback_alt] = fallback_ratio
                                print(f"   ✅ Q{question_num}: {fallback_alt} ({fallback_ratio:.1%}) - Detectado com busca expandida")
                            else:
                                print(f"   ⚪ Q{question_num}: Busca expandida encontrou {fallback_alt} mas ratio ainda baixo ({fallback_ratio:.1%} < {self.BUBBLE_FILL_THRESHOLD:.1%})")
                        else:
                            print(f"   ⚪ Q{question_num}: Nenhuma acima do threshold ({max_ratio:.1%} < {self.BUBBLE_FILL_THRESHOLD:.1%})")
                elif max_ratio >= self.BUBBLE_FILL_THRESHOLD:
                    detected_answers[question_num] = max_alt
                    print(f"   ✅ Q{question_num}: {max_alt} ({max_ratio:.1%})")
                else:
                    print(f"   ⚪ Q{question_num}: Nenhuma acima do threshold ({max_ratio:.1%} < {self.BUBBLE_FILL_THRESHOLD:.1%})")
        
        return {
            'answers': detected_answers,
            'fill_ratios': fill_ratios_all
        }
    
    def _detect_horizontal_offset(self, roi_img: np.ndarray, first_question_coords: List[Dict],
                                  bubble_size: int) -> Optional[int]:
        """
        Detecta deslocamento horizontal global analisando a primeira linha de questões
        
        Estratégia:
        1. Buscar todas as bolhas preenchidas na primeira linha
        2. Comparar posições reais com posições calculadas
        3. Calcular offset horizontal médio
        
        Args:
            roi_img: Imagem do ROI
            first_question_coords: Coordenadas calculadas da primeira questão (A, B, C, D)
            bubble_size: Tamanho das bolhas
        
        Returns:
            Offset horizontal em pixels ou None se não detectar
        """
        try:
            roi_h, roi_w = roi_img.shape[:2]
            
            # Converter para grayscale
            if len(roi_img.shape) == 3:
                gray = cv2.cvtColor(roi_img, cv2.COLOR_BGR2GRAY)
            else:
                gray = roi_img.copy()
            
            # Aplicar CLAHE
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(3, 3))
            gray_normalized = clahe.apply(gray)
            
            # Calcular Y médio da primeira linha
            y_coords = [coord['y'] + coord['height'] // 2 for coord in first_question_coords]
            y_center = int(np.mean(y_coords))
            y_tolerance = bubble_size // 2
            
            # Buscar bolhas preenchidas na região da primeira linha
            # Escanear horizontalmente na região Y da primeira linha
            search_y_start = max(0, y_center - y_tolerance)
            search_y_end = min(roi_h, y_center + y_tolerance)
            search_region = gray_normalized[search_y_start:search_y_end, :]
            
            if search_region.size == 0:
                return None
            
            # Aplicar threshold para encontrar bolhas preenchidas
            _, binary = cv2.threshold(search_region, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            
            # Detectar círculos na região
            estimated_radius = bubble_size // 2
            blurred = cv2.GaussianBlur(search_region, (5, 5), 0)
            
            circles = cv2.HoughCircles(
                blurred,
                cv2.HOUGH_GRADIENT,
                dp=1,
                minDist=int(estimated_radius * 2),
                param1=50,
                param2=30,
                minRadius=max(5, estimated_radius - 5),
                maxRadius=min(50, estimated_radius + 10)
            )
            
            if circles is None or len(circles[0]) < 2:
                return None
            
            circles = np.round(circles[0, :]).astype("int")
            
            # Filtrar círculos que estão realmente preenchidos
            filled_circles = []
            for circle in circles:
                cx, cy, r = circle
                # Ajustar coordenadas para o ROI completo
                cy_roi = cy + search_y_start
                
                # Extrair região do círculo
                x = max(0, cx - r)
                y = max(0, cy_roi - r)
                w = min(roi_w - x, r * 2)
                h = min(roi_h - y, r * 2)
                
                if w <= 0 or h <= 0:
                    continue
                
                roi_bubble = gray_normalized[y:y+h, x:x+w]
                if roi_bubble.size == 0:
                    continue
                
                # Verificar se está preenchido
                median_brightness = np.median(roi_bubble)
                threshold_value = max(50, median_brightness * 0.65)
                dark_pixels = np.sum(roi_bubble < threshold_value)
                total_pixels = roi_bubble.size
                fill_ratio = dark_pixels / total_pixels if total_pixels > 0 else 0.0
                
                if fill_ratio >= 0.3:  # Pelo menos 30% preenchido
                    filled_circles.append((cx, cy_roi, r, fill_ratio))
            
            if len(filled_circles) == 0:
                return None
            
            # Ordenar por X
            filled_circles.sort(key=lambda c: c[0])
            
            # Calcular offset comparando com coordenadas calculadas
            # Pegar a primeira bolha preenchida (deve ser A)
            first_filled_x = filled_circles[0][0]
            
            # Encontrar coordenada calculada mais próxima
            first_calc_x = first_question_coords[0]['x'] + first_question_coords[0]['width'] // 2
            
            # Calcular offset
            offset = first_filled_x - first_calc_x
            
            # Validar offset (não pode ser muito grande)
            max_offset = bubble_size * 2  # Máximo 2 bolhas de deslocamento
            if abs(offset) > max_offset:
                print(f"   ⚠️ Offset calculado muito grande ({offset}px), ignorando")
                return None
            
            print(f"   🔍 Deslocamento horizontal detectado: {offset}px")
            return int(offset)
            
        except Exception as e:
            logging.error(f"Erro ao detectar deslocamento horizontal: {str(e)}")
            return None
    
    def _detect_first_question_row(self, roi_img: np.ndarray, estimated_base_y: int, 
                                   row_height: int, bubble_size: int) -> Optional[int]:
        """
        Detecta automaticamente onde começa a primeira linha de questões no ROI
        
        Estratégia:
        1. Escanear verticalmente procurando padrões de bolhas (círculos)
        2. Procurar por grupos de 4 círculos alinhados horizontalmente (alternativas A, B, C, D)
        3. Retornar a posição Y da primeira linha encontrada
        
        Args:
            roi_img: Imagem do ROI
            estimated_base_y: Posição Y estimada baseada em cálculos CSS
            row_height: Altura esperada de cada linha
            bubble_size: Tamanho esperado das bolhas
        
        Returns:
            Posição Y detectada da primeira linha ou None se não detectar
        """
        try:
            roi_h, roi_w = roi_img.shape[:2]
            
            # Converter para grayscale
            if len(roi_img.shape) == 3:
                gray = cv2.cvtColor(roi_img, cv2.COLOR_BGR2GRAY)
            else:
                gray = roi_img.copy()
            
            # Aplicar threshold para destacar bolhas
            _, binary = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
            
            # Procurar círculos usando HoughCircles
            # Estimar raio baseado no bubble_size
            estimated_radius = bubble_size // 2
            
            # Aplicar blur para melhorar detecção
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            
            circles = cv2.HoughCircles(
                blurred,
                cv2.HOUGH_GRADIENT,
                dp=1,
                minDist=int(estimated_radius * 2.5),  # Distância mínima entre centros
                param1=50,
                param2=30,
                minRadius=max(5, estimated_radius - 5),
                maxRadius=min(50, estimated_radius + 10)
            )
            
            if circles is None or len(circles[0]) < 4:
                print(f"   ⚠️ Poucos círculos detectados para encontrar primeira linha")
                return None
            
            circles = np.round(circles[0, :]).astype("int")
            
            # Agrupar círculos por linha (Y similar)
            # Tolerância para considerar na mesma linha
            y_tolerance = row_height // 3
            
            # Ordenar por Y
            circles_sorted = sorted(circles, key=lambda c: c[1])
            
            # Agrupar em linhas
            lines = []
            current_line = [circles_sorted[0]]
            current_y = circles_sorted[0][1]
            
            for circle in circles_sorted[1:]:
                if abs(circle[1] - current_y) <= y_tolerance:
                    current_line.append(circle)
                else:
                    if len(current_line) >= 3:  # Pelo menos 3 círculos para considerar uma linha válida
                        lines.append(sorted(current_line, key=lambda c: c[0]))  # Ordenar por X
                    current_line = [circle]
                    current_y = circle[1]
            
            if len(current_line) >= 3:
                lines.append(sorted(current_line, key=lambda c: c[0]))
            
            if not lines:
                print(f"   ⚠️ Nenhuma linha de bolhas detectada")
                return None
            
            # Pegar a primeira linha (menor Y)
            first_line = lines[0]
            first_line_y = first_line[0][1]  # Y do primeiro círculo da primeira linha
            
            # Ajustar para o centro da bolha (subtrair metade do bubble_size)
            detected_base_y = first_line_y - (bubble_size // 2)
            
            # Validar que está próximo da estimativa (não pode estar muito longe)
            max_offset = row_height * 2  # Máximo 2 linhas de diferença
            if abs(detected_base_y - estimated_base_y) > max_offset:
                print(f"   ⚠️ Offset detectado muito diferente da estimativa ({detected_base_y} vs {estimated_base_y}), usando estimativa")
                return None
            
            print(f"   🔍 Primeira linha detectada em Y={first_line_y}, ajustado para base_y={detected_base_y}")
            return max(0, detected_base_y)  # Garantir que não seja negativo
            
        except Exception as e:
            logging.error(f"Erro ao detectar primeira linha: {str(e)}")
            return None
    
    def _calculate_bubble_coordinates_in_roi(self, roi_img: np.ndarray, num_questions: int) -> Dict[str, Any]:
        """
        Calcula coordenadas das bolhas diretamente no ROI recortado
        
        O ROI contém todos os blocos de respostas (4 colunas, cada uma com até 12 questões).
        Calcula as coordenadas baseado no tamanho REAL do ROI, escalando proporcionalmente.
        
        Args:
            roi_img: Imagem do ROI recortado
            num_questions: Número total de questões
        
        Returns:
            Dict com configuração de coordenadas RELATIVAS ao ROI
        """
        try:
            roi_h, roi_w = roi_img.shape[:2]
            
            # Layout: 4 colunas (blocos) lado a lado
            num_blocks = 4
            questions_per_block = 12
            
            # Valores EXATOS do CSS do template HTML (institutional_test.html)
            # Estes são os valores reais do template, medidos do CSS
            CSS_GRID_GAP = 8  # gap: 8px entre blocos (.answer-grid-container)
            CSS_BORDER_WIDTH = 5  # border: 5px solid #000000 (.answer-grid-container)
            CSS_PADDING = 5  # padding: 5px do container (.answer-grid-container)
            CSS_BLOCK_PADDING = 5  # padding: 5px dentro de cada bloco (.answer-block)
            CSS_BLOCK_HEADER_MARGIN_BOTTOM = 2  # margin: 0 0 2px 0 (.block-header)
            CSS_BLOCK_HEADER_PADDING = 4  # padding: 4px (.block-header)
            CSS_BLOCK_HEADER_FONT_SIZE = 8  # font-size: 8pt = ~10.67px a 96 DPI
            CSS_BLOCK_HEADER_HEIGHT = CSS_BLOCK_HEADER_PADDING * 2 + CSS_BLOCK_HEADER_FONT_SIZE + CSS_BLOCK_HEADER_MARGIN_BOTTOM  # ~18px
            CSS_BUBBLE_HEADER_MARGIN = 3  # margin: 3px 0 3px 0 (.bubble-headers)
            CSS_BUBBLE_HEADER_FONT_SIZE = 7  # font-size: 7pt = ~9.33px a 96 DPI
            CSS_BUBBLE_HEADER_HEIGHT = CSS_BUBBLE_HEADER_MARGIN * 2 + CSS_BUBBLE_HEADER_FONT_SIZE  # ~15px
            CSS_ANSWER_ROW_MARGIN = 2  # margin: 2px 0 (.answer-row)
            CSS_ANSWER_ROW_PADDING = 1  # padding: 1px 0 (.answer-row)
            CSS_ANSWER_ROW_HEIGHT = (CSS_ANSWER_ROW_MARGIN * 2) + (CSS_ANSWER_ROW_PADDING * 2) + 18  # margin + padding + bubble height = ~24px
            CSS_QUESTION_NUM_WIDTH = 22  # width: 22px (.question-num, .header-spacer)
            CSS_BUBBLE_SIZE = 18  # width/height: 18px (.bubble)
            CSS_BUBBLE_GAP = 6  # gap: 6px (.bubbles)
            
            # Calcular escala baseada no tamanho real do ROI
            # Estratégia: Detectar a estrutura real do ROI primeiro
            # Tentar detectar bordas e gaps reais na imagem
            
            # Primeiro, tentar detectar a borda real do ROI
            # Converter para grayscale se necessário
            if len(roi_img.shape) == 3:
                roi_gray = cv2.cvtColor(roi_img, cv2.COLOR_BGR2GRAY)
            else:
                roi_gray = roi_img.copy()
            
            # Detectar borda externa (border do container)
            _, binary = cv2.threshold(roi_gray, 200, 255, cv2.THRESH_BINARY_INV)
            
            # Encontrar contornos externos
            contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            # Procurar o maior contorno retangular (a borda externa)
            border_rect = None
            max_area = 0
            for contour in contours:
                area = cv2.contourArea(contour)
                if area > max_area and area > (roi_w * roi_h * 0.5):  # Pelo menos 50% da imagem
                    x, y, w_rect, h_rect = cv2.boundingRect(contour)
                    # Verificar se é aproximadamente retangular
                    epsilon = 0.02 * cv2.arcLength(contour, True)
                    approx = cv2.approxPolyDP(contour, epsilon, True)
                    if len(approx) >= 4:
                        border_rect = (x, y, w_rect, h_rect)
                        max_area = area
            
            # Se detectou borda, usar dimensões reais; senão, usar valores CSS estimados
            if border_rect:
                detected_border_x, detected_border_y, detected_border_w, detected_border_h = border_rect
                # A borda detectada pode estar um pouco dentro devido ao threshold
                # Usar dimensões internas (menos a borda)
                actual_available_width = detected_border_w - (CSS_BORDER_WIDTH * 2)
                actual_available_height = detected_border_h - (CSS_BORDER_WIDTH * 2)
            else:
                # Fallback: usar dimensões do ROI menos bordas estimadas
                actual_available_width = roi_w - (CSS_BORDER_WIDTH * 2) - (CSS_PADDING * 2)
                actual_available_height = roi_h - (CSS_BORDER_WIDTH * 2) - (CSS_PADDING * 2)
            
            # Calcular escala baseada na largura disponível real
            # Template típico: 4 blocos de ~180px cada + 3 gaps de 8px = 720 + 24 = 744px
            template_available_width = 744.0  # Largura disponível típica para os 4 blocos
            scale = actual_available_width / template_available_width if template_available_width > 0 else 1.0
            
            # Validar escala (não pode ser muito pequena ou muito grande)
            if scale < 0.5 or scale > 3.0:
                print(f"⚠️ Escala calculada suspeita ({scale:.3f}), usando escala baseada em altura...")
                # Tentar calcular pela altura também
                template_available_height = 12 * CSS_ANSWER_ROW_HEIGHT + CSS_BLOCK_HEADER_HEIGHT + CSS_BUBBLE_HEADER_HEIGHT
                scale_h = actual_available_height / template_available_height if template_available_height > 0 else 1.0
                # Usar média das duas escalas
                scale = (scale + scale_h) / 2.0
                print(f"   Escala ajustada: {scale:.3f}")
            
            # Escalar todos os valores
            grid_gap = int(CSS_GRID_GAP * scale)
            border_width = int(CSS_BORDER_WIDTH * scale)
            padding = int(CSS_PADDING * scale)
            block_padding = int(CSS_BLOCK_PADDING * scale)
            block_header_height = int(CSS_BLOCK_HEADER_HEIGHT * scale)
            bubble_header_height = int(CSS_BUBBLE_HEADER_HEIGHT * scale)
            answer_row_height = int(CSS_ANSWER_ROW_HEIGHT * scale)
            question_num_width = int(CSS_QUESTION_NUM_WIDTH * scale)
            bubble_size = int(CSS_BUBBLE_SIZE * scale)
            bubble_gap = int(CSS_BUBBLE_GAP * scale)
            # Escalar também margens e paddings das linhas
            answer_row_margin = int(CSS_ANSWER_ROW_MARGIN * scale)
            answer_row_padding = int(CSS_ANSWER_ROW_PADDING * scale)
            
            # Calcular largura de cada bloco
            # ROI tem: border (2x) + padding (2x) + 4 blocos + 3 gaps entre blocos
            available_width = roi_w - (border_width * 2) - (padding * 2)
            block_width = (available_width - (grid_gap * (num_blocks - 1))) // num_blocks
            
            # Calcular quantas questões cabem no ROI
            available_height = roi_h - (border_width * 2) - (padding * 2) - block_header_height - bubble_header_height
            
            # Debug: mostrar dimensões calculadas
            print(f"🔍 DEBUG - Cálculo de coordenadas:")
            print(f"   ROI: {roi_w}x{roi_h}px")
            print(f"   Escala calculada: {scale:.3f}x")
            print(f"   Largura disponível: {available_width}px")
            print(f"   Largura de cada bloco: {block_width}px")
            print(f"   Tamanho bolha escalado: {bubble_size}px")
            print(f"   Altura disponível: {available_height}px")
            print(f"   Altura por linha: {answer_row_height}px")
            if border_rect:
                print(f"   Borda detectada: {border_rect}")
            else:
                print(f"   ⚠️ Borda não detectada, usando valores estimados")
            max_questions_in_roi = available_height // answer_row_height if answer_row_height > 0 else num_questions
            
            # Limitar ao número de questões disponíveis
            questions_to_process = min(num_questions, max_questions_in_roi)
            
            coordinates = []
            
            # Calcular posições X base das alternativas (comum para todos os blocos)
            # X base = padding do bloco + largura do número da questão
            start_x_alt = block_padding + question_num_width
            alt_x_positions = []
            for i in range(4):
                # Cada alternativa está em um .bubble-container com gap de 6px
                x = start_x_alt + (i * (bubble_size + bubble_gap))
                alt_x_positions.append(x)
            
            # Y base = border + padding + header do bloco + header das bolhas
            base_y_calculated = border_width + padding + block_header_height + bubble_header_height
            
            # DETECÇÃO AUTOMÁTICA DO OFFSET INICIAL
            # Detectar onde realmente começam as questões no ROI
            detected_base_y = self._detect_first_question_row(roi_img, base_y_calculated, answer_row_height, bubble_size)
            if detected_base_y is not None:
                base_y = detected_base_y
                print(f"✅ Offset inicial detectado automaticamente: {base_y} (calculado: {base_y_calculated}, diferença: {base_y - base_y_calculated}px)")
            else:
                base_y = base_y_calculated
                print(f"⚠️ Usando offset inicial calculado: {base_y} (detecção automática falhou)")
            
            # Processar cada questão
            for question_num in range(1, questions_to_process + 1):
                # Determinar em qual bloco está a questão
                block_index = (question_num - 1) // questions_per_block
                question_in_block = ((question_num - 1) % questions_per_block) + 1
                
                # Calcular posição X do bloco (considerando border, padding e gaps)
                block_x = border_width + padding + (block_index * (block_width + grid_gap)) + block_padding
                
                # Calcular posição Y da questão dentro do bloco
                # Primeira linha começa após o header, com margem/padding da linha (valores escalados)
                question_y = base_y + answer_row_margin + answer_row_padding + ((question_in_block - 1) * answer_row_height)
                
                # Coordenadas de cada alternativa (A, B, C, D)
                for alt_index in range(4):
                    alt = chr(65 + alt_index)  # A, B, C, D
                    # Calcular posição X da bolha (centro do bubble-container)
                    # O bubble-container tem width: 18px, então a bolha está centralizada
                    bubble_container_x = block_x + alt_x_positions[alt_index]
                    # A bolha está centralizada no container, então x = posição do container
                    x_relative = bubble_container_x
                    
                    # Calcular posição Y da bolha (centro vertical da linha)
                    # A linha tem padding e margin, a bolha está centralizada verticalmente
                    # Y = posição da linha + metade da altura da linha - metade da altura da bolha
                    y_relative = question_y + (answer_row_height // 2) - (bubble_size // 2)
                    
                    # Validar que as coordenadas estão dentro do ROI
                    if x_relative < 0 or y_relative < 0 or x_relative + bubble_size > roi_w or y_relative + bubble_size > roi_h:
                        if self.debug:
                            print(f"⚠️ Coordenada fora do ROI: Q{question_num}{alt} em ({x_relative}, {y_relative}) - ROI: {roi_w}x{roi_h}")
                        continue
                    
                    coordinates.append({
                        'question': question_num,
                        'alternative': alt,
                        'x': int(x_relative),
                        'y': int(y_relative),
                        'width': bubble_size,
                        'height': bubble_size
                    })
            
            # Validar coordenadas e mostrar exemplos
            valid_coords = [c for c in coordinates if 0 <= c['x'] < roi_w and 0 <= c['y'] < roi_h 
                           and c['x'] + c['width'] <= roi_w and c['y'] + c['height'] <= roi_h]
            invalid_count = len(coordinates) - len(valid_coords)
            
            if invalid_count > 0:
                print(f"⚠️ {invalid_count} coordenadas inválidas (fora do ROI) foram removidas")
            
            # DETECÇÃO DE DESLOCAMENTO HORIZONTAL
            # Pegar coordenadas da primeira questão para detectar deslocamento
            first_question_coords = [c for c in valid_coords if c['question'] == 1]
            if first_question_coords:
                horizontal_offset = self._detect_horizontal_offset(roi_img, first_question_coords, bubble_size)
                if horizontal_offset is not None and abs(horizontal_offset) > 5:  # Aplicar apenas se offset > 5px
                    print(f"✅ Aplicando correção de deslocamento horizontal: {horizontal_offset}px")
                    # Ajustar todas as coordenadas X
                    for coord in valid_coords:
                        coord['x'] = max(0, coord['x'] + horizontal_offset)
                        # Validar novamente após ajuste
                        if coord['x'] + coord['width'] > roi_w:
                            coord['x'] = roi_w - coord['width']
                    print(f"   Coordenadas ajustadas com offset horizontal")
                else:
                    if horizontal_offset is not None:
                        print(f"   Offset horizontal detectado mas muito pequeno ({horizontal_offset}px), ignorando")
            
            # Mostrar exemplos de coordenadas (após ajuste)
            if valid_coords:
                print(f"🔍 Exemplos de coordenadas calculadas:")
                for i, coord in enumerate(valid_coords[:8]):  # Mostrar primeiras 8
                    print(f"   Q{coord['question']}{coord['alternative']}: ({coord['x']}, {coord['y']}) - {coord['width']}x{coord['height']}")
            
            print(f"✅ Coordenadas calculadas para {questions_to_process} questões no ROI")
            print(f"   Tamanho bolinha: {bubble_size}px (escala: {scale:.2f}x), Total coordenadas válidas: {len(valid_coords)}")
            print(f"   ROI: {roi_w}x{roi_h}px, Blocos: {num_blocks}, Largura bloco: {block_width}px")
            
            # Usar apenas coordenadas válidas
            coordinates = valid_coords
            
            return {
                'coordinates': coordinates,
                'bubble_size': bubble_size,
                'num_questions': questions_to_process
            }
            
        except Exception as e:
            logging.error(f"Erro ao calcular coordenadas no ROI: {str(e)}")
            import traceback
            logging.error(traceback.format_exc())
            return {'coordinates': [], 'num_questions': num_questions}
    
    def _detect_bubbles_automatic(self, roi_img: np.ndarray, num_questions: int) -> Dict[str, Any]:
        """
        Detecta bolhas automaticamente SEM coordenadas fixas
        
        Estratégia:
        1. Detecta a estrutura do grid (linhas horizontais e verticais)
        2. Localiza círculos na imagem usando detecção de contornos
        3. Agrupa círculos por posição para identificar questões e alternativas
        4. Detecta quais círculos estão preenchidos
        
        Args:
            roi_img: Imagem do ROI recortado
            num_questions: Número total de questões
        
        Returns:
            Dict com 'answers' e 'fill_ratios'
        """
        try:
            roi_h, roi_w = roi_img.shape[:2]
            
            # Converter para escala de cinza
            if len(roi_img.shape) == 3:
                gray = cv2.cvtColor(roi_img, cv2.COLOR_BGR2GRAY)
            else:
                gray = roi_img.copy()
            
            # 1. Detectar estrutura do grid usando HoughLines
            # Aplicar threshold para encontrar linhas
            _, binary = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
            
            # Detectar linhas horizontais (separadores entre questões)
            horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (roi_w // 4, 1))
            horizontal_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, horizontal_kernel)
            horizontal_lines = cv2.dilate(horizontal_lines, horizontal_kernel, iterations=2)
            
            # Detectar linhas verticais (separadores entre colunas/blocos)
            vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, roi_h // 4))
            vertical_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, vertical_kernel)
            vertical_lines = cv2.dilate(vertical_lines, vertical_kernel, iterations=2)
            
            # 2. Detectar círculos usando HoughCircles
            # Aplicar blur para suavizar
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            
            # Detectar círculos - ajustar parâmetros baseado no tamanho do ROI
            # Estimar tamanho médio das bolhas (assumindo escala similar)
            estimated_bubble_radius = max(8, min(30, int(roi_w * 0.015)))  # ~1.5% da largura
            
            circles = cv2.HoughCircles(
                blurred,
                cv2.HOUGH_GRADIENT,
                dp=1,
                minDist=int(estimated_bubble_radius * 2.5),  # Distância mínima entre centros
                param1=50,  # Threshold superior para detecção de bordas
                param2=30,  # Threshold para centro
                minRadius=max(5, estimated_bubble_radius - 3),
                maxRadius=min(50, estimated_bubble_radius + 10)
            )
            
            if circles is None:
                print("⚠️ Nenhum círculo detectado automaticamente, usando método tradicional")
                return {'answers': {}, 'fill_ratios': {}}
            
            circles = np.round(circles[0, :]).astype("int")
            print(f"🔍 Detectados {len(circles)} círculos automaticamente")
            
            # 3. Agrupar círculos por posição (organizar em grid)
            # Ordenar círculos por Y (questões) e depois por X (alternativas)
            circles_sorted = sorted(circles, key=lambda c: (c[1], c[0]))  # Ordenar por Y, depois X
            
            # Agrupar em linhas (questões) baseado na posição Y
            question_rows = []
            current_row = [circles_sorted[0]]
            row_y = circles_sorted[0][1]
            row_tolerance = estimated_bubble_radius * 2  # Tolerância para agrupar na mesma linha
            
            for circle in circles_sorted[1:]:
                if abs(circle[1] - row_y) <= row_tolerance:
                    current_row.append(circle)
                else:
                    # Nova linha encontrada
                    question_rows.append(sorted(current_row, key=lambda c: c[0]))  # Ordenar por X
                    current_row = [circle]
                    row_y = circle[1]
            if current_row:
                question_rows.append(sorted(current_row, key=lambda c: c[0]))
            
            print(f"🔍 Detectadas {len(question_rows)} linhas (questões)")
            
            # 4. Processar cada linha e detectar círculos preenchidos
            detected_answers = {}
            fill_ratios_all = {}
            
            # Processar apenas as primeiras num_questions linhas
            questions_to_process = min(num_questions, len(question_rows))
            
            for question_idx in range(questions_to_process):
                question_num = question_idx + 1
                row_circles = question_rows[question_idx]
                
                # Filtrar círculos que podem ser alternativas (esperamos 4 por linha)
                # Se houver mais de 4, pegar os 4 mais próximos do centro esperado
                if len(row_circles) >= 4:
                    # Calcular posição esperada das 4 alternativas (distribuídas horizontalmente)
                    row_start_x = row_circles[0][0]
                    row_end_x = row_circles[-1][0]
                    expected_spacing = (row_end_x - row_start_x) / 3  # 3 espaços entre 4 alternativas
                    
                    # Selecionar os 4 círculos mais próximos das posições esperadas
                    selected_circles = []
                    for alt_idx in range(4):
                        expected_x = row_start_x + (alt_idx * expected_spacing)
                        # Encontrar círculo mais próximo
                        closest = min(row_circles, key=lambda c: abs(c[0] - expected_x))
                        if closest not in selected_circles:
                            selected_circles.append(closest)
                        else:
                            # Se já foi selecionado, pegar o próximo mais próximo
                            remaining = [c for c in row_circles if c not in selected_circles]
                            if remaining:
                                selected_circles.append(min(remaining, key=lambda c: abs(c[0] - expected_x)))
                    
                    row_circles = sorted(selected_circles[:4], key=lambda c: c[0])[:4]
                elif len(row_circles) < 4:
                    # Se tiver menos de 4, usar os que temos
                    pass
                
                # Processar cada círculo da linha (alternativas A, B, C, D)
                fill_ratios = {}
                for alt_idx, circle in enumerate(row_circles[:4]):
                    alt = chr(65 + alt_idx)  # A, B, C, D
                    center_x, center_y, radius = circle
                    
                    # Extrair região do círculo
                    x = max(0, center_x - radius)
                    y = max(0, center_y - radius)
                    w = min(roi_w - x, radius * 2)
                    h = min(roi_h - y, radius * 2)
                    
                    if w <= 0 or h <= 0:
                        fill_ratios[alt] = 0.0
                        continue
                    
                    # Criar máscara circular
                    mask = np.zeros((h, w), dtype=np.uint8)
                    cv2.circle(mask, (radius, radius), radius, 255, -1)
                    
                    # Extrair região
                    roi_region = gray[y:y+h, x:x+w]
                    if roi_region.size == 0:
                        fill_ratios[alt] = 0.0
                        continue
                    
                    # Calcular fill ratio (pixels escuros / total)
                    # Bolha preenchida = muitos pixels escuros
                    masked_roi = cv2.bitwise_and(roi_region, mask)
                    dark_pixels = np.sum(masked_roi < 127)  # Pixels escuros
                    total_pixels = np.sum(mask > 0)
                    
                    fill_ratio = dark_pixels / total_pixels if total_pixels > 0 else 0.0
                    fill_ratios[alt] = fill_ratio
                
                fill_ratios_all[question_num] = fill_ratios
                
                # Escolher alternativa com maior fill ratio
                if fill_ratios:
                    max_alt = max(fill_ratios, key=fill_ratios.get)
                    max_ratio = fill_ratios[max_alt]
                    
                    if max_ratio >= self.BUBBLE_FILL_THRESHOLD:
                        detected_answers[question_num] = max_alt
                        print(f"   ✅ Q{question_num}: {max_alt} ({max_ratio:.1%}) - Auto-detectado")
                    else:
                        print(f"   ⚪ Q{question_num}: Nenhuma acima do threshold ({max_ratio:.1%} < {self.BUBBLE_FILL_THRESHOLD:.1%})")
            
            print(f"✅ Auto-detecção concluída: {len(detected_answers)}/{questions_to_process} respostas")
            
            return {
                'answers': detected_answers,
                'fill_ratios': fill_ratios_all
            }
            
        except Exception as e:
            logging.error(f"Erro na detecção automática: {str(e)}")
            import traceback
            logging.error(traceback.format_exc())
            return {'answers': {}, 'fill_ratios': {}}
    
    def _calculate_bubble_coordinates_block01(self, num_questions: int, block01_shape: Tuple[int, int], aligned_shape: Tuple[int, int]) -> Dict[str, Any]:
        """
        ETAPA 5: Calcula coordenadas das bolhas relativas ao bloco 01 recortado
        
        Usa o layout EXATO do template HTML, mas adaptado para coordenadas relativas ao bloco 01
        
        Args:
            num_questions: Número total de questões
            block01_shape: Formato do bloco 01 recortado (height, width)
            aligned_shape: Formato da imagem alinhada (height, width) - para calcular escala
        
        Returns:
            Dict com configuração de coordenadas RELATIVAS ao bloco 01
        """
        try:
            block_h, block_w = block01_shape[:2]
            aligned_h, aligned_w = aligned_shape[:2]
            
            # Calcular escala baseada na imagem alinhada
            # Template A4 padrão: 794x1123px a 96 DPI
            template_width = 794.0
            template_height = 1123.0
            scale_x = aligned_w / template_width
            scale_y = aligned_h / template_height
            
            # Valores EXATOS do CSS do template (em pixels A4 padrão)
            BLOCK_PADDING = 5  # padding: 5px (.answer-block)
            BLOCK_HEADER_HEIGHT = 25  # Altura do cabeçalho do bloco
            BUBBLE_HEADER_HEIGHT = 15  # Altura do header das bolhas
            ANSWER_ROW_HEIGHT = 20  # Altura de cada linha
            QUESTION_NUM_WIDTH = 22  # Largura do número da questão
            BUBBLE_SIZE = 18  # Tamanho da bolha (18px)
            BUBBLE_GAP = 6  # Gap entre bolhas (6px)
            
            # Escalar valores para a imagem atual
            BLOCK_PADDING_SCALED = int(BLOCK_PADDING * scale_x)
            BLOCK_HEADER_HEIGHT_SCALED = int(BLOCK_HEADER_HEIGHT * scale_y)
            BUBBLE_HEADER_HEIGHT_SCALED = int(BUBBLE_HEADER_HEIGHT * scale_y)
            ANSWER_ROW_HEIGHT_SCALED = int(ANSWER_ROW_HEIGHT * scale_y)
            QUESTION_NUM_WIDTH_SCALED = int(QUESTION_NUM_WIDTH * scale_x)
            BUBBLE_SIZE_SCALED = int(BUBBLE_SIZE * scale_x)
            BUBBLE_GAP_SCALED = int(BUBBLE_GAP * scale_x)
            
            # Calcular posições X das alternativas dentro do bloco (relativas ao bloco)
            # question-num (22px) + padding (5px) + bubbles
            alt_x_positions = []
            start_x_alt = QUESTION_NUM_WIDTH_SCALED + BLOCK_PADDING_SCALED
            for i in range(4):
                x = start_x_alt + (i * (BUBBLE_SIZE_SCALED + BUBBLE_GAP_SCALED))
                alt_x_positions.append(x)
            
            # Calcular coordenadas para questões do BLOCO 01 (questões 1-12)
            questions_per_block = 12
            coordinates = []
            
            for question_num in range(1, min(num_questions + 1, questions_per_block + 1)):
                # Posição Y da questão dentro do bloco (relativa ao topo do bloco)
                question_in_block = question_num  # No bloco 01, questão 1 = primeira questão
                question_y_in_block = BLOCK_HEADER_HEIGHT_SCALED + BUBBLE_HEADER_HEIGHT_SCALED + ((question_in_block - 1) * ANSWER_ROW_HEIGHT_SCALED)
                
                # Coordenadas de cada alternativa (A, B, C, D) - RELATIVAS ao bloco 01
                for alt_index in range(4):
                    alt = chr(65 + alt_index)  # A, B, C, D
                    x_relative = alt_x_positions[alt_index]
                    y_relative = question_y_in_block
                    
                    coordinates.append({
                        'question': question_num,
                        'alternative': alt,
                        'x': int(x_relative),
                        'y': int(y_relative),
                        'width': BUBBLE_SIZE_SCALED,
                        'height': BUBBLE_SIZE_SCALED
                    })
            
            print(f"✅ Coordenadas calculadas para {min(num_questions, questions_per_block)} questões no bloco 01")
            print(f"   Tamanho bolinha: {BUBBLE_SIZE_SCALED}px, Total coordenadas: {len(coordinates)}")
            print(f"   Escala: {scale_x:.2f}x (largura), {scale_y:.2f}x (altura)")
            
            return {
                'coordinates': coordinates,
                'bubble_size': BUBBLE_SIZE_SCALED,
                'num_questions': min(num_questions, questions_per_block)
            }
            
        except Exception as e:
            logging.error(f"Erro ao calcular coordenadas do bloco 01: {str(e)}")
            import traceback
            logging.error(traceback.format_exc())
            return {'coordinates': [], 'num_questions': num_questions}
    
    def _calculate_bubble_coordinates(self, num_questions: int, image_shape: Tuple[int, int]) -> Dict[str, Any]:
        """
        Calcula coordenadas das bolhas baseado no layout do template HTML
        
        Usa coordenadas relativas à imagem atual (não fixas em A4)
        
        Args:
            num_questions: Número total de questões
            image_shape: Formato da imagem (height, width)
        
        Returns:
            Dict com configuração de coordenadas
        """
        try:
            img_height, img_width = image_shape[:2]
            
            # Usar proporções relativas à imagem atual
            # Baseado no template HTML: 794x1123px
            template_width = 794.0
            template_height = 1123.0
            
            # Calcular escala baseada na imagem atual
            scale_x = img_width / template_width
            scale_y = img_height / template_height
            
            # Margens e padding (escalados relativamente à imagem atual)
            PAGE_MARGIN_TOP = int(0.5 * 37.8 * scale_y)  # 0.5cm
            PAGE_MARGIN_LEFT = int(0.8 * 37.8 * scale_x)  # 0.8cm
            ANSWER_SHEET_PADDING = int(18.9 * scale_x)  # 0.5cm
            
            # Alturas estimadas (escaladas)
            HEADER_HEIGHT = int(120 * scale_y)
            INSTRUCTIONS_HEIGHT = int(100 * scale_y)
            APPLICATOR_HEIGHT = int(50 * scale_y)
            ANSWER_GRID_MARGIN_TOP = int(10 * scale_y)
            
            # Posição inicial da grade
            grid_start_y = PAGE_MARGIN_TOP + ANSWER_SHEET_PADDING + HEADER_HEIGHT + INSTRUCTIONS_HEIGHT + APPLICATOR_HEIGHT + ANSWER_GRID_MARGIN_TOP
            grid_start_x = PAGE_MARGIN_LEFT + ANSWER_SHEET_PADDING
            
            # Dimensões da grade (escaladas)
            GRID_GAP = int(8 * scale_x)
            BLOCK_PADDING = int(5 * scale_x)
            BLOCK_HEADER_HEIGHT = int(25 * scale_y)
            BUBBLE_HEADER_HEIGHT = int(15 * scale_y)
            ANSWER_ROW_HEIGHT = int(20 * scale_y)
            QUESTION_NUM_WIDTH = int(22 * scale_x)
            
            # Dimensões das bolhas (escaladas)
            BUBBLE_SIZE = int(18 * scale_x)
            BUBBLE_GAP = int(6 * scale_x)
            
            # Calcular número de blocos (12 questões por bloco)
            questions_per_block = 12
            num_blocks = (num_questions + questions_per_block - 1) // questions_per_block
            
            # Largura disponível (relativa à imagem atual)
            available_width = img_width - (PAGE_MARGIN_LEFT * 2) - (ANSWER_SHEET_PADDING * 2)
            block_width = (available_width - (GRID_GAP * 3)) / 4
            
            # Posições X das alternativas dentro de um bloco
            alt_x_positions = []
            start_x_alt = QUESTION_NUM_WIDTH + BLOCK_PADDING
            for i in range(4):
                x = start_x_alt + (i * (BUBBLE_SIZE + BUBBLE_GAP))
                alt_x_positions.append(int(x))
            
            # Calcular coordenadas para cada questão
            coordinates = []
            
            for question_num in range(1, num_questions + 1):
                # Calcular em qual bloco está
                block_index = (question_num - 1) // questions_per_block
                question_in_block = ((question_num - 1) % questions_per_block) + 1
                
                # Posição X do bloco
                block_x = int(grid_start_x + (block_index * (block_width + GRID_GAP)))
                
                # Posição Y da questão dentro do bloco
                question_y_in_block = BLOCK_HEADER_HEIGHT + BUBBLE_HEADER_HEIGHT + ((question_in_block - 1) * ANSWER_ROW_HEIGHT)
                question_y = int(grid_start_y + question_y_in_block)
                
                # Coordenadas de cada alternativa (A, B, C, D)
                for alt_index in range(4):
                    alt_x_relative = alt_x_positions[alt_index]
                    alt_x_absolute = block_x + alt_x_relative
                    alt_y_absolute = question_y
                    
                    # Coordenadas da bolha (canto superior esquerdo)
                    bubble_x = int(alt_x_absolute)
                    bubble_y = int(alt_y_absolute)
                    
                    coordinates.append({
                        'question': question_num,
                        'alternative': chr(65 + alt_index),  # A, B, C, D
                        'x': bubble_x,
                        'y': bubble_y,
                        'width': BUBBLE_SIZE,
                        'height': BUBBLE_SIZE
                    })
            
            return {
                'coordinates': coordinates,
                'bubble_size': BUBBLE_SIZE,
                'num_questions': num_questions
            }
            
        except Exception as e:
            logging.error(f"Erro ao calcular coordenadas: {str(e)}")
            return {'coordinates': [], 'num_questions': num_questions}
    
    def _detect_bubbles_block01(self, block01_img: np.ndarray, coordinates_config: Dict, 
                               num_questions: int) -> Dict[str, Any]:
        """
        ETAPA 4: Detecta bolinhas preenchidas APENAS no bloco 01
        
        Calibra tamanho esperado: diâmetro ≈ 25-35px
        
        Args:
            block01_img: Imagem do bloco 01 recortado
            coordinates_config: Configuração de coordenadas
            num_questions: Número total de questões
        
        Returns:
            Dict com 'answers' e 'fill_ratios'
        """
        try:
            # Converter para grayscale
            if len(block01_img.shape) == 3:
                gray = cv2.cvtColor(block01_img, cv2.COLOR_BGR2GRAY)
            else:
                gray = block01_img.copy()
            
            # Normalizar iluminação usando CLAHE
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            gray_normalized = clahe.apply(gray)
            
            # Aplicar threshold adaptativo (melhor que OTSU para iluminação variável)
            binary = cv2.adaptiveThreshold(
                gray_normalized,
                255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY_INV,
                11,
                2
            )
            
            coordinates = coordinates_config.get('coordinates', [])
            detected_answers = {}
            fill_ratios_all = {}
            
            # Agrupar coordenadas por questão
            questions_data = {}
            for coord in coordinates:
                q = coord['question']
                if q not in questions_data:
                    questions_data[q] = []
                questions_data[q].append(coord)
            
            # Detectar para cada questão
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
                    
                    # Validar coordenadas dentro do bloco 01
                    block_h, block_w = block01_img.shape[:2]
                    if x < 0 or y < 0 or x + w > block_w or y + h > block_h:
                        fill_ratios[alt] = 0.0
                        continue
                    
                    # Extrair ROI da bolha
                    roi = binary[y:y+h, x:x+w]
                    
                    if roi.size == 0:
                        fill_ratios[alt] = 0.0
                        continue
                    
                    # Contar pixels brancos (bolha preenchida)
                    white_pixels = cv2.countNonZero(roi)
                    total_pixels = roi.size
                    fill_ratio = white_pixels / total_pixels if total_pixels > 0 else 0.0
                    
                    fill_ratios[alt] = fill_ratio
                    
                    if self.debug:
                        print(f"   Q{question_num} {alt}: {fill_ratio:.2%} preenchido")
                
                fill_ratios_all[question_num] = fill_ratios
                
                # Escolher alternativa com maior fill ratio
                if fill_ratios:
                    max_alt = max(fill_ratios, key=fill_ratios.get)
                    max_ratio = fill_ratios[max_alt]
                    
                    if max_ratio >= self.BUBBLE_FILL_THRESHOLD:
                        detected_answers[question_num] = max_alt
                        print(f"   ✅ Q{question_num}: {max_alt} ({max_ratio:.1%})")
                    else:
                        print(f"   ⚪ Q{question_num}: Nenhuma acima do threshold ({max_ratio:.1%} < {self.BUBBLE_FILL_THRESHOLD:.1%})")
            
            return {
                'answers': detected_answers,
                'fill_ratios': fill_ratios_all
            }
            
        except Exception as e:
            logging.error(f"Erro ao detectar bolhas no bloco 01: {str(e)}")
            return {'answers': {}, 'fill_ratios': {}}
    
    def _detect_bubbles(self, aligned_img: np.ndarray, coordinates_config: Dict, 
                       num_questions: int) -> Dict[str, Any]:
        """
        Detecta bolhas preenchidas na imagem alinhada
        
        Args:
            aligned_img: Imagem alinhada ao canvas A4
            coordinates_config: Configuração de coordenadas
            num_questions: Número total de questões
        
        Returns:
            Dict com 'answers' e 'fill_ratios' para debug
        """
        try:
            # Converter para grayscale
            if len(aligned_img.shape) == 3:
                gray = cv2.cvtColor(aligned_img, cv2.COLOR_BGR2GRAY)
            else:
                gray = aligned_img.copy()
            
            # Aplicar threshold
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            
            coordinates = coordinates_config.get('coordinates', [])
            detected_answers = {}
            fill_ratios_all = {}  # Armazenar todos os fill_ratios para debug
            
            # Agrupar coordenadas por questão
            questions_data = {}
            for coord in coordinates:
                q = coord['question']
                if q not in questions_data:
                    questions_data[q] = []
                questions_data[q].append(coord)
            
            # Detectar para cada questão
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
                    
                    # Extrair ROI da bolha
                    roi = binary[y:y+h, x:x+w]
                    
                    if roi.size == 0:
                        fill_ratios[alt] = 0.0
                        continue
                    
                    # Contar pixels brancos (bolha preenchida aparece como branca no binary invertido)
                    white_pixels = cv2.countNonZero(roi)
                    total_pixels = roi.size
                    fill_ratio = white_pixels / total_pixels if total_pixels > 0 else 0.0
                    
                    fill_ratios[alt] = fill_ratio
                    
                    if self.debug:
                        print(f"   Q{question_num} {alt}: {fill_ratio:.2%} preenchido")
                
                # Armazenar fill_ratios para debug
                fill_ratios_all[question_num] = fill_ratios
                
                # Escolher alternativa com maior fill ratio
                if fill_ratios:
                    max_alt = max(fill_ratios, key=fill_ratios.get)
                    max_ratio = fill_ratios[max_alt]
                    
                    # Só considerar se passar do threshold
                    if max_ratio >= self.BUBBLE_FILL_THRESHOLD:
                        detected_answers[question_num] = max_alt
                        print(f"   ✅ Q{question_num}: {max_alt} ({max_ratio:.1%})")
                    else:
                        print(f"   ⚪ Q{question_num}: Nenhuma alternativa acima do threshold ({max_ratio:.1%} < {self.BUBBLE_FILL_THRESHOLD:.1%})")
            
            return {
                'answers': detected_answers,
                'fill_ratios': fill_ratios_all
            }
            
        except Exception as e:
            logging.error(f"Erro ao detectar bolhas: {str(e)}")
            return {'answers': {}, 'fill_ratios': {}}
    
    def _calculate_score(self, detected_answers: Dict[int, str], 
                        answer_key: Dict[int, str]) -> Dict[str, Any]:
        """
        Calcula score comparando respostas detectadas com gabarito
        
        Returns:
            Dict com score, correct, total, percentage
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
        
        Args:
            test_id: ID da prova
            student_id: ID do aluno
            detected_answers: Dict {questão: resposta_detectada}
            answer_key: Dict {questão: resposta_correta}
        
        Returns:
            Lista de respostas salvas
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
                
                # Verificar se está correta (para questões de múltipla escolha)
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
        
        Args:
            test_id: ID da prova
            student_id: ID do aluno
        
        Returns:
            Dict com resultado da avaliação ou None
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
    
    def _generate_debug_image_block01(self, roi_img: np.ndarray, aligned_img: np.ndarray,
                                     coordinates_config: Dict, detected_answers: Dict[int, str],
                                     fill_ratios_all: Dict[int, Dict[str, float]], answer_key: Dict[int, str],
                                     test_id: str, student_id: str) -> None:
        """
        ETAPA 6: Gera imagem de debug desenhando diretamente no ROI recortado
        
        Sobreposição de resultados na imagem final:
        - Verde = marcada e correta
        - Vermelho = marcada mas incorreta
        - Laranja = deveria ter sido marcada
        - Cinza = não marcada (ok)
        
        Gera imagem de debug mostrando o ROI original e as detecções
        """
        try:
            # IMPORTANTE: Criar cópia ORIGINAL do ROI ANTES de desenhar marcações
            # Esta será a imagem real do usuário para comparação
            roi_original = roi_img.copy()
            
            # Garantir que é BGR
            if len(roi_original.shape) == 2:
                roi_original = cv2.cvtColor(roi_original, cv2.COLOR_GRAY2BGR)
            
            # Salvar imagem original do ROI para debug
            if self.debug:
                debug_path_original = os.path.join(self.debug_dir, f"roi_original_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
                cv2.imwrite(debug_path_original, roi_original)
                print(f"💾 Imagem ORIGINAL do ROI salva: {debug_path_original}")
            
            # Criar cópia do ROI para desenhar marcações
            debug_roi = roi_original.copy()
            
            coordinates = coordinates_config.get('coordinates', [])
            
            # Desenhar cada bolha no ROI
            for coord in coordinates:
                question_num = coord['question']
                alt = coord['alternative']
                x = coord['x']
                y = coord['y']
                w = coord['width']
                h = coord['height']
                
                # VALIDAÇÃO CRÍTICA: Garantir que coordenadas estão dentro do ROI
                roi_h, roi_w = roi_img.shape[:2]
                if x < 0 or y < 0 or x + w > roi_w or y + h > roi_h:
                    if self.debug:
                        print(f"⚠️ Coordenada fora do ROI: Q{question_num}{alt} em ({x}, {y}) - ROI: {roi_w}x{roi_h}")
                    continue
                
                # VALIDAÇÃO ADICIONAL: Verificar se está muito próximo das bordas (pode indicar erro)
                margin = 5
                if x < margin or y < margin or x + w > roi_w - margin or y + h > roi_h - margin:
                    if self.debug and question_num <= 3:  # Debug apenas primeiras questões
                        print(f"⚠️ Coordenada próxima da borda do ROI: Q{question_num}{alt} em ({x}, {y})")
                
                # Obter fill ratio
                fill_ratio = fill_ratios_all.get(question_num, {}).get(alt, 0.0)
                
                # Determinar cor baseado no resultado
                detected_answer = detected_answers.get(question_num)
                correct_answer = answer_key.get(question_num, '')
                
                if detected_answer == alt:
                    # Bolha detectada como marcada
                    if alt == correct_answer:
                        color = (0, 255, 0)  # Verde - correta
                        status = "✓ CORRETA"
                    else:
                        color = (0, 0, 255)  # Vermelho - incorreta
                        status = "✗ INCORRETA"
                else:
                    # Bolha não detectada
                    if alt == correct_answer:
                        color = (0, 165, 255)  # Laranja - deveria estar marcada
                        status = "⚠ FALTA"
                    else:
                        color = (128, 128, 128)  # Cinza - não marcada (ok)
                        status = ""
                
                # Desenhar retângulo
                cv2.rectangle(debug_roi, (x, y), (x + w, y + h), color, 2)
                
                # Desenhar texto com informações (apenas para primeiras questões para não poluir)
                if question_num <= 10:  # Mostrar apenas primeiras 10 questões
                    text = f"Q{question_num}{alt}"
                    text_size = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.4, 1)[0]
                    
                    # Fundo para texto
                    cv2.rectangle(debug_roi, 
                                (x, y - text_size[1] - 4), 
                                (x + text_size[0] + 4, y), 
                                color, -1)
                    
                    # Texto
                    cv2.putText(debug_roi, text, (x + 2, y - 2),
                              cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
                    
                    # Porcentagem abaixo da bolha
                    percent_text = f"{fill_ratio:.0%}"
                    cv2.putText(debug_roi, percent_text, (x, y + h + 12),
                              cv2.FONT_HERSHEY_SIMPLEX, 0.3, color, 1)
                    
                    # Status se houver
                    if status:
                        cv2.putText(debug_roi, status, (x, y + h + 24),
                                  cv2.FONT_HERSHEY_SIMPLEX, 0.3, color, 1)
            
            # Criar imagem final com informações
            roi_h, roi_w = debug_roi.shape[:2]
            
            # Adicionar espaço no topo para informações
            info_height = 100
            debug_final = np.ones((roi_h + info_height, roi_w, 3), dtype=np.uint8) * 255
            debug_final[info_height:, :] = debug_roi
            
            # Adicionar informações gerais no topo
            info_text = [
                f"Test ID: {test_id[:8]}...",
                f"Student ID: {student_id[:8]}...",
                f"Detectadas: {len(detected_answers)}/{len(answer_key)}",
                f"Threshold: {self.BUBBLE_FILL_THRESHOLD:.0%}",
                f"ROI: {roi_w}x{roi_h}px"
            ]
            
            y_offset = 20
            for i, text in enumerate(info_text):
                cv2.putText(debug_final, text, (10, y_offset + i * 18),
                          cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2)
                cv2.putText(debug_final, text, (10, y_offset + i * 18),
                          cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            # Legenda de cores (no canto inferior direito)
            legend_y = roi_h + 20
            legend_x = roi_w - 300
            legend_items = [
                ("Verde", (0, 255, 0), "Detectada e correta"),
                ("Vermelho", (0, 0, 255), "Detectada e incorreta"),
                ("Laranja", (0, 165, 255), "Deveria estar marcada"),
                ("Cinza", (128, 128, 128), "Não marcada (ok)")
            ]
            
            for i, (label, color, desc) in enumerate(legend_items):
                y_pos = legend_y + i * 20
                cv2.rectangle(debug_final, (legend_x, y_pos - 10), (legend_x + 20, y_pos + 5), color, -1)
                cv2.putText(debug_final, f"{label}: {desc}", (legend_x + 25, y_pos),
                          cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 1)
            
            # Criar imagem comparativa: ROI Original | ROI com Detecções
            create_comparison = True
            
            if create_comparison:
                # Redimensionar ambas as imagens para mesma altura para comparação
                user_h, user_w = roi_original.shape[:2]
                max_h = user_h
                
                # IMPORTANTE: Usar roi_original (imagem REAL do usuário) para comparação
                roi_original_resized = roi_original.copy()
                
                # Também redimensionar a versão com marcações para mostrar ao lado
                debug_roi_resized = debug_roi.copy()
                
                # Criar imagem lado a lado: ROI Original | ROI com Marcações
                gap = 20
                # Calcular largura total: original + gap + com marcações
                total_width = roi_original_resized.shape[1] + gap + debug_roi_resized.shape[1]
                comparison_img = np.ones((max_h + 100, total_width, 3), dtype=np.uint8) * 255
                
                # Colocar imagem ORIGINAL do ROI à esquerda (sem marcações)
                comparison_img[:max_h, :roi_original_resized.shape[1]] = roi_original_resized
                
                # Colocar imagem do ROI com marcações à direita
                start_x_marked = roi_original_resized.shape[1] + gap
                comparison_img[:max_h, start_x_marked:start_x_marked + debug_roi_resized.shape[1]] = debug_roi_resized
                
                # Adicionar títulos
                cv2.putText(comparison_img, "ROI ORIGINAL DO USUARIO", 
                          (10, max_h + 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
                cv2.putText(comparison_img, "ROI COM DETECCOES", 
                          (start_x_marked + 10, max_h + 25), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
                
                # Adicionar informações
                info_y = max_h + 50
                info_lines = [
                    f"Test ID: {test_id[:8]}... | Student ID: {student_id[:8]}...",
                    f"Detectadas: {len(detected_answers)}/{len(answer_key)} | Threshold: {self.BUBBLE_FILL_THRESHOLD:.0%}",
                    f"Cores na imagem = deteccoes (Verde=correta, Vermelho=incorreta, Laranja=deveria estar marcada)"
                ]
                
                for i, line in enumerate(info_lines):
                    cv2.putText(comparison_img, line, (10, info_y + i * 20),
                              cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
                
                # Salvar imagem comparativa
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                comparison_filename = f"orm_comparison_{test_id[:8]}_{student_id[:8]}_{timestamp}.png"
                comparison_path = os.path.join(self.debug_dir, comparison_filename)
                cv2.imwrite(comparison_path, comparison_img)
                print(f"💾 Imagem comparativa salva: {comparison_path}")
            
            # Salvar imagem de debug
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            debug_filename = f"orm_debug_{test_id[:8]}_{student_id[:8]}_{timestamp}.png"
            debug_path = os.path.join(self.debug_dir, debug_filename)
            
            cv2.imwrite(debug_path, debug_final)
            print(f"💾 Imagem de debug salva: {debug_path}")
            
        except Exception as e:
            logging.error(f"Erro ao gerar imagem de debug: {str(e)}")
            import traceback
            logging.error(traceback.format_exc())
    
    def _generate_debug_image(self, aligned_img: np.ndarray, coordinates_config: Dict,
                             detected_answers: Dict[int, str], fill_ratios_all: Dict[int, Dict[str, float]],
                             answer_key: Dict[int, str], test_id: str, student_id: str) -> None:
        """
        Gera imagem de debug mostrando as áreas de detecção e resultados
        
        Args:
            aligned_img: Imagem processada
            coordinates_config: Configuração de coordenadas
            detected_answers: Respostas detectadas
            fill_ratios_all: Fill ratios de todas as alternativas
            answer_key: Gabarito
            test_id: ID da prova
            student_id: ID do aluno
        """
        try:
            # Criar cópia da imagem para desenhar
            debug_img = aligned_img.copy()
            
            # Garantir que é BGR
            if len(debug_img.shape) == 2:
                debug_img = cv2.cvtColor(debug_img, cv2.COLOR_GRAY2BGR)
            
            coordinates = coordinates_config.get('coordinates', [])
            
            # Desenhar cada bolha
            for coord in coordinates:
                question_num = coord['question']
                alt = coord['alternative']
                x = coord['x']
                y = coord['y']
                w = coord['width']
                h = coord['height']
                
                # Obter fill ratio
                fill_ratio = fill_ratios_all.get(question_num, {}).get(alt, 0.0)
                
                # Determinar cor baseado no resultado
                detected_answer = detected_answers.get(question_num)
                correct_answer = answer_key.get(question_num, '')
                
                if detected_answer == alt:
                    # Bolha detectada como marcada
                    if alt == correct_answer:
                        color = (0, 255, 0)  # Verde - correta
                        status = "✓ CORRETA"
                    else:
                        color = (0, 0, 255)  # Vermelho - incorreta
                        status = "✗ INCORRETA"
                else:
                    # Bolha não detectada
                    if alt == correct_answer:
                        color = (0, 165, 255)  # Laranja - deveria estar marcada
                        status = "⚠ FALTA"
                    else:
                        color = (128, 128, 128)  # Cinza - não marcada (ok)
                        status = ""
                
                # Desenhar retângulo
                cv2.rectangle(debug_img, (x, y), (x + w, y + h), color, 2)
                
                # Desenhar texto com informações
                text = f"Q{question_num}{alt}"
                text_size = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.4, 1)[0]
                
                # Fundo para texto
                cv2.rectangle(debug_img, 
                            (x, y - text_size[1] - 4), 
                            (x + text_size[0] + 4, y), 
                            color, -1)
                
                # Texto
                cv2.putText(debug_img, text, (x + 2, y - 2),
                          cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
                
                # Porcentagem abaixo da bolha
                percent_text = f"{fill_ratio:.0%}"
                cv2.putText(debug_img, percent_text, (x, y + h + 12),
                          cv2.FONT_HERSHEY_SIMPLEX, 0.3, color, 1)
                
                # Status se houver
                if status:
                    cv2.putText(debug_img, status, (x, y + h + 24),
                              cv2.FONT_HERSHEY_SIMPLEX, 0.3, color, 1)
            
            # Adicionar informações gerais no topo
            info_text = [
                f"Test ID: {test_id[:8]}...",
                f"Student ID: {student_id[:8]}...",
                f"Detectadas: {len(detected_answers)}/{len(answer_key)}",
                f"Threshold: {self.BUBBLE_FILL_THRESHOLD:.0%}"
            ]
            
            y_offset = 20
            for i, text in enumerate(info_text):
                cv2.putText(debug_img, text, (10, y_offset + i * 20),
                          cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2)
                cv2.putText(debug_img, text, (10, y_offset + i * 20),
                          cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            # Legenda de cores
            legend_y = debug_img.shape[0] - 100
            legend_items = [
                ("Verde", (0, 255, 0), "Detectada e correta"),
                ("Vermelho", (0, 0, 255), "Detectada e incorreta"),
                ("Laranja", (0, 165, 255), "Deveria estar marcada"),
                ("Cinza", (128, 128, 128), "Não marcada (ok)")
            ]
            
            for i, (label, color, desc) in enumerate(legend_items):
                y_pos = legend_y + i * 20
                cv2.rectangle(debug_img, (10, y_pos - 10), (30, y_pos + 5), color, -1)
                cv2.putText(debug_img, f"{label}: {desc}", (35, y_pos),
                          cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 1)
            
            # Salvar imagem
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            debug_filename = f"orm_debug_{test_id[:8]}_{student_id[:8]}_{timestamp}.png"
            debug_path = os.path.join(self.debug_dir, debug_filename)
            
            cv2.imwrite(debug_path, debug_img)
            print(f"💾 Imagem de debug salva: {debug_path}")
            
        except Exception as e:
            logging.error(f"Erro ao gerar imagem de debug: {str(e)}")
            import traceback
            logging.error(traceback.format_exc())


# Função de conveniência para uso direto
def processar_prova_orm(image_path: str = None, image_data: str = None, 
                        test_id: str = None, debug: bool = False) -> Dict[str, Any]:
    """
    Função de conveniência para processar uma prova usando o sistema OMR
    
    Args:
        image_path: Caminho para a imagem
        image_data: Dados da imagem em base64
        test_id: ID da prova (opcional, será lido do QR code)
        debug: Se True, gera logs e imagens de debug
    
    Returns:
        Dict com resultado do processamento
    """
    sistema = SistemaORM(debug=debug)
    return sistema.process_exam(image_path=image_path, image_data=image_data)

