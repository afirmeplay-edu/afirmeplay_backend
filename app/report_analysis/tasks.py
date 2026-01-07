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
from app import db

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
        print(f"[REBUILD] 🚀 INÍCIO - test_id={test_id}, scope_type={scope_type}, scope_id={scope_id}")
        logger.info(f"Iniciando rebuild de relatório: test_id={test_id}, scope_type={scope_type}, scope_id={scope_id}")
        
        # Verificar se a avaliação existe
        print(f"[REBUILD] 🔍 Verificando se avaliação existe: test_id={test_id}")
        test = Test.query.get(test_id)
        if not test:
            print(f"[REBUILD] ❌ Avaliação {test_id} não encontrada")
            raise ValueError(f"Avaliação {test_id} não encontrada")
        print(f"[REBUILD] ✅ Avaliação encontrada: {test.name if hasattr(test, 'name') else 'N/A'}")
        
        # Normalizar escopo
        print(f"[REBUILD] 🔄 Normalizando escopo: scope_type={scope_type}, scope_id={scope_id}")
        scope_type, scope_id = ReportAggregateService._normalize_scope(scope_type, scope_id)
        print(f"[REBUILD] ✅ Escopo normalizado: scope_type={scope_type}, scope_id={scope_id}")
        
        # Buscar turmas conforme o escopo
        print(f"[REBUILD] 🔍 Buscando turmas para scope_type={scope_type}, scope_id={scope_id}")
        if scope_type == 'teacher':
            # Para professor, buscar turmas específicas
            print(f"[REBUILD] 👨‍🏫 Buscando turmas do professor: scope_id={scope_id}")
            teacher_classes = TeacherClass.query.filter_by(teacher_id=scope_id).all()
            teacher_class_ids = [tc.class_id for tc in teacher_classes]
            print(f"[REBUILD] 📊 Turmas do professor encontradas: {len(teacher_class_ids)}")
            class_tests = ClassTest.query.filter(
                ClassTest.test_id == test_id,
                ClassTest.class_id.in_(teacher_class_ids)
            ).all()
        else:
            # Para outros escopos, usar função existente
            # CORRIGIDO: Para 'overall', scope_id é None. Para 'city' e 'school', usar scope_id diretamente
            print(f"[REBUILD] 🌐 Buscando turmas por escopo: scope_type={scope_type}, scope_id={scope_id}")
            class_tests = _buscar_turmas_por_escopo(test_id, scope_type, scope_id)
        
        print(f"[REBUILD] 📊 Total de turmas encontradas: {len(class_tests) if class_tests else 0}")
        if not class_tests:
            print(f"[REBUILD] ⚠️ Nenhuma turma encontrada para test_id={test_id}, scope_type={scope_type}, scope_id={scope_id}")
            logger.warning(f"Nenhuma turma encontrada para test_id={test_id}, scope_type={scope_type}, scope_id={scope_id}")
            return {
                'success': False,
                'error': 'Nenhuma turma encontrada',
                'test_id': test_id,
                'scope_type': scope_type,
                'scope_id': scope_id
            }
        
        # 1. Calcular payload (dados agregados)
        print(f"[REBUILD] 📊 ETAPA 1: Calculando payload para {scope_type}:{scope_id}")
        logger.info(f"Calculando payload para {scope_type}:{scope_id}")
        
        if scope_type == 'teacher':
            # Para professor, usar função específica
            print(f"[REBUILD] 👨‍🏫 Usando _montar_resposta_relatorio_por_turmas para professor")
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
            print(f"[REBUILD] 🌐 Usando _montar_resposta_relatorio: school_id={school_id}, city_id={city_id}")
            payload = _montar_resposta_relatorio(
                test_id,
                school_id=school_id,
                city_id=city_id,
                include_ai=False  # IA será gerada separadamente
            )
        
        print(f"[REBUILD] ✅ Payload calculado com sucesso")
        
        # Extrair student_count
        student_count = (
            payload.get('total_alunos', {})
            .get('total_geral', {})
            .get('avaliados', 0)
        )
        print(f"[REBUILD] 📊 Total de alunos: {student_count}")
        
        # 2. Salvar payload no cache
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
        
        # Verificar se foi realmente salvo (forçar refresh)
        db.session.expire_all()
        aggregate_check = ReportAggregateService.get(test_id, scope_type, scope_id)
        print(f"[REBUILD] 🔍 Verificação payload: is_dirty={aggregate_check.is_dirty if aggregate_check else 'None'}, has_payload={bool(aggregate_check.payload) if aggregate_check else False}")
        
        # 3. Gerar análise de IA
        print(f"[REBUILD] 🤖 ETAPA 3: Gerando análise de IA para {scope_type}:{scope_id}")
        logger.info(f"Gerando análise de IA para {scope_type}:{scope_id}")
        try:
            print(f"[REBUILD] 🤖 Inicializando AIAnalysisService")
            ai_service = AIAnalysisService()
            print(f"[REBUILD] 🤖 Chamando analyze_report_data")
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
            
            # 4. Salvar análise de IA no cache
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
            
            # Verificar se foi realmente salvo (forçar refresh)
            db.session.expire_all()
            aggregate_check = ReportAggregateService.get(test_id, scope_type, scope_id)
            print(f"[REBUILD] 🔍 Verificação IA: ai_analysis_is_dirty={aggregate_check.ai_analysis_is_dirty if aggregate_check else 'None'}, has_ai_analysis={bool(aggregate_check.ai_analysis) if aggregate_check else False}")
        except Exception as e:
            print(f"[REBUILD] ❌ Erro ao gerar análise de IA: {type(e).__name__}: {str(e)}")
            logger.error(f"Erro ao gerar análise de IA para {scope_type}:{scope_id}: {str(e)}", exc_info=True)
            # Continuar mesmo se IA falhar (payload já foi salvo)
            # Marcar IA como dirty para tentar novamente depois
            print(f"[REBUILD] 🔄 Marcando IA como dirty para retry posterior")
            ReportAggregateService.mark_ai_dirty(test_id, scope_type, scope_id, commit=True)
        
        # Verificação final do status após tudo ser salvo
        db.session.expire_all()  # Garantir que estamos lendo dados frescos do banco
        final_status = ReportAggregateService.get_status(test_id, scope_type, scope_id)
        print(f"[REBUILD] 🔍 Status final: status={final_status['status']}, is_dirty={final_status['is_dirty']}, ai_dirty={final_status['ai_analysis_is_dirty']}")
        print(f"[REBUILD] 🔍 Status final: has_payload={final_status['has_payload']}, has_ai_analysis={final_status['has_ai_analysis']}")
        
        print(f"[REBUILD] ✅✅✅ REBUILD CONCLUÍDO COM SUCESSO para {scope_type}:{scope_id}")
        logger.info(f"Rebuild concluído com sucesso para {scope_type}:{scope_id}")
        return {
            'success': True,
            'test_id': test_id,
            'scope_type': scope_type,
            'scope_id': scope_id,
            'student_count': student_count,
            'final_status': final_status  # Incluir status final no retorno
        }
        
    except Exception as e:
        print(f"[REBUILD] ❌❌❌ ERRO CRÍTICO: {type(e).__name__}: {str(e)}")
        logger.error(f"Erro ao fazer rebuild de relatório: {str(e)}", exc_info=True)
        # Retry automático
        print(f"[REBUILD] 🔄 Tentando retry...")
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
    print(f"[TRIGGER_REBUILD] 🚀 INÍCIO - test_id={test_id}, scope_type={scope_type}, scope_id={scope_id}")
    
    from app.report_analysis.debounce import ReportDebounceService
    
    # Verificar debounce
    print(f"[TRIGGER_REBUILD] 🔍 Verificando debounce para test_id={test_id}")
    should_trigger = ReportDebounceService.should_trigger_rebuild(test_id)
    print(f"[TRIGGER_REBUILD] 📊 Resultado debounce: {should_trigger}")
    
    if not should_trigger:
        print(f"[TRIGGER_REBUILD] ⏸️ Rebuild em debounce para test_id={test_id}. Ignorando.")
        logger.info(f"Rebuild em debounce para test_id={test_id}. Ignorando.")
        return {
            'success': False,
            'message': 'Rebuild em debounce',
            'test_id': test_id
        }
    
    # Verificar se precisa rebuild
    print(f"[TRIGGER_REBUILD] 🔍 Verificando se precisa rebuild - test_id={test_id}, scope_type={scope_type}, scope_id={scope_id}")
    aggregate = ReportAggregateService.get(test_id, scope_type, scope_id)
    print(f"[TRIGGER_REBUILD] 📊 Aggregate encontrado: {aggregate is not None}")
    
    if aggregate:
        print(f"[TRIGGER_REBUILD] 📊 Aggregate.is_dirty: {aggregate.is_dirty}")
        print(f"[TRIGGER_REBUILD] 📊 Aggregate.ai_analysis_is_dirty: {aggregate.ai_analysis_is_dirty}")
    
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
    
    # Agendar rebuild
    print(f"[TRIGGER_REBUILD] 📤 Agendando rebuild_report_for_scope.delay({test_id}, {scope_type}, {scope_id})")
    try:
        task = rebuild_report_for_scope.delay(test_id, scope_type, scope_id)
        print(f"[TRIGGER_REBUILD] ✅ Rebuild agendado com sucesso! Task ID: {task.id}")
        logger.info(f"Rebuild agendado para {scope_type}:{scope_id} (task_id={task.id})")
    except Exception as e:
        print(f"[TRIGGER_REBUILD] ❌ Erro ao agendar rebuild: {type(e).__name__}: {str(e)}")
        raise
    
    return {
        'success': True,
        'message': 'Rebuild agendado',
        'test_id': test_id,
        'scope_type': scope_type,
        'scope_id': scope_id,
        'task_id': task.id
    }

