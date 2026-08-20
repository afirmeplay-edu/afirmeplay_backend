# -*- coding: utf-8 -*-
"""Rotas de avaliações de leitura (tenant) e sessões por aluno."""
from __future__ import annotations

import logging

from flask import jsonify, request
from flask_jwt_extended import jwt_required
from sqlalchemy.exc import SQLAlchemyError

from app import db
from app.decorators.tenant_required import requires_city_context
from app.entitlements import require_feature
from app.permissions import get_current_user_from_token, role_required
from app.afirme_ler.routes import AFIRME_LER_ROLES, bp
from app.afirme_ler.services.parsing import get_field
from app.afirme_ler.services.reading_evaluation_service import ReadingEvaluationService
from app.afirme_ler.services.reading_session_service import ReadingSessionService

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
    logging.error("Erro Afirme Ler (evaluations): %s", error, exc_info=True)
    return _error_response("Erro interno ao processar a solicitação.", 500)


def _require_view(user, evaluation_id):
    evaluation = ReadingEvaluationService.get_evaluation(evaluation_id)
    ReadingEvaluationService.assert_can_view(user, evaluation)
    return evaluation


def _require_apply(user, evaluation_id):
    evaluation = ReadingEvaluationService.get_evaluation(evaluation_id)
    ReadingEvaluationService.assert_can_apply(user, evaluation)
    return evaluation


