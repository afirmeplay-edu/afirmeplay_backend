# -*- coding: utf-8 -*-
"""
Rotas refatoradas para relatórios com processamento assíncrono
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from app.permissions import role_required, get_current_user_from_token
from app.models.test import Test
from app.models.classTest import ClassTest
from app.models.school import School
from app.permissions.utils import get_teacher_classes, get_manager_school, get_teacher
from app.permissions.rules import can_view_test
from app.routes.report_routes import _determinar_escopo_por_role
import logging

from app.report_analysis.services import ReportAggregateService
from app.report_analysis.tasks import trigger_rebuild_if_needed
from app.report_analysis.tasks import _get_schema_for_scope
from app.utils.tenant_middleware import city_id_to_schema_name, set_search_path, get_current_tenant_context
from app import db

logger = logging.getLogger(__name__)


def _resolve_report_schema(scope_type: str, scope_ref_id, city_id_from_request: str = None):
    """
    Resolve o schema PostgreSQL para as rotas de relatório (multi-tenant).
    Deve ser chamado antes de qualquer query a Test/ClassTest/etc.
    Retorna None se não for possível determinar o schema (ex.: admin sem city_id/school_id).
    """
    if scope_type == 'all' or scope_type == 'overall' or not scope_ref_id:
        return None
    if scope_type == 'city':
        return city_id_to_schema_name(scope_ref_id)
    if scope_type == 'school':
        if city_id_from_request:
            return city_id_to_schema_name(city_id_from_request)
        return _get_schema_for_scope(scope_type, scope_ref_id)
    if scope_type == 'teacher':
        return _get_schema_for_scope(scope_type, scope_ref_id)
    return None

# Criar blueprint
bp = Blueprint('report_analysis', __name__, url_prefix='/reports')


@bp.route('/dados-json/<string:evaluation_id>', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def dados_json(evaluation_id: str):
    """
    Retorna os dados do relatório em JSON formatado para o frontend.
    
    REFATORADO: Não executa cálculos pesados. Apenas retorna cache ou status.
    
    Args:
        evaluation_id: ID da avaliação
    
    Query Parameters:
        school_id: ID da escola (opcional)
        city_id: ID do município (opcional)
    
    Returns:
        - HTTP 200: Relatório pronto com dados completos
        - HTTP 202: Relatório sendo processado (status: "processing")
        - HTTP 404: Avaliação não encontrada ou sem permissão
    """
    try:
        # Obter usuário e escopo primeiro (multi-tenant: schema deve ser definido antes de query em Test)
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não autenticado"}), 401
        
        school_id_raw = request.args.get('school_id')
        city_id = request.args.get('city_id')
        
        try:
            scope_type, scope_ref_id = _determinar_escopo_por_role(user, school_id_raw, city_id)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        
        schema = _resolve_report_schema(scope_type, scope_ref_id, city_id)
        if not schema:
            return jsonify({
                "error": "Para acessar o relatório, informe city_id ou school_id na URL (ex.: ?city_id=... ou ?school_id=...)"
            }), 400
        
        set_search_path(schema)
        
        # Para school scope, o frontend nunca envia city_id na URL.
        # Recuperamos o city_id da escola agora que o search_path já está correto.
        if scope_type == 'school' and not city_id:
            school_obj = School.query.get(scope_ref_id)
            if school_obj and school_obj.city_id:
                city_id = school_obj.city_id
        
        # Verificar se a avaliação existe
        test = Test.query.get(evaluation_id)
        if not test:
            return jsonify({"error": "Avaliação não encontrada"}), 404
        
        # Para professores, verificar permissões
        if scope_type == 'teacher':
            if not can_view_test(user, evaluation_id):
                return jsonify({"error": "Acesso negado: você não tem permissão para ver esta avaliação"}), 403
            
            teacher_class_ids = get_teacher_classes(user.get('id'))
            if not teacher_class_ids:
                return jsonify({"error": "Professor não vinculado a nenhuma turma"}), 404
            
            class_tests = ClassTest.query.filter(
                ClassTest.test_id == evaluation_id,
                ClassTest.class_id.in_(teacher_class_ids)
            ).all()
            
            if not class_tests:
                return jsonify({"error": "Avaliação não foi aplicada em nenhuma turma do professor"}), 404
        
        # Verificar status do relatório
        # Forçar refresh para garantir que estamos lendo dados atualizados do banco
        # Isso resolve problemas de cache quando o worker atualiza os dados
        db.session.expire_all()
        aggregate = ReportAggregateService.get(evaluation_id, scope_type, scope_ref_id)
        status = ReportAggregateService.get_status(evaluation_id, scope_type, scope_ref_id)
        
        # Se não está pronto, disparar task (com debounce) e retornar status
        if status['status'] != 'ready':
            print(f"[ROUTES] 🔄 Relatório não está pronto para {scope_type}:{scope_ref_id}. Disparando rebuild.")
            logger.info(f"Relatório não está pronto para {scope_type}:{scope_ref_id}. Disparando rebuild.")
            
            # Disparar task assíncrona (com debounce). Passar city_id para scope school/city evita query em School no worker.
            city_id_for_task = (
                city_id                                            # admin passa pela URL
                or (scope_ref_id if scope_type == 'city' else None)  # escopo city: scope_ref_id já é city_id
                or user.get('city_id')                             # diretor/coordenador/professor: city_id do token
            )
            try:
                print(f"[ROUTES] 📤 Enviando task trigger_rebuild_if_needed.delay({evaluation_id}, {scope_type}, {scope_ref_id}, city_id={city_id_for_task})")
                task_result = trigger_rebuild_if_needed.delay(evaluation_id, scope_type, scope_ref_id, city_id_for_task)
                print(f"[ROUTES] ✅ Task enviada com sucesso! Task ID: {task_result.id}")
            except Exception as e:
                print(f"[ROUTES] ❌ Erro ao disparar task de rebuild: {type(e).__name__}: {str(e)}")
                logger.error(f"Erro ao disparar task de rebuild: {str(e)}")
                # Continuar mesmo se falhar (pode ser que Redis não esteja disponível)
            
            return jsonify({
                "status": "processing",
                "message": "Relatório sendo processado em background",
                "has_payload": status['has_payload'],
                "has_ai_analysis": status['has_ai_analysis'],
                "is_dirty": status['is_dirty'],
                "ai_analysis_is_dirty": status['ai_analysis_is_dirty'],
                "last_update": status['last_update'].isoformat() if status['last_update'] else None,
                "evaluation_id": evaluation_id,
                "scope_type": scope_type,
                "scope_id": scope_ref_id
            }), 202  # HTTP 202 Accepted
        
        # Relatório está pronto - retornar dados
        payload = aggregate.payload or {}
        ai_analysis = aggregate.ai_analysis or {}
        
        # Adicionar análise de IA ao payload
        payload['analise_ia'] = ai_analysis
        
        return jsonify({
            "status": "ready",
            **payload
        }), 200
        
    except Exception as e:
        logger.error(f"Erro ao gerar dados JSON do relatório: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro interno do servidor", "details": str(e)}), 500


@bp.route('/status/<string:evaluation_id>', methods=['GET'])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def get_report_status(evaluation_id: str):
    """
    Retorna apenas o status do relatório (útil para polling).
    
    Args:
        evaluation_id: ID da avaliação
    
    Query Parameters:
        school_id: ID da escola (opcional)
        city_id: ID do município (opcional)
    
    Returns:
        JSON com status do relatório
    """
    try:
        # Obter usuário e parâmetros primeiro (multi-tenant: schema deve ser definido antes de query em Test)
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não autenticado"}), 401
        
        school_id_raw = request.args.get('school_id')
        city_id = request.args.get('city_id')
        
        try:
            scope_type, scope_ref_id = _determinar_escopo_por_role(user, school_id_raw, city_id)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        
        schema = _resolve_report_schema(scope_type, scope_ref_id, city_id)
        if not schema:
            return jsonify({
                "error": "Para acessar o relatório, informe city_id ou school_id na URL (ex.: ?city_id=... ou ?school_id=...)"
            }), 400
        
        set_search_path(schema)
        
        # Para school scope, o frontend nunca envia city_id na URL.
        # Recuperamos o city_id da escola agora que o search_path já está correto.
        if scope_type == 'school' and not city_id:
            school_obj = School.query.get(scope_ref_id)
            if school_obj and school_obj.city_id:
                city_id = school_obj.city_id
        
        # Verificar se a avaliação existe
        test = Test.query.get(evaluation_id)
        if not test:
            return jsonify({"error": "Avaliação não encontrada"}), 404
        
        # Obter status
        # Forçar refresh para garantir que estamos lendo dados atualizados do banco
        db.session.expire_all()
        status = ReportAggregateService.get_status(evaluation_id, scope_type, scope_ref_id)
        
        return jsonify({
            **status,
            "last_update": status['last_update'].isoformat() if status['last_update'] else None,
            "evaluation_id": evaluation_id,
            "scope_type": scope_type,
            "scope_id": scope_ref_id
        }), 200
        
    except Exception as e:
        logger.error(f"Erro ao obter status do relatório: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro interno do servidor", "details": str(e)}), 500


@bp.route('/force-rebuild/<string:evaluation_id>', methods=['POST'])
@jwt_required()
@role_required("admin")
def force_rebuild(evaluation_id: str):
    """
    Força rebuild manual de um relatório (apenas admin).
    Útil quando relatório fica travado em "processing".
    
    Query Parameters:
        school_id: ID da escola (opcional)
        city_id: ID do município (opcional)
        sync: bool (default: false) - Se true, processa síncrono
    """
    try:
        user = get_current_user_from_token()
        school_id = request.args.get('school_id')
        city_id = request.args.get('city_id')
        use_sync = request.args.get('sync', 'false').lower() == 'true'
        
        try:
            scope_type, scope_ref_id = _determinar_escopo_por_role(user, school_id, city_id)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        
        schema = _resolve_report_schema(scope_type, scope_ref_id, city_id)
        if not schema:
            return jsonify({
                "error": "Para forçar rebuild, informe city_id ou school_id na URL (ex.: ?city_id=... ou ?school_id=...)"
            }), 400
        
        set_search_path(schema)
        
        test = Test.query.get(evaluation_id)
        if not test:
            return jsonify({"error": "Avaliação não encontrada"}), 404
        
        # Limpar debounce
        from app.report_analysis.debounce import ReportDebounceService
        ReportDebounceService.clear_debounce(evaluation_id, scope_type=scope_type, scope_id=scope_ref_id)
        
        city_id_for_rebuild = (
            city_id
            or (scope_ref_id if scope_type == 'city' else None)
            or user.get('city_id')
        )

        if use_sync:
            # Processar síncrono
            from app.report_analysis.tasks import rebuild_report_for_scope
            result = rebuild_report_for_scope(evaluation_id, scope_type, scope_ref_id, city_id_for_rebuild)
            
            if result.get('success'):
                return jsonify({
                    "message": "Rebuild concluído com sucesso",
                    "result": result
                }), 200
            else:
                return jsonify({
                    "error": "Erro ao processar rebuild",
                    "result": result
                }), 500
        else:
            # Processar assíncrono
            from app.report_analysis.tasks import rebuild_report_for_scope
            task = rebuild_report_for_scope.delay(evaluation_id, scope_type, scope_ref_id, city_id_for_rebuild)
            
            return jsonify({
                "message": "Rebuild forçado agendado",
                "task_id": task.id,
                "evaluation_id": evaluation_id,
                "scope_type": scope_type,
                "scope_id": scope_ref_id
            }), 200
            
    except Exception as e:
        logger.error(f"Erro ao forçar rebuild: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

