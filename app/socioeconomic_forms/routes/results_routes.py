# -*- coding: utf-8 -*-
"""
Rotas para API de Resultados de Formulários Socioeconômicos
"""

from flask import Blueprint, request, jsonify, g
from flask_jwt_extended import jwt_required
from app.decorators.role_required import role_required
from app.socioeconomic_forms.services.results_cache_service import ResultsCacheService
from app.socioeconomic_forms.services.results_delivery import (
    STALE_AFTER_SECONDS,
    decide_report_delivery,
)
from app.socioeconomic_forms.services.results_tasks import generate_indices_report, generate_profiles_report, generate_responses_report, generate_pneerq_report
from app.socioeconomic_forms.services.results_migration_tasks import populate_initial_cache_for_form, populate_all_forms_cache
from app.socioeconomic_forms.services.inse_saeb_service import InseAvaliacaoService
from app.socioeconomic_forms.services.results_service import ResultsService
from celery.result import AsyncResult
from app.report_analysis.celery_app import celery_app
import logging
import threading
import time


def _get_tenant_schema():
    """Retorna o schema do tenant do request atual (multi-tenant)."""
    ctx = getattr(g, 'tenant_context', None)
    if ctx and getattr(ctx, 'schema', None):
        return ctx.schema
    return 'public'

bp = Blueprint('socioeconomic_results', __name__, url_prefix='/forms')

logger = logging.getLogger(__name__)

# Job em voo por (form, filtros). Evita reenfileirar a mesma task a cada poll de 2,5 s.
_RESPONSES_INFLIGHT = {}
_RESPONSES_INFLIGHT_LOCK = threading.Lock()
_WORKER_PROBE = {"checked_at": 0.0, "alive": False}
_WORKER_PROBE_TTL = 10.0


def _responses_job_key(form_id, filters):
    from app.socioeconomic_forms.models.form_result_cache import FormResultCache

    return f"respostas:{form_id}:{FormResultCache.generate_filters_hash(filters or {})}"


def _responses_inflight_age(key):
    with _RESPONSES_INFLIGHT_LOCK:
        started = _RESPONSES_INFLIGHT.get(key)
    if started is None:
        return None
    return time.monotonic() - started


def _mark_responses_inflight(key):
    with _RESPONSES_INFLIGHT_LOCK:
        _RESPONSES_INFLIGHT[key] = time.monotonic()


def _clear_responses_inflight(key):
    with _RESPONSES_INFLIGHT_LOCK:
        _RESPONSES_INFLIGHT.pop(key, None)


def _celery_workers_alive():
    """True se algum worker respondeu ao ping. Resultado vale por alguns segundos."""
    now = time.monotonic()
    if now - _WORKER_PROBE["checked_at"] < _WORKER_PROBE_TTL:
        return _WORKER_PROBE["alive"]
    alive = False
    try:
        inspector = celery_app.control.inspect(timeout=0.5)
        alive = bool(inspector.ping()) if inspector is not None else False
    except Exception as exc:
        logger.warning("[RESPOSTAS] Worker Celery indisponível: %s", exc)
        alive = False
    _WORKER_PROBE["checked_at"] = now
    _WORKER_PROBE["alive"] = alive
    return alive


def _compute_responses_now(form_id, filters, page, limit):
    result = ResultsService.calculate_responses_report(form_id, filters, page, limit)
    ResultsCacheService.save(
        form_id=form_id,
        report_type='respostas',
        filters=filters,
        result=result,
        student_count=result.get('totalRespostas', 0) if isinstance(result, dict) else 0,
        commit=True,
    )
    return result


