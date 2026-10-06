# -*- coding: utf-8 -*-
"""
Rotas do cronograma de logística de aplicação.

GET    /logistics/opcoes-filtros
GET    /logistics/previa
GET    /logistics/schedules
POST   /logistics/schedules
GET    /logistics/schedules/<id>
PUT    /logistics/schedules/<id>
DELETE /logistics/schedules/<id>
POST   /logistics/schedules/<id>/publish
POST   /logistics/schedules/<id>/cancel

Escrita: só admin/tecadm (sem os perfis municipais, o role_required não adiciona aplicador).
Leitura: diretor/coordenador/professor também; o serviço bloqueia aplicador e demais perfis.
Publicar, editar publicado e cancelar publicado geram notificações (ver logistics/notifications.py).
"""
from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from app.decorators.tenant_required import get_current_tenant_context, requires_city_context
from app.logistics import services
from app.logistics.filters import build_filter_options, multi_arg
from app.permissions import get_current_user_from_token, role_required

bp = Blueprint("logistics", __name__, url_prefix="/logistics")

_MANAGE_ROLES = ("admin", "tecadm")
_READ_ROLES = ("admin", "tecadm", "diretor", "coordenador", "professor")


def _current_user():
    user = get_current_user_from_token()
    if not user:
        return None, (jsonify({"error": "Usuário não encontrado"}), 401)
    return user, None


def _city_id() -> str:
    return str(get_current_tenant_context().city_id)


def _handle(fn, log_label: str):
    try:
        return fn()
    except services.LogisticsError as e:
        return jsonify({"error": str(e)}), e.status_code
    except Exception as e:
        logging.exception("Erro em %s: %s", log_label, e)
        return jsonify({"error": "Erro interno ao processar cronograma de logística"}), 500


@bp.route("/opcoes-filtros", methods=["GET"])
@jwt_required()
@role_required(*_MANAGE_ROLES)
@requires_city_context
def opcoes_filtros():
    """Etapa → Avaliação → Escolas → Séries → Turmas. Params: etapa, avaliacao, escolas, series."""
    user, err = _current_user()
    if err:
        return err

    def run():
        services.require_manager(user)
        return jsonify(build_filter_options(_city_id(), request.args)), 200

    return _handle(run, "/logistics/opcoes-filtros")


@bp.route("/previa", methods=["GET"])
@jwt_required()
@role_required(*_MANAGE_ROLES)
@requires_city_context
def previa():
    """Turmas da avaliação com nº de alunos, sugestão de insumos e data sugerida (ClassTest)."""
    user, err = _current_user()
    if err:
        return err

    def run():
        services.require_manager(user)
        avaliacao = (request.args.get("avaliacao") or "").strip()
        if not avaliacao:
            raise services.LogisticsError("Parâmetro obrigatório: avaliacao")
        data = services.build_preview(
            _city_id(),
            avaliacao,
            etapa_id=(request.args.get("etapa") or "").strip() or None,
            escola_ids=multi_arg(request.args, "escolas", "escola") or None,
            serie_ids=multi_arg(request.args, "series", "serie") or None,
            turma_ids=multi_arg(request.args, "turmas", "turma") or None,
        )
        return jsonify(data), 200

    return _handle(run, "/logistics/previa")


@bp.route("/schedules", methods=["GET"])
@jwt_required()
@role_required(*_READ_ROLES)
@requires_city_context
def listar_cronogramas():
    user, err = _current_user()
    if err:
        return err
    def run():
        schedules = services.list_schedules(user, request.args)
        can_manage = services.resolve_access(user)["can_manage"]
        return jsonify({"schedules": schedules, "can_manage": can_manage}), 200

    return _handle(run, "GET /logistics/schedules")


@bp.route("/schedules", methods=["POST"])
@jwt_required()
@role_required(*_MANAGE_ROLES)
@requires_city_context
def criar_cronograma():
    user, err = _current_user()
    if err:
        return err
    data = request.get_json(silent=True) or {}
    return _handle(
        lambda: (jsonify(services.create_schedule(user, _city_id(), data)), 201),
        "POST /logistics/schedules",
    )


@bp.route("/schedules/<string:schedule_id>", methods=["GET"])
@jwt_required()
@role_required(*_READ_ROLES)
@requires_city_context
def obter_cronograma(schedule_id: str):
    user, err = _current_user()
    if err:
        return err
    return _handle(
        lambda: (jsonify(services.get_schedule(user, schedule_id)), 200),
        "GET /logistics/schedules/<id>",
    )


@bp.route("/schedules/<string:schedule_id>", methods=["PUT"])
@jwt_required()
@role_required(*_MANAGE_ROLES)
@requires_city_context
def atualizar_cronograma(schedule_id: str):
    user, err = _current_user()
    if err:
        return err
    data = request.get_json(silent=True) or {}
    return _handle(
        lambda: (jsonify(services.update_schedule(user, _city_id(), schedule_id, data)), 200),
        "PUT /logistics/schedules/<id>",
    )


@bp.route("/schedules/<string:schedule_id>", methods=["DELETE"])
@jwt_required()
@role_required(*_MANAGE_ROLES)
@requires_city_context
def excluir_cronograma(schedule_id: str):
    user, err = _current_user()
    if err:
        return err

    def run():
        services.delete_schedule(user, schedule_id)
        return jsonify({"success": True}), 200

    return _handle(run, "DELETE /logistics/schedules/<id>")


@bp.route("/schedules/<string:schedule_id>/publish", methods=["POST"])
@jwt_required()
@role_required(*_MANAGE_ROLES)
@requires_city_context
def publicar_cronograma(schedule_id: str):
    user, err = _current_user()
    if err:
        return err
    return _handle(
        lambda: (jsonify(services.publish_schedule(user, _city_id(), schedule_id)), 200),
        "POST /logistics/schedules/<id>/publish",
    )


@bp.route("/schedules/<string:schedule_id>/cancel", methods=["POST"])
@jwt_required()
@role_required(*_MANAGE_ROLES)
@requires_city_context
def cancelar_cronograma(schedule_id: str):
    user, err = _current_user()
    if err:
        return err
    return _handle(
        lambda: (jsonify(services.cancel_schedule(user, _city_id(), schedule_id)), 200),
        "POST /logistics/schedules/<id>/cancel",
    )
