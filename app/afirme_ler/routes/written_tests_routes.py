# -*- coding: utf-8 -*-
"""Rotas da avaliação escrita do Afirme Ler (/afirme-reading/written-tests)."""
from __future__ import annotations

import io
import logging

from flask import jsonify, request, send_file
from flask_jwt_extended import jwt_required

from app import db
from app.decorators.tenant_required import requires_city_context
from app.entitlements import require_feature
from app.permissions import get_current_user_from_token, role_required
from app.afirme_ler.routes import AFIRME_LER_ROLES, bp
from app.afirme_ler.services.question_bank_service import WRITE_ROLES
from app.afirme_ler.services import written_test_answer_sheet_service as answer_sheets
from app.afirme_ler.services.written_test_pdf_service import (
    WrittenTestPdfService,
    pdf_filename,
    resolve_context_city,
)
from app.afirme_ler.services.written_test_service import WrittenTestService, to_detail


def _error_response(message: str, status: int):
    return jsonify({"error": message}), status


def _handle_service_error(error: Exception):
    if isinstance(error, LookupError):
        return _error_response(str(error), 404)
    if isinstance(error, PermissionError):
        return _error_response(str(error), 403)
    if isinstance(error, ValueError):
        return _error_response(str(error), 400)
    logging.error("Erro Afirme Ler (written-tests): %s", error, exc_info=True)
    return _error_response("Erro interno ao processar a solicitação.", 500)


def _json_body():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) and data else None


