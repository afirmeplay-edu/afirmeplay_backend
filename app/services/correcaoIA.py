# -*- coding: utf-8 -*-
"""
Serviço de Correção de Provas Institucionais usando IA (Abacus AI)
Detecta ROI (borda grossa), extrai região e usa IA para detectar respostas marcadas
"""

import cv2
import numpy as np
import json
import base64
import logging
import re
from typing import Dict, List, Optional, Tuple, Any
from app.openai_config.openai_config import (
    ABACUS_API_KEY,
    ABACUS_API_URL,
    ABACUS_MODEL,
    ABACUS_MAX_TOKENS,
    ABACUS_TEMPERATURE
)
import requests
from app import db
from app.models.testQuestion import TestQuestion
from app.models.question import Question
from app.models.studentAnswer import StudentAnswer
from app.models.student import Student
from datetime import datetime


class CorrecaoIA:
    """
    Serviço para correção de provas institucionais usando IA
    """
    
    def __init__(self, debug: bool = False):
        """
        Inicializa o serviço de correção com IA
        
        Args:
            debug: Se True, gera logs detalhados
        """
        self.debug = debug
        self.logger = logging.getLogger(__name__)
        
        # Abacus AI usa REST API direta, não precisa de cliente
        self.logger.info("Abacus AI configurado (REST API)")
    
    def corrigir_prova_com_ia(self, image_data: bytes, test_id: str) -> Dict[str, Any]:
        """
        Processa correção completa usando IA:
        1. Detecta QR Code para identificar aluno
        2. Detecta ROI (borda grossa)
        3. Extrai região do formulário
        4. Busca gabarito
        5. Envia para IA com prompt detalhado
        6. Processa resposta e salva no banco
        
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
            
            
            # 2. Detectar QR Code
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
            
            
            # 3. Detectar ROI (borda grossa de 5px)
            roi_corners = self._detectar_roi_borda_grossa(img)
            if roi_corners is None:
                return {"success": False, "error": "ROI (borda grossa) não detectado na imagem"}
            
            
            # 4. Extrair e processar ROI
            roi_image = self._extrair_roi(img, roi_corners)
            if roi_image is None:
                return {"success": False, "error": "Erro ao extrair ROI"}
            
            # 5. Buscar gabarito do teste
            gabarito = self._buscar_gabarito(test_id)
            if not gabarito:
                return {"success": False, "error": "Gabarito não encontrado para esta prova"}
            
            num_questions = len(gabarito)
            
            # 6. Preparar imagem para IA
            image_base64 = self._preparar_imagem_para_ia(roi_image)
            
            # 7. Construir prompt detalhado
            prompt = self._construir_prompt_detalhado(num_questions, gabarito)
            
            # 8. Chamar IA
            ai_response = self._chamar_ia(prompt, image_base64)
            if not ai_response:
                return {"success": False, "error": "Erro ao chamar IA"}
            
            # 9. Processar resposta da IA
            resultado = self._processar_resposta_ia(ai_response, gabarito)
            if not resultado:
                return {"success": False, "error": "Erro ao processar resposta da IA"}
            
            # 10. Salvar respostas no banco
            saved_answers = self._salvar_respostas_no_banco(
                test_id=test_id,
                student_id=student_id,
                respostas_detectadas=resultado['answers'],
                gabarito=gabarito
            )
            
            # 11. Criar sessão mínima para EvaluationResultService (necessária devido a foreign key)
            # Criamos apenas uma sessão mínima sem dados desnecessários
            session_id = self._criar_sessao_minima_para_evaluation_result(
                test_id=test_id,
                student_id=student_id
            )
            
            if not session_id:
                self.logger.warning("Não foi possível criar sessão mínima, continuando sem EvaluationResult")
                evaluation_result = None
            else:
                # 12. Calcular nota, proficiência e classificação usando EvaluationResultService
                from app.services.evaluation_result_service import EvaluationResultService
                
                evaluation_result = EvaluationResultService.calculate_and_save_result(
                    test_id=test_id,
                    student_id=student_id,
                    session_id=session_id
                )
            
            # 13. Calcular resultado final
            correct_count = resultado['correction']['correct']
            total_count = resultado['correction']['total_questions']
            percentage = resultado['correction']['score_percentage']
            
            # Preparar resposta com todos os campos
            response_data = {
                "success": True,
                "student_id": student_id,
                "test_id": test_id,
                "correct": correct_count,
                "total": total_count,
                "percentage": percentage,
                "answers": resultado['answers'],
                "correction": resultado['correction'],
                "details": resultado.get('details', {}),
                "saved_answers": saved_answers
            }
            
            # Adicionar campos calculados pelo EvaluationResultService
            if evaluation_result:
                response_data["grade"] = evaluation_result.get('grade', 0.0)
                response_data["proficiency"] = evaluation_result.get('proficiency', 0.0)
                response_data["classification"] = evaluation_result.get('classification', 'Não definido')
                response_data["evaluation_result_id"] = evaluation_result.get('id')
                response_data["score_percentage"] = evaluation_result.get('score_percentage', percentage)
                response_data["correct_answers"] = correct_count  # Compatibilidade
                response_data["total_questions"] = total_count  # Compatibilidade
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
            
            # 14. Marcar formulário físico como corrigido
            self._marcar_formulario_como_corrigido(test_id, student_id)
            
            return response_data
            
        except Exception as e:
            self.logger.error(f"Erro na correção com IA: {str(e)}", exc_info=True)
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
            self.logger.error(f"Erro ao buscar ID completo para {table_name} com sufixo {suffix}: {str(e)}")
            return None
    
    def _detectar_roi_borda_grossa(self, img: np.ndarray) -> Optional[np.ndarray]:
        """
        Detecta ROI (borda grossa de 5px) ao redor dos blocos de resposta
        Retorna 4 pontos ordenados (TL, TR, BR, BL)
        """
        try:
            # Converter para grayscale
            if len(img.shape) == 3:
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            else:
                gray = img.copy()
            
            h, w = gray.shape
            
            # Aplicar blur gaussiano
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            
            # Threshold adaptativo invertido (preto vira branco)
            binary = cv2.adaptiveThreshold(
                blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY_INV, 11, 2
            )
            
            # Morfologia para limpar ruído
            kernel = np.ones((3, 3), np.uint8)
            opening = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
            
            # Encontrar contornos
            contours, _ = cv2.findContours(opening, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if not contours:
                self.logger.warning("Nenhum contorno encontrado")
                return None
            
            # Filtrar contornos por área (deve ser grande, ~20-50% da imagem)
            min_area = (w * h) * 0.15  # Mínimo 15% da imagem
            max_area = (w * h) * 0.80  # Máximo 80% da imagem
            
            valid_contours = [
                c for c in contours
                if min_area <= cv2.contourArea(c) <= max_area
            ]
            
            if not valid_contours:
                self.logger.warning("Nenhum contorno válido encontrado")
                return None
            
            # Pegar maior contorno válido
            maior_contorno = max(valid_contours, key=cv2.contourArea)
            
            # Aproximar para retângulo
            epsilon = 0.02 * cv2.arcLength(maior_contorno, True)
            aproximado = cv2.approxPolyDP(maior_contorno, epsilon, True)
            
            if len(aproximado) < 4:
                self.logger.warning(f"Contorno não tem 4 vértices (encontrados: {len(aproximado)})")
                return None
            
            # Ordenar pontos (TL, TR, BR, BL)
            pontos_ordenados = self._ordenar_pontos(aproximado)
            
            return pontos_ordenados
            
        except Exception as e:
            self.logger.error(f"Erro ao detectar ROI: {str(e)}", exc_info=True)
            return None
    
    def _ordenar_pontos(self, pontos: np.ndarray) -> np.ndarray:
        """Ordena 4 pontos como TL, TR, BR, BL"""
        pontos = pontos.reshape((4, 2))
        soma = pontos.sum(axis=1)
        diff = np.diff(pontos, axis=1)
        
        topo_esq = pontos[np.argmin(soma)]
        baixo_dir = pontos[np.argmax(soma)]
        topo_dir = pontos[np.argmin(diff)]
        baixo_esq = pontos[np.argmax(diff)]
        
        return np.array([topo_esq, topo_dir, baixo_dir, baixo_esq], dtype="float32")
    
    def _extrair_roi(self, img: np.ndarray, corners: np.ndarray) -> Optional[np.ndarray]:
        """
        Extrai ROI aplicando correção de perspectiva e cortando borda
        """
        try:
            # Calcular dimensões do retângulo
            width_top = np.linalg.norm(corners[1] - corners[0])
            width_bottom = np.linalg.norm(corners[2] - corners[3])
            height_left = np.linalg.norm(corners[3] - corners[0])
            height_right = np.linalg.norm(corners[2] - corners[1])
            
            max_width = int(max(width_top, width_bottom))
            max_height = int(max(height_left, height_right))
            
            # Pontos de destino (retângulo retificado)
            dst = np.array([
                [0, 0],
                [max_width - 1, 0],
                [max_width - 1, max_height - 1],
                [0, max_height - 1]
            ], dtype="float32")
            
            # Calcular matriz de homografia
            M = cv2.getPerspectiveTransform(corners, dst)
            
            # Aplicar transformação
            warped = cv2.warpPerspective(img, M, (max_width, max_height))
            
            # Cortar borda (5-10px de cada lado)
            border_crop = 10
            h, w = warped.shape[:2]
            if h > border_crop * 2 and w > border_crop * 2:
                warped = warped[border_crop:h-border_crop, border_crop:w-border_crop]
            
            # Redimensionar para tamanho padrão (melhor para IA)
            target_width = 2000
            scale = target_width / warped.shape[1]
            target_height = int(warped.shape[0] * scale)
            
            warped_resized = cv2.resize(warped, (target_width, target_height), interpolation=cv2.INTER_LINEAR)
            
            return warped_resized
            
        except Exception as e:
            self.logger.error(f"Erro ao extrair ROI: {str(e)}", exc_info=True)
            return None
    
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
                    gabarito[idx] = question.correct_answer.upper()  # A, B, C, D
            
            return gabarito
            
        except Exception as e:
            self.logger.error(f"Erro ao buscar gabarito: {str(e)}")
            return {}
    
    def _preparar_imagem_para_ia(self, img: np.ndarray) -> str:
        """
        Prepara imagem para envio à IA (comprime e converte para base64)
        """
        try:
            # Comprimir JPEG (qualidade 90)
            encode_params = [cv2.IMWRITE_JPEG_QUALITY, 90]
            _, buffer = cv2.imencode('.jpg', img, encode_params)
            
            # Converter para base64
            image_base64 = base64.b64encode(buffer).decode('utf-8')
            
            return image_base64
            
        except Exception as e:
            self.logger.error(f"Erro ao preparar imagem: {str(e)}")
            return ""
    
    def _construir_prompt_detalhado(self, num_questions: int, gabarito: Dict[int, str]) -> str:
        """
        Constrói prompt detalhado para a IA com estrutura do formulário e gabarito
        """
        # Formatar gabarito como JSON
        gabarito_json = json.dumps(gabarito, indent=2, ensure_ascii=False)
        
        prompt = f"""Você é um especialista em correção de provas escolares. Sua tarefa é analisar uma imagem de formulário de múltipla escolha e identificar quais bolhas foram marcadas pelo aluno.

