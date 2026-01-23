# -*- coding: utf-8 -*-
"""
Task Celery para geração assíncrona de cartões de resposta
"""

import logging
import tempfile
import zipfile
import os
from datetime import datetime
from typing import Dict, Any
from celery import Task

from app.report_analysis.celery_app import celery_app
from app import db

logger = logging.getLogger(__name__)


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
        
        # Gerar cartões usando o serviço existente
        logger.info(f"[CELERY] 🔨 Iniciando geração de PDFs para {len(students)} alunos...")
        
        generator = AnswerSheetGenerator()
        
        generated_files = generator.generate_answer_sheets(
            class_id=class_id,
            test_data=test_data,
            num_questions=num_questions,
            use_blocks=use_blocks,
            blocks_config=blocks_config,
            correct_answers=correct_answers,
            gabarito_id=gabarito_id,
            questions_options=questions_options
        )
        
        if not generated_files:
            raise ValueError("Nenhum cartão resposta foi gerado")
        
        logger.info(f"[CELERY] ✅ Cartões gerados com sucesso: {len(generated_files)}/{len(students)}")
        
        # ========================================================================
        # UPLOAD PARA MINIO
        # ========================================================================
        logger.info(f"[CELERY] 📦 Criando ZIP para upload no MinIO...")
        
        # Criar ZIP temporário
        temp_dir = tempfile.mkdtemp()
        zip_path = os.path.join(temp_dir, f'cartoes_{gabarito_id}.zip')
        
        try:
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for file_info in generated_files:
                    if file_info.get('pdf_data'):
                        student_name = file_info['student_name'].replace(' ', '_')
                        filename = f"cartao_{student_name}_{file_info['student_id']}.pdf"
                        zf.writestr(filename, file_info['pdf_data'])
            
            logger.info(f"[CELERY] ✅ ZIP criado: {os.path.getsize(zip_path)} bytes")
            
            # Ler ZIP como bytes
            with open(zip_path, 'rb') as f:
                zip_data = f.read()
            
            # Upload para MinIO
            logger.info(f"[CELERY] ☁️ Enviando ZIP para MinIO...")
            from app.services.storage.minio_service import MinIOService
            
            minio = MinIOService()
            upload_result = minio.upload_answer_sheet_zip(
                gabarito_id=gabarito_id,
                zip_data=zip_data
            )
            
            logger.info(f"[CELERY] ✅ Upload concluído: {upload_result['url']}")
            
            # Atualizar gabarito no banco com URL do MinIO
            from app.models.answerSheetGabarito import AnswerSheetGabarito
            
            gabarito = AnswerSheetGabarito.query.get(gabarito_id)
            if gabarito:
                gabarito.minio_url = upload_result['url']
                gabarito.minio_object_name = upload_result['object_name']
                gabarito.minio_bucket = upload_result['bucket']
                gabarito.zip_generated_at = datetime.utcnow()
                db.session.commit()
                logger.info(f"[CELERY] ✅ Gabarito atualizado com URL do MinIO")
            
        finally:
            # Limpar arquivos temporários
            if os.path.exists(zip_path):
                os.remove(zip_path)
            if os.path.exists(temp_dir):
                os.rmdir(temp_dir)
            logger.info(f"[CELERY] 🧹 Arquivos temporários limpos")
        
        # Preparar resposta
        cartoes_gerados = []
        for file_info in generated_files:
            cartoes_gerados.append({
                'student_id': str(file_info['student_id']),
                'student_name': file_info['student_name'],
                'has_pdf': True  # PDF foi gerado e está no MinIO
            })
        
        return {
            'success': True,
            'class_id': class_id,
            'class_name': class_obj.name,
            'num_questions': num_questions,
            'total_students': len(students),
            'generated_sheets': len(generated_files),
            'gabarito_id': gabarito_id,
            'minio_url': upload_result['url'],
            'download_size_bytes': upload_result['size'],
            'sheets': cartoes_gerados
        }
    
    except Exception as e:
        logger.error(f"[CELERY] ❌ Erro ao gerar cartões de resposta: {str(e)}", exc_info=True)
        
        # Retry se não atingiu o máximo
        if self.request.retries < self.max_retries:
            logger.info(f"[CELERY] 🔄 Tentando novamente (retry {self.request.retries + 1}/{self.max_retries})...")
            raise self.retry(exc=e)
        
        return {
            'success': False,
            'error': str(e),
            'class_id': class_id
        }
