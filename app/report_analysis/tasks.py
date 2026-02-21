# -*- coding: utf-8 -*-
"""
Tasks Celery para processamento assíncrono de relatórios

==============================================================
RELATÓRIOS QUE USAM ESTE ARQUIVO:
  - Análise das Avaliações  (frontend: AnaliseAvaliacoes / analise-avaliacoes)
  - Relatório Escolar       (frontend: RelatorioEscolar)

RESPONSABILIDADE:
  Executa os cálculos pesados em background (fora da requisição HTTP).
  Disparado pelas rotas em app/report_analysis/routes.py via Celery.

TASKS DISPONÍVEIS:
  rebuild_report_for_scope(test_id, scope_type, scope_id, city_id)
    → recalcula e salva o aggregate no banco para um escopo específico
  trigger_rebuild_if_needed(test_id, scope_type, scope_id, city_id)
    → verifica debounce e, se necessário, dispara rebuild_report_for_scope

ARQUIVOS RELACIONADOS AO SISTEMA DE RELATÓRIOS:
  app/report_analysis/routes.py       → rotas Flask que disparam estas tasks
  app/report_analysis/tasks.py        ← este arquivo
  app/report_analysis/services.py     → ReportAggregateService (leitura/escrita do cache no banco)
  app/report_analysis/calculations.py → re-exporta funções de cálculo de report_routes.py
  app/report_analysis/debounce.py     → debounce Redis (evita tasks duplicadas)
  app/report_analysis/celery_app.py   → configuração do Celery
  app/routes/report_routes.py         → funções de cálculo + _determinar_escopo_por_role
  app/routes/evaluation_results_routes.py → dados tabulares (/avaliacoes e /opcoes-filtros)
==============================================================
"""

import logging
from typing import Optional, Dict, Any
from celery import Task
from sqlalchemy import text

from app.report_analysis.celery_app import celery_app
from app.report_analysis.services import ReportAggregateService
from app.report_analysis.calculations import (
    _calcular_totais_alunos_por_escopo,
    _calcular_niveis_aprendizagem_por_escopo,
    _calcular_proficiencia_por_escopo,
    _calcular_nota_geral_por_escopo,
    _calcular_acertos_habilidade_por_escopo,
    _montar_resposta_relatorio,
    _montar_resposta_relatorio_por_turmas,
    _determinar_escopo_relatorio,
    _buscar_turmas_por_escopo,
)
from app.services.ai_analysis_service import AIAnalysisService
from app.models.test import Test
from app.models.classTest import ClassTest
from app.models.teacherClass import TeacherClass
from app.models.school import School
from app.models.teacher import Teacher
from app.utils.tenant_middleware import city_id_to_schema_name
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


