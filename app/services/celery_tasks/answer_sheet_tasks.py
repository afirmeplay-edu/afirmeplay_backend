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
from typing import Dict, Any, List
from celery import Task

from app.report_analysis.celery_app import celery_app
from app.services.progress_store import update_job, get_job
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


# ============================================================================
# FUNÇÕES AUXILIARES PARA CONSOLIDAÇÃO
# ============================================================================

def get_job_for_class(class_id: str) -> Dict:
    """
    Busca job que contém uma classe específica
    """
    try:
        from app.services.progress_store import get_all_active_jobs
        
        jobs = get_all_active_jobs()
        for job in jobs:
            tasks = job.get('tasks', [])
            for task in tasks:
                if task.get('class_id') == str(class_id):
                    return job
        return None
    except Exception as e:
        logger.error(f"Erro ao buscar job para classe {class_id}: {str(e)}")
        return None


def should_consolidate_job(job_id: str) -> bool:
    """
    Verifica se todas as tasks de um job estão completas e se deve consolidar
    """
    try:
        job = get_job(job_id)
        if not job:
            return False
        
        tasks = job.get('tasks', [])
        if not tasks:
            return False
        
        # Verificar se todas as tasks estão completas
        completed_count = sum(1 for task in tasks if task.get('status') == 'completed')
        total_count = len(tasks)
        
        logger.info(f"[CONSOLIDATE-CHECK] Job {job_id}: {completed_count}/{total_count} tasks completas")
        
        # Só consolida se todas estão completas E temos mais de 1 task
        return completed_count == total_count and total_count > 1
        
    except Exception as e:
        logger.error(f"Erro ao verificar consolidação para job {job_id}: {str(e)}")
        return False


# ============================================================================
# Função consolidate_answer_sheets_to_zip (versão antiga) REMOVIDA
# A versão correta está mais abaixo no arquivo (linha ~566)
# ============================================================================


