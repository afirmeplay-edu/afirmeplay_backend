# -*- coding: utf-8 -*-
"""
Tasks Celery para recálculo de resultados de avaliações
Processa recálculo quando gabaritos são corrigidos
"""

import logging
from datetime import datetime
from typing import Dict, Any, List
from celery import Task

from app.report_analysis.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name='evaluation_recalculation_tasks.recalculate_results_after_answer_correction',
    max_retries=3,
    time_limit=600,  # 10 minutos máximo
    soft_time_limit=540  # 9 minutos soft limit
)
def recalculate_results_after_answer_correction(
    self: Task,
    question_id: str,
    old_answer: str,
    new_answer: str,
    modified_by: str
) -> Dict[str, Any]:
    """
    Task Celery para recalcular resultados após correção de gabarito.
    
    Quando um professor corrige o gabarito de uma questão (ex: de C para A),
    esta task é disparada para recalcular todos os resultados dos alunos
    que responderam provas contendo essa questão.
    
    Args:
        question_id: ID da questão que teve o gabarito corrigido
        old_answer: Resposta correta antiga (ex: "C")
        new_answer: Resposta correta nova (ex: "A")
        modified_by: ID do usuário que fez a alteração
    
    Returns:
        Dict com estatísticas do recálculo
    """
    task_id = self.request.id
    start_time = datetime.utcnow()
    
    logger.info(
        f"[TASK-{task_id}] Iniciando recálculo de resultados\n"
        f"  Question ID: {question_id}\n"
        f"  Gabarito: {old_answer} → {new_answer}\n"
        f"  Modificado por: {modified_by}"
    )
    
    try:
        from app.models.question import Question
        from app.models.testQuestion import TestQuestion
        from app.models.studentAnswer import StudentAnswer
        from app.models.evaluationResult import EvaluationResult
        from app.services.evaluation_result_service import EvaluationResultService
        
        # 1. Buscar a questão
        question = Question.query.get(question_id)
        if not question:
            logger.error(f"[TASK-{task_id}] Questão {question_id} não encontrada")
            return {
                'success': False,
                'error': 'Questão não encontrada',
                'question_id': question_id
            }
        
        # 2. Buscar todas as provas que usam essa questão
        test_questions = TestQuestion.query.filter_by(question_id=question_id).all()
        test_ids = [tq.test_id for tq in test_questions]
        
        if not test_ids:
            logger.info(f"[TASK-{task_id}] Nenhuma prova usa a questão {question_id}")
            return {
                'success': True,
                'tests_affected': 0,
                'students_recalculated': 0,
                'message': 'Nenhuma prova afetada'
            }
        
        logger.info(f"[TASK-{task_id}] {len(test_ids)} prova(s) afetada(s)")
        
        # 3. Para cada prova, buscar alunos que responderam
        students_recalculated = 0
        tests_affected = 0
        recalculation_errors = []
        
        for test_id in test_ids:
            try:
                # Buscar respostas de alunos para essa prova
                student_answers = StudentAnswer.query.filter_by(
                    test_id=test_id,
                    question_id=question_id
                ).all()
                
                if not student_answers:
                    logger.info(f"[TASK-{task_id}] Nenhum aluno respondeu a questão na prova {test_id}")
                    continue
                
                # IDs únicos de alunos
                student_ids = list(set([sa.student_id for sa in student_answers]))
                
                logger.info(
                    f"[TASK-{task_id}] Prova {test_id}: "
                    f"{len(student_ids)} aluno(s) a recalcular"
                )
                
                # 4. Recalcular resultado de cada aluno
                for student_id in student_ids:
                    try:
                        # Buscar o resultado existente para pegar o session_id
                        existing_result = EvaluationResult.query.filter_by(
                            test_id=test_id,
                            student_id=student_id
                        ).first()
                        
                        if not existing_result:
                            logger.warning(
                                f"[TASK-{task_id}] Resultado não encontrado para "
                                f"aluno {student_id} na prova {test_id}"
                            )
                            continue
                        
                        # Recalcular usando o serviço existente
                        result = EvaluationResultService.calculate_and_save_result(
                            test_id=test_id,
                            student_id=student_id,
                            session_id=existing_result.session_id
                        )
                        
                        if result:
                            students_recalculated += 1
                            logger.debug(
                                f"[TASK-{task_id}] Recalculado: aluno {student_id}, "
                                f"nova nota: {result.get('grade', 'N/A')}"
                            )
                        else:
                            recalculation_errors.append({
                                'test_id': test_id,
                                'student_id': student_id,
                                'error': 'Serviço retornou None'
                            })
                            
                    except Exception as e:
                        logger.error(
                            f"[TASK-{task_id}] Erro ao recalcular aluno {student_id}: {str(e)}",
                            exc_info=True
                        )
                        recalculation_errors.append({
                            'test_id': test_id,
                            'student_id': student_id,
                            'error': str(e)
                        })
                
                tests_affected += 1
                
            except Exception as e:
                logger.error(
                    f"[TASK-{task_id}] Erro ao processar prova {test_id}: {str(e)}",
                    exc_info=True
                )
                recalculation_errors.append({
                    'test_id': test_id,
                    'error': str(e)
                })
        
        # Calcular tempo de execução
        end_time = datetime.utcnow()
        duration_seconds = (end_time - start_time).total_seconds()
        
        logger.info(
            f"[TASK-{task_id}] Recálculo concluído\n"
            f"  Provas afetadas: {tests_affected}\n"
            f"  Alunos recalculados: {students_recalculated}\n"
            f"  Erros: {len(recalculation_errors)}\n"
            f"  Duração: {duration_seconds:.2f}s"
        )
        
        return {
            'success': True,
            'task_id': task_id,
            'question_id': question_id,
            'old_answer': old_answer,
            'new_answer': new_answer,
            'tests_affected': tests_affected,
            'students_recalculated': students_recalculated,
            'errors': recalculation_errors,
            'duration_seconds': duration_seconds,
            'started_at': start_time.isoformat(),
            'completed_at': end_time.isoformat()
        }
        
    except Exception as e:
        logger.error(
            f"[TASK-{task_id}] Erro fatal no recálculo: {str(e)}",
            exc_info=True
        )
        return {
            'success': False,
            'task_id': task_id,
            'question_id': question_id,
            'error': str(e),
            'error_type': type(e).__name__
        }


