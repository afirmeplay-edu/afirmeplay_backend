# -*- coding: utf-8 -*-
"""Rotas de template de capa por avaliação (tenant.test)."""
from io import BytesIO
import logging

from flask import Blueprint, jsonify, request, send_file
from flask_jwt_extended import jwt_required
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app import db
from app.decorators import requires_city_context
from app.decorators.role_required import get_current_user_from_token, role_required
from app.services.cover_templates.cover_template_service import CoverTemplateService
from app.services.cover_templates.exceptions import (
    CoverTemplateNotFound,
    CoverTemplateValidationError,
)

bp = Blueprint("cover_templates", __name__)
logger = logging.getLogger(__name__)

_WRITE_ROLES = ("admin", "tecadm", "diretor", "coordenador", "professor")


@bp.errorhandler(SQLAlchemyError)
def handle_db_error(error):
    db.session.rollback()
    logger.error("Database error (cover templates): %s", error)
    return jsonify({"error": "Erro no banco de dados", "details": str(error)}), 500


@bp.errorhandler(IntegrityError)
def handle_integrity_error(error):
    db.session.rollback()
    logger.error("Integrity error (cover templates): %s", error)
    return jsonify({"error": "Erro de integridade de dados", "details": str(error)}), 400


def _service() -> CoverTemplateService:
    return CoverTemplateService()


def _error_response(exc, fallback_status=400):
    if isinstance(exc, CoverTemplateNotFound):
        return jsonify({"error": exc.message, "code": exc.code}), 404
    if isinstance(exc, CoverTemplateValidationError):
        status = 503 if exc.code in ("STORAGE_ERROR", "PREVIEW_PNG_UNAVAILABLE") else 400
        return jsonify({"error": exc.message, "code": exc.code}), status
    logger.exception("Erro inesperado em cover templates")
    return jsonify({"error": "Erro interno do servidor", "details": str(exc)}), fallback_status


def _current_user_id():
    user = get_current_user_from_token()
    if not user:
        return None
    return user.get("user_id") or user.get("id")


@bp.route("/test/<string:test_id>/cover-templates/field-catalog", methods=["GET"])
@bp.route("/evaluations/<string:test_id>/cover-templates/field-catalog", methods=["GET"])
@jwt_required()
@requires_city_context
def field_catalog(test_id):
    try:
        _service()._require_test(test_id)
        return jsonify(CoverTemplateService.field_catalog()), 200
    except Exception as exc:
        return _error_response(exc)


@bp.route("/test/<string:test_id>/cover-templates", methods=["GET"])
@bp.route("/evaluations/<string:test_id>/cover-templates", methods=["GET"])
@jwt_required()
@requires_city_context
def list_templates(test_id):
    try:
        templates = _service().list_for_test(test_id)
        return jsonify([item.to_dict() for item in templates]), 200
    except Exception as exc:
        return _error_response(exc)


@bp.route("/test/<string:test_id>/cover-templates", methods=["POST"])
@bp.route("/evaluations/<string:test_id>/cover-templates", methods=["POST"])
@jwt_required()
@role_required(*_WRITE_ROLES)
@requires_city_context
def create_template(test_id):
    try:
        file_storage = request.files.get("file") or request.files.get("cover")
        name = request.form.get("name")
        template = _service().create_from_upload(
            test_id,
            file_storage,
            name=name,
            created_by=_current_user_id(),
        )
        return jsonify(template.to_dict()), 201
    except Exception as exc:
        return _error_response(exc)


@bp.route("/test/<string:test_id>/cover-templates/<string:template_id>", methods=["GET"])
@bp.route("/evaluations/<string:test_id>/cover-templates/<string:template_id>", methods=["GET"])
@jwt_required()
@requires_city_context
def get_template(test_id, template_id):
    try:
        template = _service().get(test_id, template_id)
        return jsonify(template.to_dict()), 200
    except Exception as exc:
        return _error_response(exc)