@celery_app.task(
    bind=True,
    name='answer_sheet_tasks.generate_answer_sheets_batch_async',
    max_retries=2,
    default_retry_delay=60,
    time_limit=3600,  # 60 minutos máximo (aumentado para suportar múltiplas turmas)
    soft_time_limit=3480  # 58 minutos soft limit
)
def generate_answer_sheets_batch_async(
    self: Task,
    gabarito_ids: List[str],
    num_questions: int,
    correct_answers: Dict,
    test_data: Dict,
    use_blocks: bool,
    blocks_config: Dict,
    questions_options: Dict = None,
    batch_id: str = None,
    scope: str = 'class'
) -> Dict[str, Any]:
    """
    Task Celery para geração ASSÍNCRONA de cartões de resposta em batch.
    
    Gera 1 PDF por turma (cada PDF com múltiplas páginas, 1 por aluno).
    Suporta geração para 1 turma, múltiplas turmas de uma série ou escola inteira.
    
    Args:
        gabarito_ids: Lista de IDs dos gabaritos (1 por turma)
        num_questions: Quantidade de questões
        correct_answers: Dict com respostas corretas
        test_data: Dados da prova (title, municipality, etc.)
        use_blocks: Se usa blocos
        blocks_config: Configuração de blocos
        questions_options: Alternativas por questão (opcional)
        batch_id: ID do batch (opcional, para agrupar múltiplas turmas)
        scope: Escopo da geração ('class', 'grade' ou 'school')
    
    Returns:
        Dict com status e informações dos cartões gerados
    """
    try:
        logger.info(f"[CELERY-BATCH] 🚀 Iniciando geração de cartões - Escopo: {scope}, Gabaritos: {len(gabarito_ids)}")
        
        from app.models.studentClass import Class
        from app.models.answerSheetGabarito import AnswerSheetGabarito
        from app.models.grades import Grade
        from app.services.cartao_resposta.answer_sheet_generator import AnswerSheetGenerator
        
        # Buscar todos os gabaritos
        gabaritos = []
        for gab_id in gabarito_ids:
            gab = AnswerSheetGabarito.query.get(gab_id)
            if gab:
                gabaritos.append(gab)
            else:
                logger.warning(f"[CELERY-BATCH] ⚠️ Gabarito {gab_id} não encontrado")
        
        if not gabaritos:
            raise ValueError("Nenhum gabarito encontrado")
        
        logger.info(f"[CELERY-BATCH] ✅ {len(gabaritos)} gabarito(s) encontrado(s)")
        logger.info(f"[CELERY-BATCH] 📝 Total de questões: {num_questions}")
        
        # Criar diretório temporário para ZIP
        temp_dir = tempfile.mkdtemp()
        output_dir = os.path.join(temp_dir, 'pdfs')
        os.makedirs(output_dir, exist_ok=True)
        
        generator = AnswerSheetGenerator()
        generated_pdfs = []
        total_students = 0
        
        # ========================================================================
        # ✅ NOVO: Gerar 1 PDF POR TURMA (cada PDF com múltiplas páginas)
        # ========================================================================
        for idx, gabarito in enumerate(gabaritos, 1):
            try:
                logger.info(f"[CELERY-BATCH] 🔨 Gerando PDF {idx}/{len(gabaritos)} para turma {gabarito.class_id}...")
                
                # Buscar turma
                class_obj = Class.query.get(gabarito.class_id)
                if not class_obj:
                    logger.error(f"[CELERY-BATCH] ❌ Turma {gabarito.class_id} não encontrada")
                    continue
                
                # Gerar 1 PDF único para a turma (múltiplas páginas)
                pdf_result = generator.generate_answer_sheet_for_class(
                    class_id=str(gabarito.class_id),
                    test_data=test_data,
                    num_questions=num_questions,
                    use_blocks=use_blocks,
                    blocks_config=blocks_config,
                    correct_answers=correct_answers,
                    gabarito_id=str(gabarito.id),
                    questions_options=questions_options,
                    output_dir=output_dir
                )
                
                # Turma sem alunos: generator retorna None — pular sem erro
                if pdf_result is None:
                    logger.warning(f"[CELERY-BATCH] ⚠️ Turma {class_obj.name} sem alunos — pulando")
                    continue
                
                if pdf_result and pdf_result.get('pdf_path'):
                    generated_pdfs.append({
                        'gabarito_id': str(gabarito.id),
                        'class_id': str(gabarito.class_id),
                        'pdf_path': pdf_result['pdf_path'],
                        'filename': pdf_result['filename'],
                        'grade_name': pdf_result.get('grade_name', gabarito.grade_name),
                        'class_name': pdf_result.get('class_name', class_obj.name),
                        'total_students': pdf_result['total_students'],
                        'total_pages': pdf_result['total_pages']
                    })
                    total_students += pdf_result['total_students']
                    logger.info(f"[CELERY-BATCH] ✅ PDF gerado: {pdf_result['filename']} ({pdf_result['total_students']} páginas)")
                else:
                    logger.warning(f"[CELERY-BATCH] ⚠️ Falha ao gerar PDF para gabarito {gabarito.id}")
                
            except Exception as e:
                logger.error(f"[CELERY-BATCH] ❌ Erro ao gerar PDF para gabarito {gabarito.id}: {str(e)}", exc_info=True)
                continue
        
        if not generated_pdfs:
            raise ValueError("Nenhum PDF foi gerado")
        
        logger.info(f"[CELERY-BATCH] ✅ PDFs gerados: {len(generated_pdfs)}, Total de alunos: {total_students}")
        
        # ========================================================================
        # ✅ NOVO: CRIAR ZIP COM ESTRUTURA HIERÁRQUICA
        # ========================================================================
        zip_filename = f'cartoes_{batch_id or gabarito_ids[0]}.zip'
        zip_path = os.path.join(temp_dir, zip_filename)
        
        logger.info(f"[CELERY-BATCH] 📦 Criando ZIP com estrutura hierárquica...")
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            if scope == 'school':
                # ✅ ESCOPO ESCOLA: Organizar por série (pastas por série)
                by_grade = {}
                for pdf_info in generated_pdfs:
                    grade = pdf_info.get('grade_name', 'Sem Serie')
                    if grade not in by_grade:
                        by_grade[grade] = []
                    by_grade[grade].append(pdf_info)
                
                for grade_name, pdfs in by_grade.items():
                    for pdf_info in pdfs:
                        if os.path.exists(pdf_info['pdf_path']):
                            # Path: "Serie/Arquivo.pdf"
                            zip_internal_path = f"{grade_name}/{pdf_info['filename']}"
                            zf.write(pdf_info['pdf_path'], zip_internal_path)
            else:
                # ✅ ESCOPO TURMA/SÉRIE: ZIP plano (sem pastas)
                for pdf_info in generated_pdfs:
                    if os.path.exists(pdf_info['pdf_path']):
                        zf.write(pdf_info['pdf_path'], pdf_info['filename'])
        
        zip_size = os.path.getsize(zip_path)
        download_size = zip_size  # Para retorno na resposta
        logger.info(f"[CELERY-BATCH] ✅ ZIP criado: {zip_size} bytes")
        
        # ========================================================================
        # ✅ UPLOAD PARA MINIO (NÃO CRÍTICO - não deve derrubar a task)
        # ========================================================================
        minio_url = None
        minio_object_name = None
        minio_bucket = None
        
        # Upload usando arquivo em disco (streaming, não carrega tudo em memória)
        logger.info(f"[CELERY-BATCH] ☁️ Enviando ZIP para MinIO...")
        try:
            from app.services.storage.minio_service import MinIOService
            
            minio = MinIOService()
            
            # Path do objeto no MinIO
            if batch_id:
                object_name = f"gabaritos/batch/{batch_id}/cartoes.zip"
            else:
                object_name = f"gabaritos/{gabarito_ids[0]}/cartoes.zip"
            
            # Usar upload_from_path para não carregar ZIP inteiro em memória
            upload_result = minio.upload_from_path(
                bucket_name=minio.BUCKETS['ANSWER_SHEETS'],
                object_name=object_name,
                file_path=zip_path
            )
            
            if upload_result:
                minio_url = upload_result['url']
                minio_object_name = upload_result['object_name']
                minio_bucket = upload_result['bucket']
                
                logger.info(f"[CELERY-BATCH] ✅ Upload concluído: {minio_url}")
                
                # ✅ ATUALIZAR TODOS os gabaritos com a mesma URL do ZIP
                for gabarito_id in gabarito_ids:
                    gabarito = AnswerSheetGabarito.query.get(gabarito_id)
                    if gabarito:
                        gabarito.minio_url = minio_url
                        gabarito.minio_object_name = minio_object_name
                        gabarito.minio_bucket = minio_bucket
                        gabarito.zip_generated_at = datetime.utcnow()
                
                db.session.commit()
                logger.info(f"[CELERY-BATCH] ✅ {len(gabarito_ids)} gabarito(s) atualizado(s) com URL do MinIO")
            else:
                logger.warning(f"[CELERY-BATCH] ⚠️ Upload para MinIO falhou, mas PDFs foram gerados com sucesso")
                
        except Exception as minio_error:
            # 🔒 Erro de MinIO NÃO deve derrubar a task - PDFs já foram gerados
            logger.error(f"[CELERY-BATCH] ⚠️ Erro ao fazer upload para MinIO (não crítico): {str(minio_error)}", exc_info=True)
        
        # Limpar arquivos temporários
        try:
            import shutil
            shutil.rmtree(temp_dir)
            logger.info(f"[CELERY-BATCH] 🧹 Arquivos temporários limpos")
        except Exception as e:
            logger.warning(f"[CELERY-BATCH] ⚠️ Erro ao limpar arquivos temporários: {str(e)}")
        
        # Liberar memória explicitamente
        gc.collect()
        
        # Preparar resposta
        classes_generated = []
        for pdf_info in generated_pdfs:
            classes_generated.append({
                'gabarito_id': pdf_info['gabarito_id'],
                'class_id': pdf_info['class_id'],
                'class_name': pdf_info['class_name'],
                'grade_name': pdf_info['grade_name'],
                'filename': pdf_info['filename'],
                'total_students': pdf_info['total_students'],
                'total_pages': pdf_info['total_pages']
            })
        
        return {
            'success': True,
            'scope': scope,
            'batch_id': batch_id,
            'gabarito_ids': gabarito_ids,
            'num_questions': num_questions,
            'total_classes': len(generated_pdfs),
            'total_students': total_students,
            'total_pdfs': len(generated_pdfs),
            'minio_url': minio_url,  # Pode ser None se upload falhar
            'download_size_bytes': download_size,
            'classes': classes_generated
        }
    
    except Exception as e:
        logger.error(f"[CELERY-BATCH] ❌ Erro ao gerar cartões de resposta: {str(e)}", exc_info=True)
        
        error_str = str(e).lower()
        # 🔒 NÃO fazer retry por erro de MinIO - apenas por erros críticos de geração
        # Se PDFs foram gerados mas upload falhou, não retryar
        is_minio_error = 'minio' in error_str or 's3' in error_str or 'ssl' in error_str
        
        if is_minio_error:
            logger.warning(f"[CELERY-BATCH] ⚠️ Erro de MinIO detectado - não retryando task (PDFs podem ter sido gerados)")
            return {
                'success': False,
                'error': str(e),
                'scope': scope,
                'gabarito_ids': gabarito_ids,
                'is_minio_error': True
            }
        
        # Retry apenas para erros críticos (não relacionados a MinIO ou permissões)
        if self.request.retries < self.max_retries:
            logger.info(f"[CELERY-BATCH] 🔄 Tentando novamente (retry {self.request.retries + 1}/{self.max_retries})...")
            raise self.retry(exc=e)
        
        return {
            'success': False,
            'error': str(e),
            'scope': scope,
            'gabarito_ids': gabarito_ids
        }
