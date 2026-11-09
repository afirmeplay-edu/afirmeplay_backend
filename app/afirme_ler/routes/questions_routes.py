# -*- coding: utf-8 -*-
"""Rotas do banco de questões do Afirme Ler (public.question)."""
from __future__ import annotations

import logging
from typing import Optional

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


def _schema_outdated_message(error: Exception) -> Optional[str]:
    """Detecta colunas do Afirme Ler ausentes (migration atrasada)."""
    text = str(getattr(error, "orig", None) or error).lower()
    markers = ("dictation_marks", "writing_stimulus", "writing_reference", "origin")
    if any(marker in text for marker in markers) and (
        "undefinedcolumn" in text
        or "does not exist" in text
        or "não existe" in text
        or "column" in text
    ):
        return (
            "O banco está desatualizado para o Afirme Educacional. "
            "Peça ao suporte para aplicar as migrações das questões."
        )
    return None


def _handle_service_error(error: Exception):
    from sqlalchemy.exc import IntegrityError, OperationalError, ProgrammingError

    if isinstance(error, LookupError):
        return _error_response(str(error), 404)
    if isinstance(error, PermissionError):
        return _error_response(str(error), 403)
    if isinstance(error, ValueError):
        return _error_response(str(error), 400)

    schema_message = _schema_outdated_message(error)
    if schema_message and isinstance(error, (ProgrammingError, OperationalError, IntegrityError)):
        logging.error("Erro Afirme Ler (questions/schema): %s", error, exc_info=True)
        return _error_response(schema_message, 500)

    if isinstance(error, IntegrityError):
        logging.error("Erro Afirme Ler (questions/integrity): %s", error, exc_info=True)
        return _error_response(
            "Não foi possível salvar a questão: dados inconsistentes no banco.",
            500,
        )

    logging.error("Erro Afirme Ler (questions): %s", error, exc_info=True)
    return _error_response(
        "Não foi possível salvar a questão no servidor. Tente de novo; se continuar, avise o suporte.",
        500,
    )


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


@bp.route("/questions/import/docx", methods=["POST"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*WRITE_ROLES)
def import_bank_questions_docx():
    """Prévia (`commit=false`) ou confirmação (`commit=true`) de importação DOCX."""
    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    file_storage = request.files.get("file")
    if file_storage is None:
        return _error_response("Envie um arquivo .docx.", 400)
    try:
        from app.afirme_ler.services.docx_import_service import (
            import_questions,
            parse_import_form,
        )

        form = parse_import_form(request)
        result = import_questions(
            file_storage,
            user,
            form["defaults"],
            commit=form["commit"],
            indexes=form["indexes"],
            dictation_overrides=form["dictation_overrides"],
        )
        return jsonify(result), 200 if form["commit"] else 200
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
