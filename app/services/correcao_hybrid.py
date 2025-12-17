# -*- coding: utf-8 -*-
"""
Serviço de Correção Híbrida de Provas Institucionais
Combina detecção geométrica (OpenCV) com estrutura de salvamento do correcaoIA
Usa algoritmo comprovado de test_correction para detectar marcações
"""

import cv2
import numpy as np
import json
import logging
from typing import Dict, List, Optional, Tuple, Any
from app import db
from app.models.testQuestion import TestQuestion
from app.models.question import Question
from app.models.studentAnswer import StudentAnswer
from app.models.student import Student
from datetime import datetime


class CorrecaoHybrid:
    """
    Serviço híbrido para correção de provas institucionais
    Usa detecção geométrica ao invés de IA
    """
    
    def __init__(self, debug: bool = False):
        """
        Inicializa o serviço de correção híbrida
        
        Args:
            debug: Se True, gera logs detalhados
        """
        self.debug = debug
        self.save_debug_images = False  # Desabilita salvamento de imagens de debug
        self.logger = logging.getLogger(__name__)
        self.logger.info("Correção Híbrida inicializada (detecção geométrica)")
    
    def _save_debug_image(self, path: str, img):
        """Salva imagem de debug apenas se save_debug_images estiver habilitado"""
        if self.save_debug_images:
            self._save_debug_image(path, img)
    
    def corrigir_prova_geometrica(self, image_data: bytes, test_id: str) -> Dict[str, Any]:
        """
        Processa correção completa usando detecção geométrica:
        1. Detecta QR Code para identificar aluno
        2. Detecta triângulos de alinhamento (4 cantos)
        3. Corrige perspectiva (paper90)
        4. Detecta quadrados de referência (getOurSqr)
        5. Detecta círculos preenchidos (getAnswers)
        6. Compara com gabarito e salva no banco
        
        Args:
            image_data: Imagem em bytes (JPEG/PNG)
            test_id: ID da prova
            
        Returns:
            Dict com resultados da correção
        """
        try:
            # 1. Decodificar imagem
            img = self._decode_image(image_data)
            if img is None:
                return {"success": False, "error": "Erro ao decodificar imagem"}
            
            # 2. Detectar QR Code (usar método robusto do correcaoIA)
            qr_result = self._detectar_qr_code(img)
            if not qr_result or 'student_id' not in qr_result:
                return {"success": False, "error": "QR Code não detectado ou inválido"}
            
            student_id = qr_result['student_id']
            test_id_from_qr = qr_result.get('test_id', test_id)
            
            # Validar test_id
            if test_id_from_qr != test_id:
                self.logger.warning(f"Test ID do QR ({test_id_from_qr}) diferente do fornecido ({test_id})")
            
            # Validar se student_id existe no banco de dados
            student = Student.query.get(student_id)
            if not student:
                self.logger.error(f"Student ID {student_id} não encontrado no banco de dados")
                return {"success": False, "error": f"Aluno com ID {student_id} não encontrado no sistema"}
            
            # 3. Corrigir perspectiva usando triângulos de alinhamento
            img_aligned = self._paper90(img)
            if img_aligned is None:
                return {"success": False, "error": "Não foi possível detectar triângulos de alinhamento"}
            
            # 4. Buscar gabarito do teste
            gabarito = self._buscar_gabarito(test_id)
            if not gabarito:
                return {"success": False, "error": "Gabarito não encontrado para esta prova"}
            
            num_questions = len(gabarito)
            
            # 5. Fazer crop baseado nos triângulos (remover área externa)
            top, btt = self._getPTCrop(img_aligned)
            img_crop = img_aligned[top[1]:btt[1], top[0]:btt[0]]
            
            # 6. Detectar respostas marcadas (apenas círculos, sem depender de quadrados)
            respostas_aluno = self._getAnswers(img_crop, num_questions=num_questions)
            
            if not respostas_aluno:
                return {"success": False, "error": "Erro ao detectar respostas marcadas"}
            
            # 7. Processar e validar respostas
            # _getAnswers já retorna {question_num: 'A'|'B'|'C'|'D'|None}
            validated_answers = {}
            for q_num in range(1, num_questions + 1):
                validated_answers[q_num] = respostas_aluno.get(q_num)  # Pode ser 'A', 'B', 'C', 'D' ou None
            
            # 8. Calcular correção
            correction = self._calcular_correcao(validated_answers, gabarito)
            
            # 9. Salvar respostas no banco
            saved_answers = self._salvar_respostas_no_banco(
                test_id=test_id,
                student_id=student_id,
                respostas_detectadas=validated_answers,
                gabarito=gabarito
            )
            
            # 10. Criar sessão mínima para EvaluationResultService
            session_id = self._criar_sessao_minima_para_evaluation_result(
                test_id=test_id,
                student_id=student_id
            )
            
            if not session_id:
                self.logger.warning("Não foi possível criar sessão mínima, continuando sem EvaluationResult")
                evaluation_result = None
            else:
                # 11. Calcular nota, proficiência e classificação
                from app.services.evaluation_result_service import EvaluationResultService
                
                evaluation_result = EvaluationResultService.calculate_and_save_result(
                    test_id=test_id,
                    student_id=student_id,
                    session_id=session_id
                )
            
            # 12. Calcular resultado final
            correct_count = correction['correct']
            total_count = correction['total_questions']
            percentage = correction['score_percentage']
            
            # Preparar resposta com todos os campos
            response_data = {
                "success": True,
                "student_id": student_id,
                "test_id": test_id,
                "correct": correct_count,
                "total": total_count,
                "percentage": percentage,
                "answers": validated_answers,
                "correction": correction,
                "saved_answers": saved_answers,
                "detection_method": "geometric"  # Indicador do método usado
            }
            
            # Adicionar campos calculados pelo EvaluationResultService
            if evaluation_result:
                response_data["grade"] = evaluation_result.get('grade', 0.0)
                response_data["proficiency"] = evaluation_result.get('proficiency', 0.0)
                response_data["classification"] = evaluation_result.get('classification', 'Não definido')
                response_data["evaluation_result_id"] = evaluation_result.get('id')
                response_data["score_percentage"] = evaluation_result.get('score_percentage', percentage)
                response_data["correct_answers"] = correct_count
                response_data["total_questions"] = total_count
            else:
                # Fallback se não conseguir calcular
                self.logger.warning("EvaluationResultService não retornou resultado")
                response_data["grade"] = (correct_count / total_count * 10) if total_count > 0 else 0.0
                response_data["proficiency"] = 0.0
                response_data["classification"] = "Não calculado"
                response_data["evaluation_result_id"] = None
                response_data["score_percentage"] = percentage
                response_data["correct_answers"] = correct_count
                response_data["total_questions"] = total_count
            
            # 13. Marcar formulário físico como corrigido
            self._marcar_formulario_como_corrigido(test_id, student_id)
            
            return response_data
            
        except Exception as e:
            self.logger.error(f"Erro na correção geométrica: {str(e)}", exc_info=True)
            return {"success": False, "error": f"Erro interno: {str(e)}"}
    
    def _decode_image(self, image_data: bytes) -> Optional[np.ndarray]:
        """Decodifica imagem de bytes para numpy array"""
        try:
            nparr = np.frombuffer(image_data, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            return img
        except Exception as e:
            self.logger.error(f"Erro ao decodificar imagem: {str(e)}")
            return None
    
    def _detectar_qr_code(self, img: np.ndarray) -> Optional[Dict[str, str]]:
        """
        Detecta QR Code na imagem usando múltiplas estratégias robustas
        Tenta várias técnicas em cascata para melhorar detecção em imagens de baixa qualidade
        """
        try:
            # Converter para grayscale se necessário
            if len(img.shape) == 3:
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            else:
                gray = img.copy()
            
            h, w = gray.shape
            
            # Estratégia 1: Detecção direta na imagem original
            qr_data = self._detectar_qr_direto(gray)
            if qr_data:
                return self._parsear_qr_data(qr_data)
            
            # Estratégia 2: Pré-processamento com múltiplas técnicas
            processed_images = self._preprocessar_imagem_para_qr(gray)
            for i, processed_img in enumerate(processed_images):
                qr_data = self._detectar_qr_direto(processed_img)
                if qr_data:
                    return self._parsear_qr_data(qr_data)
            
            # Estratégia 3: Detecção por regiões (QR Code geralmente no canto superior direito)
            qr_data = self._detectar_qr_por_regioes(img)
            if qr_data:
                return self._parsear_qr_data(qr_data)
            
            # Estratégia 4: Redimensionamento múltiplo
            qr_data = self._detectar_qr_redimensionamento_multiplo(img)
            if qr_data:
                return self._parsear_qr_data(qr_data)
            
            # Estratégia 5: Método resiliente (com upscale e tight-crop)
            qr_data = self._detectar_qr_resiliente(img)
            if qr_data:
                return self._parsear_qr_data(qr_data)
            
            self.logger.warning("❌ Nenhum QR Code detectado após todas as estratégias")
            return None
                
        except Exception as e:
            self.logger.error(f"Erro ao detectar QR Code: {str(e)}", exc_info=True)
            return None
    
    def _detectar_qr_direto(self, img: np.ndarray) -> Optional[str]:
        """
        Detecção direta de QR code usando OpenCV
        """
        try:
            detector = cv2.QRCodeDetector()
            
            # Converter para grayscale se necessário
            if len(img.shape) == 3:
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            else:
                gray = img
            
            # Detecção direta
            data, _, _ = detector.detectAndDecode(gray)
            return data if data else None
            
        except Exception as e:
            self.logger.debug(f"Erro na detecção direta: {str(e)}")
            return None
    
    def _preprocessar_imagem_para_qr(self, img: np.ndarray) -> List[np.ndarray]:
        """
        Pré-processa imagem com múltiplas técnicas para melhorar detecção de QR code
        Retorna lista de imagens processadas para testar
        """
        processed_images = []
        
        try:
            # Garantir que é grayscale
            if len(img.shape) == 3:
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            else:
                gray = img.copy()
            
            # 1. Imagem original em grayscale
            processed_images.append(gray)
            
            # 2. Ajuste de contraste (CLAHE)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(gray)
            processed_images.append(enhanced)
            
            # 3. Threshold OTSU
            _, thresh_otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            processed_images.append(thresh_otsu)
            
            # 4. Threshold adaptativo
            thresh_adapt = cv2.adaptiveThreshold(
                gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                cv2.THRESH_BINARY, 11, 2
            )
            processed_images.append(thresh_adapt)
            
            # 5. Múltiplos thresholds manuais
            for threshold in [100, 127, 150, 180]:
                _, thresh = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)
                processed_images.append(thresh)
            
            # 6. Morfologia para limpar ruído
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
            morphed = cv2.morphologyEx(gray, cv2.MORPH_CLOSE, kernel)
            morphed = cv2.morphologyEx(morphed, cv2.MORPH_OPEN, kernel)
            processed_images.append(morphed)
            
            # 7. Redimensionamento para diferentes escalas
            for scale in [0.5, 1.5, 2.0]:
                new_width = int(gray.shape[1] * scale)
                new_height = int(gray.shape[0] * scale)
                resized = cv2.resize(gray, (new_width, new_height), interpolation=cv2.INTER_CUBIC)
                processed_images.append(resized)
            
            # 8. Filtro gaussiano para suavizar
            blurred = cv2.GaussianBlur(gray, (3, 3), 0)
            processed_images.append(blurred)
            
            # 9. Equalização de histograma
            equalized = cv2.equalizeHist(gray)
            processed_images.append(equalized)
            
            # 10. Inversão de cores (para QR codes escuros em fundo claro)
            inverted = cv2.bitwise_not(gray)
            processed_images.append(inverted)
            
            return processed_images
            
        except Exception as e:
            self.logger.error(f"Erro no pré-processamento: {str(e)}")
            return [gray] if 'gray' in locals() else []
    
    def _detectar_qr_por_regioes(self, img: np.ndarray) -> Optional[str]:
        """
        Detecta QR code por regiões específicas da imagem
        QR code geralmente está no canto superior direito
        """
        try:
            # Converter para grayscale se necessário
            if len(img.shape) == 3:
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            else:
                gray = img.copy()
            
            height, width = gray.shape
            detector = cv2.QRCodeDetector()
            
            # Regiões para buscar QR code (priorizando canto superior direito)
            regions = [
                # Canto superior direito (mais comum)
                (width//2, 0, width, height//2),
                # Canto superior esquerdo
                (0, 0, width//2, height//2),
                # Região central superior
                (width//4, 0, 3*width//4, height//2),
                # Região central
                (width//4, height//4, 3*width//4, 3*height//4),
                # Região inferior direita
                (width//2, height//2, width, height),
                # Região inferior esquerda
                (0, height//2, width//2, height),
            ]
            
            for i, (x1, y1, x2, y2) in enumerate(regions):
                roi = gray[y1:y2, x1:x2]
                if roi.size > 0:
                    self.logger.debug(f"📍 Testando região {i+1}: ({x1},{y1}) a ({x2},{y2})")
                    data, _, _ = detector.detectAndDecode(roi)
                    if data:
                        return data
            
            return None
            
        except Exception as e:
            self.logger.debug(f"Erro na detecção por regiões: {str(e)}")
            return None
    
    def _detectar_qr_redimensionamento_multiplo(self, img: np.ndarray) -> Optional[str]:
        """
        Detecção de QR code com múltiplos redimensionamentos
        Útil para QR codes muito pequenos ou muito grandes
        """
        try:
            detector = cv2.QRCodeDetector()
            
            # Converter para grayscale se necessário
            if len(img.shape) == 3:
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            else:
                gray = img.copy()
            
            h, w = gray.shape
            
            # Diferentes escalas para testar
            scales = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0]
            
            self.logger.debug(f"📏 Dimensões originais: {w}x{h}")
            
            for scale in scales:
                new_w = int(w * scale)
                new_h = int(h * scale)
                
                if new_w > 50 and new_h > 50:  # Imagem deve ser grande o suficiente
                    resized = cv2.resize(gray, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
                    data, _, _ = detector.detectAndDecode(resized)
                    if data:
                        return data
            
            return None
            
        except Exception as e:
            self.logger.debug(f"Erro no redimensionamento múltiplo: {str(e)}")
            return None
    
    def _detectar_qr_resiliente(self, img: np.ndarray, upscale: int = 5, margin_factor: float = 0.35) -> Optional[str]:
        """
        Detecção de QR robusta:
        - calcula ROI (canto superior direito) baseado no layout A4
        - tenta achar tight-crop via contornos quadrados (remove bordas)
        - amplia o tight-crop (upscale)
        - tenta cv2.QRCodeDetector e em fallback pyzbar (se instalado)
        """
        try:
            # Converter para grayscale se necessário
            if len(img.shape) == 3:
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            else:
                gray = img.copy()
            
            h, w = gray.shape
            
            # Estimar posição do QR code (canto superior direito)
            # Baseado em layout A4 típico
            proporcao_x = w / 1240.0
            proporcao_y = h / 1753.0
            qr_size_estimado = max(32, int(200 * min(proporcao_x, proporcao_y)))
            qr_x_estimado = w - qr_size_estimado - int(20 * proporcao_x)
            qr_y_estimado = int(20 * proporcao_y)
            
            margin = int(qr_size_estimado * margin_factor)
            x_start = max(0, qr_x_estimado - margin)
            y_start = max(0, qr_y_estimado - margin)
            x_end = min(w, qr_x_estimado + qr_size_estimado + margin)
            y_end = min(h, qr_y_estimado + qr_size_estimado + margin)
            
            roi = gray[y_start:y_end, x_start:x_end].copy()
            if roi.size == 0:
                return None
            
            # Tentar tight-crop via contornos
            def tight_crop_from_roi(img_roi):
                blur = cv2.GaussianBlur(img_roi, (3, 3), 0)
                _, bw = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                contours, _ = cv2.findContours(bw, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                if not contours:
                    return None
                
                contours = sorted(contours, key=cv2.contourArea, reverse=True)
                for cnt in contours[:5]:
                    area = cv2.contourArea(cnt)
                    if area < 100:
                        continue
                    peri = cv2.arcLength(cnt, True)
                    approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
                    if len(approx) == 4:
                        x, y, wc, hc = cv2.boundingRect(approx)
                        if wc > img_roi.shape[1] * 0.2 and hc > img_roi.shape[0] * 0.2:
                            pad = max(1, int(min(wc, hc) * 0.03))
                            return (max(0, x - pad), max(0, y - pad), 
                                   min(img_roi.shape[1], x + wc + pad), 
                                   min(img_roi.shape[0], y + hc + pad))
                
                # Fallback: bounding box do maior contorno
                cnt = contours[0]
                x, y, wc, hc = cv2.boundingRect(cnt)
                return (x, y, x + wc, y + hc)
            
            tight = tight_crop_from_roi(roi)
            if tight is not None:
                tx0, ty0, tx1, ty1 = tight
                roi_tight = roi[ty0:ty1, tx0:tx1].copy()
            else:
                roi_tight = roi
            
            # Ampliar tight-crop
            if upscale <= 1:
                upscale = 2
            roi_up = cv2.resize(roi_tight, None, fx=upscale, fy=upscale, interpolation=cv2.INTER_CUBIC)
            
            # Criar variantes para testar
            gray_up = roi_up if len(roi_up.shape) == 2 else cv2.cvtColor(roi_up, cv2.COLOR_BGR2GRAY)
            _, otsu = cv2.threshold(gray_up, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            gauss = cv2.GaussianBlur(gray_up, (0, 0), sigmaX=1.0)
            unsharp = cv2.addWeighted(gray_up, 1.4, gauss, -0.4, 0)
            
            candidates = [
                ("ampliado_color", roi_up),
                ("ampliado_gray", gray_up),
                ("ampliado_otsu", otsu),
                ("ampliado_unsharp", unsharp),
            ]
            
            # Tentar OpenCV detector
            detector = cv2.QRCodeDetector()
            for name, cand in candidates:
                try:
                    if cand.ndim == 2:  # gray
                        cand_for_cv = cv2.cvtColor(cand, cv2.COLOR_GRAY2BGR)
                    else:
                        cand_for_cv = cand
                    data, _, _ = detector.detectAndDecode(cand_for_cv)
                    if data:
                        return data
                except Exception as e:
                    self.logger.debug(f"cv2 detect erro {name}: {e}")
            
            # Fallback: tentar pyzbar (se instalado)
            try:
                from pyzbar.pyzbar import decode as pdecode
                for name, cand in candidates:
                    try:
                        results = pdecode(cand)
                        if results:
                            for r in results:
                                raw = r.data
                                try:
                                    txt = raw.decode("utf-8")
                                except Exception:
                                    txt = str(raw)
                                return txt
                    except Exception as e:
                        self.logger.debug(f"pyzbar erro {name}: {e}")
            except ImportError:
                self.logger.debug("pyzbar não disponível")
            
            return None
            
        except Exception as e:
            self.logger.debug(f"Erro na detecção resiliente: {str(e)}")
            return None
    
    def _parsear_qr_data(self, data: str) -> Optional[Dict[str, str]]:
        """
        Parseia dados do QR code (JSON ou string simples)
        """
        try:
            if not data:
                return None
            
            # Tentar parsear como JSON
            try:
                qr_json = json.loads(data)
                return {
                    'student_id': qr_json.get('student_id'),
                    'test_id': qr_json.get('test_id')
                }
            except json.JSONDecodeError:
                # Se não for JSON, tratar como student_id direto
                return {
                    'student_id': data.strip(),
                    'test_id': None
                }
                
        except Exception as e:
            self.logger.error(f"Erro ao parsear dados do QR: {str(e)}")
            return None
    
    def _paper90(self, img: np.ndarray) -> Optional[np.ndarray]:
        """
        Detecta 4 triângulos de alinhamento e corrige perspectiva
        Baseado na função paper90 de test_correction/util.py
        """
        try:
            import os
            from datetime import datetime
            
            # Criar pasta de debug se não existir
            debug_dir = "debug_triangles"
            if not os.path.exists(debug_dir):
                os.makedirs(debug_dir)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Salvar imagem original
            self._save_debug_image(f"{debug_dir}/{timestamp}_01_original.jpg", img)
            
            # Converter para grayscale
            if len(img.shape) == 3:
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            else:
                gray = img.copy()
            
            self._save_debug_image(f"{debug_dir}/{timestamp}_02_grayscale.jpg", gray)
            
            # Aplicar threshold
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            self._save_debug_image(f"{debug_dir}/{timestamp}_03_binary.jpg", binary)
            
            # Encontrar contornos
            contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            # Imagem para debug de contornos
            img_debug = img.copy()
            
            # Filtrar triângulos
            triangles = []
            all_triangles_info = []
            
            for idx, cnt in enumerate(contours):
                approx = cv2.approxPolyDP(cnt, 0.04 * cv2.arcLength(cnt, True), True)
                area = cv2.contourArea(approx)
                
                if len(approx) == 3:  # É um triângulo
                    M = cv2.moments(approx)
                    if M["m00"] != 0:
                        cx = int(M["m10"] / M["m00"])
                        cy = int(M["m01"] / M["m00"])
                        
                        # Threshold mais flexível para triângulos SVG (podem variar com resolução)
                        min_area = 50  # Área mínima (triângulos muito pequenos são ruído)
                        max_area = 50000  # Área máxima (triângulos muito grandes são outros elementos)
                        
                        all_triangles_info.append({
                            "index": idx,
                            "area": area,
                            "center": (cx, cy),
                            "accepted": min_area < area < max_area
                        })
                        
                        if min_area < area < max_area:
                            triangles.append(approx)
                            # Desenhar triângulo aceito em verde
                            cv2.drawContours(img_debug, [approx], -1, (0, 255, 0), 3)
                            cv2.circle(img_debug, (cx, cy), 8, (0, 255, 0), -1)
                            cv2.putText(img_debug, f"T{len(triangles)} A:{int(area)}", 
                                    (cx+15, cy), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                        else:
                            # Desenhar triângulo rejeitado em vermelho
                            cv2.drawContours(img_debug, [approx], -1, (0, 0, 255), 2)
                            cv2.putText(img_debug, f"X A:{int(area)}", 
                                    (cx+10, cy), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
            
            # Salvar imagem com todos os triângulos detectados
            self._save_debug_image(f"{debug_dir}/{timestamp}_04_all_triangles.jpg", img_debug)
            
            # Salvar log de triângulos
            with open(f"{debug_dir}/{timestamp}_triangles_log.txt", "w") as f:
                f.write(f"Total de triângulos encontrados: {len(all_triangles_info)}\n")
                f.write(f"Triângulos aceitos (50 < area < 50000): {len(triangles)}\n\n")
                for info in all_triangles_info:
                    f.write(f"Triângulo {info['index']}: Area={info['area']:.2f}, "
                        f"Centro={info['center']}, Aceito={info['accepted']}\n")
            
            if len(triangles) < 4:
                self.logger.warning(f"Apenas {len(triangles)} triângulos detectados (necessário 4)")
                if self.save_debug_images:
                    self.logger.warning(f"Debug salvo em: {debug_dir}/{timestamp}_*.jpg")
                return None
            
            # Ordenar triângulos por área (pegar os 4 maiores)
            triangles = sorted(triangles, key=cv2.contourArea, reverse=True)[:4]
            
            # Calcular centros dos triângulos
            centers = []
            img_final_triangles = img.copy()
            
            for idx, tri in enumerate(triangles):
                M = cv2.moments(tri)
                if M["m00"] != 0:
                    cx = int(M["m10"] / M["m00"])
                    cy = int(M["m01"] / M["m00"])
                    centers.append([cx, cy])
                    
                    # Desenhar os 4 triângulos finais em azul
                    cv2.drawContours(img_final_triangles, [tri], -1, (255, 0, 0), 4)
                    cv2.circle(img_final_triangles, (cx, cy), 10, (255, 0, 0), -1)
                    cv2.putText(img_final_triangles, f"#{idx+1}", 
                            (cx+20, cy), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 0, 0), 3)
            
            self._save_debug_image(f"{debug_dir}/{timestamp}_05_final_4_triangles.jpg", img_final_triangles)
            
            if len(centers) != 4:
                return None
            
            # Ordenar pontos: TL, TR, BR, BL
            centers = np.array(centers, dtype="float32")
            centers_ordered = self._ordenar_pontos_triangulos(centers)
            
            # Desenhar ordem dos pontos
            img_ordered = img.copy()
            labels = ["TL", "TR", "BR", "BL"]
            colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)]
            
            for idx, (center, label, color) in enumerate(zip(centers_ordered, labels, colors)):
                cx, cy = int(center[0]), int(center[1])
                cv2.circle(img_ordered, (cx, cy), 15, color, -1)
                cv2.putText(img_ordered, label, (cx+25, cy), 
                        cv2.FONT_HERSHEY_SIMPLEX, 1.2, color, 3)
            
            self._save_debug_image(f"{debug_dir}/{timestamp}_06_ordered_points.jpg", img_ordered)
            
            # Calcular dimensões do retângulo de destino
            width_top = np.linalg.norm(centers_ordered[1] - centers_ordered[0])
            width_bottom = np.linalg.norm(centers_ordered[2] - centers_ordered[3])
            height_left = np.linalg.norm(centers_ordered[3] - centers_ordered[0])
            height_right = np.linalg.norm(centers_ordered[2] - centers_ordered[1])
            
            max_width = int(max(width_top, width_bottom))
            max_height = int(max(height_left, height_right))
            
            # Pontos de destino
            dst = np.array([
                [0, 0],
                [max_width - 1, 0],
                [max_width - 1, max_height - 1],
                [0, max_height - 1]
            ], dtype="float32")
            
            # Calcular matriz de homografia
            M = cv2.getPerspectiveTransform(centers_ordered, dst)
            
            # Aplicar transformação
            warped = cv2.warpPerspective(img, M, (max_width, max_height))
            
            self._save_debug_image(f"{debug_dir}/{timestamp}_07_warped_final.jpg", warped)
            
            if self.save_debug_images:
                self.logger.info(f"✅ Debug salvo em: {debug_dir}/{timestamp}_*.jpg")
            
            return warped
            
        except Exception as e:
            self.logger.error(f"Erro em paper90: {str(e)}", exc_info=True)
            return None
    
    def _ordenar_pontos_triangulos(self, pontos: np.ndarray) -> np.ndarray:
        """Ordena 4 pontos como TL, TR, BR, BL"""
        soma = pontos.sum(axis=1)
        diff = np.diff(pontos, axis=1)
        
        topo_esq = pontos[np.argmin(soma)]
        baixo_dir = pontos[np.argmax(soma)]
        topo_dir = pontos[np.argmin(diff)]
        baixo_esq = pontos[np.argmax(diff)]
        
        return np.array([topo_esq, topo_dir, baixo_dir, baixo_esq], dtype="float32")
    
    def _get_info_triangulos(self, img: np.ndarray) -> List[List]:
        """
        Detecta triângulos na imagem e retorna lista com vértices
        Similar a getInfoTriang do test_correction, mas simplificado
        Retorna: Lista de triângulos, cada um com [[p1, p2, p3], ...]
        """
        import math
        
        # Converter para grayscale
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            gray = img.copy()
        
        # Aplicar threshold
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        
        # Encontrar contornos
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        triangles = []
        for cnt in contours:
            approx = cv2.approxPolyDP(cnt, 0.04 * cv2.arcLength(cnt, True), True)
            area = cv2.contourArea(approx)
            
            # Threshold mais flexível para triângulos SVG
            if len(approx) == 3 and 50 < area < 50000:
                # Formatar como [[x1, y1], [x2, y2], [x3, y3]]
                triangle_points = [[point[0][0], point[0][1]] for point in approx]
                triangles.append(triangle_points)
        
        # Ordenar por área e pegar os 4 maiores
        triangles = sorted(triangles, key=lambda t: self._calculate_triangle_area(t), reverse=True)[:4]
        
        return triangles
    
    def _calculate_triangle_area(self, points: List[List[int]]) -> float:
        """Calcula área de um triângulo dado seus 3 pontos"""
        import math
        p1, p2, p3 = points
        # Fórmula de Heron ou determinante
        area = abs((p1[0]*(p2[1] - p3[1]) + p2[0]*(p3[1] - p1[1]) + p3[0]*(p1[1] - p2[1])) / 2.0)
        return area
    
    def _getPTCrop(self, img: np.ndarray) -> Tuple[List[int], List[int]]:
        """
        Calcula pontos de crop baseado nos triângulos de alinhamento
        Baseado em getPTCrop de test_correction/util.py
        Retorna: (top, bottom) onde top e bottom são [x, y]
        """
        import math
        
        def get_center_of_mass(points: List[List[int]]) -> List[int]:
            """Calcula centro de massa de uma lista de pontos"""
            if len(points) == 0:
                return [0, 0]
            avg_x = sum(p[0] for p in points) / len(points)
            avg_y = sum(p[1] for p in points) / len(points)
            return [int(avg_x), int(avg_y)]
        
        def get_distance(p1: List[int], p2: List[int]) -> float:
            """Calcula distância euclidiana entre dois pontos"""
            return math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)
        
        # Obter triângulos
        triangles = self._get_info_triangulos(img)
        
        if len(triangles) < 4:
            self.logger.warning(f"Apenas {len(triangles)} triângulos encontrados para crop (esperado 4)")
            # Fallback: retornar cantos da imagem
            height, width = img.shape[:2]
            return [0, 0], [width, height]
        
        # Calcular centros de massa de cada triângulo
        triangle_centers = []
        for triangle in triangles:
            center = get_center_of_mass(triangle)
            triangle_centers.append(center)
        
        # Calcular centro da página (centro de massa dos centros dos triângulos)
        page_center = get_center_of_mass(triangle_centers)
        
        # Para cada triângulo, encontrar o ponto mais próximo do centro da página
        quad = []
        comp = []
        
        for triangle in triangles:
            pt1, pt2, pt3 = triangle
            distances = {
                get_distance(pt1, page_center): pt1,
                get_distance(pt2, page_center): pt2,
                get_distance(pt3, page_center): pt3
            }
            
            # Ponto mais próximo do centro
            closest_point = distances[min(distances.keys())]
            x, y = closest_point
            quad.append([[x, y], x + y])
            comp.append(x + y)
        
        # Encontrar top (menor x+y) e bottom (maior x+y)
        maior = max(comp)
        menor = min(comp)
        
        top = None
        bottom = None
        
        for i in quad:
            if i[1] == menor:
                top = i[0]
            elif i[1] == maior:
                bottom = i[0]
        
        if top is None or bottom is None:
            # Fallback
            height, width = img.shape[:2]
            return [0, 0], [width, height]
        
        return top, bottom
    
    def _getOurSqr(self, img: np.ndarray) -> Tuple[List, List, np.ndarray]:
        """
        Detecta quadrados de referência na área de respostas
        Baseado em getOurSqr de test_correction/util.py
        1. Faz crop da imagem usando triângulos de alinhamento
        2. Detecta todos os quadrados na área cropped
        3. Remove quadrados dos cantos
        4. Separa questões e alternativas por posição
        """
        try:
            import os
            from datetime import datetime
            import math
            
            debug_dir = "debug_triangles"
            if not os.path.exists(debug_dir):
                os.makedirs(debug_dir)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            self._save_debug_image(f"{debug_dir}/{timestamp}_08_squares_input.jpg", img)
            
            # Funções auxiliares
            def get_center_of_mass(square):
                """Calcula centro de massa de um quadrado"""
                return (square[0][0]+square[1][0]+square[2][0]+square[3][0])/4, \
                       (square[0][1]+square[1][1]+square[2][1]+square[3][1])/4
            
            def get_sum(square):
                """Soma coordenadas X e Y de um quadrado"""
                return (square[0][0]+square[1][0]+square[2][0]+square[3][0]), \
                       (square[0][1]+square[1][1]+square[2][1]+square[3][1])
            
            def get_proportion(a, b):
                """Calcula proporção entre dois quadrados"""
                sum_a = get_sum(a)
                sum_b = get_sum(b)
                return (abs(sum_a[0]-sum_b[0])/max(sum_a[0],sum_b[0]) if max(sum_a[0],sum_b[0]) > 0 else 0), \
                       (abs(sum_a[1]-sum_b[1])/max(sum_a[1],sum_b[1]) if max(sum_a[1],sum_b[1]) > 0 else 0)
            
            # ETAPA 1: Fazer crop baseado nos triângulos
            top, btt = self._getPTCrop(img)
            im_crop = img[top[1]:btt[1], top[0]:btt[0]]
            
            self._save_debug_image(f"{debug_dir}/{timestamp}_09_cropped.jpg", im_crop)
            
            height, width = im_crop.shape[:2]
            
            # Converter para grayscale e binário
            if len(im_crop.shape) == 3:
                gray = cv2.cvtColor(im_crop, cv2.COLOR_BGR2GRAY)
            else:
                gray = im_crop.copy()
            
            # CORREÇÃO: Não inverter o threshold - quadrados vazados têm borda preta e interior branco
            # Com BINARY_INV, a borda fica desconectada e não forma contorno fechado
            _, im_bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            self._save_debug_image(f"{debug_dir}/{timestamp}_10_binary.jpg", im_bw)
            
            # Usar Canny para detectar bordas finas (recomendado para quadrados vazados)
            edges = cv2.Canny(gray, 50, 150)
            kernel = np.ones((3, 3), np.uint8)
            edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel, iterations=1)
            self._save_debug_image(f"{debug_dir}/{timestamp}_10_canny.jpg", edges)
            
            # Combinar threshold binário com Canny para melhor detecção
            im_bw = cv2.bitwise_or(im_bw, edges)
            self._save_debug_image(f"{debug_dir}/{timestamp}_10_combined.jpg", im_bw)
            
            # CORREÇÃO: RETR_TREE ao invés de RETR_EXTERNAL
            # RETR_EXTERNAL descarta contornos internos - quadrados vazados têm contorno externo + buraco interno
            # RETR_TREE permite pegar contorno externo e contornos internos (buracos)
            contours, hierarchy = cv2.findContours(im_bw, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
            sqr = []
            
            # CORREÇÃO: Para quadrados vazados, não confiar só em cv2.contourArea
            # Quadrado vazado: área geométrica ≠ área visual (só a borda conta)
            # Usar boundingRect para detectar por tamanho da caixa delimitadora
            MIN_SIZE = 12  # Tamanho mínimo (quadrados muito pequenos são ruído)
            MAX_SIZE = 25  # Tamanho máximo (letras grandes como "B" são maiores que isso)
            
            # Função auxiliar: validar se é realmente um quadrado (proporção) - mais tolerante
            def is_square(approx):
                """Verifica se o quadrilátero tem proporções de quadrado"""
                pts = approx.reshape(4, 2)
                w = np.linalg.norm(pts[0] - pts[1])
                h = np.linalg.norm(pts[1] - pts[2])
                return abs(w - h) < 6  # Mais tolerante (era 5 antes)
            
            total_4_vertices = 0
            filtered_by_size = 0
            filtered_by_shape = 0
            
            for cnt in contours:
                approx = cv2.approxPolyDP(cnt, 0.04 * cv2.arcLength(cnt, True), True)
                if len(approx) == 4:
                    total_4_vertices += 1
                    
                    # Validar se é realmente um quadrado (proporção)
                    if not is_square(approx):
                        filtered_by_shape += 1
                        continue
                    
                    # CORREÇÃO: Usar boundingRect ao invés de contourArea
                    # Para quadrados vazados, a área do contorno é inconsistente
                    # A bounding box captura o tamanho real do quadrado
                    x, y, w, h = cv2.boundingRect(approx)
                    
                    # Filtrar por tamanho da bounding box: apenas quadrados com tamanho similar aos marcadores
                    # Isso ignora letras, círculos e textos automaticamente
                    if MIN_SIZE <= w <= MAX_SIZE and MIN_SIZE <= h <= MAX_SIZE:
                        sqr.append(approx)
                    else:
                        filtered_by_size += 1
            
            self.logger.info(f"Quadrados detectados: {total_4_vertices} total, "
                            f"{filtered_by_shape} filtrados por forma (não é quadrado), "
                            f"{filtered_by_size} filtrados por tamanho (fora do range {MIN_SIZE}-{MAX_SIZE}px), "
                            f"{len(sqr)} aceitos")
            
            # Formatar quadrados
            squares = self._formatShape(sqr)
            
            self.logger.info(f"Total de quadrados após formatação: {len(squares)}")
            
            question_squares = []
            alternative_squares = []
            
            threshold = 0.02  # Threshold para remover quadrados dos cantos
            
            # Remover quadrados muito próximos dos cantos (como no original)
            # Ponto mais à esquerda superior
            squares.sort(key=lambda x: get_center_of_mass(x))
            if len(squares) > 0:
                cmx, cmy = get_center_of_mass(squares[0])
                if cmx / width < threshold and cmy / height < threshold:
                    del squares[0]
            
            # Ponto mais à direita inferior
            if len(squares) > 0:
                squares.sort(key=lambda x: get_center_of_mass(x), reverse=True)
                cmx, cmy = get_center_of_mass(squares[0])
                if (width - cmx) / width < threshold and (height - cmy) / height < threshold:
                    del squares[0]
            
            # Ponto mais à esquerda inferior
            if len(squares) > 0:
                cmx = min([get_center_of_mass(x)[0] for x in squares])
                cmy = max([get_center_of_mass(x)[1] for x in squares])
                if cmx / width < threshold and (height - cmy) / height < threshold:
                    # Encontrar e remover
                    for i, sq in enumerate(squares):
                        cmx_sq, cmy_sq = get_center_of_mass(sq)
                        if abs(cmx_sq - cmx) < 5 and abs(cmy_sq - cmy) < 5:
                            del squares[i]
                            break
            
            # Ponto mais à direita superior
            if len(squares) > 0:
                cmx = max([get_center_of_mass(x)[0] for x in squares])
                cmy = min([get_center_of_mass(x)[1] for x in squares])
                cmx_sq, cmy_sq = get_center_of_mass(squares[0])
                if (width - cmx_sq) / width < threshold and cmy_sq / height < threshold:
                    del squares[0]
            
            # ETAPA 2: SEPARAR POR BLOCO (X) PRIMEIRO, DEPOIS POR LINHA (Y)
            # Layout real: DOIS blocos lado a lado (Português | Matemática)
            # Cada linha Y tem 10 quadrados (2 questões + 8 alternativas)
            # Precisamos separar por BLOCO antes de agrupar por linha
            
            MID_X = width / 2  # Meio da página para separar blocos
            
            # Separar quadrados por bloco (esquerda vs direita)
            left_block = []
            right_block = []
            
            for sq in squares:
                cx, cy = get_center_of_mass(sq)
                if cx < MID_X:
                    left_block.append(sq)
                else:
                    right_block.append(sq)
            
            self.logger.info(f"Bloco esquerdo: {len(left_block)} quadrados | "
                           f"Bloco direito: {len(right_block)} quadrados")
            
            # Função auxiliar: agrupar quadrados por linha Y
            def extract_rows(block_squares):
                """Agrupa quadrados de um bloco por linha Y"""
                rows = []
                Y_THRESHOLD = 15  # Tolerância vertical para considerar mesma linha
                
                for sq in block_squares:
                    cx, cy = get_center_of_mass(sq)
                    found = False
                    for row in rows:
                        if len(row) > 0:
                            _, row_y = get_center_of_mass(row[0])
                            if abs(cy - row_y) < Y_THRESHOLD:
                                row.append(sq)
                                found = True
                                break
                    if not found:
                        rows.append([sq])
                
                return rows
            
            # Agrupar por linha Y em cada bloco
            rows_left = extract_rows(left_block)
            rows_right = extract_rows(right_block)
            
            self.logger.info(f"Linhas no bloco esquerdo: {len(rows_left)} | "
                           f"Linhas no bloco direito: {len(rows_right)}")
            
            # Classificar cada linha dentro de cada bloco
            question_squares = []
            alternative_squares = []
            
            for block_name, rows in [("esquerdo", rows_left), ("direito", rows_right)]:
                for row_idx, row in enumerate(rows):
                    if len(row) < 5:
                        self.logger.warning(f"Bloco {block_name}, linha {row_idx + 1}: "
                                          f"tem apenas {len(row)} quadrados (esperado 5: 1 questão + 4 alternativas)")
                        continue  # Linha inválida
                    
                    # Ordenar por X (da esquerda para direita)
                    row.sort(key=lambda x: get_center_of_mass(x)[0])
                    
                    # Primeiro quadrado = questão
                    question_squares.append([row[0], get_center_of_mass(row[0])])
                    
                    # Próximos 4 quadrados = alternativas (A, B, C, D)
                    for alt_idx, alt in enumerate(row[1:5]):
                        alternative_squares.append([alt, get_center_of_mass(alt)])
            
            self.logger.info(f"Questões detectadas: {len(question_squares)} (1 por linha × {len(rows_left) + len(rows_right)} linhas)")
            self.logger.info(f"Alternativas detectadas: {len(alternative_squares)} (4 por linha)")
            
            # Ordenar questões por Y (de cima para baixo)
            question_squares.sort(key=lambda x: x[1][1])
            
            # Ordenar alternativas: primeiro por Y (linha), depois por X (A, B, C, D)
            alternative_squares.sort(key=lambda x: (x[1][1], x[1][0]))
            
            # Debug: desenhar quadrados detectados
            img_debug = im_crop.copy()
            for idx, (sq, center) in enumerate(question_squares):
                pts = np.array(sq, dtype=np.int32)
                cv2.polylines(img_debug, [pts], True, (255, 0, 0), 2)
                cv2.putText(img_debug, f"Q{idx+1}", 
                           (int(center[0]), int(center[1])), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)
            
            # Alternativas: mostrar A, B, C, D para cada linha (4 por linha)
            for idx, (sq, center) in enumerate(alternative_squares):
                pts = np.array(sq, dtype=np.int32)
                cv2.polylines(img_debug, [pts], True, (0, 255, 0), 2)
                # Cada linha tem 4 alternativas: A, B, C, D (índice dentro da linha)
                alt_letter = chr(65 + (idx % 4))  # A, B, C, D repetindo
                cv2.putText(img_debug, alt_letter, 
                           (int(center[0]), int(center[1])), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            
            self._save_debug_image(f"{debug_dir}/{timestamp}_11_detected_squares.jpg", img_debug)
            
            self.logger.info(f"✅ Detectados {len(question_squares)} questões e {len(alternative_squares)} alternativas")
            if self.save_debug_images:
                self.logger.info(f"✅ Debug salvo em: {debug_dir}/{timestamp}_*.jpg")
            
            return question_squares, alternative_squares, im_crop
            
        except Exception as e:
            self.logger.error(f"Erro em getOurSqr: {str(e)}", exc_info=True)
            return [], [], img
    
    def _formatShape(self, contours: List) -> List:
        """Formata contornos em lista de pontos"""
        shapes = []
        for cnt in contours:
            shape = []
            for point in cnt:
                shape.append([point[0][0], point[0][1]])
            shapes.append(shape)
        return shapes
    
    def _getAnswers(self, img: np.ndarray, num_questions: int = None) -> Optional[Dict[int, str]]:
        """
        Detecta círculos (bolinhas) e verifica se estão marcados
        Pipeline simples e robusto:
        1. Detecta SOMENTE círculos usando HoughCircles
        2. Verifica se cada círculo está marcado (preenchido)
        3. Agrupa por LINHA (Y) para questões e COLUNA (X) para alternativas
        
        Args:
            img: Imagem já cropped e alinhada
            num_questions: Número esperado de questões (opcional, para validação)
        
        Returns:
            Dict[question_num, 'A'|'B'|'C'|'D'] onde question_num começa em 1
        """
        try:
            import os
            from datetime import datetime
            
            debug_dir = "debug_triangles"
            if not os.path.exists(debug_dir):
                os.makedirs(debug_dir)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # PASSO 1: Converter para grayscale e aplicar blur
            if len(img.shape) == 3:
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            else:
                gray = img.copy()
            
            gray = cv2.GaussianBlur(gray, (5, 5), 0)
            self._save_debug_image(f"{debug_dir}/{timestamp}_15_gray_blur.jpg", gray)
            
            # PASSO 2: Detectar SOMENTE círculos usando HoughCircles
            circles = cv2.HoughCircles(
                gray,
                cv2.HOUGH_GRADIENT,
                dp=1.2,
                minDist=20,
                param1=50,
                param2=15,
                minRadius=6,
                maxRadius=12
            )
            
            if circles is None:
                self.logger.warning("Nenhum círculo detectado")
                return {}
            
            circles = np.round(circles[0, :]).astype("int")
            self.logger.info(f"✅ Detectados {len(circles)} círculos")
            
            # Desenhar todos os círculos detectados (debug)
            img_circles_debug = img.copy()
            for (x, y, r) in circles:
                cv2.circle(img_circles_debug, (x, y), r, (0, 255, 0), 2)
            self._save_debug_image(f"{debug_dir}/{timestamp}_16_all_circles.jpg", img_circles_debug)
            
            # PASSO 3: Verificar se cada círculo está marcado (preenchido)
            def is_marked(gray_img, x, y, r):
                """Verifica se o círculo está marcado (preenchido)"""
                mask = np.zeros(gray_img.shape, dtype=np.uint8)
                cv2.circle(mask, (x, y), int(r * 0.6), 255, -1)
                mean = cv2.mean(gray_img, mask=mask)[0]
                return mean < 180  # Escuro = marcado, claro = vazio
            
            marked_circles = []
            img_marked_debug = img.copy()
            
            for (x, y, r) in circles:
                if is_marked(gray, x, y, r):
                    marked_circles.append((x, y, r))
                    cv2.circle(img_marked_debug, (x, y), r, (0, 255, 0), -1)  # Preenchido verde
                else:
                    cv2.circle(img_marked_debug, (x, y), r, (255, 0, 0), 2)  # Vazio azul
            
            self._save_debug_image(f"{debug_dir}/{timestamp}_17_marked_circles.jpg", img_marked_debug)
            self.logger.info(f"✅ {len(marked_circles)} círculos marcados de {len(circles)} detectados")
            
            if len(marked_circles) == 0:
                self.logger.warning("Nenhum círculo marcado detectado")
                return {}
            
            # PASSO 4: Separar círculos por BLOCO (X) primeiro, depois por LINHA (Y)
            # Isso é necessário porque há múltiplos blocos lado a lado
            
            all_circles = [(x, y, r, is_marked(gray, x, y, r)) for (x, y, r) in circles]
            
            # Calcular ponto médio X para separar blocos
            if len(all_circles) == 0:
                self.logger.warning("Nenhum círculo detectado")
                return {}
            
            all_x = [c[0] for c in all_circles]
            min_x, max_x = min(all_x), max(all_x)
            width_range = max_x - min_x
            
            # Detectar quantos blocos existem analisando gaps no eixo X
            # Ordenar por X e encontrar gaps grandes
            sorted_by_x = sorted(all_circles, key=lambda c: c[0])
            x_positions = [c[0] for c in sorted_by_x]
            
            # Encontrar gaps significativos (> 30% da largura de um bloco típico)
            gaps = []
            for i in range(1, len(x_positions)):
                gap = x_positions[i] - x_positions[i-1]
                if gap > 50:  # Gap maior que 50px indica separação de bloco
                    gaps.append((x_positions[i-1] + x_positions[i]) / 2)
            
            # Dividir em blocos baseado nos gaps
            block_boundaries = [min_x - 1] + gaps + [max_x + 1]
            num_blocks = len(block_boundaries) - 1
            
            self.logger.info(f"✅ Detectados {num_blocks} blocos (gaps: {len(gaps)})")
            
            # Separar círculos por bloco
            blocks = [[] for _ in range(num_blocks)]
            for circle in all_circles:
                x = circle[0]
                for i in range(num_blocks):
                    if block_boundaries[i] <= x < block_boundaries[i + 1]:
                        blocks[i].append(circle)
                        break
            
            # Função para agrupar círculos por linha Y dentro de um bloco
            def group_by_rows(block_circles):
                rows = []
                Y_THRESH = 15
                for circle in sorted(block_circles, key=lambda c: c[1]):
                    x, y, r, marked = circle
                    added = False
                    for row in rows:
                        if len(row) > 0:
                            _, row_y, _, _ = row[0]
                            if abs(y - row_y) < Y_THRESH:
                                row.append(circle)
                                added = True
                                break
                    if not added:
                        rows.append([circle])
                
                # FILTRO: Só manter linhas com exatamente 4 círculos (A, B, C, D)
                # Isso elimina falsos positivos do cabeçalho/título
                valid_rows = [row for row in rows if len(row) == 4]
                invalid_count = len(rows) - len(valid_rows)
                if invalid_count > 0:
                    self.logger.debug(f"Filtradas {invalid_count} linhas inválidas (não têm 4 círculos)")
                
                return valid_rows
            
            # Processar cada bloco e extrair respostas
            answers = {}
            img_final_debug = img.copy()
            question_counter = 1
            
            for block_idx, block_circles in enumerate(blocks):
                if len(block_circles) == 0:
                    continue
                    
                rows = group_by_rows(block_circles)
                rows.sort(key=lambda r: r[0][1])  # Ordenar linhas por Y
                
                self.logger.info(f"Bloco {block_idx + 1}: {len(rows)} linhas, {len(block_circles)} círculos")
                
                for row in rows:
                    # Ordenar por X (da esquerda para direita) = A, B, C, D
                    row.sort(key=lambda c: c[0])
                    
                    # Filtrar apenas os círculos marcados nesta linha
                    marked_in_row = [(x, y, r) for (x, y, r, marked) in row if marked]
                    
                    if len(marked_in_row) == 0:
                        answers[question_counter] = None
                        self.logger.debug(f"Questão {question_counter}: Nenhuma resposta marcada")
                        question_counter += 1
                        continue
                    
                    if len(marked_in_row) > 1:
                        self.logger.warning(f"Questão {question_counter}: {len(marked_in_row)} círculos marcados")
                    
                    # Pegar o primeiro círculo marcado
                    x, y, r = marked_in_row[0]
                    
                    # Determinar alternativa baseado na posição X dentro da linha
                    all_x_positions = sorted([c[0] for c in row])
                    
                    try:
                        alt_idx = all_x_positions.index(x)
                        if alt_idx >= 4:
                            alt_idx = 3
                        
                        answers[question_counter] = chr(65 + alt_idx)
                        
                        # Debug visual
                        cv2.circle(img_final_debug, (x, y), r + 2, (0, 255, 0), 2)
                        cv2.putText(img_final_debug, f"Q{question_counter}:{chr(65 + alt_idx)}", 
                                  (x - 20, y - 10), 
                                  cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)
                    except ValueError:
                        answers[question_counter] = None
                    
                    question_counter += 1
            
            self.logger.info(f"✅ Total de questões processadas: {question_counter - 1}")
            
            self._save_debug_image(f"{debug_dir}/{timestamp}_18_final_answers.jpg", img_final_debug)
            self.logger.info(f"✅ Respostas detectadas: {answers}")
            
            return answers
            
        except Exception as e:
            self.logger.error(f"Erro em getAnswers: {str(e)}", exc_info=True)
            return {}
    
    def _buscar_gabarito(self, test_id: str) -> Dict[int, str]:
        """
        Busca gabarito do teste no banco de dados
        Retorna: {question_number: correct_answer}
        """
        try:
            test_questions = TestQuestion.query.filter_by(test_id=test_id).order_by(TestQuestion.order).all()
            
            gabarito = {}
            for idx, tq in enumerate(test_questions, start=1):
                question = Question.query.get(tq.question_id)
                if question and question.correct_answer:
                    gabarito[idx] = question.correct_answer.upper()
            
            return gabarito
            
        except Exception as e:
            self.logger.error(f"Erro ao buscar gabarito: {str(e)}")
            return {}
    
    def _calcular_correcao(self, answers: Dict[int, Optional[str]], gabarito: Dict[int, str]) -> Dict[str, Any]:
        """Calcula estatísticas de correção"""
        total_questions = len(gabarito)
        answered = 0
        correct = 0
        incorrect = 0
        unanswered = 0
        
        for q_num in range(1, total_questions + 1):
            detected = answers.get(q_num)
            correct_answer = gabarito.get(q_num)
            
            if not detected:
                unanswered += 1
            elif detected == correct_answer:
                correct += 1
                answered += 1
            else:
                incorrect += 1
                answered += 1
        
        score_percentage = (correct / total_questions * 100) if total_questions > 0 else 0.0
        
        return {
            "total_questions": total_questions,
            "answered": answered,
            "correct": correct,
            "incorrect": incorrect,
            "unanswered": unanswered,
            "score_percentage": round(score_percentage, 2)
        }
    
    def _salvar_respostas_no_banco(self, test_id: str, student_id: str,
                                   respostas_detectadas: Dict[int, Optional[str]],
                                   gabarito: Dict[int, str]) -> List[Dict[str, Any]]:
        """
        Salva respostas detectadas no banco de dados
        """
        try:
            # Buscar questões do teste
            test_questions = TestQuestion.query.filter_by(test_id=test_id).order_by(TestQuestion.order).all()

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

            return saved_answers

        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Erro ao salvar respostas: {str(e)}", exc_info=True)
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
            import uuid

            # Verificar se já existe uma sessão para esta correção física
            existing_session = TestSession.query.filter_by(
                test_id=test_id,
                student_id=student_id,
                status='corrigida',
                user_agent='Physical Test Correction (Hybrid)'
            ).first()

            if existing_session:
                return existing_session.id

            # Criar nova sessão mínima para correção física
            session = TestSession(
                id=str(uuid.uuid4()),
                student_id=student_id,
                test_id=test_id,
                time_limit_minutes=None,
                ip_address=None,
                user_agent='Physical Test Correction (Hybrid)',
                status='corrigida',
                started_at=datetime.utcnow(),
                submitted_at=datetime.utcnow()
            )

            db.session.add(session)
            db.session.commit()

            return session.id

        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Erro ao criar sessão mínima: {str(e)}", exc_info=True)
            return None
    
    def _marcar_formulario_como_corrigido(self, test_id: str, student_id: str) -> bool:
        """
        Marca o PhysicalTestForm como corrigido após processar a correção

        Args:
            test_id: ID da prova
            student_id: ID do aluno

        Returns:
            bool: True se marcado com sucesso, False caso contrário
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

            return True

        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Erro ao marcar formulário como corrigido: {str(e)}", exc_info=True)
            return False