def _get_schema_for_scope(scope_type: str, scope_id: Optional[str]) -> Optional[str]:
    """
    Determina o schema do tenant baseado no scope_type e scope_id.
    
    Args:
        scope_type: Tipo de escopo ('overall', 'city', 'school', 'teacher')
        scope_id: ID do escopo
        
    Returns:
        Nome do schema ou None para 'overall'
    """
    if scope_type == 'overall' or not scope_id:
        return None
    
    if scope_type == 'city':
        return city_id_to_schema_name(scope_id)
    
    elif scope_type == 'school':
        school = School.query.get(scope_id)
        if school and school.city_id:
            return city_id_to_schema_name(school.city_id)
        return None
    
    elif scope_type == 'teacher':
        from app.models.schoolTeacher import SchoolTeacher
        school_teacher = SchoolTeacher.query.filter_by(teacher_id=scope_id).first()
        if school_teacher:
            school = School.query.get(school_teacher.school_id)
            if school and school.city_id:
                return city_id_to_schema_name(school.city_id)
        return None
    
    return None


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def rebuild_report_for_scope(
    self: Task,
    test_id: str,
    scope_type: str,
    scope_id: Optional[str] = None,
    city_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Task Celery para rebuild de um escopo específico.
    
    Executa todos os cálculos pesados e gera análise de IA em background.
    
    Args:
        test_id: ID da avaliação
        scope_type: Tipo de escopo ('overall', 'city', 'school', 'teacher')
        scope_id: ID do escopo (None para 'overall')
        city_id: ID do município. Usado para definir o schema multi-tenant.
                 Obrigatório para 'overall' (que não tem scope_id),
                 e para 'city'/'school' quando já conhecido.
    
    Returns:
        Dict com resultado do processamento
    """
    try:
        print(f"[REBUILD] 🚀 INÍCIO - test_id={test_id}, scope_type={scope_type}, scope_id={scope_id}")
        logger.info(f"Iniciando rebuild de relatório: test_id={test_id}, scope_type={scope_type}, scope_id={scope_id}")
        
        if city_id and scope_type in ('overall', 'city', 'school'):
            schema = city_id_to_schema_name(city_id)
        else:
            schema = _get_schema_for_scope(scope_type, scope_id)
        _set_tenant_schema(schema)
        
        test = Test.query.get(test_id)
        if not test:
            print(f"[REBUILD] ❌ Avaliação {test_id} não encontrada")
            raise ValueError(f"Avaliação {test_id} não encontrada")
        
        scope_type, scope_id = ReportAggregateService._normalize_scope(scope_type, scope_id)

        aggregate_cached = ReportAggregateService.get(test_id, scope_type, scope_id)
        use_cached_payload = bool(
            aggregate_cached
            and not aggregate_cached.is_dirty
            and aggregate_cached.payload
        )

        if use_cached_payload:
            print(f"[REBUILD] 💾 Usando payload do cache para {scope_type}:{scope_id}")
            payload = aggregate_cached.payload or {}
            student_count = (
                payload.get('total_alunos', {})
                .get('total_geral', {})
                .get('avaliados', 0)
            )
        else:
            print(f"[REBUILD] 🔍 Buscando turmas para scope_type={scope_type}, scope_id={scope_id}")
            if scope_type == 'teacher':
                teacher_classes = TeacherClass.query.filter_by(teacher_id=scope_id).all()
                teacher_class_ids = [tc.class_id for tc in teacher_classes]
                class_tests = ClassTest.query.filter(
                    ClassTest.test_id == test_id,
                    ClassTest.class_id.in_(teacher_class_ids)
                ).all()
            else:
                class_tests = _buscar_turmas_por_escopo(test_id, scope_type, scope_id)
            
            print(f"[REBUILD] 📊 Turmas encontradas: {len(class_tests) if class_tests else 0}")
            if not class_tests:
                logger.warning(f"Nenhuma turma encontrada para test_id={test_id}, scope_type={scope_type}, scope_id={scope_id}")
                return {
                    'success': False,
                    'error': 'Nenhuma turma encontrada',
                    'test_id': test_id,
                    'scope_type': scope_type,
                    'scope_id': scope_id
                }
            
            print(f"[REBUILD] 📊 ETAPA 1: Calculando payload para {scope_type}:{scope_id}")
            logger.info(f"Calculando payload para {scope_type}:{scope_id}")
            
            if scope_type == 'teacher':
                from app.routes.report_routes import _montar_resposta_relatorio_por_turmas
                payload = _montar_resposta_relatorio_por_turmas(
                    test_id,
                    class_tests,
                    include_ai=False
                )
            else:
                school_id = scope_id if scope_type == 'school' else None
                city_id = scope_id if scope_type == 'city' else None
                payload = _montar_resposta_relatorio(
                    test_id,
                    school_id=school_id,
                    city_id=city_id,
                    include_ai=False
                )
            
            print(f"[REBUILD] ✅ Payload calculado com sucesso")
            student_count = (
                payload.get('total_alunos', {})
                .get('total_geral', {})
                .get('avaliados', 0)
            )
            print(f"[REBUILD] 📊 Total de alunos: {student_count}")
            
            print(f"[REBUILD] 💾 ETAPA 2: Salvando payload no cache para {scope_type}:{scope_id}")
            logger.info(f"Salvando payload no cache para {scope_type}:{scope_id}")
            ReportAggregateService.save_payload(
                test_id=test_id,
                scope_type=scope_type,
                scope_id=scope_id,
                payload=payload,
                student_count=student_count,
                commit=True
            )
            print(f"[REBUILD] ✅ Payload salvo no cache")
            db.session.expire_all()
        
        print(f"[REBUILD] 🤖 ETAPA 3: Gerando análise de IA para {scope_type}:{scope_id}")
        logger.info(f"Gerando análise de IA para {scope_type}:{scope_id}")
        try:
            ai_service = AIAnalysisService()
            ai_analysis = ai_service.analyze_report_data({
                "avaliacao": payload.get('avaliacao', {}),
                "total_alunos": payload.get('total_alunos', {}),
                "niveis_aprendizagem": payload.get('niveis_aprendizagem', {}),
                "proficiencia": payload.get('proficiencia', {}),
                "nota_geral": payload.get('nota_geral', {}),
                "acertos_por_habilidade": payload.get('acertos_por_habilidade', {}),
                "scope_type": scope_type,
                "scope_id": scope_id
            })
            print(f"[REBUILD] ✅ Análise de IA gerada com sucesso")
            print(f"[REBUILD] 💾 ETAPA 4: Salvando análise de IA no cache para {scope_type}:{scope_id}")
            logger.info(f"Salvando análise de IA no cache para {scope_type}:{scope_id}")
            ReportAggregateService.save_ai_analysis(
                test_id=test_id,
                scope_type=scope_type,
                scope_id=scope_id,
                ai_analysis=ai_analysis,
                commit=True
            )
            print(f"[REBUILD] ✅ Análise de IA salva no cache")
            db.session.expire_all()
        except Exception as e:
            print(f"[REBUILD] ❌ Erro ao gerar análise de IA: {type(e).__name__}: {str(e)}")
            logger.error(f"Erro ao gerar análise de IA para {scope_type}:{scope_id}: {str(e)}", exc_info=True)
            ReportAggregateService.mark_ai_dirty(test_id, scope_type, scope_id, commit=True)
        
        db.session.expire_all()
        final_status = ReportAggregateService.get_status(test_id, scope_type, scope_id)
        print(f"[REBUILD] ✅✅✅ REBUILD CONCLUÍDO - {scope_type}:{scope_id} - status={final_status['status']}")
        logger.info(f"Rebuild concluído com sucesso para {scope_type}:{scope_id}")
        return {
            'success': True,
            'test_id': test_id,
            'scope_type': scope_type,
            'scope_id': scope_id,
            'student_count': student_count,
            'final_status': final_status
        }
        
    except Exception as e:
        print(f"[REBUILD] ❌❌❌ ERRO CRÍTICO: {type(e).__name__}: {str(e)}")
        logger.error(f"Erro ao fazer rebuild de relatório: {str(e)}", exc_info=True)
        raise self.retry(exc=e)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=30)
def rebuild_reports_for_test(self: Task, test_id: str) -> Dict[str, Any]:
    """
    Task Celery para rebuild de todos os escopos de uma avaliação.
    
    Busca todos os escopos existentes (overall, city, school, teacher) e agenda
    tasks individuais para cada um.
    
    Args:
        test_id: ID da avaliação
    
    Returns:
        Dict com resultado do processamento
    """
    try:
        logger.info(f"Iniciando rebuild de todos os escopos para test_id={test_id}")
        
        # Buscar todos os aggregates existentes para esta avaliação
        from app.models.reportAggregate import ReportAggregate
        aggregates = ReportAggregate.query.filter_by(test_id=test_id).all()
        
        if not aggregates:
            # Se não existem aggregates, criar para escopos principais
            logger.info(f"Nenhum aggregate existente. Criando para escopos principais.")
            scopes_to_rebuild = [
                ('overall', None),
            ]
        else:
            # Rebuild apenas dos que estão dirty
            scopes_to_rebuild = []
            for agg in aggregates:
                if agg.is_dirty or agg.ai_analysis_is_dirty:
                    scopes_to_rebuild.append((agg.scope_type, agg.scope_id))
        
        if not scopes_to_rebuild:
            logger.info(f"Nenhum escopo precisa de rebuild para test_id={test_id}")
            return {
                'success': True,
                'test_id': test_id,
                'message': 'Nenhum escopo precisa de rebuild',
                'scopes_processed': 0
            }
        
        # Agendar tasks individuais para cada escopo
        task_ids = []
        for scope_type, scope_id in scopes_to_rebuild:
            task = rebuild_report_for_scope.delay(test_id, scope_type, scope_id)
            task_ids.append({
                'scope_type': scope_type,
                'scope_id': scope_id,
                'task_id': task.id
            })
            logger.info(f"Task agendada para {scope_type}:{scope_id} (task_id={task.id})")
        
        logger.info(f"Total de {len(task_ids)} tasks agendadas para test_id={test_id}")
        return {
            'success': True,
            'test_id': test_id,
            'scopes_processed': len(task_ids),
            'task_ids': task_ids
        }
        
    except Exception as e:
        logger.error(f"Erro ao agendar rebuild de relatórios: {str(e)}", exc_info=True)
        raise self.retry(exc=e)


@celery_app.task(bind=True, max_retries=1, default_retry_delay=30)
def trigger_rebuild_if_needed(
    self: Task,
    test_id: str,
    scope_type: str,
    scope_id: Optional[str] = None,
    city_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Task helper que verifica se precisa rebuild e agenda se necessário.
    Usa debounce para evitar múltiplas execuções.
    
    Args:
        test_id: ID da avaliação
        scope_type: Tipo de escopo
        scope_id: ID do escopo
        city_id: ID do município (opcional). Se informado para scope city/school,
                 define o schema sem consultar School (evita relation "school" does not exist).
    
    Returns:
        Dict com resultado
    """
    print(f"[TRIGGER_REBUILD] 🚀 INÍCIO - test_id={test_id}, scope_type={scope_type}, scope_id={scope_id}, city_id={city_id}")
    
    from app.report_analysis.debounce import ReportDebounceService
    
    if city_id and scope_type in ('overall', 'city', 'school'):
        schema = city_id_to_schema_name(city_id)
    else:
        schema = _get_schema_for_scope(scope_type, scope_id)
    _set_tenant_schema(schema)
    
    should_trigger = ReportDebounceService.should_trigger_rebuild(test_id, scope_type=scope_type, scope_id=scope_id)
    if not should_trigger:
        print(f"[TRIGGER_REBUILD] ⏸️ Rebuild em debounce para {scope_type}:{scope_id}. Ignorando.")
        logger.info(f"Rebuild em debounce para test_id={test_id}. Ignorando.")
        return {
            'success': False,
            'message': 'Rebuild em debounce',
            'test_id': test_id
        }
    
    aggregate = ReportAggregateService.get(test_id, scope_type, scope_id)
    needs_rebuild = (
        not aggregate or 
        aggregate.is_dirty or 
        aggregate.ai_analysis_is_dirty
    )
    print(f"[TRIGGER_REBUILD] 📊 Precisa rebuild: {needs_rebuild}")
    
    if not needs_rebuild:
        print(f"[TRIGGER_REBUILD] ✅ Relatório já está atualizado para {scope_type}:{scope_id}")
        logger.info(f"Relatório já está atualizado para {scope_type}:{scope_id}")
        return {
            'success': True,
            'message': 'Relatório já está atualizado',
            'test_id': test_id,
            'scope_type': scope_type,
            'scope_id': scope_id
        }
    
    try:
        task = rebuild_report_for_scope.delay(test_id, scope_type, scope_id, city_id)
        print(f"[TRIGGER_REBUILD] ✅ Rebuild agendado! Task ID: {task.id}")
        logger.info(f"Rebuild agendado para {scope_type}:{scope_id} (task_id={task.id})")
    except Exception as e:
        print(f"[TRIGGER_REBUILD] ❌ Erro ao agendar rebuild: {type(e).__name__}: {str(e)}")
        logger.error(f"Erro ao agendar rebuild: {type(e).__name__}: {str(e)}")
        raise
    
    return {
        'success': True,
        'message': 'Rebuild agendado',
        'test_id': test_id,
        'scope_type': scope_type,
        'scope_id': scope_id,
        'task_id': task.id
    }

