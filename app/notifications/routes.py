# -*- coding: utf-8 -*-
"""
Rotas do sininho (notificações do usuário logado, no município do contexto).

GET  /notifications/unread-count
GET  /notifications
POST /notifications/<id>/read
POST /notifications/read-all

Cada usuário só enxerga e altera as próprias linhas de notification_recipient.
"""
from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from app.decorators.tenant_required import requires_city_context
from app.notifications import services
from app.permissions import get_current_user_from_token, role_required

bp = Blueprint("notifications", __name__, url_prefix="/notifications")

_ROLES = ("admin", "tecadm", "diretor", "coordenador", "professor", "aluno")


def _current_user():
    user = get_current_user_from_token()
    if not user:
        return None, (jsonify({"error": "Usuário não encontrado"}), 401)
    return user, None


def _handle(fn, log_label: str):
    try:
        return fn()
    except services.NotificationError as e:
        return jsonify({"error": str(e)}), e.status_code
    except Exception as e:
        logging.exception("Erro em %s: %s", log_label, e)
        return jsonify({"error": "Erro interno ao processar notificações"}), 500


@bp.route("/unread-count", methods=["GET"])
@jwt_required()
@role_required(*_ROLES)
@requires_city_context
def contar_nao_lidas():
    user, err = _current_user()
    if err:
        return err
    return _handle(
        lambda: (jsonify({"count": services.unread_count(user["id"])}), 200),
        "GET /notifications/unread-count",
    )


@bp.route("", methods=["GET"])
@jwt_required()
@role_required(*_ROLES)
@requires_city_context
def listar_notificacoes():
    """Params: page, per_page (máx. 50), unread_only, type."""
    user, err = _current_user()
    if err:
        return err
    return _handle(
        lambda: (jsonify(services.list_notifications(user["id"], request.args)), 200),
        "GET /notifications",
    )


@bp.route("/<string:notification_id>/read", methods=["POST"])
@jwt_required()
@role_required(*_ROLES)
@requires_city_context
def marcar_como_lida(notification_id: str):
    user, err = _current_user()
    if err:
        return err
    return _handle(
        lambda: (jsonify(services.mark_read(user["id"], notification_id)), 200),
        "POST /notifications/<id>/read",
    )


@bp.route("/read-all", methods=["POST"])
@jwt_required()
@role_required(*_ROLES)
@requires_city_context
def marcar_todas_como_lidas():
    user, err = _current_user()
    if err:
        return err
    return _handle(
        lambda: (jsonify({"updated": services.mark_all_read(user["id"])}), 200),
        "POST /notifications/read-all",
    )
