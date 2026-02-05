# -*- coding: utf-8 -*-
"""
Rotas para resultados agregados de múltiplos formulários socioeconômicos.
Consolida dados de TODOS os formulários aplicados em um escopo específico.
"""

from flask import Blueprint, request, jsonify
from app.socioeconomic_forms.services.aggregated_results_service import AggregatedResultsService
from flask_jwt_extended import jwt_required
import logging

logger = logging.getLogger(__name__)

# Blueprint com prefixo diferenciado para agregados
bp = Blueprint('socioeconomic_aggregated_results', __name__, url_prefix='/forms/aggregated')


@bp.route('/results/indices', methods=['GET'])
@jwt_required()
def get_aggregated_indices():
    """
    GET /forms/aggregated/results/indices
    
    Retorna índices consolidados de TODOS os formulários aplicados no escopo.
    
    Query Parameters:
        - state: Estado (opcional)
        - municipio: UUID do município (opcional)
        - escola: UUID da escola (opcional)
        - serie: UUID da série (opcional)
        - turma: UUID da turma (opcional)
        - page: Página (padrão 1)
        - limit: Limite por página (padrão 20)
    
    Returns:
        {
            "escopo": {...},
            "formularios": [{formId, formTitle, totalRespostas, ...}],
            "totalFormularios": 5,
            "totalRespostas": 150,
            "indicesConsolidados": {
                "distorcaoIdadeSerie": {
                    "total": 30,
                    "porcentagem": 20,
                    "alunos": {data: [...], pagination: {...}},
                    "porFormulario": {...}
                },
                ...
            }
        }
    """
    try:
        # Obter filtros da query string
        filters = {}
        
        if request.args.get('state'):
            filters['state'] = request.args.get('state')
        
        if request.args.get('municipio'):
            filters['municipio'] = request.args.get('municipio')
        
        if request.args.get('escola'):
            filters['escola'] = request.args.get('escola')
        
        if request.args.get('serie'):
            filters['serie'] = request.args.get('serie')
        
        if request.args.get('turma'):
            filters['turma'] = request.args.get('turma')
        
        # Paginação
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 20))
        
        logger.info("[AGGREGATED INDICES] Solicitação recebida - Filtros: %s, Page: %d, Limit: %d", filters, page, limit)
        
        # Buscar resultados agregados
        result = AggregatedResultsService.get_aggregated_indices(filters, page, limit)
        
        return jsonify(result), 200
        
    except ValueError as e:
        logger.error("Erro de validação: %s", str(e))
        return jsonify({'error': 'Parâmetros inválidos', 'details': str(e)}), 400
    
    except Exception as e:
        logger.error("Erro ao obter índices agregados: %s", str(e))
        return jsonify({'error': 'Erro ao gerar relatório agregado', 'details': str(e)}), 500


@bp.route('/results/profiles', methods=['GET'])
@jwt_required()
def get_aggregated_profiles():
    """
    GET /forms/aggregated/results/profiles
    
    Retorna perfis consolidados de TODOS os formulários aplicados no escopo.
    
    Query Parameters:
        - state: Estado (opcional)
        - municipio: UUID do município (opcional)
        - escola: UUID da escola (opcional)
        - serie: UUID da série (opcional)
        - turma: UUID da turma (opcional)
    
    Returns:
        {
            "escopo": {...},
            "formularios": [{formId, formTitle, totalRespostas, ...}],
            "totalFormularios": 5,
            "totalRespostas": 150,
            "perfisConsolidados": {
                "perfilDemografico": {
                    "nome": "Perfil Demográfico...",
                    "questoes": [...],
                    "dados": {
                        "q1": {
                            "textoPergunta": "...",
                            "contagem": {...},
                            "totalRespostas": 150,
                            "porFormulario": {...}
                        }
                    }
                },
                ...
            }
        }
    """
    try:
        # Obter filtros da query string
        filters = {}
        
        if request.args.get('state'):
            filters['state'] = request.args.get('state')
        
        if request.args.get('municipio'):
            filters['municipio'] = request.args.get('municipio')
        
        if request.args.get('escola'):
            filters['escola'] = request.args.get('escola')
        
        if request.args.get('serie'):
            filters['serie'] = request.args.get('serie')
        
        if request.args.get('turma'):
            filters['turma'] = request.args.get('turma')
        
        logger.info("[AGGREGATED PROFILES] Solicitação recebida - Filtros: %s", filters)
        
        # Buscar resultados agregados
        result = AggregatedResultsService.get_aggregated_profiles(filters)
        
        return jsonify(result), 200
        
    except ValueError as e:
        logger.error("Erro de validação: %s", str(e))
        return jsonify({'error': 'Parâmetros inválidos', 'details': str(e)}), 400
    
    except Exception as e:
        logger.error("Erro ao obter perfis agregados: %s", str(e))
        return jsonify({'error': 'Erro ao gerar relatório agregado', 'details': str(e)}), 500


@bp.route('/results/summary', methods=['GET'])
@jwt_required()
def get_aggregated_summary():
    """
    GET /forms/aggregated/results/summary
    
    Retorna um resumo dos formulários aplicados no escopo (sem calcular os resultados).
    Útil para mostrar quais formulários serão incluídos na agregação.
    
    Query Parameters:
        - state: Estado (opcional)
        - municipio: UUID do município (opcional)
        - escola: UUID da escola (opcional)
        - serie: UUID da série (opcional)
        - turma: UUID da turma (opcional)
    
    Returns:
        {
            "escopo": {...},
            "formularios": [{formId, formTitle, formType, totalRespostas, createdAt}],
            "totalFormularios": 5
        }
    """
    try:
        # Obter filtros da query string
        filters = {}
        
        if request.args.get('state'):
            filters['state'] = request.args.get('state')
        
        if request.args.get('municipio'):
            filters['municipio'] = request.args.get('municipio')
        
        if request.args.get('escola'):
            filters['escola'] = request.args.get('escola')
        
        if request.args.get('serie'):
            filters['serie'] = request.args.get('serie')
        
        if request.args.get('turma'):
            filters['turma'] = request.args.get('turma')
        
        logger.info("[AGGREGATED SUMMARY] Solicitação recebida - Filtros: %s", filters)
        
        # Buscar formulários (reutilizar a lógica do service)
        from app.socioeconomic_forms.models import FormResponse
        
        forms = AggregatedResultsService._find_forms_for_scope(filters)
        
        # Buscar total de respostas de cada formulário
        forms_summary = []
        for form in forms:
            total_responses = FormResponse.query.filter_by(
                form_id=form.id,
                is_complete=True
            ).count()
            
            forms_summary.append({
                'formId': form.id,
                'formTitle': form.title,
                'formType': form.form_type,
                'totalRespostas': total_responses,
                'createdAt': form.created_at.isoformat() if form.created_at else None,
                'deadline': form.deadline.isoformat() if form.deadline else None
            })
        
        return jsonify({
            'escopo': AggregatedResultsService._format_scope_info(filters),
            'formularios': forms_summary,
            'totalFormularios': len(forms_summary)
        }), 200
        
    except Exception as e:
        logger.error("Erro ao obter resumo agregado: %s", str(e))
        return jsonify({'error': 'Erro ao gerar resumo', 'details': str(e)}), 500
