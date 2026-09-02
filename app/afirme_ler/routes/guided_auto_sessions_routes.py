# -*- coding: utf-8 -*-
"""Rotas da Leitura Guiada Automática."""
from __future__ import annotations

import logging
from io import BytesIO

from flask import jsonify, request, send_file
from flask_jwt_extended import jwt_required
from sqlalchemy.exc import SQLAlchemyError

from app import db
from app.decorators.tenant_required import requires_city_context
from app.entitlements import require_feature
from app.permissions import get_current_user_from_token, role_required
from app.afirme_ler.routes import bp
from app.afirme_ler.services.guided_auto_audio_service import GuidedAutoAudioService
from app.afirme_ler.services.guided_auto_session_service import GuidedAutoSessionService
from app.afirme_ler.services.parsing import get_field
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
    logging.error("Erro Afirme Ler (guided-auto-sessions): %s", error, exc_info=True)
    return _error_response("Erro interno ao processar a solicitação.", 500)


def _require_city_id() -> str:
    ctx = get_current_tenant_context()
    if not ctx or not getattr(ctx, "city_id", None):
        raise ValueError("Contexto de município obrigatório.")
    return str(ctx.city_id)


@bp.route("/guided-auto-sessions", methods=["POST"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*_APLICACAO_ROLES)
@requires_city_context
def create_guided_auto_session():
    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    data = request.get_json(silent=True)
    if not data:
        return _error_response("Corpo da requisição inválido.", 400)
    try:
        session = GuidedAutoSessionService.create(user, data)
        return (
            jsonify(
                GuidedAutoSessionService.serialize(
                    session, include_answers=True, include_audio_url=True
                )
            ),
            201,
        )
    except Exception as error:
        db.session.rollback()
        return _handle_service_error(error)


@bp.route("/guided-auto-sessions", methods=["GET"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*_APLICACAO_ROLES)
@requires_city_context
def list_guided_auto_sessions():
    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    try:
        sessions = GuidedAutoSessionService.list_sessions(request.args.to_dict())
        return (
            jsonify(
                [
                    GuidedAutoSessionService.serialize(
                        session, include_answers=False, include_audio_url=True
                    )
                    for session in sessions
                ]
            ),
            200,
        )
    except Exception as error:
        return _handle_service_error(error)


@bp.route("/guided-auto-sessions/<session_id>", methods=["GET"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*_APLICACAO_ROLES)
@requires_city_context
def get_guided_auto_session(session_id):
    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    try:
        session = GuidedAutoSessionService.get_session(
            session_id, include_answers=True, include_words=False
        )
        return (
            jsonify(
                GuidedAutoSessionService.serialize(
                    session,
                    include_answers=True,
                    include_audio_url=True,
                )
            ),
            200,
        )
    except Exception as error:
        return _handle_service_error(error)


@bp.route("/guided-auto-sessions/<session_id>/result", methods=["GET"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*_APLICACAO_ROLES)
@requires_city_context
def get_guided_auto_session_result(session_id):
    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    try:
        session = GuidedAutoSessionService.get_session(
            session_id, include_answers=True, include_words=False
        )
        if session.status == "failed":
            return _error_response(
                session.error_message or "Processamento falhou.", 422
            )
        if session.status != "completed":
            return (
                jsonify(
                    {
                        "error": "Resultado ainda não disponível.",
                        "status": session.status,
                    }
                ),
                409,
            )
        return (
            jsonify(
                GuidedAutoSessionService.serialize(
                    session,
                    include_answers=True,
                    include_audio_url=True,
                )
            ),
            200,
        )
    except Exception as error:
        return _handle_service_error(error)


@bp.route("/guided-auto-sessions/<session_id>/words", methods=["GET"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*_APLICACAO_ROLES)
@requires_city_context
def get_guided_auto_session_words(session_id):
    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    try:
        session = GuidedAutoSessionService.get_session(
            session_id, include_answers=False, include_words=True
        )
        return jsonify([word.to_dict() for word in (session.words or [])]), 200
    except Exception as error:
        return _handle_service_error(error)


@bp.route("/guided-auto-sessions/<session_id>/audio", methods=["POST"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*_APLICACAO_ROLES)
@requires_city_context
def upload_guided_auto_session_audio(session_id):
    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)

    upload = request.files.get("audio") or request.files.get("file")
    if not upload or not upload.filename:
        return _error_response(
            "Campo multipart 'audio' (ou 'file') é obrigatório.", 400
        )

    try:
        city_id = _require_city_id()
        session = GuidedAutoSessionService.get_session(session_id)
        part = GuidedAutoSessionService.resolve_part(
            session, request.form.get("part") or request.args.get("part")
        )

        duration_hint = None
        raw_duration = request.form.get("durationSeconds") or request.form.get(
            "duration_seconds"
        )
        if raw_duration is not None and str(raw_duration).strip() != "":
            try:
                duration_hint = float(raw_duration)
            except (TypeError, ValueError) as exc:
                raise ValueError("durationSeconds deve ser numérico.") from exc
            if duration_hint < 0:
                raise ValueError("durationSeconds não pode ser negativo.")

        data = upload.read()
        GuidedAutoAudioService.attach_part_audio(
            session,
            data,
            upload.content_type,
            part=part,
            city_id=city_id,
        )
        session = GuidedAutoSessionService.enqueue_processing(
            session.id,
            part=part,
            city_id=city_id,
            duration_hint_seconds=duration_hint,
        )
        return (
            jsonify(
                GuidedAutoSessionService.serialize(
                    session, include_answers=True, include_audio_url=True
                )
            ),
            202,
        )
    except Exception as error:
        db.session.rollback()
        return _handle_service_error(error)


@bp.route("/guided-auto-sessions/<session_id>/audio", methods=["GET"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*_APLICACAO_ROLES)
@requires_city_context
def download_guided_auto_session_audio(session_id):
    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    try:
        session = GuidedAutoSessionService.get_session(session_id)
        part = request.args.get("part")
        data, mime = GuidedAutoAudioService.download_part_audio(session, part=part)
        return send_file(
            BytesIO(data),
            mimetype=mime,
            as_attachment=False,
            download_name=f"guided-auto-{session_id}.webm",
            max_age=0,
        )
    except Exception as error:
        return _handle_service_error(error)


@bp.route(
    "/guided-auto-sessions/<session_id>/comprehension-answers", methods=["POST"]
)
@jwt_required()
@require_feature("afirme_reading")
@role_required(*_APLICACAO_ROLES)
@requires_city_context
def save_guided_auto_comprehension(session_id):
    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    data = request.get_json(silent=True)
    if data is None:
        return _error_response("Corpo da requisição inválido.", 400)
    try:
        answers = get_field(data, "answers", default=data if isinstance(data, list) else None)
        session = GuidedAutoSessionService.save_comprehension_answers(
            session_id, answers
        )
        return (
            jsonify(
                GuidedAutoSessionService.serialize(
                    session, include_answers=True, include_audio_url=True
                )
            ),
            200,
        )
    except Exception as error:
        db.session.rollback()
        return _handle_service_error(error)


@bp.route("/guided-auto-sessions/<session_id>", methods=["DELETE"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*_APLICACAO_ROLES)
@requires_city_context
def delete_guided_auto_session(session_id):
    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    try:
        GuidedAutoSessionService.delete(session_id)
        return (
            jsonify(
                {
                    "message": "Sessão de leitura guiada automática excluída com sucesso."
                }
            ),
            200,
        )
    except Exception as error:
        db.session.rollback()
        return _handle_service_error(error)


@bp.errorhandler(SQLAlchemyError)
def handle_guided_auto_db_error(error):
    db.session.rollback()
    logging.error(
        "Database error Afirme Ler guided-auto-sessions: %s", error, exc_info=True
    )
    return _error_response("Erro de banco de dados.", 500)