@bp.route("/test/<string:test_id>/cover-templates/<string:template_id>", methods=["PATCH"])
@bp.route("/evaluations/<string:test_id>/cover-templates/<string:template_id>", methods=["PATCH"])
@jwt_required()
@role_required(*_WRITE_ROLES)
@requires_city_context
def update_template(test_id, template_id):
    try:
        payload = request.get_json(silent=True) or {}
        template = _service().update(test_id, template_id, payload)
        return jsonify(template.to_dict()), 200
    except Exception as exc:
        return _error_response(exc)


@bp.route(
    "/test/<string:test_id>/cover-templates/<string:template_id>/activate",
    methods=["POST"],
)
@bp.route(
    "/evaluations/<string:test_id>/cover-templates/<string:template_id>/activate",
    methods=["POST"],
)
@jwt_required()
@role_required(*_WRITE_ROLES)
@requires_city_context
def activate_template(test_id, template_id):
    try:
        template = _service().activate(test_id, template_id)
        return jsonify(template.to_dict()), 200
    except Exception as exc:
        return _error_response(exc)


@bp.route("/test/<string:test_id>/cover-templates/<string:template_id>", methods=["DELETE"])
@bp.route(
    "/evaluations/<string:test_id>/cover-templates/<string:template_id>",
    methods=["DELETE"],
)
@jwt_required()
@role_required(*_WRITE_ROLES)
@requires_city_context
def delete_template(test_id, template_id):
    try:
        _service().delete(test_id, template_id)
        return jsonify({"success": True}), 200
    except Exception as exc:
        return _error_response(exc)


@bp.route(
    "/test/<string:test_id>/cover-templates/<string:template_id>/original",
    methods=["GET"],
)
@bp.route(
    "/evaluations/<string:test_id>/cover-templates/<string:template_id>/original",
    methods=["GET"],
)
@jwt_required(locations=["headers", "query_string"])
@requires_city_context
def get_original(test_id, template_id):
    try:
        svc = _service()
        template = svc.get(test_id, template_id)
        data, mime = svc.load_original_bytes(template)
        download_name = template.original_filename or "capa"
        return send_file(
            BytesIO(data),
            mimetype=mime,
            as_attachment=False,
            download_name=download_name,
            max_age=3600,
        )
    except Exception as exc:
        return _error_response(exc)


@bp.route(
    "/test/<string:test_id>/cover-templates/<string:template_id>/normalized",
    methods=["GET"],
)
@bp.route(
    "/evaluations/<string:test_id>/cover-templates/<string:template_id>/normalized",
    methods=["GET"],
)
@jwt_required(locations=["headers", "query_string"])
@requires_city_context
def get_normalized(test_id, template_id):
    try:
        svc = _service()
        template = svc.get(test_id, template_id)
        data = svc.load_normalized_pdf_bytes(template)
        return send_file(
            BytesIO(data),
            mimetype="application/pdf",
            as_attachment=False,
            download_name="capa-normalizada.pdf",
            max_age=3600,
        )
    except Exception as exc:
        return _error_response(exc)


@bp.route(
    "/test/<string:test_id>/cover-templates/<string:template_id>/preview",
    methods=["POST"],
)
@bp.route(
    "/evaluations/<string:test_id>/cover-templates/<string:template_id>/preview",
    methods=["POST"],
)
@jwt_required()
@role_required(*_WRITE_ROLES)
@requires_city_context
def preview_template(test_id, template_id):
    try:
        payload = request.get_json(silent=True) or {}
        data, mime = _service().preview(test_id, template_id, payload)
        extension = "png" if mime == "image/png" else "pdf"
        return send_file(
            BytesIO(data),
            mimetype=mime,
            as_attachment=False,
            download_name=f"capa-preview.{extension}",
            max_age=0,
        )
    except Exception as exc:
        return _error_response(exc)
