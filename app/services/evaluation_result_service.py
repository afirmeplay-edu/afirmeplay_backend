# -*- coding: utf-8 -*-
"""
Serviço para gerenciar resultados de avaliação calculados
"""
from app import db
from app.models.evaluationResult import EvaluationResult
from app.models.test import Test
from app.models.question import Question
from app.models.studentAnswer import StudentAnswer
from app.services.evaluation_calculator import EvaluationCalculator
from datetime import datetime
import logging
from typing import Dict, Any, Optional
import json

class EvaluationResultService:
    
    @staticmethod
    def check_multiple_choice_answer(student_answer, alternatives):
        """
        Verifica se a resposta do aluno está correta para questão de múltipla escolha
        Compara por ID da alternativa (recomendado) ou por texto (fallback)
        """
        if not alternatives or not student_answer:
            return False
            
        student_answer = str(student_answer).strip()
        
        # Se alternatives é uma string JSON, converter para lista
        if isinstance(alternatives, str):
            try:
                alternatives = json.loads(alternatives)
            except json.JSONDecodeError:
                return False
        
        # Opção 1: Comparar por ID da alternativa (recomendado)
        for alt in alternatives:
            if isinstance(alt, dict) and alt.get('isCorrect') and alt.get('id'):
                if student_answer == str(alt['id']):
                    return True
        
        # Opção 2: Comparar por texto (fallback)
        # for alt in alternatives:
        #     if isinstance(alt, dict) and alt.get('isCorrect'):
        #         alt_text = alt.get('text', '').strip()
        #         if student_answer.lower() == alt_text.lower():
        #             return True
        #     elif isinstance(alt, str):
        #         if student_answer.lower() == alt.strip().lower():
        #             return True
                    
        return False
    
    @staticmethod
    def calculate_and_save_result(test_id: str, student_id: str, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Calcula e salva o resultado completo de uma avaliação para um aluno
        
        Args:
            test_id: ID do teste
            student_id: ID do aluno
            session_id: ID da sessão
            
        Returns:
            Dicionário com os resultados calculados ou None se erro
        """
        try:
            # Buscar o teste e suas questões
            test = Test.query.get(test_id)
            if not test:
                logging.error(f"Teste {test_id} não encontrado")
                return None
            
            # Buscar todas as questões do teste
            questions = Question.query.filter_by(test_id=test_id).all()
            total_questions = len(questions)
            
            if total_questions == 0:
                logging.warning(f"Nenhuma questão encontrada para o teste {test_id}")
                return None
            
            # Buscar respostas do aluno
            answers = StudentAnswer.query.filter_by(
                test_id=test_id,
                student_id=student_id
            ).all()
            
            # Calcular acertos
            correct_answers = 0
            for answer in answers:
                question = next((q for q in questions if q.id == answer.question_id), None)
                if question:
                    if question.question_type == 'multipleChoice':
                        # Verificar usando alternatives para questões de múltipla escolha
                        is_correct = EvaluationResultService.check_multiple_choice_answer(answer.answer, question.alternatives)
                        if is_correct:
                            correct_answers += 1
                    elif question.correct_answer:
                        # Para outros tipos de questão que usam correct_answer
                        if str(answer.answer).strip().lower() == str(question.correct_answer).strip().lower():
                            correct_answers += 1
            
            # Buscar nome do curso baseado no ID
            course_name = "Anos Iniciais"  # Padrão
            if test.course:
                try:
                    from app.models.educationStage import EducationStage
                    import uuid
                    course_uuid = uuid.UUID(test.course)
                    course_obj = EducationStage.query.get(course_uuid)
                    if course_obj:
                        course_name = course_obj.name
                except (ValueError, TypeError, Exception):
                    pass
            
            subject_name = test.subject_rel.name if test.subject_rel else "Outras"
            
            # Calcular resultado completo
            result = EvaluationCalculator.calculate_complete_evaluation(
                correct_answers=correct_answers,
                total_questions=total_questions,
                course_name=course_name,
                subject_name=subject_name
            )
            
            # Calcular percentual de acertos
            score_percentage = (correct_answers / total_questions * 100) if total_questions > 0 else 0
            
            # Verificar se já existe resultado para este aluno neste teste
            existing_result = EvaluationResult.query.filter_by(
                test_id=test_id,
                student_id=student_id
            ).first()
            
            if existing_result:
                # Atualizar resultado existente
                existing_result.session_id = session_id
                existing_result.correct_answers = correct_answers
                existing_result.total_questions = total_questions
                existing_result.score_percentage = score_percentage
                existing_result.grade = result['grade']
                existing_result.proficiency = result['proficiency']
                existing_result.classification = result['classification']
                existing_result.calculated_at = datetime.utcnow()
                
                evaluation_result = existing_result
            else:
                # Criar novo resultado
                evaluation_result = EvaluationResult(
                    test_id=test_id,
                    student_id=student_id,
                    session_id=session_id,
                    correct_answers=correct_answers,
                    total_questions=total_questions,
                    score_percentage=score_percentage,
                    grade=result['grade'],
                    proficiency=result['proficiency'],
                    classification=result['classification']
                )
                db.session.add(evaluation_result)
            
            db.session.commit()
            
            return {
                'id': evaluation_result.id,
                'test_id': test_id,
                'student_id': student_id,
                'session_id': session_id,
                'correct_answers': correct_answers,
                'total_questions': total_questions,
                'score_percentage': score_percentage,
                'grade': result['grade'],
                'proficiency': result['proficiency'],
                'classification': result['classification'],
                'calculated_at': evaluation_result.calculated_at.isoformat() if evaluation_result.calculated_at else None
            }
            
        except Exception as e:
            logging.error(f"Erro ao calcular resultado para aluno {student_id} no teste {test_id}: {str(e)}", exc_info=True)
            db.session.rollback()
            return None
    
    @staticmethod
    def get_evaluation_results(test_id: str) -> Dict[str, Any]:
        """
        Busca todos os resultados calculados de uma avaliação
        
        Args:
            test_id: ID do teste
            
        Returns:
            Dicionário com estatísticas agregadas
        """
        try:
            results = EvaluationResult.query.filter_by(test_id=test_id).all()
            
            if not results:
                return {
                    'total_alunos': 0,
                    'alunos_participantes': 0,
                    'alunos_pendentes': 0,
                    'alunos_ausentes': 0,
                    'media_nota': 0.0,
                    'media_proficiencia': 0.0,
                    'distribuicao_classificacao': {
                        'abaixo_do_basico': 0,
                        'basico': 0,
                        'adequado': 0,
                        'avancado': 0
                    }
                }
            
            # Calcular estatísticas
            total_alunos = len(results)
            notas = [r.grade for r in results]
            proficiencias = [r.proficiency for r in results]
            
            # Distribuição de classificação
            classificacoes = {'Abaixo do Básico': 0, 'Básico': 0, 'Adequado': 0, 'Avançado': 0}
            for result in results:
                classificacoes[result.classification] += 1
            
            return {
                'total_alunos': total_alunos,
                'alunos_participantes': total_alunos,
                'alunos_pendentes': 0,
                'alunos_ausentes': 0,
                'media_nota': round(sum(notas) / len(notas), 2) if notas else 0.0,
                'media_proficiencia': round(sum(proficiencias) / len(proficiencias), 2) if proficiencias else 0.0,
                'distribuicao_classificacao': {
                    'abaixo_do_basico': classificacoes['Abaixo do Básico'],
                    'basico': classificacoes['Básico'],
                    'adequado': classificacoes['Adequado'],
                    'avancado': classificacoes['Avançado']
                }
            }
            
        except Exception as e:
            logging.error(f"Erro ao buscar resultados da avaliação {test_id}: {str(e)}", exc_info=True)
            return {
                'total_alunos': 0,
                'alunos_participantes': 0,
                'alunos_pendentes': 0,
                'alunos_ausentes': 0,
                'media_nota': 0.0,
                'media_proficiencia': 0.0,
                'distribuicao_classificacao': {
                    'abaixo_do_basico': 0,
                    'basico': 0,
                    'adequado': 0,
                    'avancado': 0
                }
            }
    
    @staticmethod
    def get_student_result(test_id: str, student_id: str) -> Optional[Dict[str, Any]]:
        """
        Busca resultado de um aluno específico
        
        Args:
            test_id: ID do teste
            student_id: ID do aluno
            
        Returns:
            Dicionário com resultado do aluno ou None se não encontrado
        """
        try:
            result = EvaluationResult.query.filter_by(
                test_id=test_id,
                student_id=student_id
            ).first()
            
            if not result:
                return None
            
            return result.to_dict()
            
        except Exception as e:
            logging.error(f"Erro ao buscar resultado do aluno {student_id} no teste {test_id}: {str(e)}", exc_info=True)
            return None
    
    @staticmethod
    def get_all_student_results(test_id: str) -> list:
        """
        Busca resultados de todos os alunos de uma avaliação
        
        Args:
            test_id: ID do teste
            
        Returns:
            Lista com resultados de todos os alunos
        """
        try:
            results = EvaluationResult.query.filter_by(test_id=test_id).all()
            return [result.to_dict() for result in results]
            
        except Exception as e:
            logging.error(f"Erro ao buscar resultados dos alunos do teste {test_id}: {str(e)}", exc_info=True)
            return [] 