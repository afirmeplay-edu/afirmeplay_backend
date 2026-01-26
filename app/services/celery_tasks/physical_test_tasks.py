# -*- coding: utf-8 -*-
"""
Tasks Celery para geração de formulários físicos
Processa geração de PDFs de forma assíncrona para evitar timeout
"""

import logging
import tempfile
import zipfile
import os
import gc
from datetime import datetime
from typing import Dict, Any, List, Optional
from celery import Task

from app.report_analysis.celery_app import celery_app
from app import db

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name='physical_test_tasks.upload_physical_test_zip_async',
    max_retries=0,  # NÃO fazer retry - upload não é crítico
    time_limit=300,  # 5 minutos máximo
    soft_time_limit=270  # 4.5 minutos soft limit
)
def upload_physical_test_zip_async(
    self: Task,
    test_id: str,
    zip_path: str
) -> Dict[str, Any]:
    """
    Task Celery separada para upload de ZIP de provas físicas no MinIO.
    Desacoplada da geração de PDFs - não bloqueia task principal.
    
    Args:
        test_id: ID da prova
        zip_path: Caminho do arquivo ZIP no disco
    
    Returns:
        Dict com resultado do upload (ou None se falhar)
    """
    try:
        from app.services.storage.minio_service import MinIOService
        from app.models.answerSheetGabarito import AnswerSheetGabarito
        
        if not os.path.exists(zip_path):
            logger.error(f"[CELERY-UPLOAD] ZIP não encontrado: {zip_path}")
            return {'success': False, 'error': 'ZIP não encontrado'}
        
        logger.info(f"[CELERY-UPLOAD] ☁️ Enviando ZIP para MinIO: {zip_path}")
        
        minio = MinIOService()
        upload_result = minio.upload_from_path(
            bucket_name=minio.BUCKETS['PHYSICAL_TESTS'],
            object_name=f"{test_id}/all_forms.zip",
            file_path=zip_path
        )
        
        if upload_result:
            minio_url = upload_result['url']
            minio_object_name = upload_result['object_name']
            minio_bucket = upload_result['bucket']
            download_size = upload_result['size']
            
            logger.info(f"[CELERY-UPLOAD] ✅ Upload concluído: {minio_url}")
            
            # Atualizar gabarito no banco com URL do MinIO
            gabarito = AnswerSheetGabarito.query.filter_by(test_id=test_id).first()
            if gabarito:
                gabarito.minio_url = minio_url
                gabarito.minio_object_name = minio_object_name
                gabarito.minio_bucket = minio_bucket
                gabarito.zip_generated_at = datetime.utcnow()
                db.session.commit()
                logger.info(f"[CELERY-UPLOAD] ✅ Gabarito atualizado com URL do MinIO")
            
            return {
                'success': True,
                'minio_url': minio_url,
                'download_size_bytes': download_size
            }
        else:
            logger.warning(f"[CELERY-UPLOAD] ⚠️ Upload para MinIO falhou")
            return {'success': False, 'error': 'Upload falhou'}
            
    except Exception as e:
        logger.error(f"[CELERY-UPLOAD] ⚠️ Erro ao fazer upload para MinIO: {str(e)}", exc_info=True)
        # NÃO fazer retry - upload não é crítico
        return {'success': False, 'error': str(e)}


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
    force_regenerate: bool = False,
    blocks_config: Dict = None
) -> Dict[str, Any]:
    """
    Task Celery para geração ASSÍNCRONA de formulários físicos.
    
    Gera PDFs institucionais para todos os alunos de uma prova de forma assíncrona,
    evitando timeout do Gunicorn e permitindo processar turmas grandes.
    
    Args:
        test_id: ID da prova (UUID)
        force_regenerate: Se True, regenera mesmo se já existirem formulários
        blocks_config: Configuração de blocos do payload (opcional)
            {
                'use_blocks': bool,
                'num_blocks': int,
                'questions_per_block': int,
                'separate_by_subject': bool
            }
    
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
        task = generate_physical_forms_async.delay(
            test_id='abc-123',
            blocks_config={'use_blocks': True, 'num_blocks': 2, 'questions_per_block': 5}
        )
        
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
        
        # Preparar respostas corretas
        correct_answers = {}
        for i, q in enumerate(questions_data, start=1):
            correct_answers[str(i)] = q.get('correct_answer', 'A')
        
        # Extrair questions_options (alternativas por questão)
        questions_options = {}
        for i, q in enumerate(questions_data, start=1):
            alternatives = q.get('alternatives', [])
            if isinstance(alternatives, list) and len(alternatives) >= 2:
                # Converter para formato ['A', 'B', 'C', 'D']
                letters = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
                options_list = []
                for idx, alt in enumerate(alternatives):
                    if idx < len(letters):
                        options_list.append(letters[idx])
                if options_list:
                    questions_options[str(i)] = options_list
                else:
                    questions_options[str(i)] = ['A', 'B', 'C', 'D']
            else:
                questions_options[str(i)] = ['A', 'B', 'C', 'D']
        
        # ✅ USAR blocks_config recebido do payload (se fornecido)
        if blocks_config is None:
            blocks_config = {}
        
        # Validar e normalizar blocks_config
        use_blocks = blocks_config.get('use_blocks', False)
        if use_blocks:
            if 'num_blocks' not in blocks_config:
                blocks_config['num_blocks'] = 1
            if 'questions_per_block' not in blocks_config:
                blocks_config['questions_per_block'] = 12
            if 'separate_by_subject' not in blocks_config:
                blocks_config['separate_by_subject'] = False
        
        # Gerar estrutura completa (topology) se necessário
        if use_blocks and 'topology' not in blocks_config:
            logger.info(f"[CELERY] 🔨 Gerando estrutura completa de blocos...")
            from app.routes.physical_test_routes import _generate_complete_structure
            
            complete_structure = _generate_complete_structure(
                num_questions=num_questions,
                use_blocks=use_blocks,
                blocks_config=blocks_config,
                questions_options=questions_options
            )
            blocks_config['topology'] = complete_structure
            logger.info(f"[CELERY] ✅ Estrutura gerada: {blocks_config.get('num_blocks', 1)} blocos")
        
        # Buscar ou criar/atualizar gabarito
        gabarito = AnswerSheetGabarito.query.filter_by(test_id=test_id).first()
        
        if not gabarito:
            # Criar novo gabarito
            logger.info(f"[CELERY] 📋 Criando gabarito para test_id={test_id}")
            
            gabarito = AnswerSheetGabarito(
                test_id=test_id,
                class_id=class_tests[0].class_id,
                num_questions=num_questions,
                use_blocks=use_blocks,
                blocks_config=blocks_config,
                correct_answers=correct_answers,
                created_by=test.created_by
            )
            db.session.add(gabarito)
            db.session.commit()
            
            logger.info(f"[CELERY] ✅ Gabarito criado: {gabarito.id}")
        else:
            # Atualizar gabarito existente com novo blocks_config (se fornecido)
            if blocks_config:
                logger.info(f"[CELERY] 📋 Atualizando gabarito existente com novo blocks_config")
                gabarito.num_questions = num_questions
                gabarito.use_blocks = use_blocks
                gabarito.blocks_config = blocks_config
                gabarito.correct_answers = correct_answers
                db.session.commit()
                logger.info(f"[CELERY] ✅ Gabarito atualizado: {gabarito.id}")
            else:
                logger.info(f"[CELERY] ✅ Gabarito existente: {gabarito.id} (mantendo config atual)")
        
        # Preparar test_data com blocks_config atualizado
        test_data = {
            'id': str(test.id),
            'title': test.title,
            'description': test.description or '',
            'blocks_config': gabarito.blocks_config or blocks_config or {},
            'num_questions': num_questions
        }
        
        # Criar diretório temporário para ZIP (PDFs serão salvos no output_dir padrão)
        temp_dir = tempfile.mkdtemp()
        
        # Gerar formulários usando o serviço existente (processamento incremental)
        logger.info(f"[CELERY] 🔨 Iniciando geração de PDFs para {len(students_data)} alunos...")
        
        form_service = PhysicalTestFormService()
        
        # output_dir padrão será usado (/tmp/celery_pdfs/physical_tests)
        result = form_service.generate_physical_forms(
            test_id=test_id,
            test_data=test_data
            # output_dir padrão será usado automaticamente
        )
        
        if result.get('success'):
            generated_count = result.get('generated_forms', 0)
            logger.info(f"[CELERY] ✅ Formulários gerados com sucesso: {generated_count}/{len(students_data)}")
            
            # Obter arquivos gerados diretamente do resultado (não do banco)
            generated_files = result.get('generated_files', [])
            
            # Buscar formulários salvos para resposta
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
            
            # ========================================================================
            # CRIAR ZIP A PARTIR DE ARQUIVOS EM DISCO (NÃO EM MEMÓRIA)
            # ========================================================================
            zip_path = os.path.join(temp_dir, f'provas_fisicas_{test_id}.zip')
            
            logger.info(f"[CELERY] 📦 Criando ZIP a partir de arquivos em disco...")
            
            minio_url = None
            minio_object_name = None
            minio_bucket = None
            download_size = 0
            
            if generated_files:
                try:
                    # Criar ZIP usando arquivos em disco diretamente dos generated_files
                    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                        for file_info in generated_files:
                            pdf_path = file_info.get('pdf_path')
                            if pdf_path and os.path.exists(pdf_path):
                                # Usar zipfile.write() com arquivo em disco (eficiente)
                                student_name = file_info['student_name'].replace(' ', '_').replace('/', '_')
                                filename = f"prova_{student_name}_{file_info['student_id']}.pdf"
                                zf.write(pdf_path, filename)
                    
                    zip_size = os.path.getsize(zip_path)
                    logger.info(f"[CELERY] ✅ ZIP criado: {zip_size} bytes")
                    
                    # ========================================================================
                    # UPLOAD PARA MINIO (NÃO CRÍTICO - não deve derrubar a task)
                    # ========================================================================
                    logger.info(f"[CELERY] ☁️ Enviando ZIP para MinIO...")
                    try:
                        from app.services.storage.minio_service import MinIOService
                        
                        minio = MinIOService()
                        # Usar upload_from_path para não carregar ZIP inteiro em memória
                        upload_result = minio.upload_from_path(
                            bucket_name=minio.BUCKETS['PHYSICAL_TESTS'],
                            object_name=f"{test_id}/all_forms.zip",
                            file_path=zip_path
                        )
                        
                        if upload_result:
                            minio_url = upload_result['url']
                            minio_object_name = upload_result['object_name']
                            minio_bucket = upload_result['bucket']
                            download_size = upload_result['size']
                            
                            logger.info(f"[CELERY] ✅ Upload concluído: {minio_url}")
                            
                            # Atualizar gabarito no banco com URL do MinIO
                            gabarito.minio_url = minio_url
                            gabarito.minio_object_name = minio_object_name
                            gabarito.minio_bucket = minio_bucket
                            gabarito.zip_generated_at = datetime.utcnow()
                            db.session.commit()
                            logger.info(f"[CELERY] ✅ Gabarito atualizado com URL do MinIO")
                        else:
                            logger.warning(f"[CELERY] ⚠️ Upload para MinIO falhou, mas PDFs foram gerados com sucesso")
                            
                    except Exception as minio_error:
                        # 🔒 Erro de MinIO NÃO deve derrubar a task - PDFs já foram gerados
                        logger.error(f"[CELERY] ⚠️ Erro ao fazer upload para MinIO (não crítico): {str(minio_error)}", exc_info=True)
                    
                    # Liberar memória explicitamente
                    gc.collect()
                    
                finally:
                    # Limpar arquivos temporários
                    try:
                        import shutil
                        shutil.rmtree(temp_dir)
                        logger.info(f"[CELERY] 🧹 Arquivos temporários limpos")
                    except Exception as e:
                        logger.warning(f"[CELERY] ⚠️ Erro ao limpar arquivos temporários: {str(e)}")
            
            return {
                'success': True,
                'test_id': test_id,
                'test_title': test.title,
                'total_questions': num_questions,
                'total_students': len(students_data),
                'generated_forms': len(formularios_gerados),
                'gabarito_id': str(gabarito.id),
                'minio_url': minio_url,
                'download_size_bytes': download_size,
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
        
        # 🔒 NÃO fazer retry por erro de MinIO - apenas por erros críticos de geração
        # Se PDFs foram gerados mas upload falhou, não retryar
        is_minio_error = 'minio' in error_msg.lower() or 's3' in error_msg.lower() or 'ssl' in error_msg.lower()
        
        if is_minio_error:
            logger.warning(f"[CELERY] ⚠️ Erro de MinIO detectado - não retryando task (PDFs podem ter sido gerados)")
            return {
                'success': False,
                'error': error_msg,
                'test_id': test_id,
                'generated_forms': 0,
                'is_minio_error': True
            }
        
        # Retry apenas para erros críticos (não relacionados a MinIO)
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
