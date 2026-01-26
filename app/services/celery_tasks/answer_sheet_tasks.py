# -*- coding: utf-8 -*-
"""
Task Celery para geração assíncrona de cartões de resposta
"""

import logging
import tempfile
import zipfile
import os
import gc
from datetime import datetime
from typing import Dict, Any
from celery import Task

from app.report_analysis.celery_app import celery_app
from app import db

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name='answer_sheet_tasks.upload_answer_sheets_zip_async',
    max_retries=0,  # NÃO fazer retry - upload não é crítico
    time_limit=300,  # 5 minutos máximo
    soft_time_limit=270  # 4.5 minutos soft limit
)
def upload_answer_sheets_zip_async(
    self: Task,
    gabarito_id: str,
    zip_path: str
) -> Dict[str, Any]:
    """
    Task Celery separada para upload de ZIP de cartões resposta no MinIO.
    Desacoplada da geração de PDFs - não bloqueia task principal.
    
    Args:
        gabarito_id: ID do gabarito
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
            bucket_name=minio.BUCKETS['ANSWER_SHEETS'],
            object_name=f"gabaritos/{gabarito_id}/cartoes.zip",
            file_path=zip_path
        )
        
        if upload_result:
            minio_url = upload_result['url']
            minio_object_name = upload_result['object_name']
            minio_bucket = upload_result['bucket']
            download_size = upload_result['size']
            
            logger.info(f"[CELERY-UPLOAD] ✅ Upload concluído: {minio_url}")
            
            # Atualizar gabarito no banco com URL do MinIO
            gabarito = AnswerSheetGabarito.query.get(gabarito_id)
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
    name='answer_sheet_tasks.generate_answer_sheets_async',
    max_retries=2,
    default_retry_delay=60,
    time_limit=1800,  # 30 minutos máximo
    soft_time_limit=1680  # 28 minutos soft limit
)
def generate_answer_sheets_async(
    self: Task,
    class_id: str,
    num_questions: int,
    correct_answers: Dict,
    test_data: Dict,
    use_blocks: bool,
    blocks_config: Dict,
    questions_options: Dict = None,
    gabarito_id: str = None
) -> Dict[str, Any]:
    """
    Task Celery para geração ASSÍNCRONA de cartões de resposta.
    
    Gera PDFs de cartões resposta para todos os alunos de uma turma de forma assíncrona,
    evitando timeout do Gunicorn e permitindo processar turmas grandes.
    
    Args:
        class_id: ID da turma
        num_questions: Quantidade de questões
        correct_answers: Dict com respostas corretas
        test_data: Dados da prova (title, municipality, etc.)
        use_blocks: Se usa blocos
        blocks_config: Configuração de blocos
        questions_options: Alternativas por questão (opcional)
        gabarito_id: ID do gabarito (opcional)
    
    Returns:
        Dict com status e informações dos cartões gerados
    """
    try:
        logger.info(f"[CELERY] 🚀 Iniciando geração de cartões de resposta para class_id={class_id}")
        
        from app.models.student import Student
        from app.models.studentClass import Class
        from app.services.cartao_resposta.answer_sheet_generator import AnswerSheetGenerator
        
        # Buscar turma
        class_obj = Class.query.get(class_id)
        if not class_obj:
            raise ValueError(f"Turma {class_id} não encontrada")
        
        logger.info(f"[CELERY] ✅ Turma encontrada: {class_obj.name}")
        
        # Buscar alunos da turma
        students = Student.query.filter_by(class_id=class_id).all()
        if not students:
            raise ValueError(f"Nenhum aluno encontrado na turma {class_id}")
        
        logger.info(f"[CELERY] 📊 Total de alunos: {len(students)}")
        logger.info(f"[CELERY] 📝 Total de questões: {num_questions}")
        
        # Criar diretório temporário para ZIP (PDFs serão salvos no output_dir padrão)
        temp_dir = tempfile.mkdtemp()
        
        # Gerar cartões usando processamento incremental (salva em disco no output_dir padrão)
        logger.info(f"[CELERY] 🔨 Iniciando geração de PDFs para {len(students)} alunos...")
        
        generator = AnswerSheetGenerator()
        
        # output_dir padrão será usado (/tmp/celery_pdfs/answer_sheets)
        generated_files = generator.generate_answer_sheets(
            class_id=class_id,
            test_data=test_data,
            num_questions=num_questions,
            use_blocks=use_blocks,
            blocks_config=blocks_config,
            correct_answers=correct_answers,
            gabarito_id=gabarito_id,
            questions_options=questions_options
            # output_dir padrão será usado automaticamente
        )
        
        if not generated_files:
            raise ValueError("Nenhum cartão resposta foi gerado")
        
        logger.info(f"[CELERY] ✅ Cartões gerados com sucesso: {len(generated_files)}/{len(students)}")
        
        # ========================================================================
        # CRIAR ZIP A PARTIR DE ARQUIVOS EM DISCO (NÃO EM MEMÓRIA)
        # ========================================================================
        zip_path = os.path.join(temp_dir, f'cartoes_{gabarito_id}.zip')
        
        logger.info(f"[CELERY] 📦 Criando ZIP a partir de arquivos em disco...")
        
        # Criar ZIP usando arquivos em disco (não bytes em memória)
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for file_info in generated_files:
                pdf_path = file_info.get('pdf_path')
                if pdf_path and os.path.exists(pdf_path):
                    # Usar zipfile.write() com arquivo em disco (eficiente)
                    student_name = file_info['student_name'].replace(' ', '_').replace('/', '_')
                    filename = f"cartao_{student_name}_{file_info['student_id']}.pdf"
                    zf.write(pdf_path, filename)
        
        zip_size = os.path.getsize(zip_path)
        logger.info(f"[CELERY] ✅ ZIP criado: {zip_size} bytes")
        
        # ========================================================================
        # UPLOAD PARA MINIO (NÃO CRÍTICO - não deve derrubar a task)
        # ========================================================================
        minio_url = None
        minio_object_name = None
        minio_bucket = None
        download_size = 0
        
        # Upload usando arquivo em disco (streaming, não carrega tudo em memória)
        logger.info(f"[CELERY] ☁️ Enviando ZIP para MinIO...")
        try:
            from app.services.storage.minio_service import MinIOService
            
            minio = MinIOService()
            # Usar upload_from_path para não carregar ZIP inteiro em memória
            upload_result = minio.upload_from_path(
                bucket_name=minio.BUCKETS['ANSWER_SHEETS'],
                object_name=f"gabaritos/{gabarito_id}/cartoes.zip",
                file_path=zip_path
            )
            
            if upload_result:
                minio_url = upload_result['url']
                minio_object_name = upload_result['object_name']
                minio_bucket = upload_result['bucket']
                download_size = upload_result['size']
                
                logger.info(f"[CELERY] ✅ Upload concluído: {minio_url}")
                
                # Atualizar gabarito no banco com URL do MinIO
                from app.models.answerSheetGabarito import AnswerSheetGabarito
                
                gabarito = AnswerSheetGabarito.query.get(gabarito_id)
                if gabarito:
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
        
        # Limpar arquivos temporários
        try:
            import shutil
            shutil.rmtree(temp_dir)
            logger.info(f"[CELERY] 🧹 Arquivos temporários limpos")
        except Exception as e:
            logger.warning(f"[CELERY] ⚠️ Erro ao limpar arquivos temporários: {str(e)}")
        
        # Liberar memória explicitamente
        gc.collect()
        
        # Preparar resposta (sem incluir pdf_data - PDFs foram salvos em disco e enviados ao MinIO)
        cartoes_gerados = []
        for file_info in generated_files:
            cartoes_gerados.append({
                'student_id': str(file_info['student_id']),
                'student_name': file_info['student_name'],
                'has_pdf': True  # PDF foi gerado (salvo em disco e enviado ao MinIO)
            })
        
        return {
            'success': True,
            'class_id': class_id,
            'class_name': class_obj.name,
            'num_questions': num_questions,
            'total_students': len(students),
            'generated_sheets': len(generated_files),
            'gabarito_id': gabarito_id,
            'minio_url': minio_url,  # Pode ser None se upload falhar
            'download_size_bytes': download_size,
            'sheets': cartoes_gerados
        }
    
    except Exception as e:
        logger.error(f"[CELERY] ❌ Erro ao gerar cartões de resposta: {str(e)}", exc_info=True)
        
        # 🔒 NÃO fazer retry por erro de MinIO - apenas por erros críticos de geração
        # Se PDFs foram gerados mas upload falhou, não retryar
        is_minio_error = 'minio' in str(e).lower() or 's3' in str(e).lower() or 'ssl' in str(e).lower()
        
        if is_minio_error:
            logger.warning(f"[CELERY] ⚠️ Erro de MinIO detectado - não retryando task (PDFs podem ter sido gerados)")
            return {
                'success': False,
                'error': str(e),
                'class_id': class_id,
                'is_minio_error': True
            }
        
        # Retry apenas para erros críticos (não relacionados a MinIO)
        if self.request.retries < self.max_retries:
            logger.info(f"[CELERY] 🔄 Tentando novamente (retry {self.request.retries + 1}/{self.max_retries})...")
            raise self.retry(exc=e)
        
        return {
            'success': False,
            'error': str(e),
            'class_id': class_id
        }
