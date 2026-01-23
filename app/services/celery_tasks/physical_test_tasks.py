# -*- coding: utf-8 -*-
"""
Tasks Celery para geração de formulários físicos
Processa geração de PDFs de forma assíncrona para evitar timeout
"""

import logging
import tempfile
from typing import Dict, Any, List, Optional
from celery import Task

from app.report_analysis.celery_app import celery_app
from app import db

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name='physical_test_tasks.generate_physical_forms_async',
    max_retries=2,  # Retry 2x se falhar
    default_retry_delay=60,  # 1 minuto entre retries
    time_limit=900,  # 15 minutos máximo (para turmas muito grandes)
    soft_time_limit=840  # 14 minutos soft limit
)
def generate_physical_forms_async(
    self: Task,
    test_id: str,
    force_regenerate: bool = False
) -> Dict[str, Any]:
    """
    Task Celery para geração ASSÍNCRONA de formulários físicos.
    
    Gera PDFs institucionais para todos os alunos de uma prova de forma assíncrona,
    evitando timeout do Gunicorn e permitindo processar turmas grandes.
    
    Args:
        test_id: ID da prova (UUID)
        force_regenerate: Se True, regenera mesmo se já existirem formulários
    
    Returns:
        Dict com resultado da geração:
        {
            'success': bool,
            'test_id': str,
            'test_title': str,
            'generated_forms': int,
            'total_students': int,
            'total_questions': int,
            'gabarito_id': str,
            'forms': List[Dict]  # Lista de formulários gerados
        }
    
    Raises:
        Exception: Se ocorrer erro na geração (com retry automático)
    
    Example:
        # Disparar task
        task = generate_physical_forms_async.delay(test_id='abc-123')
        
        # Verificar status
        from celery.result import AsyncResult
        result = AsyncResult(task.id)
        if result.ready():
            data = result.get()
    """
    try:
        logger.info(f"[CELERY] 🚀 Iniciando geração de formulários físicos para test_id={test_id}")
        
        # Imports locais para evitar problemas de circular import
        from app.models.test import Test
        from app.models.student import Student
        from app.models.classTest import ClassTest
        from app.models.question import Question
        from app.models.testQuestion import TestQuestion
        from app.models.answerSheetGabarito import AnswerSheetGabarito
        from app.services.physical_test_form_service import PhysicalTestFormService
        
        # Verificar se a prova existe
        test = Test.query.get(test_id)
        if not test:
            error_msg = f"Prova {test_id} não encontrada"
            logger.error(f"[CELERY] ❌ {error_msg}")
            raise ValueError(error_msg)
        
        logger.info(f"[CELERY] ✅ Prova encontrada: {test.title}")
        
        # Buscar ClassTest (aplicações da prova)
        class_tests = ClassTest.query.filter_by(test_id=test_id).all()
        
        if not class_tests:
            error_msg = f"A prova {test.title} não foi aplicada em nenhuma turma"
            logger.warning(f"[CELERY] ⚠️ {error_msg}")
            return {
                'success': False,
                'error': error_msg,
                'test_id': test_id,
                'test_title': test.title,
                'generated_forms': 0
            }
        
        logger.info(f"[CELERY] 📊 Prova aplicada em {len(class_tests)} turma(s)")
        
        # Coletar todos os alunos de todas as turmas
        all_students = []
        class_ids = [ct.class_id for ct in class_tests]
        
        students = Student.query.filter(
            Student.class_id.in_(class_ids)
        ).order_by(Student.name).all()
        
        students_data = [
            {
                'id': str(s.id),
                'nome': s.name
            }
            for s in students
        ]
        
        logger.info(f"[CELERY] 📊 Total de alunos ativos: {len(students_data)}")
        
        if not students_data:
            error_msg = "Nenhum aluno ativo encontrado nas turmas"
            logger.warning(f"[CELERY] ⚠️ {error_msg}")
            return {
                'success': False,
                'error': error_msg,
                'test_id': test_id,
                'test_title': test.title,
                'generated_forms': 0
            }
        
        # Buscar questões da prova
        test_questions = TestQuestion.query.filter_by(
            test_id=test_id
        ).order_by(TestQuestion.order).all()
        
        questions_data = []
        for tq in test_questions:
            question = Question.query.get(tq.question_id)
            if question:
                questions_data.append({
                    'id': str(question.id),
                    'text': question.text,
                    'formatted_text': question.formatted_text,
                    'title': question.title,
                    'alternatives': question.alternatives or [],
                    'correct_answer': question.correct_answer,
                    'order': tq.order
                })
        
        num_questions = len(questions_data)
        logger.info(f"[CELERY] 📝 Total de questões: {num_questions}")
        
        # Buscar ou criar gabarito
        gabarito = AnswerSheetGabarito.query.filter_by(test_id=test_id).first()
        
        if not gabarito:
            # Criar gabarito
            logger.info(f"[CELERY] 📋 Criando gabarito para test_id={test_id}")
            
            # Preparar respostas corretas
            correct_answers = {}
            for i, q in enumerate(questions_data, start=1):
                correct_answers[str(i)] = q.get('correct_answer', 'A')
            
            # Configuração de blocos padrão (4 blocos de 26 questões)
            blocks_config = {
                'use_blocks': True,
                'num_blocks': 4,
                'questions_per_block': 26,
                'topology': {
                    'blocks': []
                }
            }
            
            # Criar topologia
            for block_num in range(1, 5):
                start_q = (block_num - 1) * 26 + 1
                end_q = min(block_num * 26, num_questions)
                
                block_questions = []
                for q_num in range(start_q, end_q + 1):
                    block_questions.append({
                        'q': q_num,
                        'alternatives': ['A', 'B', 'C', 'D']
                    })
                
                blocks_config['topology']['blocks'].append({
                    'block_id': block_num,
                    'questions': block_questions
                })
            
            gabarito = AnswerSheetGabarito(
                test_id=test_id,
                class_id=class_tests[0].class_id,
                num_questions=num_questions,
                use_blocks=True,
                blocks_config=blocks_config,
                correct_answers=correct_answers,
                created_by=test.created_by
            )
            db.session.add(gabarito)
            db.session.commit()
            
            logger.info(f"[CELERY] ✅ Gabarito criado: {gabarito.id}")
        else:
            logger.info(f"[CELERY] ✅ Gabarito existente: {gabarito.id}")
        
        # Preparar test_data
        test_data = {
            'id': str(test.id),
            'title': test.title,
            'description': test.description or '',
            'blocks_config': gabarito.blocks_config or {},
            'num_questions': num_questions
        }
        
        # Gerar formulários usando o serviço existente
        logger.info(f"[CELERY] 🔨 Iniciando geração de PDFs para {len(students_data)} alunos...")
        
        form_service = PhysicalTestFormService()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            result = form_service.generate_physical_forms(
                test_id=test_id,
                output_dir=temp_dir,
                test_data=test_data
            )
        
        if result.get('success'):
            generated_count = result.get('generated_forms', 0)
            logger.info(f"[CELERY] ✅ Formulários gerados com sucesso: {generated_count}/{len(students_data)}")
            
            # Buscar formulários salvos
            forms = form_service.get_physical_forms_by_test(test_id)
            formularios_gerados = []
            
            for form in forms:
                formularios_gerados.append({
                    'student_id': form['student_id'],
                    'student_name': form['student_name'],
                    'form_id': form['id'],
                    'form_type': form['form_type'],
                    'created_at': form['generated_at']
                })
            
            return {
                'success': True,
                'test_id': test_id,
                'test_title': test.title,
                'total_questions': num_questions,
                'total_students': len(students_data),
                'generated_forms': len(formularios_gerados),
                'gabarito_id': str(gabarito.id),
                'forms': formularios_gerados,
                'message': f'Formulários gerados com sucesso para {len(formularios_gerados)} alunos'
            }
        else:
            error_msg = result.get('error', 'Erro desconhecido ao gerar formulários')
            logger.error(f"[CELERY] ❌ Erro na geração: {error_msg}")
            raise Exception(error_msg)
    
    except Exception as e:
        error_msg = str(e)
        logger.error(f"[CELERY] ❌ Erro ao gerar formulários físicos: {error_msg}", exc_info=True)
        
        # Retry automático se não excedeu max_retries
        if self.request.retries < self.max_retries:
            logger.info(f"[CELERY] 🔄 Tentando novamente (retry {self.request.retries + 1}/{self.max_retries})...")
            raise self.retry(exc=e)
        else:
            # Retornar erro após esgotar retries
            return {
                'success': False,
                'error': error_msg,
                'test_id': test_id,
                'generated_forms': 0
            }