@bp.route("/written-tests", methods=["POST"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*WRITE_ROLES)
@requires_city_context
def create_written_test():
    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    data = _json_body()
    if data is None:
        return _error_response("Corpo da requisição inválido.", 400)
    try:
        return jsonify(to_detail(WrittenTestService.create(user, data))), 201
    except Exception as error:
        db.session.rollback()
        return _handle_service_error(error)


@bp.route("/written-tests", methods=["GET"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*AFIRME_LER_ROLES)
@requires_city_context
def list_written_tests():
    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    try:
        return jsonify(WrittenTestService.list_tests(request.args.to_dict())), 200
    except Exception as error:
        db.session.rollback()
        return _handle_service_error(error)


@bp.route("/written-tests/<written_test_id>", methods=["GET"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*AFIRME_LER_ROLES)
@requires_city_context
def get_written_test(written_test_id):
    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    try:
        return jsonify(to_detail(WrittenTestService.get(written_test_id))), 200
    except Exception as error:
        db.session.rollback()
        return _handle_service_error(error)


@bp.route("/written-tests/<written_test_id>", methods=["PUT"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*WRITE_ROLES)
@requires_city_context
def update_written_test(written_test_id):
    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    data = _json_body()
    if data is None:
        return _error_response("Corpo da requisição inválido.", 400)
    try:
        return jsonify(to_detail(WrittenTestService.update(user, written_test_id, data))), 200
    except Exception as error:
        db.session.rollback()
        return _handle_service_error(error)


@bp.route("/written-tests/<written_test_id>", methods=["DELETE"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*WRITE_ROLES)
@requires_city_context
def delete_written_test(written_test_id):
    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    try:
        WrittenTestService.delete(user, written_test_id)
        return jsonify({"message": "Avaliação excluída com sucesso."}), 200
    except Exception as error:
        db.session.rollback()
        return _handle_service_error(error)


@bp.route("/written-tests/<written_test_id>/questions", methods=["PUT"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*WRITE_ROLES)
@requires_city_context
def set_written_test_questions(written_test_id):
    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    data = _json_body()
    if data is None:
        return _error_response("Corpo da requisição inválido.", 400)
    try:
        written_test = WrittenTestService.set_questions(user, written_test_id, data)
        return jsonify(to_detail(written_test)), 200
    except Exception as error:
        db.session.rollback()
        return _handle_service_error(error)


@bp.route("/written-tests/<written_test_id>/apply", methods=["POST"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*WRITE_ROLES)
@requires_city_context
def apply_written_test(written_test_id):
    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    data = _json_body()
    if data is None:
        return _error_response("Corpo da requisição inválido.", 400)
    try:
        return jsonify(WrittenTestService.apply(user, written_test_id, data)), 200
    except Exception as error:
        db.session.rollback()
        return _handle_service_error(error)


@bp.route("/written-tests/<written_test_id>/classes", methods=["GET"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*AFIRME_LER_ROLES)
@requires_city_context
def list_written_test_classes(written_test_id):
    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    try:
        return jsonify(WrittenTestService.list_classes(written_test_id)), 200
    except Exception as error:
        db.session.rollback()
        return _handle_service_error(error)


@bp.route("/written-tests/<written_test_id>/classes/<class_id>/students", methods=["GET"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*AFIRME_LER_ROLES)
@requires_city_context
def list_written_test_class_students(written_test_id, class_id):
    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    try:
        return jsonify(WrittenTestService.list_students(written_test_id, class_id)), 200
    except Exception as error:
        db.session.rollback()
        return _handle_service_error(error)


@bp.route("/written-tests/<written_test_id>/classes/<class_id>", methods=["DELETE"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*WRITE_ROLES)
@requires_city_context
def remove_written_test_class(written_test_id, class_id):
    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    try:
        WrittenTestService.remove_class(user, written_test_id, class_id)
        return jsonify({"message": "Aplicação da turma retirada com sucesso."}), 200
    except Exception as error:
        db.session.rollback()
        return _handle_service_error(error)


@bp.route("/written-tests/<written_test_id>/pdf", methods=["GET"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*AFIRME_LER_ROLES)
@requires_city_context
def download_written_test_pdf(written_test_id):
    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    try:
        written_test = WrittenTestService.get(written_test_id)
        pdf_bytes = WrittenTestPdfService().generate_pdf(written_test, resolve_context_city())
    except Exception as error:
        db.session.rollback()
        return _handle_service_error(error)
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=pdf_filename(written_test.title),
        max_age=0,
    )


def _context_city_id():
    from app.utils.tenant_middleware import get_current_tenant_context

    context = get_current_tenant_context()
    return getattr(context, "city_id", None) if context else None


@bp.route("/written-tests/<written_test_id>/answer-sheets", methods=["POST"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*AFIRME_LER_ROLES)
@requires_city_context
def create_written_test_answer_sheets(written_test_id):
    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    data = request.get_json(silent=True)
    if data is not None and not isinstance(data, dict):
        return _error_response("Corpo da requisição inválido.", 400)
    city_id = _context_city_id()
    if not city_id:
        return _error_response("Município do contexto não identificado.", 400)
    try:
        run = answer_sheets.create_run(user, written_test_id, data or {})
        answer_sheets.dispatch_run(run, city_id)
        return jsonify(answer_sheets.describe_run(run)), 202
    except answer_sheets.GenerationInProgress as conflict:
        db.session.rollback()
        payload = {"error": str(conflict), "run": answer_sheets.describe_run(conflict.run)}
        return jsonify(payload), 409
    except Exception as error:
        db.session.rollback()
        return _handle_service_error(error)


@bp.route("/written-tests/<written_test_id>/answer-sheets", methods=["GET"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*AFIRME_LER_ROLES)
@requires_city_context
def list_written_test_answer_sheets(written_test_id):
    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    try:
        return jsonify(answer_sheets.list_runs(written_test_id)), 200
    except Exception as error:
        db.session.rollback()
        return _handle_service_error(error)


@bp.route("/written-tests/<written_test_id>/answer-sheets/<run_id>/download", methods=["GET"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*AFIRME_LER_ROLES)
@requires_city_context
def download_written_test_answer_sheets(written_test_id, run_id):
    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    try:
        zip_bytes, filename = answer_sheets.download_zip(written_test_id, run_id)
    except Exception as error:
        db.session.rollback()
        return _handle_service_error(error)
    return send_file(
        io.BytesIO(zip_bytes),
        mimetype="application/zip",
        as_attachment=True,
        download_name=filename,
        max_age=0,
    )


@bp.route("/written-tests/<written_test_id>/publish", methods=["POST"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*WRITE_ROLES)
@requires_city_context
def publish_written_test(written_test_id):
    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    try:
        return jsonify(to_detail(WrittenTestService.publish(user, written_test_id))), 200
    except Exception as error:
        db.session.rollback()
        return _handle_service_error(error)
