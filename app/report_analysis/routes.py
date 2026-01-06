# -*- coding: utf-8 -*-
"""
Rotas refatoradas para relatórios com processamento assíncrono
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from app.permissions import role_required, get_current_user_from_token
from app.models.test import Test
from app.models.classTest import ClassTest
from app.permissions.utils import get_teacher_classes, get_manager_school, get_teacher
from app.permissions.rules import can_view_test
from app.routes.report_routes import _determinar_escopo_por_role
import logging

from app.report_analysis.services import ReportAggregateService
from app.report_analysis.tasks import trigger_rebuild_if_needed

logger = logging.getLogger(__name__)

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
        # Verificar se a avaliação existe
        test = Test.query.get(evaluation_id)
        if not test:
            return jsonify({"error": "Avaliação não encontrada"}), 404
        
        # Obter usuário atual
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não autenticado"}), 401
        
        # Obter parâmetros de filtro (usados apenas para admin)
        school_id_raw = request.args.get('school_id')
        city_id = request.args.get('city_id')
        
        # Determinar escopo baseado no role do usuário
        try:
            scope_type, scope_ref_id = _determinar_escopo_por_role(user, school_id_raw, city_id)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        
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
        aggregate = ReportAggregateService.get(evaluation_id, scope_type, scope_ref_id)
        status = ReportAggregateService.get_status(evaluation_id, scope_type, scope_ref_id)
        
        # Se não está pronto, disparar task (com debounce) e retornar status
        if status['status'] != 'ready':
            logger.info(f"Relatório não está pronto para {scope_type}:{scope_ref_id}. Disparando rebuild.")
            
            # Disparar task assíncrona (com debounce)
            try:
                trigger_rebuild_if_needed.delay(evaluation_id, scope_type, scope_ref_id)
            except Exception as e:
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
        # Verificar se a avaliação existe
        test = Test.query.get(evaluation_id)
        if not test:
            return jsonify({"error": "Avaliação não encontrada"}), 404
        
        # Obter usuário atual
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não autenticado"}), 401
        
        # Obter parâmetros de filtro
        school_id_raw = request.args.get('school_id')
        city_id = request.args.get('city_id')
        
        # Determinar escopo
        try:
            scope_type, scope_ref_id = _determinar_escopo_por_role(user, school_id_raw, city_id)
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        
        # Obter status
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

