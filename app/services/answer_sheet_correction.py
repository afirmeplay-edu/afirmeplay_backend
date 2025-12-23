# -*- coding: utf-8 -*-
"""
Serviço de Correção de Cartões Resposta usando IA
Reutiliza lógica do CorrecaoIA mas busca gabarito do AnswerSheetGabarito
"""

import cv2
import numpy as np
import json
import base64
import logging
import re
from typing import Dict, List, Optional, Tuple, Any
# answer_sheet_correction reutiliza correcaoIA
from app import db
from app.models.studentAnswer import StudentAnswer
from app.models.student import Student
from datetime import datetime


class AnswerSheetCorrection:
    """
    Serviço para correção de cartões resposta usando IA
    """
    
    def __init__(self, debug: bool = False):
        """
        Inicializa o serviço de correção com IA
        
        Args:
            debug: Se True, gera logs detalhados
        """
        self.debug = debug
        self.logger = logging.getLogger(__name__)
        
        # IA é usada via correcaoIA
        self.logger.info("IA configurada (via correcaoIA)")
    
    def corrigir_cartao_resposta(self, image_data: bytes, gabarito_id: str = None, 
                                 test_id: str = None) -> Dict[str, Any]:
        """
        Processa correção completa usando IA:
        1. Detecta QR Code para identificar aluno
        2. Detecta ROI (borda grossa)
        3. Extrai região do formulário
        4. Busca gabarito (do AnswerSheetGabarito ou do Test)
        5. Envia para IA com prompt detalhado
        6. Processa resposta e salva no banco
        
        Args:
            image_data: Imagem em bytes (JPEG/PNG)
            gabarito_id: ID do gabarito (AnswerSheetGabarito)
            test_id: ID da prova (opcional, se não tiver gabarito_id)
            
        Returns:
            Dict com resultados da correção
        """
        try:
            # 1. Decodificar imagem
            img = self._decode_image(image_data)
            if img is None:
                return {"success": False, "error": "Erro ao decodificar imagem"}
            
            self.logger.info(f"Imagem decodificada: {img.shape}")
            
            # 2. Detectar QR Code
            qr_result = self._detectar_qr_code(img)
            if not qr_result or 'student_id' not in qr_result:
                return {"success": False, "error": "QR Code não detectado ou inválido"}
            
            student_id = qr_result['student_id']
            gabarito_id_from_qr = qr_result.get('gabarito_id')
            test_id_from_qr = qr_result.get('test_id')
            
            # Usar gabarito_id do QR se não foi fornecido
            if not gabarito_id and gabarito_id_from_qr:
                gabarito_id = gabarito_id_from_qr
            
            # Usar test_id do QR se não foi fornecido
            if not test_id and test_id_from_qr:
                test_id = test_id_from_qr
            
            self.logger.info(f"QR Code detectado: student_id={student_id}, gabarito_id={gabarito_id}, test_id={test_id}")
            
            # 3. Detectar ROI (borda grossa de 5px)
            roi_corners = self._detectar_roi_borda_grossa(img)
            if roi_corners is None:
                return {"success": False, "error": "ROI (borda grossa) não detectado na imagem"}
            
            self.logger.info("ROI detectado com sucesso")
            
            # 4. Extrair e processar ROI
            roi_image = self._extrair_roi(img, roi_corners)
            if roi_image is None:
                return {"success": False, "error": "Erro ao extrair ROI"}
            
            self.logger.info(f"ROI extraído: {roi_image.shape}")
            
            # 5. Buscar gabarito
            if gabarito_id:
                gabarito, num_questions = self._buscar_gabarito_por_id(gabarito_id)
            elif test_id:
                gabarito, num_questions = self._buscar_gabarito_por_test_id(test_id)
            else:
                return {"success": False, "error": "gabarito_id ou test_id é obrigatório"}
            
            if not gabarito:
                return {"success": False, "error": "Gabarito não encontrado"}
            
            self.logger.info(f"Gabarito carregado: {num_questions} questões")
            
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
            
            # 10. Salvar respostas no banco (se tiver test_id)
            saved_answers = []
            if test_id:
                saved_answers = self._salvar_respostas_no_banco(
                    test_id=test_id,
                    student_id=student_id,
                    respostas_detectadas=resultado['answers'],
                    gabarito=gabarito
                )
            
            # 11. Calcular nota, proficiência e classificação usando EvaluationResultService (se tiver test_id)
            evaluation_result = None
            if test_id:
                from app.services.evaluation_result_service import EvaluationResultService
                import uuid
                
                # Gerar session_id temporário para correções físicas
                session_id = f"physical_correction_ia_{uuid.uuid4().hex[:8]}"
                
                evaluation_result = EvaluationResultService.calculate_and_save_result(
                    test_id=test_id,
                    student_id=student_id,
                    session_id=session_id
                )
            
            # 12. Calcular resultado final
            correct_count = resultado['correction']['correct']
            total_count = resultado['correction']['total_questions']
            percentage = resultado['correction']['score_percentage']
            
            # Preparar resposta com todos os campos
            response_data = {
                "success": True,
                "student_id": student_id,
                "gabarito_id": gabarito_id,
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
                response_data["correct_answers"] = correct_count
                response_data["total_questions"] = total_count
            else:
                # Fallback se não conseguir calcular
                response_data["grade"] = (correct_count / total_count * 10) if total_count > 0 else 0.0
                response_data["proficiency"] = 0.0
                response_data["classification"] = "Não calculado"
                response_data["evaluation_result_id"] = None
                response_data["score_percentage"] = percentage
                response_data["correct_answers"] = correct_count
                response_data["total_questions"] = total_count
            
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
        Detecta QR Code na imagem - reutiliza lógica do CorrecaoIA
        """
        try:
            from app.services.correcaoIA import CorrecaoIA
            correcao_ia = CorrecaoIA(debug=self.debug)
            return correcao_ia._detectar_qr_code(img)
        except Exception as e:
            self.logger.error(f"Erro ao detectar QR Code: {str(e)}")
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
                            'test_id': test_id,
                            'gabarito_id': None  # Não está no formato compacto
                        }
                    else:
                        self.logger.warning(f"Não foi possível encontrar IDs completos: "
                                          f"student_suffix={short_student_id}, test_suffix={short_test_id}")
                        # Fallback: retornar os sufixos mesmo assim
                        return {
                            'student_id': short_student_id,
                            'test_id': short_test_id,
                            'gabarito_id': None
                        }
            
            # Tentar formato compacto com dois pontos: s:xxx t:xxx
            if data.startswith('s:') and ' t:' in data:
                parts = data.split(' t:')
                if len(parts) == 2:
                    student_id = parts[0].replace('s:', '').strip()
                    test_id = parts[1].strip()
                    return {
                        'student_id': student_id,
                        'test_id': test_id,
                        'gabarito_id': None  # Não está no formato compacto
                    }
            
            # Tentar parsear como JSON (compatibilidade com formato antigo)
            try:
                qr_json = json.loads(data)
                return {
                    'student_id': qr_json.get('student_id'),
                    'test_id': qr_json.get('test_id'),
                    'gabarito_id': qr_json.get('gabarito_id')
                }
            except json.JSONDecodeError:
                # Se não for JSON, tratar como student_id direto
                return {
                    'student_id': data.strip(),
                    'test_id': None,
                    'gabarito_id': None
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
        Detecta ROI (borda grossa de 5px) - reutiliza lógica do CorrecaoIA
        """
        try:
            from app.services.correcaoIA import CorrecaoIA
            correcao_ia = CorrecaoIA(debug=self.debug)
            return correcao_ia._detectar_roi_borda_grossa(img)
        except Exception as e:
            self.logger.error(f"Erro ao detectar ROI: {str(e)}")
            return None
    
    def _extrair_roi(self, img: np.ndarray, corners: np.ndarray) -> Optional[np.ndarray]:
        """
        Extrai ROI aplicando correção de perspectiva - reutiliza lógica do CorrecaoIA
        """
        try:
            from app.services.correcaoIA import CorrecaoIA
            correcao_ia = CorrecaoIA(debug=self.debug)
            return correcao_ia._extrair_roi(img, corners)
        except Exception as e:
            self.logger.error(f"Erro ao extrair ROI: {str(e)}")
            return None
    
    def _buscar_gabarito_por_id(self, gabarito_id: str) -> Tuple[Dict[int, str], int]:
        """
        Busca gabarito do AnswerSheetGabarito no banco de dados
        Retorna: (gabarito_dict, num_questions)
        """
        try:
            from app.models.answerSheetGabarito import AnswerSheetGabarito
            
            gabarito_obj = AnswerSheetGabarito.query.get(gabarito_id)
            if not gabarito_obj:
                return {}, 0
            
            # Converter correct_answers de JSON para dict
            correct_answers = gabarito_obj.correct_answers
            if isinstance(correct_answers, str):
                correct_answers = json.loads(correct_answers)
            
            # Converter chaves para int
            gabarito = {}
            for key, value in correct_answers.items():
                try:
                    q_num = int(key)
                    gabarito[q_num] = str(value).upper() if value else None
                except (ValueError, TypeError):
                    continue
            
            num_questions = gabarito_obj.num_questions
            
            return gabarito, num_questions
            
        except Exception as e:
            self.logger.error(f"Erro ao buscar gabarito por ID: {str(e)}")
            return {}, 0
    
    def _buscar_gabarito_por_test_id(self, test_id: str) -> Tuple[Dict[int, str], int]:
        """
        Busca gabarito do teste no banco de dados (reutiliza lógica do CorrecaoIA)
        Retorna: (gabarito_dict, num_questions)
        """
        try:
            from app.services.correcaoIA import CorrecaoIA
            from app.models.testQuestion import TestQuestion
            from app.models.question import Question
            
            test_questions = TestQuestion.query.filter_by(test_id=test_id).order_by(TestQuestion.order).all()
            
            gabarito = {}
            for idx, tq in enumerate(test_questions, start=1):
                question = Question.query.get(tq.question_id)
                if question and question.correct_answer:
                    gabarito[idx] = question.correct_answer.upper()  # A, B, C, D
            
            num_questions = len(gabarito)
            
            return gabarito, num_questions
            
        except Exception as e:
            self.logger.error(f"Erro ao buscar gabarito por test_id: {str(e)}")
            return {}, 0
    
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
        Constrói prompt detalhado para a IA - reutiliza lógica do CorrecaoIA
        """
        try:
            from app.services.correcaoIA import CorrecaoIA
            correcao_ia = CorrecaoIA(debug=self.debug)
            return correcao_ia._construir_prompt_detalhado(num_questions, gabarito)
        except Exception as e:
            self.logger.error(f"Erro ao construir prompt: {str(e)}")
            return ""
    
    def _chamar_ia(self, prompt: str, image_base64: str) -> Optional[str]:
        """
        Chama API de IA - reutiliza lógica do CorrecaoIA
        """
        try:
            from app.services.correcaoIA import CorrecaoIA
            correcao_ia = CorrecaoIA(debug=self.debug)
            return correcao_ia._chamar_ia(prompt, image_base64)
        except Exception as e:
            self.logger.error(f"Erro ao chamar IA: {str(e)}")
            return None
    
    def _processar_resposta_ia(self, ai_response: str, gabarito: Dict[int, str]) -> Optional[Dict[str, Any]]:
        """
        Processa resposta da IA - reutiliza lógica do CorrecaoIA
        """
        try:
            from app.services.correcaoIA import CorrecaoIA
            correcao_ia = CorrecaoIA(debug=self.debug)
            return correcao_ia._processar_resposta_ia(ai_response, gabarito)
        except Exception as e:
            self.logger.error(f"Erro ao processar resposta da IA: {str(e)}")
            return None
    
    def _salvar_respostas_no_banco(self, test_id: str, student_id: str,
                                   respostas_detectadas: Dict[int, Optional[str]],
                                   gabarito: Dict[int, str]) -> List[Dict[str, Any]]:
        """
        Salva respostas detectadas no banco de dados - reutiliza lógica do CorrecaoIA
        """
        try:
            from app.services.correcaoIA import CorrecaoIA
            correcao_ia = CorrecaoIA(debug=self.debug)
            return correcao_ia._salvar_respostas_no_banco(
                test_id=test_id,
                student_id=student_id,
                respostas_detectadas=respostas_detectadas,
                gabarito=gabarito
            )
        except Exception as e:
            self.logger.error(f"Erro ao salvar respostas: {str(e)}")
            return []