def _processing_respostas_payload(status):
    return {
        'status': 'processing',
        'message': (
            'Relatório sendo gerado em background. Faça polling neste mesmo '
            'endpoint (GET respostas) até receber 200 com os dados.'
        ),
        'pollSameUrl': True,
        'cacheStatus': status,
    }


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
        filters = {k: v for k, v in filters.items() if v}
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 20))
        
        status = ResultsCacheService.get_status(form_id, 'indices', filters)
        
        if status['status'] == 'ready':
            result = ResultsCacheService.get_result(form_id, 'indices', filters)
            return jsonify(result), 200
        
        # Disparar task sem usar result backend (evita "Connection closed by server" no Redis em Windows)
        schema = _get_tenant_schema()
        generate_indices_report.apply_async(
            (form_id, filters, page, limit, schema),
            ignore_result=True
        )
        return jsonify({
            'status': 'processing',
            'message': 'Relatório sendo gerado em background. Faça polling neste mesmo endpoint (GET indices) até receber 200 com os dados.',
            'pollSameUrl': True,
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
            result = ResultsCacheService.get_result(form_id, 'profiles', filters)
            return jsonify(result), 200
        
        # Disparar task sem usar result backend (evita "Connection closed by server" no Redis em Windows)
        schema = _get_tenant_schema()
        generate_profiles_report.apply_async(
            (form_id, filters, schema),
            ignore_result=True
        )
        return jsonify({
            'status': 'processing',
            'message': 'Relatório sendo gerado em background. Faça polling neste mesmo endpoint (GET profiles) até receber 200 com os dados.',
            'pollSameUrl': True,
            'cacheStatus': status
        }), 202  # HTTP 202 Accepted
        
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Erro ao obter relatório de perfis: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao processar solicitação", "details": str(e)}), 500


@bp.route('/<form_id>/results/inse-saeb', methods=['GET'])
@bp.route('/<form_id>/results/inse-avaliacao', methods=['GET'])
@jwt_required()
@role_required("admin", "tecadm", "diretor", "coordenador")
def get_inse_avaliacao_report(form_id):
    """
    Relatório INSE x Avaliação: cruza respostas do formulário socioeconômico com resultados
    da avaliação (proficiência por disciplina, INSE por aluno).

    Também retorna comparativos agregados (médias por raça/cor, por nível INSE e
    cruzamento raça×INSE), sempre calculados no backend sobre o escopo completo
    (filtros territoriais/avaliação), independentemente do filtro de raça da tabela.

    Query params:
    - state: Estado (ex: "SP")
    - municipio: ID do município (UUID)
    - escola: ID da escola
    - serie: ID da série (UUID)
    - turma: ID da turma (UUID)
    - avaliacao: ID da avaliação (test_id) — obrigatório
    - raca_cor: valor exato de q5 (ex.: Branca, Preta, Parda, Indígena)
    - raca_cor_grupo: grupo racial (Branca, PretaParda, Outras, NaoDeclarada, NaoInformada)
    - page: Página da lista de alunos (default: 1)
    - limit: Limite por página (default: 50)
    """
    try:
        filters = {
            'state': request.args.get('state'),
            'municipio': request.args.get('municipio'),
            'escola': request.args.get('escola'),
            'serie': request.args.get('serie'),
            'turma': request.args.get('turma'),
        }
        filters = {k: v for k, v in filters.items() if v}
        avaliacao_id = request.args.get('avaliacao')
        if not avaliacao_id:
            return jsonify({"error": "Parâmetro 'avaliacao' é obrigatório"}), 400
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 50))
        raca_cor = request.args.get('raca_cor')
        raca_cor_grupo = request.args.get('raca_cor_grupo')

        result = InseAvaliacaoService.gerar_relatorio(
            form_id=form_id,
            filters=filters,
            avaliacao_id=avaliacao_id,
            page=page,
            limit=limit,
            raca_cor=raca_cor,
            raca_cor_grupo=raca_cor_grupo,
        )
        return jsonify(result), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Erro ao obter relatório INSE x Avaliação: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao processar solicitação", "details": str(e)}), 500


@bp.route('/<form_id>/results/respostas', methods=['GET'])
@jwt_required()
@role_required("admin", "tecadm", "diretor", "coordenador")
def get_respostas_report(form_id):
    """
    Obtém relatório "Respostas do socioeconômico": por questão, quantidade de respostas,
    porcentagem sobre o total, contagem por opção e quem respondeu / o que respondeu.

    Query params:
    - state, municipio, escola, serie, turma: Filtros
    - page: Página para listas de alunos (default: 1)
    - limit: Limite de alunos por página (default: 20)

    Respostas HTTP:
    - 200: cache pronto ou relatório calculado nesta requisição
      (formId, formTitle, totalRespostas, questoes).
    - 202: há worker Celery e o job deste filtro já foi enfileirado uma vez.
      O body não traz questoes. status=processing, pollSameUrl=true,
      cacheStatus.status em not_found | dirty | empty.
      O próximo GET com a mesma query não enfileira de novo.
      Se o job não gravar o cache em STALE_AFTER_SECONDS, o GET seguinte
      calcula na requisição (200) ou devolve 500.
    - 400/500: erro do cálculo. A tela deve parar o polling.
    """
    job_key = None
    try:
        filters = {
            'state': request.args.get('state'),
            'municipio': request.args.get('municipio'),
            'escola': request.args.get('escola'),
            'serie': request.args.get('serie'),
            'turma': request.args.get('turma')
        }
        filters = {k: v for k, v in filters.items() if v}
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 20))

        status = ResultsCacheService.get_status(form_id, 'respostas', filters)
        job_key = _responses_job_key(form_id, filters)

        if status['status'] == 'ready':
            _clear_responses_inflight(job_key)
            result = ResultsCacheService.get_result(form_id, 'respostas', filters)
            return jsonify(result), 200

        decision = decide_report_delivery(
            cache_ready=False,
            workers_alive=_celery_workers_alive(),
            inflight_age=_responses_inflight_age(job_key),
            stale_after=STALE_AFTER_SECONDS,
        )

        if decision == 'compute_sync':
            logger.info(
                "[RESPOSTAS] Calculando na requisição form_id=%s filters=%s",
                form_id,
                filters,
            )
            result = _compute_responses_now(form_id, filters, page, limit)
            _clear_responses_inflight(job_key)
            logger.info(
                "[RESPOSTAS] Relatório pronto form_id=%s totalRespostas=%s",
                form_id,
                result.get('totalRespostas') if isinstance(result, dict) else None,
            )
            return jsonify(result), 200

        if decision == 'enqueue':
            _mark_responses_inflight(job_key)
            try:
                schema = _get_tenant_schema()
                generate_responses_report.apply_async(
                    (form_id, filters, page, limit, schema),
                    ignore_result=True
                )
                logger.info(
                    "[RESPOSTAS] Task enfileirada uma vez form_id=%s filters=%s",
                    form_id,
                    filters,
                )
            except Exception as exc:
                logger.warning(
                    "[RESPOSTAS] Falha ao enfileirar (%s); calculando na requisição",
                    exc,
                )
                result = _compute_responses_now(form_id, filters, page, limit)
                _clear_responses_inflight(job_key)
                return jsonify(result), 200

        return jsonify(_processing_respostas_payload(status)), 202

    except ValueError as e:
        if job_key:
            _clear_responses_inflight(job_key)
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        if job_key:
            _clear_responses_inflight(job_key)
        logger.error(f"Erro ao obter relatório de respostas: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao processar solicitação", "details": str(e)}), 500