ESTRUTURA DO FORMULÁRIO:
- O formulário contém {num_questions} questões numeradas de 1 a {num_questions}
- Cada questão tem exatamente 4 alternativas: A, B, C, D
- As questões estão organizadas em blocos de 12 questões cada
- Cada bloco tem um cabeçalho com "BLOCO XX"
- As alternativas estão em colunas: A (primeira), B (segunda), C (terceira), D (quarta)
- As bolhas são círculos de aproximadamente 18px de diâmetro

INSTRUÇÕES DE DETECÇÃO:
1. Identifique APENAS bolhas COMPLETAMENTE PREENCHIDAS (pelo menos 80% preto)
2. IGNORE marcações parciais, rasuras ou marcas muito fracas
3. Se uma questão tiver múltiplas marcações, considere a mais escura/completa
4. Se uma questão não tiver marcação clara, retorne null

GABARITO (RESPOSTAS CORRETAS):
{gabarito_json}

FORMATO DE RESPOSTA:
Retorne APENAS um JSON válido com esta estrutura exata:
{{
  "answers": {{
    "1": "A",    // ou "B", "C", "D", ou null se não marcada
    "2": "B",
    "3": null,
    ...
  }},
  "correction": {{
    "total_questions": {num_questions},
    "answered": 0,      // quantas foram respondidas
    "correct": 0,       // quantas estão corretas
    "incorrect": 0,     // quantas estão incorretas
    "unanswered": 0,    // quantas não foram respondidas
    "score_percentage": 0.0  // porcentagem de acertos (0-100)
  }},
  "details": {{
    "1": {{
      "detected": "A",
      "correct": "A",
      "is_correct": true,
      "confidence": 0.95
    }},
    "2": {{
      "detected": "B",
      "correct": "A",
      "is_correct": false,
      "confidence": 0.87
    }},
    ...
  }}
}}

