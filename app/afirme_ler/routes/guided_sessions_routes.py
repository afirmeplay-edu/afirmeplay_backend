# -*- coding: utf-8 -*-
"""Rotas de Leitura Guiada (sessão livre aluno+texto+áudio)."""
from __future__ import annotations

import logging

from flask import jsonify, request
from flask_jwt_extended import jwt_required
from sqlalchemy.exc import SQLAlchemyError

from app import db
from app.decorators.tenant_required import requires_city_context
from app.entitlements import require_feature
from app.permissions import get_current_user_from_token, role_required
from app.afirme_ler.routes import bp
from app.afirme_ler.services.guided_audio_service import GuidedAudioService
from app.afirme_ler.services.guided_session_service import GuidedSessionService
from app.utils.tenant_middleware import get_current_tenant_context

_APLICACAO_ROLES = (
    "admin",
    "tecadm",
    "professor",
    "coordenador",
    "diretor",
    "aplicador",
)


def _error_response(message: str, status: int):
    return jsonify({"error": message}), status


def _handle_service_error(error: Exception):
    if isinstance(error, LookupError):
        return _error_response(str(error), 404)
    if isinstance(error, PermissionError):
        return _error_response(str(error), 403)
    if isinstance(error, ValueError):
        return _error_response(str(error), 400)
    if isinstance(error, RuntimeError):
        return _error_response(str(error), 500)
    logging.error("Erro Afirme Ler (guided-sessions): %s", error, exc_info=True)
    return _error_response("Erro interno ao processar a solicitação.", 500)


@bp.route("/guided-sessions", methods=["POST"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*_APLICACAO_ROLES)
@requires_city_context
def create_guided_session():
    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    data = request.get_json(silent=True)
    if not data:
        return _error_response("Corpo da requisição inválido.", 400)
    try:
        session = GuidedSessionService.create(user, data)
        return (
            jsonify(
                GuidedSessionService.serialize(
                    session, include_answers=True, include_audio_url=True
                )
            ),
            201,
        )
    except Exception as error:
        db.session.rollback()
        return _handle_service_error(error)


@bp.route("/guided-sessions", methods=["GET"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*_APLICACAO_ROLES)
@requires_city_context
def list_guided_sessions():
    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    try:
        sessions = GuidedSessionService.list_sessions(request.args.to_dict())
        return (
            jsonify(
                [
                    GuidedSessionService.serialize(
                        session, include_answers=False, include_audio_url=True
                    )
                    for session in sessions
                ]
            ),
            200,
        )
    except Exception as error:
        return _handle_service_error(error)


@bp.route("/guided-sessions/<session_id>", methods=["GET"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*_APLICACAO_ROLES)
@requires_city_context
def get_guided_session(session_id):
    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    try:
        session = GuidedSessionService.get_session(session_id, include_answers=True)
        return (
            jsonify(
                GuidedSessionService.serialize(
                    session, include_answers=True, include_audio_url=True
                )
            ),
            200,
        )
    except Exception as error:
        return _handle_service_error(error)


@bp.route("/guided-sessions/<session_id>/audio", methods=["POST"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*_APLICACAO_ROLES)
@requires_city_context
def upload_guided_session_audio(session_id):
    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)

    upload = request.files.get("audio") or request.files.get("file")
    if not upload or not upload.filename:
        return _error_response(
            "Campo multipart 'audio' (ou 'file') é obrigatório.", 400
        )

    try:
        session = GuidedSessionService.get_session(session_id)
        data = upload.read()
        ctx = get_current_tenant_context()
        city_id = str(ctx.city_id) if ctx and getattr(ctx, "city_id", None) else None
        GuidedAudioService.attach_audio(
            session,
            data,
            upload.content_type,
            city_id=city_id,
        )
        session = GuidedSessionService.get_session(session.id, include_answers=True)
        return (
            jsonify(
                GuidedSessionService.serialize(
                    session, include_answers=True, include_audio_url=True
                )
            ),
            200,
        )
    except Exception as error:
        db.session.rollback()
        return _handle_service_error(error)


@bp.route("/guided-sessions/<session_id>/audio", methods=["GET"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*_APLICACAO_ROLES)
@requires_city_context
def download_guided_session_audio(session_id):
    """Proxy autenticado de playback (fetch + blob no frontend)."""
    from io import BytesIO

    from flask import send_file

    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    try:
        session = GuidedSessionService.get_session(session_id)
        data, mime = GuidedAudioService.download_audio(session)
        return send_file(
            BytesIO(data),
            mimetype=mime,
            as_attachment=False,
            download_name=f"guided-{session_id}.webm",
            max_age=0,
        )
    except Exception as error:
        return _handle_service_error(error)


@bp.route("/guided-sessions/<session_id>", methods=["DELETE"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*_APLICACAO_ROLES)
@requires_city_context
def delete_guided_session(session_id):
    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    try:
        GuidedSessionService.delete(session_id)
        return jsonify({"message": "Sessão de leitura guiada excluída com sucesso."}), 200
    except Exception as error:
        db.session.rollback()
        return _handle_service_error(error)


@bp.errorhandler(SQLAlchemyError)
def handle_guided_db_error(error):
    db.session.rollback()
    logging.error("Database error Afirme Ler guided-sessions: %s", error, exc_info=True)
    return _error_response("Erro de banco de dados.", 500)
