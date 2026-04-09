# -*- coding: utf-8 -*-
"""
Serviço de Correção de Cartões Resposta
Sistema independente que reutiliza funções de detecção do correcao_hybrid
mas trabalha exclusivamente com AnswerSheetGabarito e AnswerSheetResult
"""

import cv2
import numpy as np
import json
import logging
from typing import Dict, List, Optional, Tuple, Any
from app import db
from app.models.student import Student
from app.models.answerSheetGabarito import AnswerSheetGabarito
from app.models.answerSheetResult import AnswerSheetResult
from datetime import datetime


class AnswerSheetCorrectionService:
    """
    Serviço para correção de cartões resposta
    Reutiliza funções de detecção do CorrecaoHybrid mas trabalha apenas com
    AnswerSheetGabarito e AnswerSheetResult
    """
    
    def __init__(self, debug: bool = False):
        self.debug = debug
        self.logger = logging.getLogger(__name__)
        self.logger.info("Serviço de Correção de Cartões Resposta inicializado")
    
    def corrigir_cartao_resposta(self, image_data: bytes) -> Dict[str, Any]:
        """
        Processa correção completa de cartão resposta:
        1. Detecta QR Code (gabarito_id + student_id)
        2. Detecta triângulos de alinhamento
        3. Corrige perspectiva
        4. Detecta bolhas marcadas
        5. Busca gabarito em AnswerSheetGabarito
        6. Compara respostas
        7. Calcula nota, proficiência, classificação
        8. Salva em AnswerSheetResult
        
        Args:
            image_data: Imagem em bytes (JPEG/PNG)
            
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
            gabarito_id = qr_result.get('gabarito_id')
            
            if not gabarito_id:
                return {"success": False, "error": "gabarito_id não encontrado no QR code"}
            
            self.logger.info(f"QR Code detectado: student_id={student_id}, gabarito_id={gabarito_id}")
            
            # 3. Validar aluno
            student = Student.query.get(student_id)
            if not student:
                return {"success": False, "error": f"Aluno com ID {student_id} não encontrado no sistema"}
            
            # 4. Buscar gabarito em AnswerSheetGabarito
            gabarito_obj = AnswerSheetGabarito.query.get(gabarito_id)
            if not gabarito_obj:
                return {"success": False, "error": "Gabarito não encontrado"}
            
            # Converter correct_answers para dict
            correct_answers = gabarito_obj.correct_answers
            if isinstance(correct_answers, str):
                correct_answers = json.loads(correct_answers)
            
            gabarito = {}
            for key, value in correct_answers.items():
                try:
                    q_num = int(key)
                    gabarito[q_num] = str(value).upper() if value else None
                except (ValueError, TypeError):
                    continue
            
            num_questions = gabarito_obj.num_questions
            
            # 5. Corrigir perspectiva usando triângulos
            img_aligned = self._corrigir_perspectiva(img)
            if img_aligned is None:
                return {"success": False, "error": "Não foi possível detectar triângulos de alinhamento"}
            
            # 6. Fazer crop baseado nos triângulos
            top, btt = self._calcular_crop_points(img_aligned)
            img_crop = img_aligned[top[1]:btt[1], top[0]:btt[0]]
            
            # 7. Detectar respostas marcadas
            respostas_aluno = self._detectar_respostas(img_crop, num_questions=num_questions)
            
            if not respostas_aluno:
                return {"success": False, "error": "Erro ao detectar respostas marcadas"}
            
            # 8. Validar respostas
            validated_answers = {}
            for q_num in range(1, num_questions + 1):
                validated_answers[q_num] = respostas_aluno.get(q_num)
            
            # 9. Calcular correção
            correction = self._calcular_correcao(validated_answers, gabarito)
            
            # 10. Calcular nota, proficiência por disciplina e média geral
            correct_count = correction['correct']
            total_count = correction['total_questions']
            percentage = correction['score_percentage']
            grade = (correct_count / total_count * 10) if total_count > 0 else 0.0
            
            from app.services.cartao_resposta.proficiency_by_subject import calcular_proficiencia_por_disciplina
            blocks_config = getattr(gabarito_obj, 'blocks_config', None) or {}
            proficiency_by_subject, proficiency, classification = calcular_proficiencia_por_disciplina(
                blocks_config=blocks_config,
                validated_answers=validated_answers,
                gabarito_dict=gabarito,
                grade_name=gabarito_obj.grade_name or '',
            )
            
            # 11. Salvar resultado em AnswerSheetResult
            saved_result = self._salvar_resultado(
                gabarito_id=gabarito_id,
                student_id=student_id,
                detected_answers=validated_answers,
                correction=correction,
                grade=grade,
                proficiency=proficiency,
                classification=classification,
                proficiency_by_subject=proficiency_by_subject,
            )
            
            return {
                "success": True,
                "student_id": student_id,
                "gabarito_id": gabarito_id,
                "correct": correct_count,
                "total": total_count,
                "percentage": percentage,
                "answers": validated_answers,
                "correction": correction,
                "grade": grade,
                "proficiency": proficiency,
                "classification": classification,
                "proficiency_by_subject": proficiency_by_subject,
                "answer_sheet_result_id": saved_result.get('id') if saved_result else None,
                "score_percentage": percentage,
                "correct_answers": correct_count,
                "total_questions": total_count
            }
            
        except Exception as e:
            self.logger.error(f"Erro na correção: {str(e)}", exc_info=True)
            return {"success": False, "error": f"Erro interno: {str(e)}"}
    
    # ========================================================================
    # FUNÇÕES DE DETECÇÃO (Reutilizadas do CorrecaoHybrid)
    # ========================================================================
    
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
        Detecta QR Code na imagem - reutiliza lógica do CorrecaoHybrid
        """
        from app.services.correcao_hybrid import CorrecaoHybrid
        correcao_hybrid = CorrecaoHybrid(debug=self.debug)
        return correcao_hybrid._detectar_qr_code(img)
    
    def _corrigir_perspectiva(self, img: np.ndarray) -> Optional[np.ndarray]:
        """Corrige perspectiva usando triângulos - reutiliza do CorrecaoHybrid"""
        from app.services.correcao_hybrid import CorrecaoHybrid
        correcao_hybrid = CorrecaoHybrid(debug=self.debug)
        return correcao_hybrid._paper90(img)
    
    def _calcular_crop_points(self, img: np.ndarray) -> Tuple[List[int], List[int]]:
        """Calcula pontos de crop - reutiliza do CorrecaoHybrid"""
        from app.services.correcao_hybrid import CorrecaoHybrid
        correcao_hybrid = CorrecaoHybrid(debug=self.debug)
        return correcao_hybrid._getPTCrop(img)
    
    def _detectar_respostas(self, img: np.ndarray, num_questions: int = None) -> Optional[Dict[int, str]]:
        """Detecta bolhas marcadas - reutiliza do CorrecaoHybrid"""
        from app.services.correcao_hybrid import CorrecaoHybrid
        correcao_hybrid = CorrecaoHybrid(debug=self.debug)
        return correcao_hybrid._getAnswers(img, num_questions=num_questions)
    
    # ========================================================================
    # FUNÇÕES ESPECÍFICAS DO CARTÃO RESPOSTA
    # ========================================================================
    
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
    
    def _calcular_proficiencia_classificacao(self, score_percentage: float, 
                                            gabarito_obj: AnswerSheetGabarito) -> Tuple[float, str]:
        """Calcula proficiência e classificação"""
        try:
            from app.services.evaluation_calculator import EvaluationCalculator, CourseLevel, Subject
            
            # Inferir nível e disciplina do gabarito
            course_level = CourseLevel.ANOS_INICIAIS
            subject = Subject.OUTRAS
            
            grade_name = gabarito_obj.grade_name or ''
            if any(x in grade_name.lower() for x in ['infantil', 'pré', 'pre']):
                course_level = CourseLevel.EDUCACAO_INFANTIL
            elif any(x in grade_name.lower() for x in ['1º', '2º', '3º', '4º', '5º', 'anos iniciais']):
                course_level = CourseLevel.ANOS_INICIAIS
            elif any(x in grade_name.lower() for x in ['6º', '7º', '8º', '9º', 'anos finais']):
                course_level = CourseLevel.ANOS_FINAIS
            elif any(x in grade_name.lower() for x in ['1º médio', '2º médio', '3º médio', 'ensino médio']):
                course_level = CourseLevel.ENSINO_MEDIO
            
            title = gabarito_obj.title or ''
            if 'matemática' in title.lower() or 'matematica' in title.lower():
                subject = Subject.MATEMATICA
            
            calculator = EvaluationCalculator()
            proficiency = calculator.calculate_proficiency(
                score_percentage=score_percentage,
                course_level=course_level,
                subject=subject
            )
            classification = calculator.calculate_classification(
                proficiency=proficiency,
                course_level=course_level,
                subject=subject
            )
            
            return proficiency, classification.value if hasattr(classification, 'value') else str(classification)
            
        except Exception as e:
            self.logger.error(f"Erro ao calcular proficiência/classificação: {str(e)}")
            return 0.0, "Não calculado"
    
    def _salvar_resultado(self, gabarito_id: str, student_id: str,
                         detected_answers: Dict[int, Optional[str]],
                         correction: Dict[str, Any],
                         grade: float, proficiency: float,
                         classification: str,
                         proficiency_by_subject: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """Salva resultado em AnswerSheetResult"""
        try:
            # Verificar se já existe resultado
            existing_result = AnswerSheetResult.query.filter_by(
                gabarito_id=gabarito_id,
                student_id=student_id
            ).first()
            
            if existing_result:
                # Atualizar
                existing_result.detected_answers = detected_answers
                existing_result.correct_answers = correction.get('correct', 0)
                existing_result.total_questions = correction.get('total_questions', 0)
                existing_result.incorrect_answers = correction.get('incorrect', 0)
                existing_result.unanswered_questions = correction.get('unanswered', 0)
                existing_result.answered_questions = correction.get('answered', 0)
                existing_result.score_percentage = correction.get('score_percentage', 0.0)
                existing_result.grade = grade
                existing_result.proficiency = proficiency
                existing_result.classification = classification
                existing_result.proficiency_by_subject = proficiency_by_subject
                existing_result.corrected_at = datetime.utcnow()
                existing_result.detection_method = 'geometric'
                
                db.session.flush()
                payload = existing_result.to_dict()
                db.session.commit()
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
                    correct_answers=correction.get('correct', 0),
                    total_questions=correction.get('total_questions', 0),
                    incorrect_answers=correction.get('incorrect', 0),
                    unanswered_questions=correction.get('unanswered', 0),
                    answered_questions=correction.get('answered', 0),
                    score_percentage=correction.get('score_percentage', 0.0),
                    grade=grade,
                    proficiency=proficiency,
                    classification=classification,
                    proficiency_by_subject=proficiency_by_subject,
                    detection_method='geometric'
                )
                
                db.session.add(result)
                db.session.flush()
                payload = result.to_dict()
                db.session.commit()
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
            self.logger.error(f"Erro ao salvar resultado: {str(e)}", exc_info=True)
            return None

