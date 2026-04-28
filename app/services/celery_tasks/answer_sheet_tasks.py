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
from celery import Task, group, chord

from app.report_analysis.celery_app import celery_app
from app.services.progress_store import get_job
from app.services.answer_sheet_job_store import update_answer_sheet_job
from app.services.cartao_resposta.answer_sheet_generator import sanitize_filename
from app import db
from app.utils.tenant_middleware import city_id_to_schema_name, set_search_path

logger = logging.getLogger(__name__)


def _mirror_recalc_job_to_db(job_id: str) -> None:
    """
    Atualiza contadores/status do job em public.answer_sheet_generation_jobs
    em **transação separada**, para polling funcionar entre workers sem
    interferir no commit em lote dos AnswerSheetResult na sessão principal.
    """
    from sqlalchemy.orm import sessionmaker

    from app import db
    from app.models.answerSheetGenerationJob import AnswerSheetGenerationJob
    from app.services.progress_store import get_job

    j = get_job(job_id)
    if not j:
        return
    try:
        tot = int(j.get("total") or 0)
        comp = int(j.get("completed") or 0)
        pct = min(100, int(round(100 * comp / tot))) if tot else 0
        Session = sessionmaker(bind=db.engine)
        s = Session()
        try:
            row = s.query(AnswerSheetGenerationJob).filter_by(job_id=job_id).first()
            if not row:
                return
            row.completed = comp
            row.successful = int(j.get("successful") or 0)
            row.failed = int(j.get("failed") or 0)
            row.status = j.get("status") or "processing"
            row.progress_current = comp
            row.progress_percentage = pct
            ca = j.get("completed_at")
            if ca:
                if isinstance(ca, str):
                    try:
                        row.completed_at = datetime.fromisoformat(
                            ca.replace("Z", "+00:00")
                        )
                    except (ValueError, TypeError):
                        pass
                elif isinstance(ca, datetime):
                    row.completed_at = ca
            s.commit()
        finally:
            s.close()
    except Exception as e:
        logger.warning("Espelho DB do job de recálculo %s: %s", job_id, e)


def run_recalculate_answer_sheet_results_for_gabarito(
    gabarito_id: str,
    job_id: str,
    city_id: str,
) -> Dict[str, Any]:
    """
    Recalcula AnswerSheetResult após edição do gabarito.
    Pode rodar no worker Celery ou no processo da API (fallback quando broker/Redis indisponível).
    """
    from app.models.answerSheetGabarito import AnswerSheetGabarito
    from app.models.answerSheetResult import AnswerSheetResult
    from app.models.student import Student
    from app.services.progress_store import (
        update_item_processing,
        update_item_done,
        update_item_error,
        complete_job,
        update_job,
    )
    from app.report_analysis.answer_sheet_aggregate_service import (
        invalidate_answer_sheet_reports_after_gabarito_bulk_update,
    )
    from app.services.cartao_resposta.answer_sheet_recalculation_service import (
        recalculate_answer_sheet_result_fields,
    )

    if not city_id:
        raise ValueError("city_id é obrigatório para recálculo (multitenant)")
    city_schema = city_id_to_schema_name(str(city_id))
    set_search_path(city_schema)

    gabarito = AnswerSheetGabarito.query.get(gabarito_id)
    if not gabarito:
        raise ValueError("Gabarito não encontrado")

    results = AnswerSheetResult.query.filter_by(gabarito_id=gabarito_id).all()

    update_job(
        job_id,
        {
            "stage_message": "Recalculando resultados...",
            "phase": "recalculating",
        },
    )
    _mirror_recalc_job_to_db(job_id)

    commit_every = 50
    processed = 0
    for idx, res in enumerate(results):
        try:
            set_search_path(city_schema)

            student = Student.query.get(res.student_id) if res.student_id else None
            extra = {
                "student_id": str(res.student_id) if res.student_id else None,
                "student_name": getattr(student, "name", None) if student else None,
            }
            update_item_processing(job_id, idx, extra=extra)

            fields = recalculate_answer_sheet_result_fields(
                gabarito_obj=gabarito,
                detected_answers_raw=res.detected_answers,
            )
            for k, v in fields.items():
                setattr(res, k, v)
            res.corrected_at = datetime.utcnow()

            processed += 1
            if processed % commit_every == 0:
                db.session.commit()

            update_item_done(
                job_id,
                idx,
                {
                    "student_id": str(res.student_id) if res.student_id else None,
                    "student_name": getattr(student, "name", None) if student else None,
                    "correct": int(getattr(res, "correct_answers", 0) or 0),
                    "total": int(getattr(res, "total_questions", 0) or 0),
                    "percentage": float(getattr(res, "score_percentage", 0.0) or 0.0),
                    "grade": float(getattr(res, "grade", 0.0) or 0.0),
                    "classification": getattr(res, "classification", None),
                    "proficiency": float(getattr(res, "proficiency", 0.0) or 0.0),
                },
            )
            _mirror_recalc_job_to_db(job_id)
        except Exception as item_err:
            try:
                db.session.rollback()
            except Exception:
                pass
            update_item_error(
                job_id,
                idx,
                str(item_err),
                extra={"student_id": str(res.student_id) if res.student_id else None},
            )
            _mirror_recalc_job_to_db(job_id)

    db.session.commit()

    try:
        invalidate_answer_sheet_reports_after_gabarito_bulk_update(
            gabarito_id, city_id, commit=True
        )
    except Exception as inv_err:
        logger.warning("Invalidate answer_sheet report cache (bulk): %s", inv_err)

    complete_job(job_id)
    update_job(
        job_id,
        {
            "status": "completed",
            "stage_message": "Concluído",
            "phase": "done",
        },
    )
    _mirror_recalc_job_to_db(job_id)

    return {
        "success": True,
        "job_id": job_id,
        "gabarito_id": gabarito_id,
        "total": len(results),
    }


