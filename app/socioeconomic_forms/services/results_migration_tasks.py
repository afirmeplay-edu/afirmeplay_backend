# -*- coding: utf-8 -*-
"""
Tasks Celery para popular cache inicial de resultados de formulários socioeconômicos existentes.
Task de migração para formulários que já têm respostas mas não têm cache.
Em ambiente multi-tenant, o schema deve ser passado (search_path).
"""

import logging
from typing import Dict, Any, List, Optional
from celery import Task

from app.report_analysis.celery_app import celery_app
from app.socioeconomic_forms.models import Form, FormResponse, FormResultCache
from app.socioeconomic_forms.services.results_service import ResultsService
from app.socioeconomic_forms.services.results_cache_service import ResultsCacheService
from app.socioeconomic_forms.services.results_tasks import (
    _set_tenant_schema,
    generate_indices_report,
    generate_profiles_report,
)
from app.models import Student, School, City
from app import db

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=1, default_retry_delay=60)
def populate_initial_cache_for_form(
    self: Task,
    form_id: str,
    schema: Optional[str] = None
) -> Dict[str, Any]:
    """
    Task para popular cache inicial de um formulário específico.
    Identifica os filtros únicos aplicados e gera resultados para cada combinação.
    
    Args:
        form_id: ID do formulário
        schema: Nome do schema PostgreSQL do tenant (multi-tenant).
    
    Returns:
        Dict com resultado do processamento
    """
    try:
        _set_tenant_schema(schema)
        logger.info(f"[POPULATE] Iniciando população de cache para form_id={form_id}")
        
        form = Form.query.get(form_id)
        if not form:
            logger.error(f"[POPULATE] Formulário {form_id} não encontrado")
            raise ValueError(f"Formulário {form_id} não encontrado")
        
        # Verificar se tem respostas
        responses_count = FormResponse.query.filter_by(
            form_id=form_id,
            status='completed'
        ).count()
        
        if responses_count == 0:
            logger.info(f"[POPULATE] Formulário {form_id} não tem respostas completas. Pulando.")
            return {
                'success': True,
                'form_id': form_id,
                'message': 'Nenhuma resposta completa encontrada',
                'caches_created': 0
            }
        
        logger.info(f"[POPULATE] Formulário {form_id} tem {responses_count} respostas completas")
        
        # Identificar filtros únicos a processar
        filter_combinations = _identify_filter_combinations(form)
        
        logger.info(f"[POPULATE] Identificadas {len(filter_combinations)} combinações de filtros")
        
        # Agendar tasks para cada combinação de filtros
        tasks_created = []
        for filters in filter_combinations:
            # Verificar se já existe cache para esta combinação
            existing_cache = ResultsCacheService.get(form_id, 'indices', filters)
            if existing_cache and not existing_cache.is_dirty:
                logger.info(f"[POPULATE] Cache já existe para {filters}. Pulando.")
                continue
            
            # Agendar tasks para indices e profiles (repassar schema para multi-tenant)
            try:
                task_indices = generate_indices_report.delay(form_id, filters, 1, 20, schema)
                task_profiles = generate_profiles_report.delay(form_id, filters, schema)
                
                tasks_created.append({
                    'filters': filters,
                    'task_indices_id': task_indices.id,
                    'task_profiles_id': task_profiles.id
                })
                
                logger.info(f"[POPULATE] Tasks agendadas para filters={filters}")
            except Exception as e:
                logger.error(f"[POPULATE] Erro ao agendar tasks para {filters}: {str(e)}")
        
        logger.info(f"[POPULATE] Total de {len(tasks_created)} pares de tasks agendadas para form_id={form_id}")
        
        return {
            'success': True,
            'form_id': form_id,
            'responses_count': responses_count,
            'filter_combinations': len(filter_combinations),
            'tasks_created': len(tasks_created),
            'tasks': tasks_created
        }
        
    except Exception as e:
        logger.error(f"[POPULATE] Erro ao popular cache: {str(e)}", exc_info=True)
        raise self.retry(exc=e)