@bp.route('/<form_id>/results/pneerq', methods=['GET'])
@jwt_required()
@role_required("admin", "tecadm", "diretor", "coordenador")
def get_pneerq_report(form_id):
    """
    Obtém relatório PNEERQ (equidade racial) calculado a partir das respostas do formulário.
    Se o cache estiver dirty ou não existir, agenda task Celery e retorna 202 para polling na mesma URL.

    Query params:
    - state: Estado (ex: "SP")
    - municipio: ID do município (UUID)
    - escola: ID da escola (String)
    - serie: ID da série (UUID)
    - turma: ID da turma (UUID)
    - ageDistortionDelta: (DEPRECADO) se enviado pelo frontend, será ignorado.
    """
    try:
        filters = {
            'state': request.args.get('state'),
            'municipio': request.args.get('municipio'),
            'escola': request.args.get('escola'),
            'serie': request.args.get('serie'),
            'turma': request.args.get('turma')
        }
        filters = {k: v for k, v in filters.items() if v}

        status = ResultsCacheService.get_status(form_id, 'pneerq', filters)
        if status['status'] == 'ready':
            result = ResultsCacheService.get_result(form_id, 'pneerq', filters)
            return jsonify(result), 200

        schema = _get_tenant_schema()
        generate_pneerq_report.apply_async(
            (form_id, filters, schema),
            ignore_result=True
        )
        return jsonify({
            'status': 'processing',
            'message': 'Relatório PNEERQ sendo gerado em background. Faça polling neste mesmo endpoint (GET pneerq) até receber 200 com os dados.',
            'pollSameUrl': True,
            'cacheStatus': status
        }), 202

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Erro ao obter relatório PNEERQ: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao processar solicitação", "details": str(e)}), 500


@bp.route('/<form_id>/results/status/<task_id>', methods=['GET'])
@jwt_required()
@role_required("admin", "tecadm", "diretor", "coordenador")
def check_task_status(form_id, task_id):
    """
    Verifica status de uma task Celery.
    Para resultados de formulários usamos ignore_result; use polling no mesmo endpoint
    GET .../results/indices ou .../results/profiles até receber 200.
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
                error_info = str(task.info) if task.info else "Erro desconhecido"
                return jsonify({'status': 'failed', 'error': error_info}), 500
        return jsonify({
            'status': 'processing',
            'progress': task.info.get('progress', 0) if isinstance(task.info, dict) else 0
        }), 200
    except Exception as e:
        # Result backend (Redis) pode falhar em alguns ambientes; orientar a usar polling no mesmo URL
        logger.warning(f"Status da task não disponível (use polling no endpoint de indices/profiles): {e}")
        return jsonify({
            'status': 'processing',
            'message': 'Faça polling no mesmo endpoint GET .../results/indices ou .../results/profiles com os mesmos filtros até receber 200 com os dados.',
            'pollSameUrl': True
        }), 200


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
        schema = _get_tenant_schema()
        task = populate_initial_cache_for_form.delay(form_id, schema)
        
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
    Popula cache inicial de TODOS os formulários que têm respostas (no tenant atual).
    
    ⚠️ ATENÇÃO: Esta operação pode gerar muitas tasks e levar tempo.
    Use apenas uma vez para migração inicial ou com cautela.
    """
    try:
        schema = _get_tenant_schema()
        task = populate_all_forms_cache.delay(schema)
        
        return jsonify({
            'message': 'População de cache de todos os formulários iniciada',
            'taskId': task.id,
            'status': 'processing',
            'warning': 'Esta operação pode levar vários minutos dependendo da quantidade de formulários'
        }), 202  # HTTP 202 Accepted
        
    except Exception as e:
        logger.error(f"Erro ao iniciar população de todos os caches: {str(e)}", exc_info=True)
        return jsonify({"error": "Erro ao iniciar população", "details": str(e)}), 500