@celery_app.task(
    bind=True,
    name='answer_sheet_tasks.recalculate_answer_sheet_results_for_gabarito',
    max_retries=1,
    default_retry_delay=30,
    time_limit=1800,
    soft_time_limit=1740,
)
def recalculate_answer_sheet_results_for_gabarito(
    self: Task,
    gabarito_id: str,
    job_id: str,
    city_id: str,
) -> Dict[str, Any]:
    """
    Wrapper Celery: delega para run_recalculate_answer_sheet_results_for_gabarito.
    """
    from app.services.progress_store import complete_job, update_job

    try:
        return run_recalculate_answer_sheet_results_for_gabarito(
            gabarito_id, job_id, city_id
        )
    except Exception as e:
        logger.error("[CELERY-RECALC] ❌ %s", str(e), exc_info=True)
        try:
            db.session.rollback()
        except Exception:
            pass
        try:
            update_job(
                job_id,
                {
                    "status": "failed",
                    "error": str(e),
                    "stage_message": "Falhou",
                    "phase": "done",
                },
            )
        except Exception:
            pass
        try:
            complete_job(job_id)
        except Exception:
            pass
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e)
        return {
            "success": False,
            "job_id": job_id,
            "gabarito_id": gabarito_id,
            "error": str(e),
        }


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
# TASK PARA GERAÇÃO DE CARTÕES POR TURMA (INDIVIDUAL)
# ============================================================================

