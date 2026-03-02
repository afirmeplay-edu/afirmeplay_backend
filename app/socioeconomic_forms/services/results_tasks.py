# -*- coding: utf-8 -*-
"""
Tasks Celery para processamento assíncrono de resultados de formulários socioeconômicos.
Inspirado em app/report_analysis/tasks.py
Em ambiente multi-tenant, o schema deve ser passado para as tasks (search_path).
"""

import logging
from typing import Dict, Any, Optional
from celery import Task
from sqlalchemy import text

from app.report_analysis.celery_app import celery_app
from app.socioeconomic_forms.services.results_service import ResultsService
from app.socioeconomic_forms.services.results_cache_service import ResultsCacheService
from app.socioeconomic_forms.models import Form
from app import db

logger = logging.getLogger(__name__)


def _set_tenant_schema(schema: Optional[str]) -> None:
    """Define o search_path do PostgreSQL para a task (multi-tenant)."""
    if not schema or schema == 'public':
        return
    try:
        search_path = f'"{schema}", public'
        db.session.execute(text(f"SET search_path TO {search_path}"))
        db.session.commit()
        logger.debug(f"[TENANT] search_path definido para schema={schema}")
    except Exception as e:
        logger.warning(f"[TENANT] Erro ao definir search_path: {e}")
        db.session.rollback()


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def generate_indices_report(
    self: Task,
    form_id: str,
    filters: Dict[str, Any],
    page: int = 1,
    limit: int = 20,
    schema: Optional[str] = None
) -> Dict[str, Any]:
    """
    Task Celery para gerar relatório de índices gerais.
    
    Args:
        form_id: ID do formulário
        filters: Filtros aplicados
        page: Página para paginação
        limit: Limite de registros
        schema: Nome do schema PostgreSQL do tenant (multi-tenant). Se omitido, usa search_path atual.
    
    Returns:
        Dict com resultado do processamento
    """
    try:
        _set_tenant_schema(schema)
        logger.info(f"[INDICES] Iniciando geração de relatório: form_id={form_id}, filters={filters}")
        
        # Verificar se o formulário existe
        form = Form.query.get(form_id)
        if not form:
            logger.error(f"[INDICES] Formulário {form_id} não encontrado")
            raise ValueError(f"Formulário {form_id} não encontrado")
        
        # Verificar se já existe resultado válido em cache
        cached = ResultsCacheService.get_result(form_id, 'indices', filters)
        if cached:
            logger.info(f"[INDICES] Usando resultado do cache para form_id={form_id}")
            return {
                'success': True,
                'cached': True,
                'result': cached
            }
        
        # Calcular resultado
        logger.info(f"[INDICES] Calculando resultado para form_id={form_id}")
        result = ResultsService.calculate_general_indices(form_id, filters, page, limit)
        
        # Extrair student_count
        student_count = result.get('totalRespostas', 0)
        
        # Salvar no cache
        logger.info(f"[INDICES] Salvando resultado no cache: form_id={form_id}, student_count={student_count}")
        ResultsCacheService.save(
            form_id=form_id,
            report_type='indices',
            filters=filters,
            result=result,
            student_count=student_count,
            commit=True
        )
        
        logger.info(f"[INDICES] Relatório gerado com sucesso: form_id={form_id}")
        return {
            'success': True,
            'cached': False,
            'result': result,
            'student_count': student_count
        }
        
    except Exception as e:
        logger.error(f"[INDICES] Erro ao gerar relatório: {str(e)}", exc_info=True)
        raise self.retry(exc=e)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def generate_profiles_report(
    self: Task,
    form_id: str,
    filters: Dict[str, Any],
    schema: Optional[str] = None
) -> Dict[str, Any]:
    """
    Task Celery para gerar relatório de perfis.
    
    Args:
        form_id: ID do formulário
        filters: Filtros aplicados
        schema: Nome do schema PostgreSQL do tenant (multi-tenant). Se omitido, usa search_path atual.
    
    Returns:
        Dict com resultado do processamento
    """
    try:
        _set_tenant_schema(schema)
        logger.info(f"[PROFILES] Iniciando geração de relatório: form_id={form_id}, filters={filters}")
        
        # Verificar se o formulário existe
        form = Form.query.get(form_id)
        if not form:
            logger.error(f"[PROFILES] Formulário {form_id} não encontrado")
            raise ValueError(f"Formulário {form_id} não encontrado")
        
        # Verificar se já existe resultado válido em cache
        cached = ResultsCacheService.get_result(form_id, 'profiles', filters)
        if cached:
            logger.info(f"[PROFILES] Usando resultado do cache para form_id={form_id}")
            return {
                'success': True,
                'cached': True,
                'result': cached
            }
        
        # Calcular resultado
        logger.info(f"[PROFILES] Calculando resultado para form_id={form_id}")
        result = ResultsService.calculate_profiles_report(form_id, filters)
        
        # Extrair student_count
        student_count = result.get('totalRespostas', 0)
        
        # Salvar no cache
        logger.info(f"[PROFILES] Salvando resultado no cache: form_id={form_id}, student_count={student_count}")
        ResultsCacheService.save(
            form_id=form_id,
            report_type='profiles',
            filters=filters,
            result=result,
            student_count=student_count,
            commit=True
        )
        
        logger.info(f"[PROFILES] Relatório gerado com sucesso: form_id={form_id}")
        return {
            'success': True,
            'cached': False,
            'result': result,
            'student_count': student_count
        }
        
    except Exception as e:
        logger.error(f"[PROFILES] Erro ao gerar relatório: {str(e)}", exc_info=True)
        raise self.retry(exc=e)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def generate_responses_report(
    self: Task,
    form_id: str,
    filters: Dict[str, Any],
    page: int = 1,
    limit: int = 20,
    schema: Optional[str] = None
) -> Dict[str, Any]:
    """
    Task Celery para gerar relatório "Respostas do socioeconômico".
    
    Args:
        form_id: ID do formulário
        filters: Filtros aplicados
        page: Página para listas de alunos
        limit: Limite de alunos por página
        schema: Nome do schema PostgreSQL do tenant (multi-tenant).
    
    Returns:
        Dict com resultado do processamento
    """
    try:
        _set_tenant_schema(schema)
        logger.info(f"[RESPOSTAS] Iniciando geração de relatório: form_id={form_id}, filters={filters}")
        
        form = Form.query.get(form_id)
        if not form:
            logger.error(f"[RESPOSTAS] Formulário {form_id} não encontrado")
            raise ValueError(f"Formulário {form_id} não encontrado")
        
        cached = ResultsCacheService.get_result(form_id, 'respostas', filters)
        if cached:
            logger.info(f"[RESPOSTAS] Usando resultado do cache para form_id={form_id}")
            return {
                'success': True,
                'cached': True,
                'result': cached
            }
        
        logger.info(f"[RESPOSTAS] Calculando resultado para form_id={form_id}")
        result = ResultsService.calculate_responses_report(form_id, filters, page, limit)
        student_count = result.get('totalRespostas', 0)
        
        ResultsCacheService.save(
            form_id=form_id,
            report_type='respostas',
            filters=filters,
            result=result,
            student_count=student_count,
            commit=True
        )
        
        logger.info(f"[RESPOSTAS] Relatório gerado com sucesso: form_id={form_id}")
        return {
            'success': True,
            'cached': False,
            'result': result,
            'student_count': student_count
        }
        
    except Exception as e:
        logger.error(f"[RESPOSTAS] Erro ao gerar relatório: {str(e)}", exc_info=True)
        raise self.retry(exc=e)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def rebuild_results_for_form(self: Task, form_id: str, schema: Optional[str] = None) -> Dict[str, Any]:
    """
    Task helper para rebuild de todos os caches dirty de um formulário.
    Similar ao rebuild_reports_for_test do report_analysis.
    
    Args:
        form_id: ID do formulário
        schema: Nome do schema PostgreSQL do tenant (multi-tenant). Repassado às tasks de índices/perfis.
    
    Returns:
        Dict com resultado do processamento
    """
    try:
        _set_tenant_schema(schema)
        logger.info(f"[REBUILD] Iniciando rebuild para form_id={form_id}")
        
        # Buscar todos os caches dirty deste formulário
        from app.socioeconomic_forms.models import FormResultCache
        dirty_caches = FormResultCache.query.filter_by(
            form_id=form_id,
            is_dirty=True
        ).all()
        
        if not dirty_caches:
            logger.info(f"[REBUILD] Nenhum cache dirty encontrado para form_id={form_id}")
            return {
                'success': True,
                'form_id': form_id,
                'message': 'Nenhum cache precisa de rebuild',
                'caches_processed': 0
            }
        
        # Agendar tasks individuais para cada cache (repassar schema para multi-tenant)
        task_ids = []
        for cache in dirty_caches:
            if cache.report_type == 'indices':
                task = generate_indices_report.delay(form_id, cache.filters, 1, 20, schema)
            elif cache.report_type == 'profiles':
                task = generate_profiles_report.delay(form_id, cache.filters, schema)
            elif cache.report_type == 'respostas':
                task = generate_responses_report.delay(form_id, cache.filters, 1, 20, schema)
            else:
                continue
            
            task_ids.append({
                'report_type': cache.report_type,
                'filters': cache.filters,
                'task_id': task.id
            })
            logger.info(f"[REBUILD] Task agendada: type={cache.report_type}, filters={cache.filters} (task_id={task.id})")
        
        logger.info(f"[REBUILD] Total de {len(task_ids)} tasks agendadas para form_id={form_id}")
        return {
            'success': True,
            'form_id': form_id,
            'caches_processed': len(task_ids),
            'task_ids': task_ids
        }
        
    except Exception as e:
        logger.error(f"[REBUILD] Erro ao agendar rebuild: {str(e)}", exc_info=True)
        raise self.retry(exc=e)
