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
        self.save_debug_images = False  # Desativado: não salva imagens de debug
        self.logger = logging.getLogger(__name__)
        self.logger.info("Correção Híbrida inicializada (detecção geométrica)")
    
    def _save_debug_image(self, path: str, img):
        """Salva imagem de debug apenas se save_debug_images estiver habilitado"""
        if self.save_debug_images:
            import os
            dir_path = os.path.dirname(path)
            if dir_path and not os.path.exists(dir_path):
                os.makedirs(dir_path)
            cv2.imwrite(path, img)
    
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
        Parseia dados do QR code (formato ultra-compacto s12345678t87654321, 
        formato compacto s:xxx t:xxx, JSON ou string simples)
        Busca IDs completos no banco quando usa formato encurtado
        """
        try:
            if not data:
                return None
            
            # Tentar formato ultra-compacto primeiro: s12345678t87654321
            if data.startswith('s') and 't' in data[1:]:
                t_index = data.find('t', 1)
                if t_index > 1:
                    short_student_id = data[1:t_index]
                    short_test_id = data[t_index+1:]
                    
                    # Buscar IDs completos no banco usando os últimos caracteres
                    student_id = self._buscar_id_completo_por_sufixo('student', short_student_id)
                    test_id = self._buscar_id_completo_por_sufixo('test', short_test_id)
                    
                    if student_id and test_id:
                        return {
                            'student_id': student_id,
                            'test_id': test_id
                        }
                    else:
                        self.logger.warning(f"Não foi possível encontrar IDs completos: "
                                          f"student_suffix={short_student_id}, test_suffix={short_test_id}")
                        # Fallback: retornar os sufixos mesmo assim
                        return {
                            'student_id': short_student_id,
                            'test_id': short_test_id
                        }
            
            # Tentar formato compacto com dois pontos: s:xxx t:xxx
            if data.startswith('s:') and ' t:' in data:
                parts = data.split(' t:')
                if len(parts) == 2:
                    student_id = parts[0].replace('s:', '').strip()
                    test_id = parts[1].strip()
                    return {
                        'student_id': student_id,
                        'test_id': test_id
                    }
            
            # Tentar parsear como JSON (compatibilidade com formato antigo)
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
    
    def _buscar_id_completo_por_sufixo(self, table_name: str, suffix: str) -> Optional[str]:
        """
        Busca ID completo no banco usando sufixo (últimos caracteres)
        
        Args:
            table_name: Nome da tabela ('student' ou 'test')
            suffix: Últimos caracteres do ID (sem hífens)
            
        Returns:
            ID completo ou None se não encontrado
        """
        try:
            from sqlalchemy import func
            
            if table_name == 'student':
                from app.models.student import Student
                # Buscar usando LIKE '%suffix' (últimos caracteres sem hífens)
                # Remove hífens do ID e compara com o sufixo
                student = Student.query.filter(
                    func.replace(Student.id, '-', '').like(f'%{suffix}')
                ).first()
                return student.id if student else None
            elif table_name == 'test':
                from app.models.test import Test
                # Buscar usando LIKE '%suffix' (últimos caracteres sem hífens)
                test = Test.query.filter(
                    func.replace(Test.id, '-', '').like(f'%{suffix}')
                ).first()
                return test.id if test else None
            return None
        except Exception as e:
            self.logger.error(f"Erro ao buscar ID completo para {table_name} com sufixo {suffix}: {str(e)}")
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
    
    def _four_point_transform(self, image: np.ndarray, pts: np.ndarray) -> np.ndarray:
        """
        Aplica transformação de perspectiva usando 4 pontos
        Equivalente a imutils.perspective.four_point_transform
        """
        # Obter pontos ordenados
        rect = self._order_points(pts)
        (tl, tr, br, bl) = rect
        
        # Calcular largura do novo retângulo
        widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
        widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
        maxWidth = max(int(widthA), int(widthB))
        
        # Calcular altura do novo retângulo
        heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
        heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
        maxHeight = max(int(heightA), int(heightB))
        
        # Pontos de destino
        dst = np.array([
            [0, 0],
            [maxWidth - 1, 0],
            [maxWidth - 1, maxHeight - 1],
            [0, maxHeight - 1]
        ], dtype="float32")
        
        # Calcular matriz de transformação e aplicar
        M = cv2.getPerspectiveTransform(rect, dst)
        warped = cv2.warpPerspective(image, M, (maxWidth, maxHeight))
        
        return warped
    
    def _order_points(self, pts: np.ndarray) -> np.ndarray:
        """
        Ordena pontos como: top-left, top-right, bottom-right, bottom-left
        """
        rect = np.zeros((4, 2), dtype="float32")
        
        # Soma e diferença
        s = pts.sum(axis=1)
        diff = np.diff(pts, axis=1)
        
        # Top-left: menor soma
        rect[0] = pts[np.argmin(s)]
        # Bottom-right: maior soma
        rect[2] = pts[np.argmax(s)]
        # Top-right: menor diferença
        rect[1] = pts[np.argmin(diff)]
        # Bottom-left: maior diferença
        rect[3] = pts[np.argmax(diff)]
        
        return rect
    
    def _sort_contours(self, cnts: List, method: str = "left-to-right") -> List:
        """
        Ordena contornos
        Equivalente a imutils.contours.sort_contours
        """
        reverse = False
        i = 0
        
        if method == "right-to-left" or method == "bottom-to-top":
            reverse = True
        
        if method == "top-to-bottom" or method == "bottom-to-top":
            i = 1
        
        boundingBoxes = [cv2.boundingRect(c) for c in cnts]
        (cnts, boundingBoxes) = zip(*sorted(zip(cnts, boundingBoxes),
            key=lambda b: b[1][i], reverse=reverse))
        
        return list(cnts)
    
    def _getAnswers(self, img: np.ndarray, num_questions: int = None) -> Optional[Dict[int, str]]:
        """
        Detecta bolhas e verifica se estão marcadas
        Baseado no algoritmo de detecção de bolhas usando Canny edge detection
        
        Pipeline:
        1. Detecta bordas dos blocos usando Canny
        2. Encontra contornos retangulares dos blocos
        3. Para cada bloco, faz crop e processa bolhas individualmente
        4. Aplica threshold binário invertido
        5. Detecta bolhas por tamanho e aspect ratio
        6. Agrupa bolhas em questões (4 por questão)
        7. Conta pixels brancos para determinar resposta marcada
        
        Args:
            img: Imagem já cropped e alinhada (após correção de perspectiva)
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
            
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            self._save_debug_image(f"{debug_dir}/{timestamp}_15_gray_blur.jpg", blurred)
            
            # PASSO 2: Detectar bordas usando Canny (para detectar blocos)
            edged = cv2.Canny(blurred, 75, 200)
            self._save_debug_image(f"{debug_dir}/{timestamp}_15_canny_edges.jpg", edged)
            
            # PASSO 3: Encontrar contornos dos blocos (retângulos grandes)
            # Tentar múltiplas abordagens para detectar blocos
            block_contours = []
            img_height, img_width = gray.shape[:2]
            min_block_area = (img_width * img_height) * 0.03  # Pelo menos 3% da imagem
            max_block_area = (img_width * img_height) * 0.8    # No máximo 80% da imagem
            
            # Abordagem 1: Canny edges
            cnts = cv2.findContours(edged.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            cnts = cnts[0] if len(cnts) == 2 else cnts[1]
            
            for c in cnts:
                area = cv2.contourArea(c)
                if min_block_area < area < max_block_area:
                    peri = cv2.arcLength(c, True)
                    approx = cv2.approxPolyDP(c, 0.02 * peri, True)
                    # Procurar por retângulos (4 vértices)
                    if len(approx) == 4:
                        # Verificar se é realmente um retângulo (aspect ratio razoável)
                        x, y, w, h = cv2.boundingRect(approx)
                        aspect_ratio = w / float(h) if h > 0 else 0
                        if 0.3 < aspect_ratio < 3.0:  # Retângulos não muito alongados
                            block_contours.append(approx)
            
            # Abordagem 2: Se não encontrou blocos, tentar threshold adaptativo
            if len(block_contours) == 0:
                self.logger.debug("Canny não encontrou blocos, tentando threshold adaptativo")
                thresh_adapt = cv2.adaptiveThreshold(blurred, 255, 
                                                    cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                                    cv2.THRESH_BINARY_INV, 11, 2)
                cnts = cv2.findContours(thresh_adapt, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                cnts = cnts[0] if len(cnts) == 2 else cnts[1]
                
                for c in cnts:
                    area = cv2.contourArea(c)
                    if min_block_area < area < max_block_area:
                        peri = cv2.arcLength(c, True)
                        approx = cv2.approxPolyDP(c, 0.02 * peri, True)
                        if len(approx) == 4:
                            x, y, w, h = cv2.boundingRect(approx)
                            aspect_ratio = w / float(h) if h > 0 else 0
                            if 0.3 < aspect_ratio < 3.0:
                                block_contours.append(approx)
            
            # Ordenar blocos da esquerda para direita
            if len(block_contours) > 0:
                block_contours = sorted(block_contours, key=lambda c: cv2.boundingRect(c)[0])
            
            self.logger.info(f"✅ Detectados {len(block_contours)} blocos de resposta")
            
            # Se não encontrou blocos, processar imagem inteira
            if len(block_contours) == 0:
                self.logger.warning("Nenhum bloco detectado, processando imagem inteira")
                return self._process_bubbles_in_roi(img, gray, blurred, timestamp, debug_dir, 1)
            
            # PASSO 4: Processar cada bloco individualmente
            all_answers = {}
            question_counter = 1
            img_final_debug = img.copy()
            
            for block_idx, block_cnt in enumerate(block_contours):
                # Fazer crop do bloco (usar boundingRect para simplificar)
                x, y, w, h = cv2.boundingRect(block_cnt)
                
                # Adicionar margem pequena
                margin = 5
                x = max(0, x - margin)
                y = max(0, y - margin)
                w = min(img.shape[1] - x, w + 2 * margin)
                h = min(img.shape[0] - y, h + 2 * margin)
                
                block_roi = img[y:y+h, x:x+w]
                block_gray = gray[y:y+h, x:x+w]
                block_blurred = blurred[y:y+h, x:x+w]
                
                # Debug: salvar ROI do bloco com informações
                self._save_debug_image(f"{debug_dir}/{timestamp}_block_{block_idx+1}_roi.jpg", block_roi)
                
                # Log informações do bloco
                self.logger.info(f"Bloco {block_idx + 1}: ROI {w}x{h} pixels, posição ({x}, {y})")
                
                # Processar bolhas neste bloco
                block_answers = self._process_bubbles_in_roi(
                    block_roi, block_gray, block_blurred, 
                    timestamp, debug_dir, question_counter, block_idx + 1
                )
                
                # Atualizar contador de questões e adicionar respostas
                for q_num, answer in block_answers.items():
                    all_answers[question_counter] = answer
                    question_counter += 1
                
                # Debug: desenhar contorno do bloco
                cv2.drawContours(img_final_debug, [block_cnt], -1, (255, 0, 0), 3)
                cv2.putText(img_final_debug, f"Block {block_idx+1}", 
                          (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)
            
            self.logger.info(f"✅ Total de questões processadas: {question_counter - 1}")
            self._save_debug_image(f"{debug_dir}/{timestamp}_18_final_answers.jpg", img_final_debug)
            self.logger.info(f"✅ Respostas detectadas: {all_answers}")
            
            return all_answers
            
        except Exception as e:
            self.logger.error(f"Erro em getAnswers: {str(e)}", exc_info=True)
            return {}
    
    def _process_bubbles_in_roi(self, roi_img: np.ndarray, roi_gray: np.ndarray, 
                                roi_blurred: np.ndarray, timestamp: str, 
                                debug_dir: str, start_question: int, 
                                block_num: int = None) -> Dict[int, str]:
        """
        Processa bolhas dentro de um ROI (bloco)
        Baseado no algoritmo fornecido de detecção de bolhas
        
        Args:
            roi_img: ROI colorido
            roi_gray: ROI em grayscale
            roi_blurred: ROI com blur aplicado
            timestamp: Timestamp para debug
            debug_dir: Diretório para salvar imagens de debug
            start_question: Número da primeira questão neste bloco
            block_num: Número do bloco (opcional, para debug)
        
        Returns:
            Dict[question_num, 'A'|'B'|'C'|'D'] onde question_num começa em start_question
        """
        try:
            # Debug: salvar ROI original e grayscale
            if block_num:
                self._save_debug_image(f"{debug_dir}/{timestamp}_block_{block_num}_original.jpg", roi_img)
                self._save_debug_image(f"{debug_dir}/{timestamp}_block_{block_num}_grayscale.jpg", roi_gray)
            
            # Aplicar threshold binário invertido
            # THRESH_BINARY_INV: branco = marcado/preenchido, preto = vazio
            thresh = cv2.threshold(roi_blurred, 0, 255, 
                                  cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]
            
            if block_num:
                self._save_debug_image(f"{debug_dir}/{timestamp}_block_{block_num}_thresh.jpg", thresh)
                
                # Debug: criar imagem combinada mostrando original e threshold lado a lado
                h, w = roi_img.shape[:2]
                combined = np.zeros((h, w * 2, 3), dtype=np.uint8)
                combined[:, :w] = roi_img
                combined[:, w:] = cv2.cvtColor(thresh, cv2.COLOR_GRAY2BGR)
                self._save_debug_image(f"{debug_dir}/{timestamp}_block_{block_num}_combined.jpg", combined)
                
                # Debug: também salvar threshold normal (sem inversão) para comparação
                thresh_normal = cv2.threshold(roi_blurred, 0, 255, 
                                             cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]
                self._save_debug_image(f"{debug_dir}/{timestamp}_block_{block_num}_thresh_normal.jpg", 
                                     thresh_normal)
            
            # Encontrar contornos na imagem threshold
            # Usar RETR_TREE para pegar contornos externos E internos (bolhas dentro da borda)
            all_cnts, hierarchy = cv2.findContours(thresh.copy(), cv2.RETR_TREE, 
                                                   cv2.CHAIN_APPROX_SIMPLE)
            # Processar hierarquia para separar borda do bloco das bolhas internas
            roi_height, roi_width = roi_img.shape[:2]
            roi_area = roi_width * roi_height
            max_border_area = roi_area * 0.3  # Borda ocupa mais de 30% da área
            
            # Encontrar a borda do bloco (contorno externo grande)
            border_contour_idx = None
            border_contour = None
            if hierarchy is not None:
                for i, h in enumerate(hierarchy[0]):
                    if h[3] == -1:  # Contorno externo (sem pai)
                        area = cv2.contourArea(all_cnts[i])
                        if area > max_border_area:
                            border_contour_idx = i
                            border_contour = all_cnts[i]
                            break
            
            # Filtrar contornos: pegar apenas os que estão DENTRO da borda (filhos da borda)
            # OU contornos externos pequenos (bolhas que não estão dentro de nada)
            valid_cnts = []
            
            if border_contour_idx is not None:
                # Encontrar todos os filhos da borda (contornos internos)
                def get_children(parent_idx):
                    children = []
                    for i, h in enumerate(hierarchy[0]):
                        if h[3] == parent_idx:  # Este contorno tem a borda como pai
                            children.append(i)
                            # Recursivamente pegar filhos dos filhos
                            children.extend(get_children(i))
                    return children
                
                # Pegar todos os contornos que são filhos da borda (bolhas dentro)
                children_indices = get_children(border_contour_idx)
                for idx in children_indices:
                    valid_cnts.append(all_cnts[idx])
                
                self.logger.info(f"Bloco {block_num or 'único'}: Borda detectada (índice {border_contour_idx}), "
                               f"{len(children_indices)} contornos internos encontrados")
            else:
                # Se não encontrou borda, usar todos os contornos externos pequenos
                for i, h in enumerate(hierarchy[0] if hierarchy is not None else []):
                    if h[3] == -1:  # Contorno externo
                        area = cv2.contourArea(all_cnts[i])
                        if area <= max_border_area:  # Não é a borda
                            valid_cnts.append(all_cnts[i])
                
                self.logger.info(f"Bloco {block_num or 'único'}: Borda não detectada, "
                               f"usando {len(valid_cnts)} contornos externos pequenos")
            
            cnts = valid_cnts
            
            # Debug: desenhar TODOS os contornos encontrados (incluindo borda e internos)
            img_all_contours = roi_img.copy()
            
            # Desenhar borda em magenta se encontrada
            if border_contour is not None:
                cv2.drawContours(img_all_contours, [border_contour], -1, (255, 0, 255), 3)
                (bx, by, bw, bh) = cv2.boundingRect(border_contour)
                cv2.putText(img_all_contours, "BORDA", (bx, by-10), 
                          cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 255), 2)
            
            # Desenhar contornos válidos (bolhas dentro)
            for idx, c in enumerate(cnts):
                (x, y, w, h) = cv2.boundingRect(c)
                ar = w / float(h) if h > 0 else 0
                area = cv2.contourArea(c)
                
                # Desenhar contorno
                cv2.drawContours(img_all_contours, [c], -1, (0, 255, 0), 2)
                # Desenhar bounding box
                cv2.rectangle(img_all_contours, (x, y), (x+w, y+h), (0, 255, 0), 1)
                # Adicionar informações
                cv2.putText(img_all_contours, f"C{idx+1}: {w}x{h}", 
                          (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)
                cv2.putText(img_all_contours, f"AR:{ar:.2f}", 
                          (x, y+h+15), cv2.FONT_HERSHEY_SIMPLEX, 0.3, (0, 255, 0), 1)
            
            if block_num:
                self._save_debug_image(f"{debug_dir}/{timestamp}_block_{block_num}_all_contours.jpg", 
                                     img_all_contours)
            
            self.logger.info(f"Bloco {block_num or 'único'}: {len(cnts)} contornos internos (bolhas) encontrados")
            
            # Log detalhado de cada contorno
            if block_num and len(cnts) > 0:
                for idx, c in enumerate(cnts):
                    (x, y, w, h) = cv2.boundingRect(c)
                    ar = w / float(h) if h > 0 else 0
                    area = cv2.contourArea(c)
                    self.logger.info(f"  Bolha {idx+1}: w={w}, h={h}, ar={ar:.2f}, area={area:.0f}, pos=({x},{y})")
            
            # Filtrar contornos que correspondem a bolhas
            # Ajustado para bolhas menores (ROI pequeno reduz o tamanho das bolhas)
            # NOTA: A borda externa já foi filtrada pela hierarquia acima
            questionCnts = []
            
            # Calcular área do ROI para filtrar bordas internas grandes
            roi_height, roi_width = roi_img.shape[:2]
            roi_area = roi_width * roi_height
            max_internal_border_area = roi_area * 0.2  # Borda interna pode ocupar até 20% da área
            
            for c in cnts:
                # compute the bounding box of the contour, then use the
                # bounding box to derive the aspect ratio
                (x, y, w, h) = cv2.boundingRect(c)
                ar = w / float(h) if h > 0 else 0
                area = cv2.contourArea(c)
                
                # Filtrar bordas internas grandes (como a "Bolha 1" com w=301, h=160)
                if area > max_internal_border_area:
                    if block_num:
                        self.logger.debug(f"Bloco {block_num}: Ignorando borda interna - w={w}, h={h}, area={area:.0f}")
                    continue
                
                # Ajustado para aceitar bolhas menores (10-12 pixels mínimo)
                # Aspect ratio entre 0.9 e 1.1 (quase circular/quadrado)
                if w >= 10 and h >= 10 and ar >= 0.9 and ar <= 1.1:
                    questionCnts.append(c)
            
            if block_num:
                self.logger.info(f"Bloco {block_num}: {len(questionCnts)} bolhas detectadas após filtro")
            
            if len(questionCnts) == 0:
                self.logger.warning(f"Bloco {block_num or 'único'}: Nenhuma bolha detectada após filtro")
                # Debug: salvar imagem com informações detalhadas dos contornos rejeitados
                img_rejected = roi_img.copy()
                
                # Recalcular área máxima para borda interna (mesmo cálculo do filtro)
                roi_height_debug, roi_width_debug = roi_img.shape[:2]
                roi_area_debug = roi_width_debug * roi_height_debug
                max_internal_border_area_debug = roi_area_debug * 0.2
                
                # Adicionar texto informativo no topo
                cv2.putText(img_rejected, f"Total contornos internos: {len(cnts)} | Filtro: w>=10, h>=10, ar 0.9-1.1", 
                          (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
                
                # Desenhar borda se encontrada
                if border_contour is not None:
                    cv2.drawContours(img_rejected, [border_contour], -1, (255, 0, 255), 3)
                    (bx, by, bw, bh) = cv2.boundingRect(border_contour)
                    cv2.putText(img_rejected, "BORDA (ignorada)", (bx, by-10), 
                              cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 255), 2)
                
                for idx, c in enumerate(cnts[:30]):  # Mostrar até 30 contornos
                    (x, y, w, h) = cv2.boundingRect(c)
                    ar = w / float(h) if h > 0 else 0
                    area = cv2.contourArea(c)
                    color = (0, 0, 255)  # Vermelho para rejeitados
                    
                    # Verificar se seria aceito com critérios ajustados
                    if w >= 10 and h >= 10 and ar >= 0.9 and ar <= 1.1:
                        # Verificar se não é borda interna
                        if area <= max_internal_border_area_debug:
                            color = (255, 165, 0)  # Laranja para quase aceito
                            reason_text = "ACEITO"
                        else:
                            color = (255, 0, 255)  # Magenta para borda interna
                            reason_text = "BORDA_INT"
                    else:
                        # Adicionar motivo da rejeição
                        reasons = []
                        if w < 10:
                            reasons.append("w<10")
                        if h < 10:
                            reasons.append("h<10")
                        if ar < 0.9 or ar > 1.1:
                            reasons.append(f"ar!={ar:.2f}")
                        reason_text = " | ".join(reasons) if reasons else "OUTRO"
                    
                    # Desenhar contorno
                    cv2.drawContours(img_rejected, [c], -1, color, 2)
                    # Desenhar bounding box
                    cv2.rectangle(img_rejected, (x, y), (x+w, y+h), color, 2)
                    # Informações acima
                    cv2.putText(img_rejected, f"C{idx+1}: {w}x{h}", 
                              (x, max(0, y-5)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
                    # Informações abaixo
                    info_text = f"AR:{ar:.2f} A:{int(area)}"
                    cv2.putText(img_rejected, info_text, 
                              (x, min(roi_img.shape[0]-5, y+h+20)), cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)
                    
                    # Motivo da rejeição/classificação
                    cv2.putText(img_rejected, reason_text, 
                              (x, min(roi_img.shape[0]-5, y+h+35)), 
                              cv2.FONT_HERSHEY_SIMPLEX, 0.35, color, 1)
                
                if block_num:
                    self._save_debug_image(f"{debug_dir}/{timestamp}_block_{block_num}_rejected_contours.jpg", 
                                         img_rejected)
                    
                    # Salvar também o threshold para análise
                    self._save_debug_image(f"{debug_dir}/{timestamp}_block_{block_num}_thresh_analysis.jpg", thresh)
                
                return {}
            
            # CORREÇÃO: Detectar TODAS as bolhas (vazias e preenchidas) usando HoughCircles
            # Isso garante que sempre detectemos 4 bolhas por linha
            # Primeiro, detectar círculos usando HoughCircles (detecta bordas, não precisa estar preenchido)
            # Usar Canny para melhorar detecção de bordas roxas
            edges = cv2.Canny(roi_gray, 50, 150)
            circles = cv2.HoughCircles(
                edges,  # Usar bordas Canny ao invés de grayscale direto
                cv2.HOUGH_GRADIENT,
                dp=1,
                minDist=15,  # Distância mínima entre centros de círculos (reduzido)
                param1=30,   # Threshold superior para detecção de bordas (reduzido para detectar bordas roxas)
                param2=15,   # Threshold para detecção de centro (reduzido = mais círculos)
                minRadius=10,  # Raio mínimo (bolhas são ~12-13px de raio)
                maxRadius=15   # Raio máximo (ajustado)
            )
            
            # Converter círculos detectados em contornos para processamento uniforme
            all_bubbles = list(questionCnts)  # Começar com bolhas preenchidas já detectadas
            
            if circles is not None:
                circles = np.round(circles[0, :]).astype("int")
                for (x_c, y_c, r) in circles:
                    # Verificar se este círculo não é muito diferente das bolhas já detectadas
                    # e se não está muito próximo de uma bolha já detectada
                    is_duplicate = False
                    for existing_c in questionCnts:
                        (ex, ey, ew, eh) = cv2.boundingRect(existing_c)
                        ex_center = ex + ew // 2
                        ey_center = ey + eh // 2
                        distance = np.sqrt((x_c - ex_center)**2 + (y_c - ey_center)**2)
                        if distance < 15:  # Se está muito próximo, é duplicata
                            is_duplicate = True
                            break
                    
                    if not is_duplicate:
                        # Criar contorno aproximado do círculo
                        # Criar um contorno circular usando pontos
                        circle_pts = []
                        for angle in range(0, 360, 10):
                            px = int(x_c + r * np.cos(np.radians(angle)))
                            py = int(y_c + r * np.sin(np.radians(angle)))
                            circle_pts.append([[px, py]])
                        circle_contour = np.array(circle_pts, dtype=np.int32)
                        all_bubbles.append(circle_contour)
            
            # Agrupar bolhas por LINHA (Y similar) primeiro
            # Baseado no tutorial PyImageSearch: https://pyimagesearch.com/2016/10/03/bubble-sheet-multiple-choice-scanner-and-test-grader-using-omr-python-and-opencv/
            Y_TOLERANCE = 15  # Tolerância vertical para considerar mesma linha
            
            # Agrupar bolhas por linha Y
            rows = []
            for c in all_bubbles:
                (x, y, w, h) = cv2.boundingRect(c)
                center_y = y + h // 2  # Centro Y da bolha
                
                # Procurar linha existente próxima
                found_row = False
                for row in rows:
                    if len(row) > 0:
                        # Pegar Y médio da linha
                        row_y_centers = [cv2.boundingRect(b)[1] + cv2.boundingRect(b)[3] // 2 for b in row]
                        avg_row_y = sum(row_y_centers) / len(row_y_centers)
                        
                        # Se está na mesma linha (tolerância)
                        if abs(center_y - avg_row_y) < Y_TOLERANCE:
                            row.append(c)
                            found_row = True
                            break
                
                # Se não encontrou linha próxima, criar nova linha
                if not found_row:
                    rows.append([c])
            
            # Ordenar linhas por Y (de cima para baixo) = questões
            rows.sort(key=lambda row: cv2.boundingRect(row[0])[1])
            
            # Filtrar linhas que não têm pelo menos 3 bolhas (esperamos 4, mas aceitamos 3+)
            rows = [row for row in rows if len(row) >= 3]
            
            if block_num:
                self.logger.info(f"Bloco {block_num}: {len(rows)} linhas (questões) detectadas")
            
            # Debug: desenhar todas as bolhas agrupadas por linha
            img_bubbles_debug = roi_img.copy()
            for row_idx, row in enumerate(rows):
                for bubble_idx, c in enumerate(row):
                    (x, y, w, h) = cv2.boundingRect(c)
                    cv2.drawContours(img_bubbles_debug, [c], -1, (0, 255, 0), 2)
                    cv2.rectangle(img_bubbles_debug, (x, y), (x+w, y+h), (0, 255, 0), 1)
                    cv2.putText(img_bubbles_debug, f"R{row_idx+1}B{bubble_idx+1}", 
                              (x, y-5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)
            
            if block_num:
                self._save_debug_image(f"{debug_dir}/{timestamp}_block_{block_num}_bubbles_grouped.jpg", 
                                     img_bubbles_debug)
            
            # Processar cada linha (questão)
            answers = {}
            question_num = start_question
            roi_width = roi_img.shape[1]  # Largura do ROI para calcular X relativo
            LETTERS = ['A', 'B', 'C', 'D']  # Ordem das alternativas
            
            # Definir centros X esperados (em X relativo 0.0 a 1.0) - usado apenas como fallback
            # Ajustado considerando número da questão à esquerda e padding do bloco
            COLUNAS_X_CENTERS = {
                'A': 0.20,   # 20% da largura do ROI (ajustado para considerar número da questão)
                'B': 0.40,   # 40% da largura do ROI
                'C': 0.60,   # 60% da largura do ROI
                'D': 0.80,   # 80% da largura do ROI
            }
            
            def get_bubble_letter_by_distance(x_center, roi_width):
                """Mapeia posição X para letra usando distância mínima aos centros esperados (fallback)"""
                x_rel = x_center / roi_width if roi_width > 0 else 0
                
                # Calcular distância para cada coluna esperada
                distances = {}
                for letra, expected_x_rel in COLUNAS_X_CENTERS.items():
                    distances[letra] = abs(x_rel - expected_x_rel)
                
                # Retornar a letra com menor distância
                return min(distances.items(), key=lambda x: x[1])[0]
            
            for row_idx, row in enumerate(rows):
                if len(row) == 0:
                    question_num += 1
                    continue
                
                # CORREÇÃO: Ordenar bolhas por X (da esquerda para direita)
                # Isso garante que a primeira bolha é sempre A, segunda é B, etc.
                row.sort(key=lambda c: cv2.boundingRect(c)[0])
                
                # Processar TODAS as bolhas detectadas na linha
                bolhas_com_pixels = []
                
                for c in row:
                    (x, y, w, h) = cv2.boundingRect(c)
                    x_center = x + w // 2  # Centro X da bolha
                    y_center = y + h // 2  # Centro Y da bolha
                    
                    # Criar máscara CIRCULAR exata da bolha
                    radius = min(w, h) // 2
                    if radius < 3:
                        continue
                    
                    mask = np.zeros(thresh.shape, dtype="uint8")
                    cv2.circle(mask, (x_center, y_center), max(1, radius - 2), 255, -1)
                    
                    # Aplicar máscara e contar pixels brancos
                    mask_applied = cv2.bitwise_and(thresh, thresh, mask=mask)
                    total = cv2.countNonZero(mask_applied)
                    
                    # Calcular área do círculo para normalizar
                    circle_area = np.pi * (max(1, radius - 2)) ** 2
                    if circle_area > 0:
                        fill_percentage = (total / circle_area) * 100
                    else:
                        fill_percentage = 0
                    
                    bolhas_com_pixels.append({
                        'contour': c,
                        'x_center': x_center,
                        'total_pixels': total,
                        'fill_percentage': fill_percentage,
                        'position': len(bolhas_com_pixels)  # Posição na linha (0, 1, 2, 3)
                    })
                
                if len(bolhas_com_pixels) == 0:
                    self.logger.warning(f"Bloco {block_num or 'único'}, Questão {question_num}: Nenhuma bolha válida")
                    answers[question_num] = None
                    question_num += 1
                    continue
                
                # Encontrar a bolha com mais pixels (a marcada)
                bolha_marcada = max(bolhas_com_pixels, key=lambda b: b['total_pixels'])
                posicao_na_linha = bolha_marcada['position']  # Usar o campo 'position' já armazenado
                
                # Mapear posição para letra
                # ESTRATÉGIA PRINCIPAL: Se temos 3 ou 4 bolhas, mapear diretamente pela posição
                # ESTRATÉGIA FALLBACK: Se temos menos de 3, usar distância relativa X
                if len(bolhas_com_pixels) >= 3:
                    # Mapeamento direto: primeira = A, segunda = B, terceira = C, quarta = D
                    # Assumimos que as bolhas estão ordenadas da esquerda para direita
                    # Se temos 3 bolhas, a primeira é sempre A (mesmo que a bolha A vazia não tenha sido detectada)
                    bubble_letter = LETTERS[posicao_na_linha] if posicao_na_linha < len(LETTERS) else LETTERS[-1]
                    mapping_method = "direto_por_posição"
                else:
                    # Fallback: usar posição relativa X para mapear
                    # Útil quando apenas 1 ou 2 bolhas foram detectadas
                    x_rel = bolha_marcada['x_center'] / roi_width if roi_width > 0 else 0
                    bubble_letter = get_bubble_letter_by_distance(bolha_marcada['x_center'], roi_width)
                    mapping_method = "distância_relativa"
                
                # Log detalhado
                if block_num:
                    totals_str = ", ".join([f"{LETTERS[b['position']] if b['position'] < len(LETTERS) else '?'}: {b['total_pixels']}px ({b['fill_percentage']:.1f}%)" 
                                           for b in bolhas_com_pixels])
                    self.logger.info(f"Bloco {block_num}, Questão {question_num}: {totals_str}")
                    self.logger.info(f"  → Método de mapeamento: {mapping_method}")
                    self.logger.info(f"  → Marcada: {bubble_letter} (posição {posicao_na_linha + 1}, "
                                   f"{bolha_marcada['total_pixels']}px, {bolha_marcada['fill_percentage']:.1f}%)")
                    if mapping_method == "distância_relativa":
                        x_rel = bolha_marcada['x_center'] / roi_width if roi_width > 0 else 0
                        self.logger.info(f"  → X absoluto: {bolha_marcada['x_center']}px, X relativo: {x_rel:.3f}, ROI width: {roi_width}px")
                
                answers[question_num] = bubble_letter
                
                # Debug visual
                cv2.drawContours(img_bubbles_debug, [bolha_marcada['contour']], -1, (0, 255, 0), 3)
                (bx, by, bw, bh) = cv2.boundingRect(bolha_marcada['contour'])
                cv2.putText(img_bubbles_debug, f"Q{question_num}:{bubble_letter}", 
                          (bx - 20, by - 10), 
                          cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)
                
                question_num += 1
            
            if block_num:
                self._save_debug_image(f"{debug_dir}/{timestamp}_block_{block_num}_final.jpg", 
                                     img_bubbles_debug)
                
                # Debug: criar imagem com estatísticas
                stats_img = roi_img.copy()
                stats_text = [
                    f"Total contornos: {len(cnts)}",
                    f"Bolhas detectadas: {len(questionCnts)}",
                    f"Questoes processadas: {len(answers)}",
                    f"Filtro: w>=10, h>=10, ar 0.9-1.1",
                    f"ROI size: {roi_img.shape[1]}x{roi_img.shape[0]}"
                ]
                y_offset = 20
                for text in stats_text:
                    cv2.putText(stats_img, text, (10, y_offset), 
                              cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
                    y_offset += 20
                self._save_debug_image(f"{debug_dir}/{timestamp}_block_{block_num}_stats.jpg", 
                                     stats_img)
            
            return answers
            
        except Exception as e:
            self.logger.error(f"Erro ao processar bolhas no ROI: {str(e)}", exc_info=True)
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