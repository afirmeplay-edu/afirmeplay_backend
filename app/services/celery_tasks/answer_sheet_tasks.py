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
    
    Gera UM PDF com múltiplas páginas (1 página por aluno) para uma turma.
    Suporta geração hierárquica: múltiplas tasks, 1 gabarito compartilhado.
    
    Args:
        class_id: ID da turma
        num_questions: Quantidade de questões
        correct_answers: Dict com respostas corretas
        test_data: Dados da prova (title, municipality, etc.)
        use_blocks: Se usa blocos
        blocks_config: Configuração de blocos
        questions_options: Alternativas por questão (opcional)
        gabarito_id: ID do gabarito OBRIGATÓRIO (gerado no endpoint)
    
    Returns:
        Dict com status e informações dos cartões gerados
    """
    try:
        logger.info(f"[CELERY] 🚀 Gerando cartões para turma class_id={class_id}, gabarito_id={gabarito_id}")
        
        # ✅ VALIDAR gabarito_id OBRIGATÓRIO
        if not gabarito_id:
            raise ValueError("gabarito_id é OBRIGATÓRIO e não pode ser None")
        
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
        print(f"\n=== DEBUG TASK CELERY ===")
        print(f"Classe ID: {class_id}")
        print(f"Estudantes encontrados na task: {len(students)}")
        if students:
            for student in students:
                print(f"  - Estudante: {student.name} (ID: {student.id})")
        else:
            print(f"  - Nenhum estudante encontrado para classe {class_id}")
        print(f"========================\n")
        
        if not students:
            # ⚠️ Turma sem alunos = PULAR (não gerar PDF vazio)
            warning_msg = f"Turma '{class_obj.name}' ({class_id}) não tem alunos registrados. Turma pulada."
            logger.warning(f"[CELERY] ⚠️ {warning_msg}")
            return {
                'success': True,
                'skipped': True,
                'reason': warning_msg,
                'class_id': str(class_id),
                'class_name': class_obj.name,
                'num_questions': num_questions,
                'students_processed': 0,
                'message': f'Turma {class_obj.name} pulada - sem alunos'
            }
        
        logger.info(f"[CELERY] 📊 Total de alunos: {len(students)}")
        logger.info(f"[CELERY] 📝 Total de questões: {num_questions}")
        
        # ✅ GERAR 1 PDF COM MÚLTIPLAS PÁGINAS (1 página por aluno)
        logger.info(f"[CELERY] 🔨 Gerando PDF para {len(students)} alunos...")
        
        generator = AnswerSheetGenerator()
        
        # Novo método: gera 1 PDF com múltiplas páginas
        result = generator.generate_answer_sheets(
            class_id=class_id,
            test_data=test_data,
            num_questions=num_questions,
            use_blocks=use_blocks,
            blocks_config=blocks_config,
            correct_answers=correct_answers,
            gabarito_id=gabarito_id,
            questions_options=questions_options
        )
        
        if not result:
            raise ValueError("Nenhum cartão resposta foi gerado")
        
        pdf_path = result['pdf_path']
        file_size = result['file_size']
        
        logger.info(f"[CELERY] ✅ PDF gerado com sucesso: {result['class_name']} ({file_size} bytes, {len(students)} alunos)")
        
        print(f"\n=== SUCESSO TASK CELERY ===")
        print(f"Classe: {result['class_name']}")
        print(f"Estudantes processados: {len(students)}")
        print(f"PDF gerado: {pdf_path}")
        print(f"Tamanho: {file_size} bytes")
        print(f"==========================\n")
        
        # ========================================================================
        # UPLOAD PARA MINIO (NÃO CRÍTICO - não deve derrubar a task)
        # ========================================================================
        minio_url = None
        minio_object_name = None
        minio_bucket = None
        
        logger.info(f"[CELERY] ☁️ Enviando PDF para MinIO...")
        try:
            from app.services.storage.minio_service import MinIOService
            
            minio = MinIOService()
            
            # ✅ UPLOAD DO PDF DIRETO (não ZIP)
            # Path: gabaritos/{gabarito_id}/{class_id}/cartoes.pdf
            upload_result = minio.upload_from_path(
                bucket_name=minio.BUCKETS['ANSWER_SHEETS'],
                object_name=f"gabaritos/{gabarito_id}/{class_id}/cartoes.pdf",
                file_path=pdf_path
            )
            
            if upload_result:
                minio_url = upload_result['url']
                minio_object_name = upload_result['object_name']
                minio_bucket = upload_result['bucket']
                
                logger.info(f"[CELERY] ✅ Upload concluído: {minio_url}")
                
                # ✅ ATUALIZAR GABARITO COM INFORMAÇÕES DESTA TURMA
                from app.models.answerSheetGabarito import AnswerSheetGabarito
                
                gabarito = AnswerSheetGabarito.query.get(gabarito_id)
                if gabarito:
                    # Se é a primeira turma, salvar URL principal
                    if not gabarito.minio_url:
                        gabarito.minio_url = minio_url
                        gabarito.minio_object_name = minio_object_name
                        gabarito.minio_bucket = minio_bucket
                    
                    gabarito.zip_generated_at = datetime.utcnow()
                    db.session.commit()
                    logger.info(f"[CELERY] ✅ Gabarito {gabarito_id} atualizado (turma: {class_obj.name})")
                else:
                    logger.warning(f"[CELERY] ⚠️ Gabarito {gabarito_id} não encontrado para atualizar")
            else:
                logger.warning(f"[CELERY] ⚠️ Upload para MinIO falhou, mas PDF foi gerado com sucesso")
                
        except Exception as minio_error:
            # 🔒 Erro de MinIO NÃO deve derrubar a task - PDF já foi gerado
            logger.error(f"[CELERY] ⚠️ Erro ao fazer upload para MinIO (não crítico): {str(minio_error)}", exc_info=True)
        
        # Liberar memória explicitamente
        gc.collect()
        
        # ========================================================================
        # VERIFICAR SE ESTA É A ÚLTIMA TASK E DISPARAR CONSOLIDAÇÃO
        # ========================================================================
        try:
            # Para múltiplas turmas, disparar consolidação após delay para garantir que todas terminaram
            from app.models.answerSheetGabarito import AnswerSheetGabarito
            gabarito = AnswerSheetGabarito.query.get(gabarito_id)
            if gabarito and gabarito.scope_type in ['school', 'grade']:
                logger.info(f"[CELERY] Agendando consolidação para gabarito {gabarito_id} em 30 segundos...")
                # Usar countdown para dar tempo de outras tasks terminarem
                consolidate_answer_sheets_to_zip.apply_async(
                    args=[gabarito_id],
                    countdown=30  # 30 segundos de delay
                )
        except Exception as consolidate_error:
            logger.warning(f"[CELERY] Erro ao agendar consolidação: {str(consolidate_error)}")
        
        return {
            'success': True,
            'class_id': str(class_id),
            'class_name': class_obj.name,
            'num_questions': num_questions,
            'total_students': len(students),
            'gabarito_id': gabarito_id,
            'minio_url': minio_url,
            'file_size_bytes': file_size
        }
    
    except Exception as e:
        logger.error(f"[CELERY] ❌ Erro ao gerar cartões de resposta: {str(e)}", exc_info=True)
        
        # 🔒 ERROS QUE NÃO DEVEM FAZER RETRY
        error_str = str(e).lower()
        no_retry_errors = [
            'nenhum aluno',
            'not found',
            'não encontrado',
            'acesso negado',
            'permiss',
            'unauthorized'
        ]
        
        # Verificar se é erro que não deve fazer retry
        should_not_retry = any(error_keyword in error_str for error_keyword in no_retry_errors)
        
        if should_not_retry:
            logger.warning(f"[CELERY] ⚠️ Erro que não requer retry: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'class_id': class_id
            }
        
        # 🔒 NÃO fazer retry por erro de MinIO - apenas por erros críticos de geração
        # Se PDFs foram gerados mas upload falhou, não retryar
        is_minio_error = 'minio' in error_str or 's3' in error_str or 'ssl' in error_str
        
        if is_minio_error:
            logger.warning(f"[CELERY] ⚠️ Erro de MinIO detectado - não retryando task (PDFs podem ter sido gerados)")
            return {
                'success': False,
                'error': str(e),
                'class_id': class_id,
                'is_minio_error': True
            }
        
        # Retry apenas para erros críticos (não relacionados a MinIO ou permissões)
        if self.request.retries < self.max_retries:
            logger.info(f"[CELERY] 🔄 Tentando novamente (retry {self.request.retries + 1}/{self.max_retries})...")
            raise self.retry(exc=e)
        
        return {
            'success': False,
            'error': str(e),
            'class_id': class_id
        }

# ============================================================================
# NOVA TASK: Geração Hierárquica por "Pai" (Escola/Série/Turma)
# ============================================================================

# ❌ FUNÇÃO REMOVIDA - generate_answer_sheets_hierarchical_parent()
# 
# Esta função foi criada para gerar PDFs hierárquicos misturando conceitos
# de gabarito com geração multi-turma, o que NÃO era o requisito do usuário.
#
# O novo endpoint /generate-hierarchical REUTILIZA generate_answer_sheets_async()
# (o mesmo método que /generate usa) para cada turma identificada no escopo.
#
# Se no futuro precisar de uma tarefa Celery customizada para hierárquica,
# seria melhor criar uma que simplesmente orquestre múltiplas chamadas ao
# generate_answer_sheets_async() ao invés de reimplementar toda a lógica.


# ============================================================================
# NOVA TASK: Consolidação de múltiplos PDFs em ZIP
# ============================================================================

@celery_app.task(
    bind=True,
    name='answer_sheet_tasks.consolidate_answer_sheets_to_zip',
    max_retries=2,
    default_retry_delay=60,
    time_limit=600,  # 10 minutos máximo
    soft_time_limit=540  # 9 minutos soft limit
)
def consolidate_answer_sheets_to_zip(
    self: Task,
    gabarito_id: str
) -> Dict[str, Any]:
    """
    Consolida todos os PDFs de um gabarito em um único ZIP.
    
    Esta task busca todos os PDFs de um gabarito no MinIO, cria um ZIP e atualiza o gabarito.
    
    Args:
        gabarito_id: ID do gabarito a ser consolidado
    
    Returns:
        Dict com resultado da consolidação
    """
    try:
        logger.info(f"[CONSOLIDATE] Iniciando consolidação de PDFs para gabarito {gabarito_id}")
        
        from app.services.storage.minio_service import MinIOService
        from app.models.answerSheetGabarito import AnswerSheetGabarito
        import tempfile
        import shutil
        
        minio = MinIOService()
        
        # Buscar gabarito
        gabarito = AnswerSheetGabarito.query.get(gabarito_id)
        if not gabarito:
            raise ValueError(f"Gabarito {gabarito_id} não encontrado")
        
        # Listar todos os PDFs do gabarito no MinIO
        prefix = f"gabaritos/{gabarito_id}/"
        
        try:
            objects = minio.list_files(
                bucket_name=minio.BUCKETS['ANSWER_SHEETS'],
                prefix=prefix
            )
            
            pdf_objects = [obj for obj in objects if obj.endswith('.pdf')]
            
            if not pdf_objects:
                logger.warning(f"[CONSOLIDATE] Nenhum PDF encontrado para gabarito {gabarito_id}")
                return {'success': False, 'error': 'Nenhum PDF encontrado'}
            
            logger.info(f"[CONSOLIDATE] Encontrados {len(pdf_objects)} PDFs para consolidar")
            
        except Exception as list_error:
            logger.error(f"[CONSOLIDATE] Erro ao listar objetos: {str(list_error)}")
            raise ValueError(f"Erro ao listar PDFs: {str(list_error)}")
        
        # Criar diretório temporário
        temp_dir = tempfile.mkdtemp(prefix='consolidate_pdfs_')
        
        try:
            # Baixar todos os PDFs
            pdf_files = []
            from app.models.studentClass import Class
            
            for i, object_name in enumerate(pdf_objects):
                try:
                    # Extrair class_id do caminho: gabaritos/{gabarito_id}/{class_id}/cartoes.pdf
                    parts = object_name.split('/')
                    class_id = parts[2] if len(parts) > 2 else None
                    
                    # Buscar informações da turma para o nome do arquivo
                    file_display_name = "cartoes.pdf"
                    if class_id:
                        turma = Class.query.get(class_id)
                        if turma:
                            # Buscar o nome da série através do relacionamento grade
                            serie = turma.grade.name if turma.grade else "Sem Série"
                            turma_nome = turma.name or "Sem Nome"
                            file_display_name = f"{serie} - {turma_nome}.pdf"
                            logger.info(f"[CONSOLIDATE] Arquivo será nomeado como: {file_display_name}")
                    
                    # Nome do arquivo local (usar UUID temporário)
                    filename = os.path.basename(object_name)
                    file_path = os.path.join(temp_dir, filename)
                    
                    # Baixar PDF do MinIO
                    pdf_data = minio.download_file(
                        bucket_name=minio.BUCKETS['ANSWER_SHEETS'],
                        object_name=object_name
                    )
                    
                    with open(file_path, 'wb') as f:
                        f.write(pdf_data)
                    
                    # Guardar caminho e nome de exibição
                    pdf_files.append({
                        'path': file_path,
                        'display_name': file_display_name
                    })
                    logger.info(f"[CONSOLIDATE] Baixado: {filename}")
                    
                except Exception as e:
                    logger.error(f"[CONSOLIDATE] Erro ao baixar {object_name}: {str(e)}")
                    continue
            
            if not pdf_files:
                raise ValueError("Nenhum PDF foi baixado com sucesso")
            
            # Criar ZIP
            zip_filename = f"cartoes_resposta_{gabarito_id}.zip"
            zip_path = os.path.join(temp_dir, zip_filename)
            
            logger.info(f"[CONSOLIDATE] Criando ZIP com {len(pdf_files)} PDFs...")
            
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for pdf_info in pdf_files:
                    # Usar o nome formatado "série - turma.pdf"
                    zipf.write(pdf_info['path'], arcname=pdf_info['display_name'])
            
            zip_size = os.path.getsize(zip_path)
            logger.info(f"[CONSOLIDATE] ZIP criado: {zip_size} bytes")
            
            # Upload do ZIP para MinIO (substituindo o PDF individual)
            zip_upload_result = minio.upload_from_path(
                bucket_name=minio.BUCKETS['ANSWER_SHEETS'],
                object_name=f"gabaritos/{gabarito_id}/cartoes.zip",
                file_path=zip_path
            )
            
            if not zip_upload_result:
                raise ValueError("Falha no upload do ZIP para MinIO")
            
            # Atualizar gabarito com URL do ZIP
            gabarito.minio_url = zip_upload_result['url']
            gabarito.minio_object_name = zip_upload_result['object_name']
            gabarito.minio_bucket = zip_upload_result['bucket']
            gabarito.zip_generated_at = datetime.utcnow()
            db.session.commit()
            
            logger.info(f"[CONSOLIDATE] Gabarito atualizado com URL do ZIP: {zip_upload_result['url']}")
            
            print(f"\\n=== CONSOLIDAÇÃO CONCLUÍDA ===")
            print(f"Gabarito ID: {gabarito_id}")
            print(f"PDFs processados: {len(pdf_files)}")
            print(f"ZIP criado: {zip_upload_result['url']}")
            print(f"=============================\\n")
            
            return {
                'success': True,
                'gabarito_id': gabarito_id,
                'pdf_count': len(pdf_files),
                'zip_url': zip_upload_result['url'],
                'zip_size_bytes': zip_size
            }
            
        finally:
            # Limpar diretório temporário
            try:
                shutil.rmtree(temp_dir)
            except Exception as e:
                logger.warning(f"[CONSOLIDATE] Erro ao limpar temp_dir: {str(e)}")
    
    except Exception as e:
        logger.error(f"[CONSOLIDATE] Erro na consolidação: {str(e)}", exc_info=True)
        return {'success': False, 'error': str(e)}
