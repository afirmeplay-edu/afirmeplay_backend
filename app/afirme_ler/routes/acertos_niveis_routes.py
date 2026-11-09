# -*- coding: utf-8 -*-
"""Rotas gerais do relatório Acertos e Níveis do Afirme Ler."""
from __future__ import annotations

import logging

from flask import jsonify, request
from flask_jwt_extended import jwt_required

from app.decorators.tenant_required import requires_city_context
from app.entitlements import require_feature
from app.permissions import get_current_user_from_token, role_required
from app.afirme_ler.routes import AFIRME_LER_ROLES, bp
from app.afirme_ler.services import acertos_niveis_service


def _error_response(message: str, status: int):
    return jsonify({"error": message}), status


def _handle_service_error(error: Exception):
    if isinstance(error, LookupError):
        return _error_response(str(error), 404)
    if isinstance(error, PermissionError):
        return _error_response(str(error), 403)
    if isinstance(error, ValueError):
        return _error_response(str(error), 400)
    logging.error("Erro Afirme Ler (acertos-niveis): %s", error, exc_info=True)
    return _error_response("Erro interno ao processar a solicitação.", 500)


@bp.route("/acertos-niveis/filtros", methods=["GET"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*AFIRME_LER_ROLES)
@requires_city_context
def get_acertos_niveis_filtros():
    """Catálogo de fontes/avaliações/níveis para o relatório."""
    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    try:
        return jsonify(acertos_niveis_service.catalog(request.args.to_dict())), 200
    except Exception as error:
        return _handle_service_error(error)


@bp.route("/acertos-niveis", methods=["GET"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*AFIRME_LER_ROLES)
@requires_city_context
def get_acertos_niveis():
    """
    Relatório Acertos e Níveis (Afirme Ler).

    Fase 1: fonte=escrita (ICA). Fluência fica para adaptação posterior.
    Query: fonte, avaliacaoId (obrigatório), escolaId, serieId, turmaId,
    estudanteId, turno, nivel, status.
    """
    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    try:
        return jsonify(acertos_niveis_service.report(request.args.to_dict())), 200
    except Exception as error:
        return _handle_service_error(error)