def trigger_recalculation_sync(
    question_id: str,
    old_answer: str,  # pylint: disable=unused-argument
    new_answer: str,  # pylint: disable=unused-argument
    modified_by: str,  # pylint: disable=unused-argument
    student_ids: List[str]
) -> Dict[str, Any]:
    """
    Recálculo síncrono para poucos alunos (< 20).
    Executa imediatamente sem usar Celery.
    
    Args:
        question_id: ID da questão
        old_answer: Resposta antiga
        new_answer: Resposta nova
        modified_by: ID do usuário
        student_ids: Lista de IDs de alunos a recalcular
    
    Returns:
        Dict com estatísticas
    """
    logger.info(
        f"[SYNC] Recálculo síncrono iniciado\n"
        f"  Question ID: {question_id}\n"
        f"  Alunos: {len(student_ids)}"
    )
    
    try:
        from app.models.testQuestion import TestQuestion
        from app.models.evaluationResult import EvaluationResult
        from app.services.evaluation_result_service import EvaluationResultService
        
        # Buscar provas que usam essa questão
        test_questions = TestQuestion.query.filter_by(question_id=question_id).all()
        test_ids = [tq.test_id for tq in test_questions]
        
        if not test_ids:
            return {
                'success': True,
                'tests_affected': 0,
                'students_recalculated': 0,
                'message': 'Nenhuma prova afetada'
            }
        
        students_recalculated = 0
        tests_affected = 0
        errors = []
        
        for test_id in test_ids:
            # Buscar resultados existentes para os alunos nesta prova
            results = EvaluationResult.query.filter(
                EvaluationResult.test_id == test_id,
                EvaluationResult.student_id.in_(student_ids)
            ).all()
            
            if not results:
                continue
            
            tests_affected += 1
            
            for result in results:
                try:
                    # Recalcular
                    new_result = EvaluationResultService.calculate_and_save_result(
                        test_id=test_id,
                        student_id=result.student_id,
                        session_id=result.session_id
                    )
                    
                    if new_result:
                        students_recalculated += 1
                        
                except Exception as e:
                    logger.error(f"[SYNC] Erro ao recalcular: {str(e)}", exc_info=True)
                    errors.append({
                        'test_id': test_id,
                        'student_id': result.student_id,
                        'error': str(e)
                    })
        
        logger.info(
            f"[SYNC] Recálculo síncrono concluído\n"
            f"  Provas: {tests_affected}\n"
            f"  Alunos: {students_recalculated}"
        )
        
        return {
            'success': True,
            'sync': True,
            'question_id': question_id,
            'tests_affected': tests_affected,
            'students_recalculated': students_recalculated,
            'errors': errors
        }
        
    except Exception as e:
        logger.error(f"[SYNC] Erro fatal: {str(e)}", exc_info=True)
        return {
            'success': False,
            'sync': True,
            'error': str(e)
        }
