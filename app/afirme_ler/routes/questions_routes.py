# -*- coding: utf-8 -*-
"""Rotas do banco de questões do Afirme Ler (public.question)."""
from __future__ import annotations

import logging

from flask import jsonify, request
from flask_jwt_extended import jwt_required

from app import db
from app.entitlements import require_feature
from app.permissions import get_current_user_from_token, role_required
from app.afirme_ler.routes import AFIRME_LER_ROLES, bp
from app.afirme_ler.services.question_bank_service import (
    WRITE_ROLES,
    QuestionBankService,
    to_response,
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
    logging.error("Erro Afirme Ler (questions): %s", error, exc_info=True)
    return _error_response("Erro interno ao processar a solicitação.", 500)


@bp.route("/questions", methods=["POST"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*WRITE_ROLES)
def create_bank_question():
    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not data:
        return _error_response("Corpo da requisição inválido.", 400)
    try:
        question = QuestionBankService.create(user, data)
        return jsonify(to_response(question)), 201
    except Exception as error:
        db.session.rollback()
        return _handle_service_error(error)


@bp.route("/questions", methods=["GET"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*AFIRME_LER_ROLES)
def list_bank_questions():
    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    try:
        return jsonify(QuestionBankService.list_questions(user, request.args.to_dict())), 200
    except Exception as error:
        db.session.rollback()
        return _handle_service_error(error)


@bp.route("/questions/<question_id>", methods=["GET"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*AFIRME_LER_ROLES)
def get_bank_question(question_id):
    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    try:
        question = QuestionBankService.get_question(user, question_id)
        return jsonify(to_response(question)), 200
    except Exception as error:
        db.session.rollback()
        return _handle_service_error(error)


@bp.route("/questions/<question_id>", methods=["PUT"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*WRITE_ROLES)
def update_bank_question(question_id):
    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not data:
        return _error_response("Corpo da requisição inválido.", 400)
    try:
        question = QuestionBankService.update(user, question_id, data)
        return jsonify(to_response(question)), 200
    except Exception as error:
        db.session.rollback()
        return _handle_service_error(error)


@bp.route("/questions/image-description", methods=["POST"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*WRITE_ROLES)
def preview_bank_question_image():
    """Descreve a foto do formulário e devolve o texto, sem gravar a questão."""
    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not data:
        return _error_response("Corpo da requisição inválido.", 400)
    try:
        description = QuestionBankService.preview_image_description(user, data)
        return jsonify({"imageDescription": description}), 200
    except Exception as error:
        db.session.rollback()
        return _handle_service_error(error)


@bp.route("/questions/<question_id>/image-description", methods=["POST"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*WRITE_ROLES)
def describe_bank_question_image(question_id):
    """O professor pede a descrição da figura já anexada na questão de ditado."""
    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    try:
        question = QuestionBankService.describe_image(user, question_id)
        return jsonify(to_response(question)), 200
    except Exception as error:
        db.session.rollback()
        return _handle_service_error(error)
