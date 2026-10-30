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


@bp.route("/written-tests/<written_test_id>/answer-sheet-corrections", methods=["POST"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*AFIRME_LER_ROLES)
@requires_city_context
def correct_written_test_answer_sheets(written_test_id):
    """Lê várias folhas e grava a letra das objetivas e as imagens do ditado e do bilhete."""
    from app.afirme_ler.services.written_test_answer_sheet_correction import (
        correct_uploaded_sheets,
        load_correction_batch,
    )

    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    try:
        WrittenTestService.get(written_test_id)
        images, sources, load_errors, file_count = load_correction_batch(request)
        if file_count == 0:
            return _error_response("Envie um ou mais PDFs ou imagens do cartão.", 400)
        return jsonify(correct_uploaded_sheets(
            written_test_id,
            images,
            sources=sources,
            load_errors=load_errors,
            file_count=file_count,
        )), 200
    except Exception as error:
        db.session.rollback()
        return _handle_service_error(error)


@bp.route(
    "/written-tests/<written_test_id>/answer-sheet-corrections/<student_id>/crops/<int:number>",
    methods=["GET"],
)
@jwt_required()
@require_feature("afirme_reading")
@role_required(*AFIRME_LER_ROLES)
@requires_city_context
def download_written_test_crop(written_test_id, student_id, number):
    """Devolve o PNG do recorte para o professor ver a letra."""
    from app.afirme_ler.services.written_test_answer_sheet_correction import load_crop_png

    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    try:
        WrittenTestService.get(written_test_id)
        png = load_crop_png(written_test_id, student_id, number)
    except Exception as error:
        db.session.rollback()
        return _handle_service_error(error)
    return send_file(
        io.BytesIO(png),
        mimetype="image/png",
        as_attachment=False,
        download_name=f"recorte_q{int(number):02d}.png",
        max_age=0,
    )


@bp.route("/written-tests/<written_test_id>/answer-sheet-corrections", methods=["GET"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*AFIRME_LER_ROLES)
@requires_city_context
def list_written_test_answer_sheet_corrections(written_test_id):
    """Lista a nota das objetivas e a correção do ditado e do bilhete."""
    from app.afirme_ler.services.written_test_writing_grade import list_corrections

    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    try:
        return jsonify(list_corrections(written_test_id)), 200
    except Exception as error:
        db.session.rollback()
        return _handle_service_error(error)


@bp.route("/written-tests/<written_test_id>/writing-corrections", methods=["POST"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*AFIRME_LER_ROLES)
@requires_city_context
def save_written_test_writing_correction(written_test_id):
    """Lançamento manual do ditado e do bilhete quando o cartão não foi enviado."""
    from app.afirme_ler.services.written_test_writing_grade import save_manual_writing

    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return _error_response("Corpo da requisição inválido.", 400)
    student_id = data.get("studentId")
    if not student_id or not str(student_id).strip():
        return _error_response("studentId é obrigatório.", 400)
    try:
        return jsonify(save_manual_writing(
            written_test_id, str(student_id).strip(), data, reviewer_id=user.get("id"),
        )), 200
    except Exception as error:
        db.session.rollback()
        return _handle_service_error(error)


@bp.route("/written-tests/<written_test_id>/writing-reviews", methods=["POST"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*WRITE_ROLES)
@requires_city_context
def review_written_test_writing(written_test_id):
    """O professor confirma a transcrição e a nota é recalculada em cima desse texto."""
    from app.afirme_ler.services.written_test_writing_grade import confirm_writing

    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return _error_response("Corpo da requisição inválido.", 400)
    student_id = data.get("studentId")
    if not student_id or not str(student_id).strip():
        return _error_response("studentId é obrigatório.", 400)
    try:
        return jsonify(confirm_writing(
            written_test_id, str(student_id).strip(), data, str(user.get("id") or ""),
        )), 200
    except Exception as error:
        db.session.rollback()
        return _handle_service_error(error)


@bp.route("/written-tests/<written_test_id>/writing-release", methods=["POST"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*WRITE_ROLES)
@requires_city_context
def release_written_test_writing(written_test_id):
    """Libera a nota. Questão ainda pendente não é publicada."""
    from app.afirme_ler.services.written_test_writing_grade import release_writing

    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return _error_response("Corpo da requisição inválido.", 400)
    student_id = data.get("studentId")
    if not student_id or not str(student_id).strip():
        return _error_response("studentId é obrigatório.", 400)
    try:
        return jsonify(release_writing(
            written_test_id, str(student_id).strip(), str(user.get("id") or ""),
        )), 200
    except Exception as error:
        db.session.rollback()
        return _handle_service_error(error)


@bp.route("/written-tests/<written_test_id>/ica-dashboard", methods=["GET"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*AFIRME_LER_ROLES)
@requires_city_context
def written_test_ica_dashboard(written_test_id):
    """Participação, IAD e o recorte município, escola, série, turma ou aluno."""
    from app.afirme_ler.services.written_test_ica_service import ica_dashboard

    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    try:
        return jsonify(ica_dashboard(written_test_id, request.args.to_dict())), 200
    except Exception as error:
        db.session.rollback()
        return _handle_service_error(error)


@bp.route("/written-tests/<written_test_id>/skill-map", methods=["GET"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*AFIRME_LER_ROLES)
@requires_city_context
def written_test_skill_map(written_test_id):
    """Aproveitamento por habilidade no mesmo recorte do painel."""
    from app.afirme_ler.services.written_test_ica_service import skill_map

    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    try:
        return jsonify(skill_map(written_test_id, request.args.to_dict())), 200
    except Exception as error:
        db.session.rollback()
        return _handle_service_error(error)


@bp.route("/written-tests/<written_test_id>/results.csv", methods=["GET"])
@jwt_required()
@require_feature("afirme_reading")
@role_required(*AFIRME_LER_ROLES)
@requires_city_context
def written_test_ica_csv(written_test_id):
    """CSV dos alunos finalizados no recorte atual."""
    from app.afirme_ler.services.written_test_ica_service import ica_csv

    user = get_current_user_from_token()
    if not user:
        return _error_response("Usuário não encontrado.", 401)
    try:
        content, filename = ica_csv(written_test_id, request.args.to_dict())
    except Exception as error:
        db.session.rollback()
        return _handle_service_error(error)
    return send_file(
        io.BytesIO(content),
        mimetype="text/csv; charset=utf-8",
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