@celery_app.task(bind=True, max_retries=1, default_retry_delay=120)
def populate_all_forms_cache(self: Task, schema: Optional[str] = None) -> Dict[str, Any]:
    """
    Task para popular cache inicial de TODOS os formulários que têm respostas (no tenant).
    Use com cuidado - pode gerar muitas tasks.
    
    Args:
        schema: Nome do schema PostgreSQL do tenant (multi-tenant).
    
    Returns:
        Dict com resultado do processamento
    """
    try:
        _set_tenant_schema(schema)
        logger.info("[POPULATE_ALL] Iniciando população de cache para todos os formulários")
        
        # Buscar todos os formulários que têm respostas completas
        forms_with_responses = db.session.query(Form.id, db.func.count(FormResponse.id).label('response_count'))\
            .join(FormResponse, Form.id == FormResponse.form_id)\
            .filter(FormResponse.status == 'completed')\
            .group_by(Form.id)\
            .having(db.func.count(FormResponse.id) > 0)\
            .all()
        
        total_forms = len(forms_with_responses)
        logger.info(f"[POPULATE_ALL] Encontrados {total_forms} formulários com respostas completas")
        
        if total_forms == 0:
            return {
                'success': True,
                'message': 'Nenhum formulário com respostas encontrado',
                'forms_processed': 0
            }
        
        # Agendar task individual para cada formulário (repassar schema)
        tasks_created = []
        for form_id, response_count in forms_with_responses:
            try:
                task = populate_initial_cache_for_form.delay(form_id, schema)
                tasks_created.append({
                    'form_id': form_id,
                    'response_count': response_count,
                    'task_id': task.id
                })
                logger.info(f"[POPULATE_ALL] Task agendada para form_id={form_id} ({response_count} respostas)")
            except Exception as e:
                logger.error(f"[POPULATE_ALL] Erro ao agendar task para form_id={form_id}: {str(e)}")
        
        logger.info(f"[POPULATE_ALL] Total de {len(tasks_created)} tasks agendadas")
        
        return {
            'success': True,
            'total_forms': total_forms,
            'tasks_created': len(tasks_created),
            'tasks': tasks_created
        }
        
    except Exception as e:
        logger.error(f"[POPULATE_ALL] Erro ao popular cache de todos os formulários: {str(e)}", exc_info=True)
        raise self.retry(exc=e)


def _identify_filter_combinations(form: Form) -> List[Dict[str, Any]]:
    """
    Identifica combinações de filtros únicos para gerar resultados.
    
    Estratégia:
    1. Se Form.filters existe e está preenchido, usar como base
    2. Caso contrário, construir baseado em selected_schools/selected_grades
    3. Gerar combinações hierárquicas:
       - Geral (estado + município)
       - Por escola (se múltiplas escolas)
       - Por série (se múltiplas séries)
    
    Args:
        form: Objeto Form
    
    Returns:
        Lista de dicionários com filtros
    """
    combinations = []
    
    # Caso 1: Form tem filters preenchido
    if form.filters and (form.filters.get('estado') or form.filters.get('municipio')):
        logger.info(f"[IDENTIFY] Form {form.id} tem filters: {form.filters}")
        
        # Combinação base (geral)
        base_filters = {
            'state': form.filters.get('estado'),
            'municipio': form.filters.get('municipio')
        }
        combinations.append({k: v for k, v in base_filters.items() if v})
        
        # Se tem escola específica nos filters, adicionar
        if form.filters.get('escola'):
            school_filters = base_filters.copy()
            school_filters['escola'] = form.filters['escola']
            combinations.append({k: v for k, v in school_filters.items() if v})
            
            # Se tem série, adicionar
            if form.filters.get('serie'):
                grade_filters = school_filters.copy()
                grade_filters['serie'] = form.filters['serie']
                combinations.append({k: v for k, v in grade_filters.items() if v})
    
    # Caso 2: Form não tem filters, construir baseado em selected_*
    else:
        logger.info(f"[IDENTIFY] Form {form.id} NÃO tem filters. Construindo baseado em selected_*")
        
        # Buscar estado e município da primeira escola
        if form.selected_schools and len(form.selected_schools) > 0:
            first_school_id = form.selected_schools[0]
            school = School.query.get(first_school_id)
            
            if school and school.city_id:
                city = City.query.get(school.city_id)
                
                if city:
                    # Combinação base (geral)
                    base_filters = {
                        'state': city.state,
                        'municipio': city.id
                    }
                    combinations.append(base_filters)
                    
                    # Adicionar combinação para cada escola
                    for school_id in form.selected_schools[:5]:  # Limitar a 5 escolas
                        school_filters = base_filters.copy()
                        school_filters['escola'] = school_id
                        combinations.append(school_filters)
                        
                        # Se tem séries, adicionar combinação escola + série
                        if form.selected_grades:
                            for grade_id in form.selected_grades[:3]:  # Limitar a 3 séries
                                grade_filters = school_filters.copy()
                                grade_filters['serie'] = grade_id
                                combinations.append(grade_filters)
    
    # Remover duplicatas
    unique_combinations = []
    seen = set()
    for combo in combinations:
        # Criar chave única baseada nos valores
        key = tuple(sorted(combo.items()))
        if key not in seen:
            seen.add(key)
            unique_combinations.append(combo)
    
    logger.info(f"[IDENTIFY] Total de {len(unique_combinations)} combinações únicas identificadas")
    
    return unique_combinations
