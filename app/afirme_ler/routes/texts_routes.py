# -*- coding: utf-8 -*-
"""Rotas de textos de leitura e questões de compreensão."""
from __future__ import annotations

import logging

from flask import jsonify, request
from flask_jwt_extended import jwt_required
from sqlalchemy.exc import SQLAlchemyError

from app import db
from app.entitlements import require_feature
from app.permissions import get_current_user_from_token, role_required
from app.afirme_ler.routes import AFIRME_LER_ROLES, bp
from app.afirme_ler.services.reading_question_service import ReadingQuestionService
from app.afirme_ler.services.reading_text_service import ReadingTextService

_CADASTRO_ROLES = AFIRME_LER_ROLES


def _error_response(message: str, status: int):
    return jsonify({"error": message}), status


def _handle_service_error(error: Exception):
    if isinstance(error, LookupError):
        return _error_response(str(error), 404)
    if isinstance(error, PermissionError):
        return _error_response(str(error), 403)
    if isinstance(error, ValueError):
        return _error_response(str(error), 400)
    logging.error("Erro Afirme Ler (texts): %s", error, exc_info=True)
    return _error_response("Erro interno ao processar a solicitação.", 500)


@bp.route("/texts", methods=["POST"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*_CADASTRO_ROLES)
def create_reading_text():
    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    data = request.get_json(silent=True)
    if not data:
        return _error_response("Corpo da requisição inválido.", 400)
    try:
        text = ReadingTextService.create(user, data)
        return jsonify(text.to_dict(include_questions=True)), 201
    except Exception as error:
        db.session.rollback()
        return _handle_service_error(error)


@bp.route("/texts", methods=["GET"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*_CADASTRO_ROLES)
def list_reading_texts():
    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    try:
        texts = ReadingTextService.list_texts(user, request.args.to_dict())
        return jsonify([text.to_dict() for text in texts]), 200
    except Exception as error:
        return _handle_service_error(error)


@bp.route("/texts/<text_id>", methods=["GET"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*_CADASTRO_ROLES)
def get_reading_text(text_id):
    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    try:
        text = ReadingTextService.get_visible_text(user, text_id, include_questions=True)
        return jsonify(text.to_dict(include_questions=True)), 200
    except Exception as error:
        return _handle_service_error(error)


@bp.route("/texts/<text_id>", methods=["PATCH"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*_CADASTRO_ROLES)
def update_reading_text(text_id):
    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    data = request.get_json(silent=True)
    if not data:
        return _error_response("Corpo da requisição inválido.", 400)
    try:
        text = ReadingTextService.update(user, text_id, data)
        return jsonify(text.to_dict(include_questions=True)), 200
    except Exception as error:
        db.session.rollback()
        return _handle_service_error(error)


@bp.route("/texts/<text_id>", methods=["DELETE"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*_CADASTRO_ROLES)
def delete_reading_text(text_id):
    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    try:
        ReadingTextService.delete(user, text_id)
        return jsonify({"message": "Texto excluído com sucesso."}), 200
    except Exception as error:
        db.session.rollback()
        return _handle_service_error(error)


@bp.route("/texts/<text_id>/questions", methods=["POST"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*_CADASTRO_ROLES)
def create_reading_question(text_id):
    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    data = request.get_json(silent=True)
    if not data:
        return _error_response("Corpo da requisição inválido.", 400)
    try:
        question = ReadingQuestionService.create(user, text_id, data)
        return jsonify(question.to_dict()), 201
    except Exception as error:
        db.session.rollback()
        return _handle_service_error(error)


@bp.route("/texts/<text_id>/questions/bulk", methods=["POST"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*_CADASTRO_ROLES)
def create_reading_questions_bulk(text_id):
    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    data = request.get_json(silent=True)
    if not isinstance(data, list):
        return _error_response("Envie um array de questões.", 400)
    try:
        questions = ReadingQuestionService.create_bulk(user, text_id, data)
        return jsonify([question.to_dict() for question in questions]), 201
    except Exception as error:
        db.session.rollback()
        return _handle_service_error(error)


@bp.route("/texts/<text_id>/questions", methods=["GET"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*_CADASTRO_ROLES)
def list_reading_questions(text_id):
    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    try:
        questions = ReadingQuestionService.list_questions(user, text_id)
        return jsonify([question.to_dict() for question in questions]), 200
    except Exception as error:
        return _handle_service_error(error)


@bp.route("/texts/<text_id>/questions/<question_id>", methods=["GET"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*_CADASTRO_ROLES)
def get_reading_question(text_id, question_id):
    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    try:
        question = ReadingQuestionService.get_question(user, text_id, question_id)
        return jsonify(question.to_dict()), 200
    except Exception as error:
        return _handle_service_error(error)


@bp.route("/texts/<text_id>/questions/<question_id>", methods=["PATCH"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*_CADASTRO_ROLES)
def update_reading_question(text_id, question_id):
    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    data = request.get_json(silent=True)
    if not data:
        return _error_response("Corpo da requisição inválido.", 400)
    try:
        question = ReadingQuestionService.update(user, text_id, question_id, data)
        return jsonify(question.to_dict()), 200
    except Exception as error:
        db.session.rollback()
        return _handle_service_error(error)


@bp.route("/texts/<text_id>/questions/<question_id>", methods=["DELETE"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*_CADASTRO_ROLES)
def delete_reading_question(text_id, question_id):
    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    try:
        ReadingQuestionService.delete(user, text_id, question_id)
        return jsonify({"message": "Questão excluída com sucesso."}), 200
    except Exception as error:
        db.session.rollback()
        return _handle_service_error(error)


@bp.errorhandler(SQLAlchemyError)
def handle_db_error(error):
    db.session.rollback()
    logging.error("Database error Afirme Ler texts: %s", error, exc_info=True)
    return _error_response("Erro de banco de dados.", 500)
