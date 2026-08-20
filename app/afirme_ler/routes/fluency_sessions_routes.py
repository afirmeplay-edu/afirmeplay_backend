# -*- coding: utf-8 -*-
"""Rotas da sessão ad-hoc de Fluência Leitora (Opção A)."""
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
from app.afirme_ler.routes import AFIRME_LER_ROLES, bp
from app.afirme_ler.services.fluency_audio_service import FluencyAudioService
from app.afirme_ler.services.fluency_session_service import FluencySessionService
from app.afirme_ler.services.parsing import get_field
from app.utils.tenant_middleware import get_current_tenant_context

_APLICACAO_ROLES = AFIRME_LER_ROLES


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
    logging.error("Erro Afirme Ler (fluency-sessions): %s", error, exc_info=True)
    return _error_response("Erro interno ao processar a solicitação.", 500)


def _require_city_id() -> str:
    ctx = get_current_tenant_context()
    if not ctx or not getattr(ctx, "city_id", None):
        raise ValueError("Contexto de município obrigatório.")
    return str(ctx.city_id)


def _load_session(user, session_id, *, mutate=False, include_answers=False):
    session = FluencySessionService.get_session(
        session_id, include_answers=include_answers
    )
    FluencySessionService.assert_can_access(user, session, mutate=mutate)
    return session


@bp.route("/fluency-sessions", methods=["POST"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*_APLICACAO_ROLES)
@requires_city_context
def create_fluency_session():
    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    data = request.get_json(silent=True)
    if not data:
        return _error_response("Corpo da requisição inválido.", 400)
    try:
        session = FluencySessionService.create(user, data)
        return jsonify(FluencySessionService.serialize(session, include_answers=True)), 201
    except Exception as error:
        db.session.rollback()
        return _handle_service_error(error)


@bp.route("/fluency-sessions/<session_id>", methods=["GET"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*_APLICACAO_ROLES)
@requires_city_context
def get_fluency_session(session_id):
    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    try:
        session = _load_session(user, session_id, include_answers=True)
        return (
            jsonify(
                FluencySessionService.serialize(session, include_answers=True)
            ),
            200,
        )
    except Exception as error:
        return _handle_service_error(error)


@bp.route("/fluency-sessions/<session_id>/fluency", methods=["PATCH"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*_APLICACAO_ROLES)
@requires_city_context
def save_fluency_session_fluency(session_id):
    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    data = request.get_json(silent=True) or {}
    fluency_data = get_field(data, "fluencyData", "fluency_data", default=data)
    try:
        _load_session(user, session_id, mutate=True)
        session = FluencySessionService.save_fluency(session_id, fluency_data)
        return jsonify(FluencySessionService.serialize(session, include_answers=True)), 200
    except Exception as error:
        db.session.rollback()
        return _handle_service_error(error)


@bp.route("/fluency-sessions/<session_id>/comprehension-answers", methods=["POST"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*_APLICACAO_ROLES)
@requires_city_context
def save_fluency_session_comprehension(session_id):
    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    data = request.get_json(silent=True)
    if isinstance(data, dict):
        answers = get_field(data, "answers", default=[])
    else:
        answers = data
    try:
        _load_session(user, session_id, mutate=True)
        session = FluencySessionService.save_comprehension_answers(
            session_id, answers or []
        )
        return jsonify(FluencySessionService.serialize(session, include_answers=True)), 200
    except Exception as error:
        db.session.rollback()
        return _handle_service_error(error)


@bp.route("/fluency-sessions/<session_id>/audio", methods=["POST"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*_APLICACAO_ROLES)
@requires_city_context
def upload_fluency_session_audio(session_id):
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
        session = _load_session(user, session_id, mutate=True)
        if session.status not in ("em_andamento",):
            raise ValueError("Sessão não está em andamento.")
        part = FluencyAudioService.validate_part(
            request.form.get("part") or request.args.get("part")
        )
        data = upload.read()
        result = FluencyAudioService.attach_part_audio(
            session,
            data,
            upload.content_type,
            part=part,
            city_id=city_id,
        )
        return jsonify(result), 200
    except Exception as error:
        db.session.rollback()
        return _handle_service_error(error)


@bp.route("/fluency-sessions/<session_id>/audio", methods=["GET"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*_APLICACAO_ROLES)
@requires_city_context
def download_fluency_session_audio(session_id):
    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    try:
        session = _load_session(user, session_id)
        part = request.args.get("part")
        data, mime = FluencyAudioService.download_part_audio(session, part=part)
        return send_file(
            BytesIO(data),
            mimetype=mime,
            as_attachment=False,
            download_name=f"fluency-{session_id}-{part or 'audio'}.webm",
        )
    except Exception as error:
        return _handle_service_error(error)


@bp.route("/fluency-sessions/<session_id>/report", methods=["GET"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*_APLICACAO_ROLES)
@requires_city_context
def get_fluency_session_report(session_id):
    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    try:
        session = _load_session(user, session_id, include_answers=True)
        report = FluencySessionService.build_report(session_id)
        return jsonify(report), 200
    except Exception as error:
        return _handle_service_error(error)


@bp.route("/fluency-sessions/<session_id>/submit", methods=["POST"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*_APLICACAO_ROLES)
@requires_city_context
def submit_fluency_session(session_id):
    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    try:
        _load_session(user, session_id, mutate=True)
        session = FluencySessionService.finalize_session(session_id)
        return jsonify(FluencySessionService.serialize(session, include_answers=True)), 200
    except Exception as error:
        db.session.rollback()
        return _handle_service_error(error)


@bp.route("/fluency-sessions/<session_id>/absent", methods=["POST"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*_APLICACAO_ROLES)
@requires_city_context
def mark_fluency_session_absent(session_id):
    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    try:
        _load_session(user, session_id, mutate=True)
        session = FluencySessionService.mark_absent(session_id)
        return jsonify(FluencySessionService.serialize(session)), 200
    except Exception as error:
        db.session.rollback()
        return _handle_service_error(error)


@bp.errorhandler(SQLAlchemyError)
def handle_fluency_sessions_db_error(error):
    db.session.rollback()
    logging.error("Erro de banco (fluency-sessions): %s", error, exc_info=True)
    return _error_response("Erro de banco de dados.", 500)
