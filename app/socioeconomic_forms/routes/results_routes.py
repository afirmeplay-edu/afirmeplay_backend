# -*- coding: utf-8 -*-
"""
Rotas para API de Resultados de Formulários Socioeconômicos
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from app.decorators.role_required import role_required
from app.socioeconomic_forms.services.results_cache_service import ResultsCacheService
from app.socioeconomic_forms.services.results_tasks import generate_indices_report, generate_profiles_report
from app.socioeconomic_forms.services.results_migration_tasks import populate_initial_cache_for_form, populate_all_forms_cache
from celery.result import AsyncResult
from app.report_analysis.celery_app import celery_app
import logging

bp = Blueprint('socioeconomic_results', __name__, url_prefix='/forms')

logger = logging.getLogger(__name__)


@bp.route('/<form_id>/results/indices', methods=['GET'])
@jwt_required()
@role_required("admin", "tecadm", "diretor", "coordenador")
def get_indices_report(form_id):
    """
    Obtém relatório de índices gerais.
    Se o cache estiver dirty ou não existir, agenda task Celery e retorna task_id para polling.
    
    Query params:
    - state: Estado (ex: "SP")
    - municipio: ID do município (UUID)
    - escola: ID da escola (String)
    - serie: ID da série (UUID)
    - turma: ID da turma (UUID)
    - page: Página para paginação dos alunos (default: 1)
    - limit: Limite de alunos por página (default: 20)
    """
    try:
        # Extrair filtros
        filters = {
            'state': request.args.get('state'),
            'municipio': request.args.get('municipio'),
            'escola': request.args.get('escola'),
            'serie': request.args.get('serie'),
            'turma': request.args.get('turma')
        }
        # Remover None values
        filters = {k: v for k, v in filters.items() if v}
        
        # Paginação
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 20))
        
        # Verificar status do cache
        status = ResultsCacheService.get_status(form_id, 'indices', filters)
        
        if status['status'] == 'ready':
            # Cache está pronto, retornar resultado
            result = ResultsCacheService.get_result(form_id, 'indices', filters)
            return jsonify(result), 200
        
        # Cache dirty ou não existe - disparar task
        task = generate_indices_report.delay(form_id, filters, page, limit)
        
        return jsonify({
            'status': 'processing',
            'taskId': task.id,
            'message': 'Relatório sendo gerado em background',
            'cacheStatus': status
        }), 202  # HTTP 202 Accepted
        
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Erro ao obter relatório de índices: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao processar solicitação", "details": str(e)}), 500


@bp.route('/<form_id>/results/profiles', methods=['GET'])
@jwt_required()
@role_required("admin", "tecadm", "diretor", "coordenador")
def get_profiles_report(form_id):
    """
    Obtém relatório de perfis.
    Se o cache estiver dirty ou não existir, agenda task Celery e retorna task_id para polling.
    
    Query params:
    - state: Estado (ex: "SP")
    - municipio: ID do município (UUID)
    - escola: ID da escola (String)
    - serie: ID da série (UUID)
    - turma: ID da turma (UUID)
    """
    try:
        # Extrair filtros
        filters = {
            'state': request.args.get('state'),
            'municipio': request.args.get('municipio'),
            'escola': request.args.get('escola'),
            'serie': request.args.get('serie'),
            'turma': request.args.get('turma')
        }
        # Remover None values
        filters = {k: v for k, v in filters.items() if v}
        
        # Verificar status do cache
        status = ResultsCacheService.get_status(form_id, 'profiles', filters)
        
        if status['status'] == 'ready':
            # Cache está pronto, retornar resultado
            result = ResultsCacheService.get_result(form_id, 'profiles', filters)
            return jsonify(result), 200
        
        # Cache dirty ou não existe - disparar task
        task = generate_profiles_report.delay(form_id, filters)
        
        return jsonify({
            'status': 'processing',
            'taskId': task.id,
            'message': 'Relatório sendo gerado em background',
            'cacheStatus': status
        }), 202  # HTTP 202 Accepted
        
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Erro ao obter relatório de perfis: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao processar solicitação", "details": str(e)}), 500


@bp.route('/<form_id>/results/status/<task_id>', methods=['GET'])
@jwt_required()
@role_required("admin", "tecadm", "diretor", "coordenador")
def check_task_status(form_id, task_id):
    """
    Verifica status de uma task Celery.
    Frontend deve fazer polling neste endpoint até status = 'completed'.
    """
    try:
        task = AsyncResult(task_id, app=celery_app)
        
        if task.ready():
            if task.successful():
                task_result = task.result
                return jsonify({
                    'status': 'completed',
                    'result': task_result.get('result'),
                    'cached': task_result.get('cached', False),
                    'studentCount': task_result.get('student_count', 0)
                }), 200
            else:
                # Task falhou
                error_info = str(task.info) if task.info else "Erro desconhecido"
                return jsonify({
                    'status': 'failed',
                    'error': error_info
                }), 500
        else:
            # Task ainda está processando
            return jsonify({
                'status': 'processing',
                'progress': task.info.get('progress', 0) if isinstance(task.info, dict) else 0
            }), 200
        
    except Exception as e:
        logger.error(f"Erro ao verificar status da task: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao verificar status", "details": str(e)}), 500


@bp.route('/<form_id>/results/cache/invalidate', methods=['POST'])
@jwt_required()
@role_required("admin", "tecadm")
def invalidate_cache(form_id):
    """
    Invalida (marca como dirty) todos os caches de um formulário.
    Útil para forçar recálculo de todos os relatórios.
    """
    try:
        ResultsCacheService._mark_dirty_all_for_form(form_id, commit=True)
        
        return jsonify({
            'message': 'Todos os caches do formulário foram invalidados',
            'formId': form_id
        }), 200
        
    except Exception as e:
        logger.error(f"Erro ao invalidar cache: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao invalidar cache", "details": str(e)}), 500


@bp.route('/<form_id>/results/cache/status', methods=['GET'])
@jwt_required()
@role_required("admin", "tecadm", "diretor", "coordenador")
def get_cache_status(form_id):
    """
    Obtém status de um cache específico.
    
    Query params:
    - reportType: Tipo do relatório ('indices' ou 'profiles')
    - state, municipio, escola, serie, turma: Filtros
    """
    try:
        report_type = request.args.get('reportType', 'indices')
        
        filters = {
            'state': request.args.get('state'),
            'municipio': request.args.get('municipio'),
            'escola': request.args.get('escola'),
            'serie': request.args.get('serie'),
            'turma': request.args.get('turma')
        }
        # Remover None values
        filters = {k: v for k, v in filters.items() if v}
        
        status = ResultsCacheService.get_status(form_id, report_type, filters)
        
        return jsonify(status), 200
        
    except Exception as e:
        logger.error(f"Erro ao obter status do cache: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao obter status", "details": str(e)}), 500


@bp.route('/<form_id>/results/cache/populate', methods=['POST'])
@jwt_required()
@role_required("admin", "tecadm")
def populate_form_cache(form_id):
    """
    Popula cache inicial de um formulário específico.
    Útil para formulários existentes que não têm cache ainda.
    
    Identifica automaticamente os filtros únicos e gera resultados para cada combinação.
    """
    try:
        task = populate_initial_cache_for_form.delay(form_id)
        
        return jsonify({
            'message': 'População de cache iniciada',
            'formId': form_id,
            'taskId': task.id,
            'status': 'processing'
        }), 202  # HTTP 202 Accepted
        
    except Exception as e:
        logger.error(f"Erro ao iniciar população de cache: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao iniciar população", "details": str(e)}), 500


@bp.route('/results/cache/populate-all', methods=['POST'])
@jwt_required()
@role_required("admin", "tecadm")
def populate_all_forms_cache_endpoint():
    """
    Popula cache inicial de TODOS os formulários que têm respostas.
    
    ⚠️ ATENÇÃO: Esta operação pode gerar muitas tasks e levar tempo.
    Use apenas uma vez para migração inicial ou com cautela.
    """
    try:
        task = populate_all_forms_cache.delay()
        
        return jsonify({
            'message': 'População de cache de todos os formulários iniciada',
            'taskId': task.id,
            'status': 'processing',
            'warning': 'Esta operação pode levar vários minutos dependendo da quantidade de formulários'
        }), 202  # HTTP 202 Accepted
        
    except Exception as e:
        logger.error(f"Erro ao iniciar população de todos os caches: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao iniciar população", "details": str(e)}), 500
