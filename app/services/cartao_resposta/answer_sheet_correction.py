# -*- coding: utf-8 -*-
"""
Serviço de Correção de Cartões Resposta usando Detecção Geométrica
Reutiliza lógica do CorrecaoHybrid mas busca gabarito do AnswerSheetGabarito
"""

import cv2
import numpy as np
import json
import logging
from typing import Dict, List, Optional, Tuple, Any
from app import db
from app.models.studentAnswer import StudentAnswer
from app.models.student import Student
from datetime import datetime


class AnswerSheetCorrection:
    """
    Serviço para correção de cartões resposta usando detecção geométrica
    """
    
    def __init__(self, debug: bool = False):
        """
        Inicializa o serviço de correção com detecção geométrica
        
        Args:
            debug: Se True, gera logs detalhados
        """
        self.debug = debug
        self.logger = logging.getLogger(__name__)
        
        # Detecção geométrica é usada via correcao_hybrid
        self.logger.info("Detecção geométrica configurada (via correcao_hybrid)")
    
    def corrigir_cartao_resposta(self, image_data: bytes, gabarito_id: str = None, 
                                 test_id: str = None) -> Dict[str, Any]:
        """
        Processa correção completa usando detecção geométrica:
        1. Detecta QR Code para identificar aluno
        2. Detecta triângulos de alinhamento (4 cantos)
        3. Corrige perspectiva
        4. Detecta bolhas marcadas
        5. Busca gabarito (do AnswerSheetGabarito ou do Test)
        6. Compara respostas e salva no banco
        
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
            
            # Validar se student_id existe no banco de dados
            student = Student.query.get(student_id)
            if not student:
                self.logger.error(f"Student ID {student_id} não encontrado no banco de dados")
                return {"success": False, "error": f"Aluno com ID {student_id} não encontrado no sistema"}
            
            # 3. Buscar gabarito
            if gabarito_id:
                gabarito, num_questions = self._buscar_gabarito_por_id(gabarito_id)
            elif test_id:
                gabarito, num_questions = self._buscar_gabarito_por_test_id(test_id)
            else:
                return {"success": False, "error": "gabarito_id ou test_id é obrigatório"}
            
            if not gabarito:
                return {"success": False, "error": "Gabarito não encontrado"}
            
            self.logger.info(f"Gabarito carregado: {num_questions} questões")
            
            # 4. Usar correção geométrica do CorrecaoHybrid
            from app.services.correcao_hybrid import CorrecaoHybrid
            
            correcao_hybrid = CorrecaoHybrid(debug=self.debug)
            
            # Chamar método de correção geométrica
            # O método corrigir_prova_geometrica espera test_id, mas podemos adaptar
            if test_id:
                # Se temos test_id, usar diretamente
                resultado = correcao_hybrid.corrigir_prova_geometrica(
                    image_data=image_data,
                    test_id=test_id
                )
            else:
                # Se só temos gabarito_id, precisamos fazer a detecção manualmente
                # usando os métodos internos do CorrecaoHybrid
                resultado = self._corrigir_com_gabarito_id(
                    correcao_hybrid, img, student_id, gabarito_id, gabarito, num_questions
                )
            
            if not resultado.get('success'):
                return resultado
            
            # 5. Salvar resultado em AnswerSheetResult (tabela específica para cartões resposta)
            if gabarito_id:
                saved_result = self._salvar_resultado_cartao_resposta(
                    gabarito_id=gabarito_id,
                    student_id=student_id,
                    detected_answers=resultado.get('answers', {}),
                    correction=resultado.get('correction', {}),
                    grade=resultado.get('grade', 0.0),
                    proficiency=resultado.get('proficiency', 0.0),
                    classification=resultado.get('classification', 'Não calculado')
                )
                resultado['answer_sheet_result_id'] = saved_result.get('id') if saved_result else None
            
            # 6. Adicionar informações do gabarito_id na resposta
            resultado['gabarito_id'] = gabarito_id
            
            return resultado
            
        except Exception as e:
            self.logger.error(f"Erro na correção: {str(e)}", exc_info=True)
            return {"success": False, "error": f"Erro interno: {str(e)}"}
    
    def _corrigir_com_gabarito_id(self, correcao_hybrid, img: np.ndarray, 
                                  student_id: str, gabarito_id: str,
                                  gabarito: Dict[int, str], num_questions: int) -> Dict[str, Any]:
        """
        Correção quando só temos gabarito_id (sem test_id)
        Usa métodos internos do CorrecaoHybrid
        """
        try:
            # 3. Corrigir perspectiva usando triângulos de alinhamento
            img_aligned = correcao_hybrid._paper90(img)
            if img_aligned is None:
                return {"success": False, "error": "Não foi possível detectar triângulos de alinhamento"}
            
            # 4. Fazer crop baseado nos triângulos
            top, btt = correcao_hybrid._getPTCrop(img_aligned)
            img_crop = img_aligned[top[1]:btt[1], top[0]:btt[0]]
            
            # 5. Detectar respostas marcadas
            respostas_aluno = correcao_hybrid._getAnswers(img_crop, num_questions=num_questions)
            
            if not respostas_aluno:
                return {"success": False, "error": "Erro ao detectar respostas marcadas"}
            
            # 6. Processar e validar respostas
            validated_answers = {}
            for q_num in range(1, num_questions + 1):
                validated_answers[q_num] = respostas_aluno.get(q_num)
            
            # 7. Calcular correção
            correction = correcao_hybrid._calcular_correcao(validated_answers, gabarito)
            
            # 8. Calcular nota, proficiência e classificação
            correct_count = correction['correct']
            total_count = correction['total_questions']
            percentage = correction['score_percentage']
            
            # Calcular proficiência e classificação usando EvaluationCalculator
            proficiency, classification = self._calcular_proficiencia_classificacao(
                score_percentage=percentage,
                gabarito_id=gabarito_id
            )
            from app.services.cartao_resposta.course_name_resolver import infer_course_name_from_grade
            from app.services.evaluation_calculator import EvaluationCalculator
            from app.models.answerSheetGabarito import AnswerSheetGabarito
            gabarito_obj_grade = AnswerSheetGabarito.query.get(gabarito_id)
            grade_name = (
                (gabarito_obj_grade.grade_name if gabarito_obj_grade else "")
                or (gabarito_obj_grade.title if gabarito_obj_grade else "")
            )
            course_name = infer_course_name_from_grade(grade_name)
            # Inferir se há Matemática no gabarito para alinhar regra do GERAL
            has_matematica = False
            try:
                from app.services.cartao_resposta.proficiency_by_subject import (
                    infer_has_matematica_from_blocks_config,
                )
                blocks_config = getattr(gabarito_obj_grade, 'blocks_config', None) if gabarito_obj_grade else None
                if isinstance(blocks_config, str):
                    import json
                    blocks_config = json.loads(blocks_config)
                has_matematica = infer_has_matematica_from_blocks_config(blocks_config or {})
            except Exception:
                title = (getattr(gabarito_obj_grade, 'title', '') if gabarito_obj_grade else '') or ''
                has_matematica = 'matem' in title.lower()

            grade = EvaluationCalculator.calculate_grade(
                proficiency=proficiency,
                course_name=course_name,
                subject_name='GERAL',
                use_simple_calculation=False,
                has_matematica=has_matematica,
            )
            
            # 9. Salvar resultado em AnswerSheetResult
            saved_result = self._salvar_resultado_cartao_resposta(
                gabarito_id=gabarito_id,
                student_id=student_id,
                detected_answers=validated_answers,
                correction=correction,
                grade=grade,
                proficiency=proficiency,
                classification=classification
            )
            
            return {
                "success": True,
                "student_id": student_id,
                "gabarito_id": gabarito_id,
                "test_id": None,
                "correct": correct_count,
                "total": total_count,
                "percentage": percentage,
                "answers": validated_answers,
                "correction": correction,
                "saved_answers": [],
                "detection_method": "geometric",
                "grade": grade,
                "proficiency": proficiency,
                "classification": classification,
                "evaluation_result_id": None,
                "answer_sheet_result_id": saved_result.get('id') if saved_result else None,
                "score_percentage": percentage,
                "correct_answers": correct_count,
                "total_questions": total_count
            }
            
        except Exception as e:
            self.logger.error(f"Erro na correção com gabarito_id: {str(e)}", exc_info=True)
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
        Detecta QR Code na imagem - reutiliza lógica do CorrecaoHybrid
        """
        try:
            from app.services.correcao_hybrid import CorrecaoHybrid
            correcao_hybrid = CorrecaoHybrid(debug=self.debug)
            return correcao_hybrid._detectar_qr_code(img)
        except Exception as e:
            self.logger.error(f"Erro ao detectar QR Code: {str(e)}")
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
        Busca gabarito do teste no banco de dados (reutiliza lógica do CorrecaoHybrid)
        Retorna: (gabarito_dict, num_questions)
        """
        try:
            from app.services.correcao_hybrid import CorrecaoHybrid
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
    
    def _calcular_proficiencia_classificacao(self, score_percentage: float, 
                                             gabarito_id: str = None) -> Tuple[float, str]:
        """
        Calcula proficiência e classificação usando EvaluationCalculator
        Tenta inferir nível de curso e disciplina do gabarito ou usa valores padrão
        """
        try:
            from app.services.evaluation_calculator import EvaluationCalculator, CourseLevel, Subject
            from app.services.cartao_resposta.course_name_resolver import infer_course_name_from_grade
            
            # Tentar buscar informações do gabarito para inferir nível e disciplina
            course_level = CourseLevel.ANOS_INICIAIS  # Padrão
            subject = Subject.OUTRAS  # Padrão
            
            if gabarito_id:
                from app.models.answerSheetGabarito import AnswerSheetGabarito
                gabarito_obj = AnswerSheetGabarito.query.get(gabarito_id)
                if gabarito_obj:
                    # Tentar inferir nível de curso do grade_name
                    grade_name = gabarito_obj.grade_name or gabarito_obj.title or ''
                    course_name = infer_course_name_from_grade(grade_name)
                    if course_name == 'Educação Infantil':
                        course_level = CourseLevel.EDUCACAO_INFANTIL
                    elif course_name == 'Anos Iniciais':
                        course_level = CourseLevel.ANOS_INICIAIS
                    elif course_name == 'Anos Finais':
                        course_level = CourseLevel.ANOS_FINAIS
                    elif course_name == 'Ensino Médio':
                        course_level = CourseLevel.ENSINO_MEDIO
                    elif course_name == 'Educação Especial':
                        course_level = CourseLevel.EDUCACAO_ESPECIAL
                    elif course_name == 'EJA':
                        course_level = CourseLevel.EJA
                    
                    # Tentar inferir disciplina do título
                    title = gabarito_obj.title or ''
                    if 'matemática' in title.lower() or 'matematica' in title.lower():
                        subject = Subject.MATEMATICA
            
            calculator = EvaluationCalculator()
            
            # Calcular proficiência
            proficiency = calculator.calculate_proficiency(
                score_percentage=score_percentage,
                course_level=course_level,
                subject=subject
            )
            
            # Calcular classificação
            classification = calculator.calculate_classification(
                proficiency=proficiency,
                course_level=course_level,
                subject=subject
            )
            
            return proficiency, classification.value if hasattr(classification, 'value') else str(classification)
            
        except Exception as e:
            self.logger.error(f"Erro ao calcular proficiência/classificação: {str(e)}")
            # Fallback: retornar valores padrão
            return 0.0, "Não calculado"
    
    def _salvar_resultado_cartao_resposta(self, gabarito_id: str, student_id: str,
                                          detected_answers: Dict[int, Optional[str]],
                                          correction: Dict[str, Any],
                                          grade: float, proficiency: float,
                                          classification: str) -> Optional[Dict[str, Any]]:
        """
        Salva resultado da correção na tabela AnswerSheetResult
        """
        try:
            from app.models.answerSheetResult import AnswerSheetResult
            
            # Verificar se já existe resultado para este aluno e gabarito
            existing_result = AnswerSheetResult.query.filter_by(
                gabarito_id=gabarito_id,
                student_id=student_id
            ).first()
            
            if existing_result:
                # Atualizar resultado existente
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
                existing_result.corrected_at = datetime.utcnow()
                existing_result.detection_method = 'geometric'
                
                db.session.flush()
                payload = existing_result.to_dict()
                db.session.commit()
                
                return payload
            else:
                # Criar novo resultado
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
                    detection_method='geometric'
                )
                
                db.session.add(result)
                db.session.flush()
                payload = result.to_dict()
                db.session.commit()
                
                return payload
                
        except Exception as e:
            db.session.rollback()
            self.logger.error(f"Erro ao salvar resultado do cartão resposta: {str(e)}", exc_info=True)
            return None

