# -*- coding: utf-8 -*-
"""
Tasks Celery para processamento assíncrono de relatórios
"""

import logging
from typing import Optional, Dict, Any
from celery import Task

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

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def rebuild_report_for_scope(
    self: Task,
    test_id: str,
    scope_type: str,
    scope_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Task Celery para rebuild de um escopo específico.
    
    Executa todos os cálculos pesados e gera análise de IA em background.
    
    Args:
        test_id: ID da avaliação
        scope_type: Tipo de escopo ('overall', 'city', 'school', 'teacher')
        scope_id: ID do escopo (None para 'overall')
    
    Returns:
        Dict com resultado do processamento
    """
    try:
        logger.info(f"Iniciando rebuild de relatório: test_id={test_id}, scope_type={scope_type}, scope_id={scope_id}")
        
        # Verificar se a avaliação existe
        test = Test.query.get(test_id)
        if not test:
            raise ValueError(f"Avaliação {test_id} não encontrada")
        
        # Normalizar escopo
        scope_type, scope_id = ReportAggregateService._normalize_scope(scope_type, scope_id)
        
        # Buscar turmas conforme o escopo
        if scope_type == 'teacher':
            # Para professor, buscar turmas específicas
            teacher_classes = TeacherClass.query.filter_by(teacher_id=scope_id).all()
            teacher_class_ids = [tc.class_id for tc in teacher_classes]
            class_tests = ClassTest.query.filter(
                ClassTest.test_id == test_id,
                ClassTest.class_id.in_(teacher_class_ids)
            ).all()
        else:
            # Para outros escopos, usar função existente
            school_id = scope_id if scope_type == 'school' else None
            city_id = scope_id if scope_type == 'city' else None
            _, normalized_scope_id = _determinar_escopo_relatorio(school_id, city_id)
            class_tests = _buscar_turmas_por_escopo(test_id, scope_type, normalized_scope_id)
        
        if not class_tests:
            logger.warning(f"Nenhuma turma encontrada para test_id={test_id}, scope_type={scope_type}, scope_id={scope_id}")
            return {
                'success': False,
                'error': 'Nenhuma turma encontrada',
                'test_id': test_id,
                'scope_type': scope_type,
                'scope_id': scope_id
            }
        
        # 1. Calcular payload (dados agregados)
        logger.info(f"Calculando payload para {scope_type}:{scope_id}")
        
        if scope_type == 'teacher':
            # Para professor, usar função específica
            from app.routes.report_routes import _montar_resposta_relatorio_por_turmas
            payload = _montar_resposta_relatorio_por_turmas(
                test_id,
                class_tests,
                include_ai=False  # IA será gerada separadamente
            )
        else:
            # Para outros escopos
            school_id = scope_id if scope_type == 'school' else None
            city_id = scope_id if scope_type == 'city' else None
            payload = _montar_resposta_relatorio(
                test_id,
                school_id=school_id,
                city_id=city_id,
                include_ai=False  # IA será gerada separadamente
            )
        
        # Extrair student_count
        student_count = (
            payload.get('total_alunos', {})
            .get('total_geral', {})
            .get('avaliados', 0)
        )
        
        # 2. Salvar payload no cache
        logger.info(f"Salvando payload no cache para {scope_type}:{scope_id}")
        ReportAggregateService.save_payload(
            test_id=test_id,
            scope_type=scope_type,
            scope_id=scope_id,
            payload=payload,
            student_count=student_count,
            commit=True
        )
        
        # 3. Gerar análise de IA
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
            
            # 4. Salvar análise de IA no cache
            logger.info(f"Salvando análise de IA no cache para {scope_type}:{scope_id}")
            ReportAggregateService.save_ai_analysis(
                test_id=test_id,
                scope_type=scope_type,
                scope_id=scope_id,
                ai_analysis=ai_analysis,
                commit=True
            )
        except Exception as e:
            logger.error(f"Erro ao gerar análise de IA para {scope_type}:{scope_id}: {str(e)}", exc_info=True)
            # Continuar mesmo se IA falhar (payload já foi salvo)
            # Marcar IA como dirty para tentar novamente depois
            ReportAggregateService.mark_ai_dirty(test_id, scope_type, scope_id, commit=True)
        
        logger.info(f"Rebuild concluído com sucesso para {scope_type}:{scope_id}")
        return {
            'success': True,
            'test_id': test_id,
            'scope_type': scope_type,
            'scope_id': scope_id,
            'student_count': student_count
        }
        
    except Exception as e:
        logger.error(f"Erro ao fazer rebuild de relatório: {str(e)}", exc_info=True)
        # Retry automático
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
    scope_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Task helper que verifica se precisa rebuild e agenda se necessário.
    Usa debounce para evitar múltiplas execuções.
    
    Args:
        test_id: ID da avaliação
        scope_type: Tipo de escopo
        scope_id: ID do escopo
    
    Returns:
        Dict com resultado
    """
    from app.report_analysis.debounce import ReportDebounceService
    
    # Verificar debounce
    if not ReportDebounceService.should_trigger_rebuild(test_id):
        logger.info(f"Rebuild em debounce para test_id={test_id}. Ignorando.")
        return {
            'success': False,
            'message': 'Rebuild em debounce',
            'test_id': test_id
        }
    
    # Verificar se precisa rebuild
    aggregate = ReportAggregateService.get(test_id, scope_type, scope_id)
    needs_rebuild = (
        not aggregate or 
        aggregate.is_dirty or 
        aggregate.ai_analysis_is_dirty
    )
    
    if not needs_rebuild:
        logger.info(f"Relatório já está atualizado para {scope_type}:{scope_id}")
        return {
            'success': True,
            'message': 'Relatório já está atualizado',
            'test_id': test_id,
            'scope_type': scope_type,
            'scope_id': scope_id
        }
    
    # Agendar rebuild
    task = rebuild_report_for_scope.delay(test_id, scope_type, scope_id)
    logger.info(f"Rebuild agendado para {scope_type}:{scope_id} (task_id={task.id})")
    
    return {
        'success': True,
        'message': 'Rebuild agendado',
        'test_id': test_id,
        'scope_type': scope_type,
        'scope_id': scope_id,
        'task_id': task.id
    }