@bp.route("/evaluations", methods=["POST"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*_ROLES)
@requires_city_context
def create_reading_evaluation():
    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    data = request.get_json(silent=True)
    if not data:
        return _error_response("Corpo da requisição inválido.", 400)
    try:
        evaluation = ReadingEvaluationService.create(user, data)
        return jsonify(evaluation.to_dict()), 201
    except Exception as error:
        db.session.rollback()
        return _handle_service_error(error)


@bp.route("/evaluations", methods=["GET"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*_ROLES)
@requires_city_context
def list_reading_evaluations():
    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    try:
        items = ReadingEvaluationService.list_evaluations(user, request.args.to_dict())
        return jsonify([item.to_dict() for item in items]), 200
    except Exception as error:
        return _handle_service_error(error)


@bp.route("/evaluations/<evaluation_id>", methods=["GET"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*_ROLES)
@requires_city_context
def get_reading_evaluation(evaluation_id):
    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    try:
        include_sessions = request.args.get("includeSessions", "").lower() in (
            "1",
            "true",
            "yes",
        )
        evaluation = ReadingEvaluationService.get_evaluation(
            evaluation_id,
            include_sessions=include_sessions,
        )
        ReadingEvaluationService.assert_can_view(user, evaluation)
        payload = ReadingEvaluationService.to_detail_dict(evaluation)
        if include_sessions:
            payload["sessions"] = evaluation.to_dict(include_sessions=True).get(
                "sessions", []
            )
        return jsonify(payload), 200
    except Exception as error:
        return _handle_service_error(error)


@bp.route("/evaluations/<evaluation_id>", methods=["PATCH"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*_ROLES)
@requires_city_context
def update_reading_evaluation(evaluation_id):
    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    data = request.get_json(silent=True)
    if not data:
        return _error_response("Corpo da requisição inválido.", 400)
    try:
        evaluation = ReadingEvaluationService.update(user, evaluation_id, data)
        return jsonify(evaluation.to_dict()), 200
    except Exception as error:
        db.session.rollback()
        return _handle_service_error(error)


@bp.route("/evaluations/<evaluation_id>", methods=["DELETE"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*_ROLES)
@requires_city_context
def delete_reading_evaluation(evaluation_id):
    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    try:
        ReadingEvaluationService.delete(user, evaluation_id)
        return jsonify({"message": "Avaliação excluída com sucesso."}), 200
    except Exception as error:
        db.session.rollback()
        return _handle_service_error(error)


@bp.route("/evaluations/<evaluation_id>/apply", methods=["POST"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*_ROLES)
@requires_city_context
def apply_reading_evaluation(evaluation_id):
    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    data = request.get_json(silent=True) or {}
    try:
        result = ReadingEvaluationService.apply_to_classes(user, evaluation_id, data)
        return jsonify(result), 200
    except Exception as error:
        db.session.rollback()
        return _handle_service_error(error)


@bp.route("/evaluations/<evaluation_id>/sessions", methods=["GET"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*_ROLES)
@requires_city_context
def list_reading_sessions(evaluation_id):
    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    try:
        _require_view(user, evaluation_id)
        sessions = ReadingSessionService.list_sessions(evaluation_id)
        return jsonify([session.to_dict() for session in sessions]), 200
    except Exception as error:
        return _handle_service_error(error)


@bp.route("/evaluations/<evaluation_id>/sessions/<session_id>", methods=["GET"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*_ROLES)
@requires_city_context
def get_reading_session(evaluation_id, session_id):
    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    try:
        _require_view(user, evaluation_id)
        session = ReadingSessionService.get_session(
            evaluation_id, session_id, include_answers=True
        )
        return jsonify(session.to_dict(include_answers=True)), 200
    except Exception as error:
        return _handle_service_error(error)


@bp.route("/evaluations/<evaluation_id>/sessions/<session_id>/start", methods=["POST"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*_ROLES)
@requires_city_context
def start_reading_session(evaluation_id, session_id):
    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    try:
        session = ReadingSessionService.start_session(user, evaluation_id, session_id)
        return jsonify(session.to_dict()), 200
    except Exception as error:
        db.session.rollback()
        return _handle_service_error(error)


@bp.route("/evaluations/<evaluation_id>/sessions/<session_id>/fluency", methods=["PATCH"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*_ROLES)
@requires_city_context
def save_reading_fluency(evaluation_id, session_id):
    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    data = request.get_json(silent=True) or {}
    fluency_data = get_field(data, "fluencyData", "fluency_data", default=data)
    try:
        _require_apply(user, evaluation_id)
        session = ReadingSessionService.save_fluency(
            evaluation_id, session_id, fluency_data
        )
        return jsonify(session.to_dict()), 200
    except Exception as error:
        db.session.rollback()
        return _handle_service_error(error)


@bp.route("/evaluations/<evaluation_id>/sessions/<session_id>/report", methods=["GET"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*_ROLES)
@requires_city_context
def get_reading_session_report(evaluation_id, session_id):
    """Relatório consolidado da Fluência Leitora (PLCM, precisão, ICA / Leiturômetro)."""
    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    try:
        _require_view(user, evaluation_id)
        report = ReadingSessionService.build_report(evaluation_id, session_id)
        return jsonify(report), 200
    except Exception as error:
        return _handle_service_error(error)


@bp.route("/evaluations/<evaluation_id>/sessions/<session_id>/comprehension-answers", methods=["POST"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*_ROLES)
@requires_city_context
def save_reading_comprehension_answers(evaluation_id, session_id):
    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    data = request.get_json(silent=True)
    if isinstance(data, dict):
        answers = get_field(data, "answers", default=[])
    else:
        answers = data
    try:
        _require_apply(user, evaluation_id)
        session = ReadingSessionService.save_comprehension_answers(
            evaluation_id, session_id, answers
        )
        return jsonify(session.to_dict(include_answers=True)), 200
    except Exception as error:
        db.session.rollback()
        return _handle_service_error(error)


@bp.route("/evaluations/<evaluation_id>/sessions/<session_id>/submit", methods=["POST"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*_ROLES)
@requires_city_context
def submit_reading_session(evaluation_id, session_id):
    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    try:
        _require_apply(user, evaluation_id)
        session = ReadingSessionService.finalize_session(evaluation_id, session_id)
        return jsonify(session.to_dict(include_answers=True)), 200
    except Exception as error:
        db.session.rollback()
        return _handle_service_error(error)


@bp.route("/evaluations/<evaluation_id>/sessions/<session_id>/absent", methods=["POST"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*_ROLES)
@requires_city_context
def mark_reading_session_absent(evaluation_id, session_id):
    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    try:
        _require_apply(user, evaluation_id)
        session = ReadingSessionService.mark_absent(evaluation_id, session_id)
        return jsonify(session.to_dict()), 200
    except Exception as error:
        db.session.rollback()
        return _handle_service_error(error)


@bp.errorhandler(SQLAlchemyError)
def handle_evaluations_db_error(error):
    db.session.rollback()
    logging.error("Database error Afirme Ler evaluations: %s", error, exc_info=True)
    return _error_response("Erro de banco de dados.", 500)
