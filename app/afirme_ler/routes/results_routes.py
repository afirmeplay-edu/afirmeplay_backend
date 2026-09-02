# -*- coding: utf-8 -*-
"""Relatórios de resultados da avaliação de fluência leitora."""
from __future__ import annotations

import logging

from flask import jsonify, request
from flask_jwt_extended import jwt_required

from app.decorators.tenant_required import requires_city_context
from app.entitlements import require_feature
from app.permissions import get_current_user_from_token, role_required
from app.afirme_ler.routes import AFIRME_LER_ROLES, bp
from app.afirme_ler.services.fluency_aplicacao_service import FluencyAplicacaoService
from app.afirme_ler.services.fluency_results_service import FluencyResultsService

_ROLES = AFIRME_LER_ROLES


def _error_response(message: str, status: int):
    return jsonify({"error": message}), status


def _handle_service_error(error: Exception):
    if isinstance(error, LookupError):
        return _error_response(str(error), 404)
    if isinstance(error, PermissionError):
        return _error_response(str(error), 403)
    if isinstance(error, ValueError):
        return _error_response(str(error), 400)
    logging.error("Erro Afirme Ler (resultados): %s", error, exc_info=True)
    return _error_response("Erro interno ao processar a solicitação.", 500)


@bp.route("/resultados/filtros", methods=["GET"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*_ROLES)
@requires_city_context
def get_resultados_filtros():
    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    try:
        return jsonify(FluencyResultsService.catalog(user)), 200
    except Exception as error:
        return _handle_service_error(error)


@bp.route("/resultados/estudantes/<student_id>", methods=["GET"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*_ROLES)
@requires_city_context
def get_resultado_estudante(student_id):
    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    try:
        payload = FluencyResultsService.student_profile(
            user, student_id, request.args.to_dict()
        )
        return jsonify(payload), 200
    except Exception as error:
        return _handle_service_error(error)


@bp.route("/resultados/estudantes/<student_id>/aplicacao", methods=["GET"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*_ROLES)
@requires_city_context
def get_resultado_estudante_aplicacao(student_id):
    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    try:
        payload = FluencyAplicacaoService.student_aplicacao(
            user, student_id, request.args.to_dict()
        )
        return jsonify(payload), 200
    except Exception as error:
        return _handle_service_error(error)


@bp.route("/resultados", methods=["GET"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*_ROLES)
@requires_city_context
def get_resultados():
    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    try:
        payload = FluencyResultsService.report(user, request.args.to_dict())
        return jsonify(payload), 200
    except Exception as error:
        return _handle_service_error(error)
