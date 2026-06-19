# -*- coding: utf-8 -*-
"""Rotas de listas de palavras (fluência CAEd)."""
from __future__ import annotations

import logging

from flask import jsonify, request
from flask_jwt_extended import jwt_required
from sqlalchemy.exc import SQLAlchemyError

from app import db
from app.entitlements import require_feature
from app.permissions import get_current_user_from_token, role_required
from app.afirme_ler.routes import bp
from app.afirme_ler.services.word_list_service import WordListService

_CADASTRO_ROLES = ("admin", "tecadm", "professor", "coordenador", "diretor")


def _error_response(message: str, status: int):
    return jsonify({"error": message}), status


def _handle_service_error(error: Exception):
    if isinstance(error, LookupError):
        return _error_response(str(error), 404)
    if isinstance(error, PermissionError):
        return _error_response(str(error), 403)
    if isinstance(error, ValueError):
        return _error_response(str(error), 400)
    logging.error("Erro Afirme Ler (word-lists): %s", error, exc_info=True)
    return _error_response("Erro interno ao processar a solicitação.", 500)


@bp.route("/word-lists", methods=["POST"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*_CADASTRO_ROLES)
def create_word_list():
    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    data = request.get_json(silent=True)
    if not data:
        return _error_response("Corpo da requisição inválido.", 400)
    try:
        word_list = WordListService.create(user, data)
        return jsonify(word_list.to_dict()), 201
    except Exception as error:
        db.session.rollback()
        return _handle_service_error(error)


@bp.route("/word-lists", methods=["GET"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*_CADASTRO_ROLES)
def list_word_lists():
    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    try:
        items = WordListService.list_word_lists(user, request.args.to_dict())
        return jsonify([item.to_dict() for item in items]), 200
    except Exception as error:
        return _handle_service_error(error)


@bp.route("/word-lists/<word_list_id>", methods=["GET"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*_CADASTRO_ROLES)
def get_word_list(word_list_id):
    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    try:
        word_list = WordListService.get_visible(user, word_list_id)
        return jsonify(word_list.to_dict()), 200
    except Exception as error:
        return _handle_service_error(error)


@bp.route("/word-lists/<word_list_id>", methods=["PATCH"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*_CADASTRO_ROLES)
def update_word_list(word_list_id):
    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    data = request.get_json(silent=True)
    if not data:
        return _error_response("Corpo da requisição inválido.", 400)
    try:
        word_list = WordListService.update(user, word_list_id, data)
        return jsonify(word_list.to_dict()), 200
    except Exception as error:
        db.session.rollback()
        return _handle_service_error(error)


@bp.route("/word-lists/<word_list_id>", methods=["DELETE"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*_CADASTRO_ROLES)
def delete_word_list(word_list_id):
    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    try:
        WordListService.delete(user, word_list_id)
        return jsonify({"message": "Lista excluída com sucesso."}), 200
    except Exception as error:
        db.session.rollback()
        return _handle_service_error(error)


@bp.errorhandler(SQLAlchemyError)
def handle_db_error(error):
    db.session.rollback()
    logging.error("Database error Afirme Ler word-lists: %s", error, exc_info=True)
    return _error_response("Erro de banco de dados.", 500)
