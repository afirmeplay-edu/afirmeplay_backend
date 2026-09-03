# -*- coding: utf-8 -*-
"""PDF da ficha da avaliação (capa + questões). Síncrono, sem OMR."""
from io import BytesIO
import logging

from flask import Blueprint, jsonify, request, send_file
from flask_jwt_extended import jwt_required

from app.decorators import requires_city_context
from app.decorators.role_required import role_required
from app.services.evaluation_exam_pdf_service import (
    EvaluationExamPdfService,
    ExamPdfError,
)

bp = Blueprint("evaluation_exam_pdf", __name__)
logger = logging.getLogger(__name__)

_ROLES = ("admin", "tecadm", "diretor", "coordenador", "professor")


def _error_response(exc):
    if isinstance(exc, ExamPdfError):
        return jsonify({"error": exc.message, "code": exc.code}), exc.status
    logger.exception("Erro ao gerar PDF da ficha")
    return jsonify({"error": "Erro interno do servidor", "code": "INTERNAL_ERROR"}), 500


def _parse_include_gabarito() -> bool:
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return False
    value = payload.get("include_gabarito", False)
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "sim")
    return bool(value)


@bp.route("/test/<string:test_id>/exam-pdf", methods=["POST"])
@bp.route("/evaluations/<string:test_id>/exam-pdf", methods=["POST"])
@jwt_required()
@role_required(*_ROLES)
@requires_city_context
def download_exam_pdf(test_id):
    try:
        include_gabarito = _parse_include_gabarito()
        pdf_bytes, filename = EvaluationExamPdfService().build_exam_pdf(
            test_id, include_gabarito=include_gabarito
        )
        return send_file(
            BytesIO(pdf_bytes),
            mimetype="application/pdf",
            as_attachment=True,
            download_name=filename,
        )
    except ExamPdfError as exc:
        return _error_response(exc)
    except Exception as exc:
        return _error_response(exc)