IMPORTANTE:
- Retorne APENAS o JSON, sem texto adicional antes ou depois
- Use números como strings nas chaves ("1", "2", etc.)
- Se não conseguir detectar uma resposta, use null
- Calcule a correção comparando "answers" com o gabarito fornecido
- Calcule score_percentage como: (correct / total_questions) * 100
"""
        return prompt
    
    def _chamar_ia(self, prompt: str, image_base64: str) -> Optional[str]:
        """
        Chama Abacus AI RouteLLM API REST diretamente com prompt e imagem
        Usa endpoint https://routellm.abacus.ai/v1/chat/completions (compatível com OpenAI)
        """
        try:
            # Preparar headers
            headers = {
                "Authorization": f"Bearer {ABACUS_API_KEY}",
                "Content-Type": "application/json"
            }
            
            # Preparar payload no formato OpenAI API
            payload = {
                "model": ABACUS_MODEL,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": prompt
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_base64}"
                                }
                            }
                        ]
                    }
                ],
                "temperature": ABACUS_TEMPERATURE,
                "max_tokens": ABACUS_MAX_TOKENS
            }
            
            # Fazer requisição
            self.logger.info(f"Chamando Abacus AI REST API (modelo: {ABACUS_MODEL})...")
            response = requests.post(
                ABACUS_API_URL,
                headers=headers,
                json=payload,
                timeout=120  # Timeout de 2 minutos para análise de imagens
            )
            
            # Verificar status da resposta
            response.raise_for_status()
            
            # Parsear resposta JSON
            result = response.json()
            
            # Extrair conteúdo da resposta (múltiplos formatos possíveis)
            content = None
            
            # Formato 1: OpenAI API (choices[0].message.content)
            if 'choices' in result and len(result['choices']) > 0:
                if 'message' in result['choices'][0] and 'content' in result['choices'][0]['message']:
                    content = result['choices'][0]['message']['content']
            
            # Formato 2: Resposta direta (content)
            elif 'content' in result:
                content = result['content']
            
            # Formato 3: Resposta direta (text)
            elif 'text' in result:
                content = result['text']
            
            # Formato 4: Resposta direta (response)
            elif 'response' in result:
                content = result['response']
            
            # Formato 5: Resposta direta (message)
            elif 'message' in result:
                content = result['message']
            
            if content:
                self.logger.info("Resposta recebida com sucesso do Abacus AI")
                return content
            else:
                self.logger.error(f"Resposta do Abacus AI em formato inesperado: {result}")
                return None
                
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Erro na requisição HTTP para Abacus AI: {str(e)}")
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_detail = e.response.json()
                    self.logger.error(f"Detalhes do erro: {error_detail}")
                except:
                    self.logger.error(f"Status code: {e.response.status_code}, Text: {e.response.text[:200]}")
            return None
        except Exception as e:
            self.logger.error(f"Erro ao chamar Abacus AI: {str(e)}", exc_info=True)
            return None
    
    def _processar_resposta_ia(self, ai_response: str, gabarito: Dict[int, str]) -> Optional[Dict[str, Any]]:
        """
        Processa resposta da IA e valida estrutura
        """
        try:
            # Log da resposta bruta para debug
            self.logger.debug(f"Resposta bruta da IA (primeiros 500 chars): {ai_response[:500]}")
            
            if not ai_response:
                self.logger.error("Resposta da IA está vazia")
                return None
            
            # Tentar extrair JSON da resposta (múltiplas estratégias)
            json_str = None
            
            # Estratégia 1: JSON dentro de ```json ... ```
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', ai_response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
                self.logger.debug("JSON encontrado dentro de ```json```")
            
            # Estratégia 2: JSON dentro de ``` ... ```
            if not json_str:
                json_match = re.search(r'```\s*(\{.*?\})\s*```', ai_response, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1)
                    self.logger.debug("JSON encontrado dentro de ```")
            
            # Estratégia 3: Buscar primeiro { até último } (mais robusto)
            if not json_str:
                # Encontrar primeiro {
                start_idx = ai_response.find('{')
                if start_idx != -1:
                    # Encontrar último } a partir do primeiro {
                    # Contar chaves para encontrar o JSON completo
                    brace_count = 0
                    end_idx = start_idx
                    for i in range(start_idx, len(ai_response)):
                        if ai_response[i] == '{':
                            brace_count += 1
                        elif ai_response[i] == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                end_idx = i + 1
                                break
                    
                    if end_idx > start_idx:
                        json_str = ai_response[start_idx:end_idx]
                        self.logger.debug("JSON encontrado usando contagem de chaves")
            
            # Estratégia 4: Regex simples para { ... }
            if not json_str:
                json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', ai_response, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                    self.logger.debug("JSON encontrado usando regex simples")
            
            # Estratégia 5: Tentar parsear a resposta inteira como JSON
            if not json_str:
                try:
                    # Tentar parsear resposta inteira
                    test_json = json.loads(ai_response.strip())
                    if isinstance(test_json, dict):
                        json_str = ai_response.strip()
                        self.logger.debug("Resposta inteira é JSON válido")
                except:
                    pass
            
            if not json_str:
                self.logger.error(f"JSON não encontrado na resposta da IA. Resposta completa: {ai_response}")
                return None
            
            # Parsear JSON
            resultado = json.loads(json_str)
            
            # Validar estrutura
            if 'answers' not in resultado:
                self.logger.error("Resposta não contém 'answers'")
                return None
            
            if 'correction' not in resultado:
                self.logger.error("Resposta não contém 'correction'")
                return None
            
            # Validar e normalizar respostas
            answers = resultado['answers']
            validated_answers = {}
            
            for q_num_str, answer in answers.items():
                q_num = int(q_num_str)
                if answer and answer.upper() in ['A', 'B', 'C', 'D']:
                    validated_answers[q_num] = answer.upper()
                else:
                    validated_answers[q_num] = None
            
            # Recalcular correção se necessário
            correction = self._calcular_correcao(validated_answers, gabarito)
            
            # Atualizar resultado
            resultado['answers'] = validated_answers
            resultado['correction'] = correction
            
            return resultado
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Erro ao parsear JSON da IA: {str(e)}")
            return None
        except Exception as e:
            self.logger.error(f"Erro ao processar resposta da IA: {str(e)}", exc_info=True)
            return None
    
    def _calcular_correcao(self, answers: Dict[int, Optional[str]], gabarito: Dict[int, str]) -> Dict[str, Any]:
        """
        Calcula estatísticas de correção
        """
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
            from datetime import datetime
            import uuid
            
            # Verificar se já existe uma sessão para esta correção física
            existing_session = TestSession.query.filter_by(
                test_id=test_id,
                student_id=student_id,
                status='corrigida',
                user_agent='Physical Test Correction (IA)'
            ).first()
            
            if existing_session:
                return existing_session.id
            
            # Criar nova sessão mínima para correção física
            session = TestSession(
                id=str(uuid.uuid4()),  # Gerar ID explícito
                student_id=student_id,
                test_id=test_id,
                time_limit_minutes=None,
                ip_address=None,
                user_agent='Physical Test Correction (IA)',
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
            from datetime import datetime
            
            # Buscar formulário físico do aluno para esta prova
            form = PhysicalTestForm.query.filter_by(
                test_id=test_id,
                student_id=student_id
            ).first()
            
            if not form:
                self.logger.warning(f"Formulário físico não encontrado para test_id={test_id}, student_id={student_id}")
                return False
            
            # Marcar como enviado (se ainda não foi marcado)
            # Se estamos corrigindo, significa que o formulário foi entregue/enviado
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