@celery_app.task(
    bind=True,
    name='answer_sheet_tasks.generate_answer_sheets_async',
    max_retries=2,
    default_retry_delay=60,
    time_limit=900,  # 15 minutos máximo
    soft_time_limit=840  # 14 minutos soft limit
)
def generate_answer_sheets_async(
    self: Task,
    class_id: str,
    city_id: str,
    num_questions: int,
    correct_answers: Dict,
    test_data: Dict,
    use_blocks: bool,
    blocks_config: Dict,
    questions_options: Dict = None,
    gabarito_id: str = None
) -> Dict[str, Any]:
    """
    ⚠️ TASK DESCONTINUADA - NÃO ESTÁ SENDO USADA
    
    Esta task gera 1 PDF ÚNICO com múltiplas páginas (1 página por aluno).
    
    PROBLEMA: Demora muito para várias turmas.
    
    SUBSTITUTO: Use generate_answer_sheets_single_class_async que gera PDFs
    individuais por aluno e é usado pela rota POST /answer-sheets/generate.
    
    Esta task foi mantida apenas para compatibilidade com código legado.
    
    ---
    
    Task Celery para geração ASSÍNCRONA de cartões de resposta para UMA turma.
    
    Args:
        class_id: ID da turma (UUID)
        city_id: ID da cidade (UUID) - necessário para configurar search_path
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
        logger.info(f"[CELERY] 🚀 Iniciando geração de cartões para turma: {class_id}")
        
        from app.models.answerSheetGabarito import AnswerSheetGabarito
        from app.services.cartao_resposta.answer_sheet_generator import AnswerSheetGenerator
        from app.models.studentClass import Class
        from app.models.city import City
        
        # MULTITENANT: bind do schema físico (schema_translate_map) para a cidade
        city = City.query.get(city_id)
        if not city:
            error_msg = f"Cidade {city_id} não encontrada"
            logger.error(f"[CELERY] ❌ {error_msg}")
            raise ValueError(error_msg)
        
        city_schema = city_id_to_schema_name(str(city.id))
        logger.info(f"[CELERY] 🌐 Schema físico do tenant: {city_schema}")
        
        set_search_path(city_schema)
        
        # Buscar turma
        class_obj = Class.query.get(class_id)
        if not class_obj:
            error_msg = f"Turma {class_id} não encontrada"
            logger.error(f"[CELERY] ❌ {error_msg}")
            raise ValueError(error_msg)
        
        logger.info(f"[CELERY] ✅ Turma encontrada: {class_obj.name}")
        
        # Gerar cartões
        generator = AnswerSheetGenerator()
        result = generator.generate_answer_sheets(
            class_id=class_id,
            num_questions=num_questions,
            correct_answers=correct_answers,
            test_data=test_data,
            use_blocks=use_blocks,
            blocks_config=blocks_config,
            questions_options=questions_options,
            gabarito_id=gabarito_id,
            use_arch4=True  # ✅ Architecture 4: Template Base + Overlay (10-50× mais rápido)
        )
        
        logger.info(f"[CELERY] ✅ Cartões gerados com sucesso para turma {class_id}")
        
        return {
            'success': True,
            'class_id': class_id,
            'class_name': class_obj.name,
            'result': result
        }
        
    except Exception as e:
        logger.error(f"[CELERY] ❌ Erro ao gerar cartões: {str(e)}", exc_info=True)
        logger.info(f"[CELERY] 🔄 Tentando novamente (retry {self.request.retries + 1}/2)...")
        raise self.retry(exc=e)


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
    city_id: str,
    num_questions: int,
    correct_answers: Dict,
    test_data: Dict,
    use_blocks: bool,
    blocks_config: Dict,
    questions_options: Dict = None,
    batch_id: str = None,
    scope: str = 'class',
    class_ids: List[str] = None
) -> Dict[str, Any]:
    """
    Task Celery para geração ASSÍNCRONA de cartões de resposta em batch.
    
    Gera 1 PDF por turma (cada PDF com múltiplas páginas, 1 por aluno).
    Suporta geração para 1 turma, múltiplas turmas de uma série ou escola inteira.
    
    Args:
        gabarito_ids: Lista de IDs dos gabaritos (1 por turma)
        city_id: ID da cidade (UUID) - necessário para configurar search_path
        num_questions: Quantidade de questões
        correct_answers: Dict com respostas corretas
        test_data: Dados da prova (title, municipality, etc.)
        use_blocks: Se usa blocos
        blocks_config: Configuração de blocos
        questions_options: Alternativas por questão (opcional)
        batch_id: ID do batch (opcional, para agrupar múltiplas turmas)
        scope: Escopo da geração ('class', 'grade' ou 'school')
        class_ids: Lista de IDs das turmas (opcional, para escopo hierárquico)
    
    Returns:
        Dict com status e informações dos cartões gerados
    """
    try:
        logger.info(f"[CELERY-BATCH] 🚀 Iniciando geração de cartões - Escopo: {scope}, Gabaritos: {len(gabarito_ids)}")
        
        from app.models.answerSheetGabarito import AnswerSheetGabarito
        from app.services.cartao_resposta.answer_sheet_generator import AnswerSheetGenerator
        from app.models.studentClass import Class
        from app.models.city import City
        from app import db
        
        # MULTITENANT: bind do schema físico para a cidade
        city = City.query.get(city_id)
        if not city:
            error_msg = f"Cidade {city_id} não encontrada"
            logger.error(f"[CELERY-BATCH] ❌ {error_msg}")
            raise ValueError(error_msg)
        
        city_schema = city_id_to_schema_name(str(city.id))
        logger.info(f"[CELERY-BATCH] 🌐 Schema físico do tenant: {city_schema}")
        
        set_search_path(city_schema)

        def _ensure_tenant_search_path():
            """Após commit, reforça o bind do tenant (nova conexão do pool)."""
            set_search_path(city_schema)
        
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

        test_data = dict(test_data) if test_data else {}
        
        # Criar diretório temporário para ZIP
        temp_dir = tempfile.mkdtemp()
        output_dir = os.path.join(temp_dir, 'pdfs')
        os.makedirs(output_dir, exist_ok=True)
        
        generator = AnswerSheetGenerator()
        generated_pdfs = []
        skipped_classes = []  # ✅ NOVO: rastrear turmas puladas
        total_students = 0

        # ========================================================================
        # ✅ NOVO: Gerar PDFs a partir de UM gabarito (escopo) e lista de turmas
        # ========================================================================
        if class_ids:
            # Novo fluxo: 1 gabarito representando o escopo inteiro
            if len(gabaritos) != 1:
                raise ValueError("Fluxo com class_ids requer exatamente 1 gabarito (escopo)")

            gabarito_master = gabaritos[0]

            # Buscar todas as turmas do escopo (lista explícita)
            classes = Class.query.filter(Class.id.in_(class_ids)).all()
            if not classes:
                raise ValueError("Nenhuma turma encontrada para os IDs informados")

            logger.info(f"[CELERY-BATCH] ✅ Gerando PDFs individuais para {len(classes)} turma(s) usando gabarito único {gabarito_master.id}")
            logger.info(f"[CELERY-BATCH] 🚀 OTIMIZADO: 1 template base para TODAS as turmas + overlay por aluno")

            # ========================================================================
            # ARCHITECTURE 4 OTIMIZADO: 1 Template Base para TODAS as turmas
            # ========================================================================
            from app.models.student import Student
            from weasyprint import HTML
            from pypdf import PdfReader, PdfWriter
            import io
            
            # Gerar template base UMA VEZ (compartilhado por todas as turmas)
            logger.info(f"[CELERY-BATCH] 📄 Gerando template base único (1× WeasyPrint)...")
            
            placeholder_student = {
                'id': ' ',
                'name': ' ',
                'nome': ' ',
                'school_name': ' ',
                'class_name': ' ',
                'grade_name': ' ',
                'qr_code': generator._get_placeholder_qr_base64()
            }
            
            questions_map = generator._build_questions_map(num_questions, questions_options)
            questions_by_block = generator._organize_questions_by_blocks(num_questions, blocks_config, questions_map)
            
            base_template_data = {
                'test_data': test_data,
                'student': placeholder_student,
                'questions_by_block': questions_by_block,
                'questions_map': questions_map,
                'blocks_config': blocks_config,
                'total_questions': num_questions,
                'datetime': datetime,
                'generated_date': datetime.now().strftime('%d/%m/%Y %H:%M')
            }
            
            template = generator.env.get_template('answer_sheet.html')
            base_html = template.render(**base_template_data)
            base_pdf_bytes = HTML(string=base_html).write_pdf()
            
            logger.info(f"[CELERY-BATCH] ✅ Template base gerado ({len(base_pdf_bytes)} bytes) - será reutilizado para TODAS as turmas")
            
            # Contar total de alunos e criar job no progress_store
            total_alunos_todas_turmas = sum(len(Student.query.filter_by(class_id=c.id).all()) for c in classes)
            logger.info(f"[CELERY-BATCH] 📊 Total de alunos em todas as turmas: {total_alunos_todas_turmas}")
            # Job de progresso (items por aluno) é semeado na API (seed_answer_sheet_progress_job);
            # não recriar aqui para não sobrescrever Redis nem perder metadados de turma.
            
            # Processar todas as turmas usando o MESMO template base
            total_processed = 0
            student_item_idx = 0  # índice sequencial 0..N-1 para progress_store (igual prova física)
            from app.services.progress_store import update_item_processing, update_item_done, update_item_error
            from app.models.grades import Grade
            
            for idx, class_obj in enumerate(classes, 1):
                turma_id_log = 'n/d'
                try:
                    # Obrigatório antes de tocar em Class/Student: commit no job (finally) expira ORM e
                    # a próxima conexão do pool pode não ter search_path → "relation class does not exist" em public.
                    _ensure_tenant_search_path()
                    turma_id_log = str(class_obj.id)
                    turma_name_log = (class_obj.name or '')
                    logger.info(f"[CELERY-BATCH] 🔨 Processando turma {idx}/{len(classes)}: {turma_name_log}")

                    # Buscar alunos da turma
                    students = Student.query.filter_by(class_id=class_obj.id).all()
                    
                    # Informações da turma para progress tracking
                    grade_name = ''
                    if class_obj.grade_id:
                        grade_obj = Grade.query.get(class_obj.grade_id)
                        if grade_obj:
                            grade_name = grade_obj.name
                    school_name = class_obj.school.name if class_obj.school else 'Sem Escola'
                    
                    if not students:
                        logger.warning(f"[CELERY-BATCH] ⚠️ Turma {class_obj.name} sem alunos — pulando")
                        skipped_classes.append({
                            'class_name': class_obj.name,
                            'grade_name': grade_name
                        })
                        continue
                    
                    # Criar diretório para a turma
                    grade_name = (class_obj.grade.name if class_obj.grade else '').strip() or 'serie'
                    grade_safe = sanitize_filename(grade_name, max_length=40)
                    class_name_raw = (class_obj.name or 'turma').strip()
                    class_safe = sanitize_filename(class_name_raw, max_length=40)
                    class_folder = os.path.join(output_dir, f"{grade_safe}_{class_safe}")
                    os.makedirs(class_folder, exist_ok=True)
                    
                    # Gerar overlay e PDF individual para cada aluno
                    for student_idx, student in enumerate(students):
                        item_index = student_item_idx
                        student_item_idx += 1
                        try:
                            if batch_id:
                                update_item_processing(
                                    batch_id,
                                    item_index,
                                    extra={
                                        'class_id': str(class_obj.id),
                                        'class_name': class_obj.name,
                                        'school_name': school_name,
                                        'student_id': str(student.id),
                                        'student_name': student.name,
                                    },
                                )
                            student_data = generator._get_complete_student_data(student)
                            
                            # Gerar overlay (ReportLab - rápido!)
                            overlay_bytes = generator._generate_student_overlay_pdf(
                                student_data,
                                test_data,
                                gabarito_id=str(gabarito_master.id)
                            )
                            
                            if not overlay_bytes:
                                logger.error(f"[CELERY-BATCH] Falha ao gerar overlay para aluno {student.id}")
                                if batch_id:
                                    update_item_error(batch_id, item_index, 'Falha ao gerar overlay', extra={
                                        'class_id': str(class_obj.id),
                                        'class_name': class_obj.name,
                                        'school_name': school_name,
                                        'student_id': str(student.id),
                                        'student_name': student.name,
                                    })
                                continue
                            
                            # Nova leitura do PDF base por aluno (merge_page muta a página)
                            base_fresh = PdfReader(io.BytesIO(base_pdf_bytes))
                            base_page = base_fresh.pages[0]
                            overlay_reader = PdfReader(io.BytesIO(overlay_bytes))
                            base_page.merge_page(overlay_reader.pages[0])
                            
                            # Salvar PDF individual
                            writer = PdfWriter()
                            writer.add_page(base_page)
                            
                            pdf_buffer = io.BytesIO()
                            writer.write(pdf_buffer)
                            pdf_buffer.seek(0)
                            pdf_bytes = pdf_buffer.read()
                            
                            student_name = student_data.get('name', 'aluno')
                            name_safe = sanitize_filename(student_name, max_length=60)
                            filename = f"{name_safe}_{grade_safe}_{class_safe}.pdf"
                            filepath = os.path.join(class_folder, filename)
                            
                            with open(filepath, 'wb') as f:
                                f.write(pdf_bytes)
                            
                            total_students += 1
                            total_processed += 1
                            # ZIP / resultado da task: 1 entrada por PDF gerado (caminho relativo no ZIP)
                            rel_zip_name = f"{grade_safe}_{class_safe}/{filename}"
                            generated_pdfs.append({
                                'gabarito_id': str(gabarito_master.id),
                                'class_id': str(class_obj.id),
                                'pdf_path': filepath,
                                'filename': rel_zip_name,
                                'grade_name': grade_name,
                                'class_name': class_obj.name,
                                'school_name': school_name,
                                'total_students': 1,
                                'total_pages': 1,
                            })
                            
                            # Marcar aluno como concluído no progress store
                            if batch_id:
                                update_item_done(batch_id, item_index, {
                                    'class_id': str(class_obj.id),
                                    'class_name': class_obj.name,
                                    'school_name': school_name,
                                    'student_id': str(student.id),
                                    'student_name': student.name
                                })
                        
                        except Exception as e:
                            logger.error(f"[CELERY-BATCH] ❌ Erro ao processar aluno {student.id}: {str(e)}")
                            if batch_id:
                                update_item_error(batch_id, item_index, str(e), extra={
                                    'class_id': str(class_obj.id),
                                    'class_name': class_obj.name,
                                    'school_name': school_name,
                                    'student_id': str(student.id),
                                    'student_name': student.name,
                                })
                            continue
                    
                    logger.info(f"[CELERY-BATCH] ✅ Turma {class_obj.name}: {len(students)} PDFs individuais gerados")

                except Exception as e:
                    try:
                        db.session.rollback()
                    except Exception:
                        pass
                    logger.error(
                        f"[CELERY-BATCH] ❌ Erro ao processar turma {turma_id_log}: {str(e)}",
                        exc_info=True,
                    )
                    continue
                finally:
                    # Progresso progressivo: atualizar job (DB) a cada turma processada
                    if batch_id and len(classes) > 0:
                        pct = min(100, int(round((idx / len(classes)) * 100)))
                        update_answer_sheet_job(batch_id, {'progress_current': idx, 'progress_percentage': pct})
                    _ensure_tenant_search_path()
        else:
            # Fluxo antigo: 1 gabarito por turma
            for idx, gabarito in enumerate(gabaritos, 1):
                try:
                    logger.info(f"[CELERY-BATCH] 🔨 Gerando PDF {idx}/{len(gabaritos)} para turma {gabarito.class_id}...")
                    
                    # Buscar turma
                    class_obj = Class.query.get(gabarito.class_id)
                    if not class_obj:
                        logger.error(f"[CELERY-BATCH] ❌ Turma {gabarito.class_id} não encontrada")
                        continue
                    
                    # Gerar 1 PDF único para a turma (múltiplas páginas)
                    pdf_result = generator.generate_answer_sheets(
                        class_id=str(gabarito.class_id),
                        test_data=test_data,
                        num_questions=num_questions,
                        use_blocks=use_blocks,
                        blocks_config=blocks_config,
                        correct_answers=correct_answers,
                        gabarito_id=str(gabarito.id),
                        questions_options=questions_options,
                        output_dir=output_dir,
                        use_arch4=True  # ✅ Architecture 4: Template Base + Overlay (10-50× mais rápido)
                    )
                    
                    # Turma sem alunos: generator retorna None — pular sem erro
                    if pdf_result is None:
                        logger.warning(f"[CELERY-BATCH] ⚠️ Turma {class_obj.name} sem alunos — pulando")
                        # ✅ NOVO: adicionar à lista de puladas
                        from app.models.grades import Grade
                        grade_name = ''
                        if class_obj.grade_id:
                            grade_obj = Grade.query.get(class_obj.grade_id)
                            if grade_obj:
                                grade_name = grade_obj.name
                        skipped_classes.append({
                            'class_name': class_obj.name,
                            'grade_name': grade_name
                        })
                        continue
                    
                    if pdf_result and pdf_result.get('pdf_path'):
                        generated_pdfs.append({
                            'gabarito_id': str(gabarito.id),
                            'class_id': str(gabarito.class_id),
                            'pdf_path': pdf_result['pdf_path'],
                            'filename': pdf_result['filename'],
                            'grade_name': pdf_result.get('grade_name', gabarito.grade_name),
                            'class_name': pdf_result.get('class_name', class_obj.name),
                            'school_name': class_obj.school.name if class_obj.school else 'Sem Escola',
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
                finally:
                    # Progresso progressivo: atualizar job (DB) a cada turma processada
                    if batch_id and len(gabaritos) > 0:
                        pct = min(100, int(round((idx / len(gabaritos)) * 100)))
                        update_answer_sheet_job(batch_id, {'progress_current': idx, 'progress_percentage': pct})
        
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
            if scope == 'city':
                # ✅ ESCOPO MUNICÍPIO: Organizar por Escola/Série
                by_school = {}
                for pdf_info in generated_pdfs:
                    school = pdf_info.get('school_name', 'Sem Escola')
                    grade = pdf_info.get('grade_name', 'Sem Serie')
                    folder = f"{school}/{grade}"
                    if folder not in by_school:
                        by_school[folder] = []
                    by_school[folder].append(pdf_info)

                for folder, pdfs in by_school.items():
                    for pdf_info in pdfs:
                        if os.path.exists(pdf_info['pdf_path']):
                            zip_internal_path = f"{folder}/{pdf_info['filename']}"
                            zf.write(pdf_info['pdf_path'], zip_internal_path)

            elif scope == 'school':
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
                
                # ✅ ATUALIZAR TODOS os gabaritos com a mesma URL do ZIP + escopo e totais da geração
                _scope = scope
                _municipality = (city.name or '') if city else ''
                _state = (city.state or '') if city else ''
                _school_id = None
                _school_name = ''
                _grade_id = None
                _grade_name = ''
                _class_id = None
                if generated_pdfs and scope != 'city':
                    first_class = Class.query.get(generated_pdfs[0]['class_id'])
                    if first_class:
                        if first_class.school_id:
                            _school_id = str(first_class.school_id)
                            _school_name = (first_class.school.name or '') if first_class.school else ''
                        if first_class.grade_id:
                            _grade_id = first_class.grade_id
                            _grade_name = (first_class.grade.name or '') if first_class.grade else generated_pdfs[0].get('grade_name', '')
                        _class_id = first_class.id
                uniq_classes = len({str(p['class_id']) for p in generated_pdfs}) if generated_pdfs else 0
                updated = 0
                for gabarito_id in gabarito_ids:
                    gabarito = db.session.query(AnswerSheetGabarito).filter_by(id=gabarito_id).first()
                    if not gabarito:
                        continue
                    gabarito.minio_url = minio_url
                    gabarito.minio_object_name = minio_object_name
                    gabarito.minio_bucket = minio_bucket
                    gabarito.zip_generated_at = datetime.utcnow()
                    gabarito.scope_type = _scope
                    gabarito.municipality = _municipality
                    gabarito.state = _state
                    gabarito.school_id = _school_id
                    gabarito.school_name = _school_name
                    gabarito.grade_id = _grade_id
                    gabarito.grade_name = _grade_name
                    gabarito.class_id = _class_id
                    gabarito.last_generation_classes_count = uniq_classes
                    gabarito.last_generation_students_count = total_students
                    updated += 1
                try:
                    db.session.commit()
                    logger.info(f"[CELERY-BATCH] ✅ {updated} gabarito(s) atualizado(s) com URL do MinIO")
                    # Histórico: uma linha por gabarito (mesmo job/ZIP), escopos distintos acumulam
                    try:
                        from app.models.answerSheetGenerationJob import AnswerSheetGenerationJob
                        from app.services.cartao_resposta.answer_sheet_gabarito_generation import (
                            record_answer_sheet_generations,
                            build_class_scope_entries,
                        )
                        job_row = (
                            AnswerSheetGenerationJob.query.filter_by(job_id=batch_id).first()
                            if batch_id
                            else None
                        )
                        uid = str(job_row.user_id) if job_row and job_row.user_id else None
                        cid_list = [str(x) for x in class_ids] if class_ids else []
                        snapshot = {
                            'scope': scope,
                            'city_id': city_id,
                            'class_ids': build_class_scope_entries(cid_list) if cid_list else [],
                        }
                        record_answer_sheet_generations(
                            gabarito_ids=[str(g) for g in gabarito_ids],
                            batch_id=batch_id,
                            scope=scope,
                            scope_snapshot=snapshot,
                            minio_url=minio_url,
                            minio_object_name=minio_object_name,
                            minio_bucket=minio_bucket,
                            total_classes=uniq_classes,
                            total_students=total_students,
                            created_by=uid,
                        )
                    except Exception as gen_e:
                        logger.warning(
                            '[CELERY-BATCH] ⚠️ Histórico answer_sheet_generations: %s',
                            gen_e,
                            exc_info=True,
                        )
                except Exception as e:
                    from sqlalchemy.orm.exc import StaleDataError
                    db.session.rollback()
                    if isinstance(e, StaleDataError):
                        logger.warning("[CELERY-BATCH] ⚠️ Gabarito(s) foi(ram) excluído(s) durante a geração; atualização de URL ignorada.")
                    else:
                        logger.error(f"[CELERY-BATCH] ⚠️ Erro ao atualizar gabarito(s) (não crítico): {e}", exc_info=True)
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
        
        # Preparar resposta (agregar por turma quando há 1 PDF por aluno)
        agg_by_class = {}
        for pdf_info in generated_pdfs:
            cid = str(pdf_info['class_id'])
            if cid not in agg_by_class:
                agg_by_class[cid] = {
                    'gabarito_id': pdf_info['gabarito_id'],
                    'class_id': cid,
                    'class_name': pdf_info['class_name'],
                    'grade_name': pdf_info['grade_name'],
                    'filename': pdf_info['filename'],
                    'total_students': 0,
                    'total_pages': 0,
                }
            agg_by_class[cid]['total_students'] += pdf_info.get('total_students', 1)
            agg_by_class[cid]['total_pages'] += pdf_info.get('total_pages', 1)
        classes_generated = list(agg_by_class.values())

        if batch_id:
            from app.services.progress_store import complete_job
            complete_job(batch_id)
        
        return {
            'success': True,
            'scope': scope,
            'batch_id': batch_id,
            'gabarito_ids': gabarito_ids,
            'num_questions': num_questions,
            'total_classes': len(agg_by_class),
            'total_students': total_students,
            'total_pdfs': len(generated_pdfs),
            'minio_url': minio_url,  # Pode ser None se upload falhar
            'download_size_bytes': download_size,
            'classes': classes_generated,
            'skipped_classes': skipped_classes  # ✅ NOVO: turmas puladas (sem alunos)
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


# =============================================================================
# Novo fluxo: 1 PDF por aluno, 1 task por turma (group) + chord para ZIP/upload
# =============================================================================

@celery_app.task(
    bind=True,
    name='answer_sheet_tasks.generate_answer_sheets_single_class_async',
    max_retries=2,
    default_retry_delay=60,
    time_limit=1800,
    soft_time_limit=1740
)
def generate_answer_sheets_single_class_async(
    self: Task,
    class_id: str,
    base_output_dir: str,
    city_id: str,
    gabarito_id: str,
    num_questions: int,
    correct_answers: Dict,
    test_data: Dict,
    use_blocks: bool,
    blocks_config: Dict,
    questions_options: Dict = None,
    batch_id: str = None,
    total_classes: int = 0,
) -> Dict[str, Any]:
    """
    Gera 1 PDF por aluno da turma e salva em base_output_dir/.../turma_{nome}/.
    Configura bind do tenant (multitenancy). Atualiza progresso gradual (Redis + DB) quando batch_id/total_classes são passados.
    Retorna apenas class_id e total_students (sem paths).
    """
    try:
        from app.services.cartao_resposta.answer_sheet_generator import AnswerSheetGenerator
        from app.models.city import City
        from app import db
        from app.services.progress_store import increment_answer_sheet_progress

        city = City.query.get(city_id)
        if not city:
            raise ValueError(f"Cidade {city_id} não encontrada")
        city_schema = city_id_to_schema_name(str(city.id))
        set_search_path(city_schema)

        test_data_merged = dict(test_data) if test_data else {}

        generator = AnswerSheetGenerator()
        result = generator.generate_class_answer_sheets(
            class_id=class_id,
            base_output_dir=base_output_dir,
            test_data=test_data_merged,
            num_questions=num_questions,
            use_blocks=use_blocks,
            blocks_config=blocks_config,
            correct_answers=correct_answers,
            gabarito_id=gabarito_id,
            questions_options=questions_options,
        )

        # Progresso gradual: incrementar contador e atualizar job (Redis + DB)
        if batch_id and total_classes > 0:
            inc = increment_answer_sheet_progress(batch_id, total_classes)
            if inc:
                new_current, new_pct = inc
                update_answer_sheet_job(batch_id, {'progress_current': new_current, 'progress_percentage': new_pct})

        if result is None:
            return {'class_id': class_id, 'total_students': 0}
        return {'class_id': result['class_id'], 'total_students': result['total_students']}
    except Exception as e:
        logger.error(f"[CELERY-SINGLE] ❌ Turma {class_id}: {str(e)}", exc_info=True)
        if batch_id and total_classes > 0:
            try:
                from app.services.progress_store import increment_answer_sheet_progress
                inc = increment_answer_sheet_progress(batch_id, total_classes)
                if inc:
                    update_answer_sheet_job(batch_id, {'progress_current': inc[0], 'progress_percentage': inc[1]})
            except Exception:
                pass
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e)
        return {'class_id': class_id, 'total_students': 0, 'error': str(e)}


@celery_app.task(
    bind=True,
    name='answer_sheet_tasks.build_zip_and_upload_answer_sheets',
    max_retries=3,  # ✅ Permitir retry se falhar (chord callback pode falhar por timeout)
    time_limit=1800,  # ✅ 30 minutos (tempo suficiente para esperar na fila + executar)
    soft_time_limit=1740,  # ✅ 29 minutos soft limit
    retry_backoff=True,  # ✅ Exponential backoff entre retries
    retry_backoff_max=600,  # ✅ Máximo 10 minutos entre retries
    retry_jitter=True,  # ✅ Adicionar jitter para evitar thundering herd
)
def build_zip_and_upload_answer_sheets(
    self: Task,
    group_results: List[Dict],
    batch_id: str,
    base_output_dir: str,
    city_id: str,
    gabarito_ids: List[str],
    scope: str,
    num_questions: int,
) -> Dict[str, Any]:
    """
    Chord callback: percorre base_output_dir, cria ZIP mantendo estrutura de pastas,
    upload MinIO, atualiza job e gabaritos, remove base_output_dir.
    group_results = lista de {class_id, total_students} retornada pelo group.
    """
    import shutil
    try:
        from app import db
        from app.models.city import City
        from app.models.answerSheetGabarito import AnswerSheetGabarito
        from app.models.studentClass import Class
        from app.services.storage.minio_service import MinIOService

        if not os.path.isdir(base_output_dir):
            logger.warning(f"[CELERY-CHORD] base_output_dir não existe: {base_output_dir}")
            return {'success': False, 'error': 'base_output_dir not found', 'batch_id': batch_id}

        total_students = sum(r.get('total_students', 0) for r in group_results)
        zip_filename = f'cartoes_{batch_id}.zip'
        zip_path = os.path.join(os.path.dirname(base_output_dir), zip_filename)

        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for root, _dirs, files in os.walk(base_output_dir):
                for f in files:
                    if not f.endswith('.pdf'):
                        continue
                    full_path = os.path.join(root, f)
                    rel = os.path.relpath(full_path, base_output_dir)
                    zf.write(full_path, rel)

        zip_size = os.path.getsize(zip_path)
        logger.info(f"[CELERY-CHORD] ZIP criado: {zip_size} bytes, {total_students} alunos")

        minio_url = None
        city = City.query.get(city_id)
        if city:
            set_search_path(city_id_to_schema_name(str(city.id)))

        try:
            minio = MinIOService()
            object_name = f"gabaritos/batch/{batch_id}/cartoes.zip"
            upload_result = minio.upload_from_path(
                bucket_name=minio.BUCKETS['ANSWER_SHEETS'],
                object_name=object_name,
                file_path=zip_path
            )
            if upload_result:
                minio_url = upload_result['url']
                minio_object_name = upload_result['object_name']
                minio_bucket = upload_result['bucket']
                logger.info(f"[CELERY-CHORD] Upload MinIO: {minio_url}")

                _scope = scope
                _municipality = (city.name or '') if city else ''
                _state = (city.state or '') if city else ''
                _school_id = _school_name = _grade_id = _grade_name = _class_id = None
                if group_results and city:
                    first_class = Class.query.get(group_results[0].get('class_id'))
                    if first_class:
                        _school_id = str(first_class.school_id) if first_class.school_id else None
                        _school_name = (first_class.school.name or '') if first_class.school else ''
                        _grade_id = first_class.grade_id
                        _grade_name = (first_class.grade.name or '') if first_class.grade else ''
                        _class_id = first_class.id

                    for gabarito_id in gabarito_ids:
                        gab = db.session.query(AnswerSheetGabarito).filter_by(id=gabarito_id).first()
                        if not gab:
                            continue
                        gab.minio_url = minio_url
                        gab.minio_object_name = minio_object_name
                        gab.minio_bucket = minio_bucket
                        gab.zip_generated_at = datetime.utcnow()
                        gab.scope_type = _scope
                        gab.municipality = _municipality
                        gab.state = _state
                        gab.school_id = _school_id
                        gab.school_name = _school_name
                        gab.grade_id = _grade_id
                        gab.grade_name = _grade_name
                        gab.class_id = _class_id
                        gab.last_generation_classes_count = len([r for r in group_results if r.get('total_students', 0) > 0])
                        gab.last_generation_students_count = total_students
                    try:
                        db.session.commit()
                        try:
                            from app.models.answerSheetGenerationJob import AnswerSheetGenerationJob
                            from app.services.cartao_resposta.answer_sheet_gabarito_generation import (
                                record_answer_sheet_generations,
                                build_class_scope_entries,
                            )
                            job_row = (
                                AnswerSheetGenerationJob.query.filter_by(job_id=batch_id).first()
                                if batch_id
                                else None
                            )
                            uid = str(job_row.user_id) if job_row and job_row.user_id else None
                            tc = len([r for r in group_results if r.get('total_students', 0) > 0])
                            cid_list = [
                                str(r.get('class_id'))
                                for r in group_results
                                if r.get('class_id')
                            ]
                            snapshot = {
                                'scope': scope,
                                'city_id': city_id,
                                'class_ids': build_class_scope_entries(cid_list) if cid_list else [],
                            }
                            record_answer_sheet_generations(
                                gabarito_ids=[str(g) for g in gabarito_ids],
                                batch_id=batch_id,
                                scope=scope,
                                scope_snapshot=snapshot,
                                minio_url=minio_url,
                                minio_object_name=minio_object_name,
                                minio_bucket=minio_bucket,
                                total_classes=tc,
                                total_students=total_students,
                                created_by=uid,
                            )
                        except Exception as gen_e:
                            logger.warning(
                                '[CELERY-CHORD] Histórico answer_sheet_generations: %s',
                                gen_e,
                                exc_info=True,
                            )
                    except Exception as e:
                        db.session.rollback()
                        logger.warning(f"[CELERY-CHORD] Erro ao atualizar gabaritos: {e}")
        except Exception as minio_error:
            logger.error(f"[CELERY-CHORD] Erro MinIO (não crítico): {minio_error}", exc_info=True)

        try:
            os.remove(zip_path)
        except Exception:
            pass
        try:
            shutil.rmtree(base_output_dir)
            logger.info(f"[CELERY-CHORD] base_output_dir removido")
        except Exception as e:
            logger.warning(f"[CELERY-CHORD] Erro ao remover base_output_dir: {e}")

        update_answer_sheet_job(batch_id, {
            'progress_current': len(group_results),
            'progress_percentage': 100,
            'status': 'completed',
            'minio_url': minio_url,
            'total_students': total_students,
            'total_classes': len([r for r in group_results if r.get('total_students', 0) > 0]),
        })

        return {
            'success': True,
            'batch_id': batch_id,
            'scope': scope,
            'total_students': total_students,
            'total_classes': len(group_results),
            'minio_url': minio_url,
            'download_size_bytes': zip_size,
        }
    except Exception as e:
        logger.error(f"[CELERY-CHORD] ❌ {str(e)}", exc_info=True)
        try:
            if os.path.isdir(base_output_dir):
                shutil.rmtree(base_output_dir)
        except Exception:
            pass
        update_answer_sheet_job(batch_id, {'status': 'failed', 'error': str(e)})
        return {'success': False, 'error': str(e), 'batch_id': batch_id}
