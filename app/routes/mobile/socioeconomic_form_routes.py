# -*- coding: utf-8 -*-
"""
Rotas mobile para formulários socioeconômicos (entrada offline pelo aplicador).
"""
from flask import request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from app import db
from app.models.user import User, RoleEnum
from app.routes.mobile.blueprint import mobile_bp
from app.services.mobile.device_service import is_valid_uuid_v4
from app.services.mobile.socioeconomic_form_mobile_service import (
    SocioeconomicFormMobileError,
    get_form_entry,
    list_students_for_form,
    list_users_for_form,
    submit_form_response,
)
from app.utils.tenant_middleware import get_current_tenant_context

import logging

logger = logging.getLogger(__name__)

_ALLOWED = frozenset(
    {
        RoleEnum.ADMIN,
        RoleEnum.COORDENADOR,
        RoleEnum.DIRETOR,
        RoleEnum.TECADM,
        RoleEnum.APLICADOR,
        RoleEnum.PROFESSOR,
    }
)


def _require_device_header():
    device_id = request.headers.get("X-Device-Id")
    if not device_id or not is_valid_uuid_v4(device_id):
        return None, (jsonify({"error": "X-Device-Id obrigatório (UUID v4)"}), 400)
    return device_id, None


def _require_allowed_user():
    uid = get_jwt_identity()
    user = User.query.get(uid)
    if not user or user.role not in _ALLOWED:
        return None, (jsonify({"error": "Operação não autorizada"}), 403)
    return user, None


@mobile_bp.route(
    "/socioeconomic-forms/<string:form_id>/students",
    methods=["GET", "OPTIONS"],
)
@jwt_required(optional=True)
def mobile_list_form_students(form_id):
    if request.method == "OPTIONS":
        return "", 200
    if get_jwt_identity() is None:
        return jsonify({"error": "Token Bearer obrigatório"}), 401

    device_id, err = _require_device_header()
    if err:
        return err
    user, err = _require_allowed_user()
    if err:
        return err

    ctx = get_current_tenant_context()
    if not ctx or not ctx.city_id:
        return jsonify({"error": "Contexto de município obrigatório"}), 400

    flat_raw = (request.args.get("flat") or "").strip().lower()
    flat = flat_raw in ("1", "true", "yes")

    try:
        payload = list_students_for_form(
            form_id,
            school_id=request.args.get("school_id"),
            class_id=request.args.get("class_id"),
            grade_id=request.args.get("grade_id"),
            flat=flat,
        )
        return jsonify(payload), 200
    except SocioeconomicFormMobileError as e:
        return jsonify({"error": e.message}), e.status_code
    except Exception as e:
        logger.error(f"Erro ao listar alunos do formulário {form_id}: {e}", exc_info=True)
        return jsonify({"error": "Erro ao listar alunos"}), 500


@mobile_bp.route(
    "/socioeconomic-forms/<string:form_id>/users",
    methods=["GET", "OPTIONS"],
)
@jwt_required(optional=True)
def mobile_list_form_users(form_id):
    if request.method == "OPTIONS":
        return "", 200
    if get_jwt_identity() is None:
        return jsonify({"error": "Token Bearer obrigatório"}), 401

    device_id, err = _require_device_header()
    if err:
        return err
    user, err = _require_allowed_user()
    if err:
        return err

    ctx = get_current_tenant_context()
    if not ctx or not ctx.city_id:
        return jsonify({"error": "Contexto de município obrigatório"}), 400

    try:
        payload = list_users_for_form(
            form_id,
            school_id=request.args.get("school_id"),
        )
        return jsonify(payload), 200
    except SocioeconomicFormMobileError as e:
        return jsonify({"error": e.message}), e.status_code
    except Exception as e:
        logger.error(f"Erro ao listar usuários do formulário {form_id}: {e}", exc_info=True)
        return jsonify({"error": "Erro ao listar usuários"}), 500


@mobile_bp.route("/socioeconomic-forms/entry", methods=["GET", "OPTIONS"])
@jwt_required(optional=True)
def mobile_get_form_entry():
    if request.method == "OPTIONS":
        return "", 200
    if get_jwt_identity() is None:
        return jsonify({"error": "Token Bearer obrigatório"}), 401

    device_id, err = _require_device_header()
    if err:
        return err
    user, err = _require_allowed_user()
    if err:
        return err

    form_id = (request.args.get("form_id") or "").strip()
    if not form_id:
        return jsonify({"error": "form_id é obrigatório"}), 400

    student_id = (request.args.get("student_id") or "").strip() or None
    user_id = (request.args.get("user_id") or "").strip() or None
    if not student_id and not user_id:
        return jsonify({"error": "student_id ou user_id é obrigatório"}), 400

    try:
        payload = get_form_entry(
            form_id,
            student_id=student_id,
            user_id=user_id,
        )
        return jsonify(payload), 200
    except SocioeconomicFormMobileError as e:
        return jsonify({"error": e.message}), e.status_code
    except Exception as e:
        logger.error(f"Erro ao carregar formulário {form_id}: {e}", exc_info=True)
        return jsonify({"error": "Erro ao carregar formulário"}), 500


@mobile_bp.route("/socioeconomic-forms/submit", methods=["POST", "OPTIONS"])
@jwt_required(optional=True)
def mobile_submit_form():
    if request.method == "OPTIONS":
        return "", 200
    if get_jwt_identity() is None:
        return jsonify({"error": "Token Bearer obrigatório"}), 401

    device_id, err = _require_device_header()
    if err:
        return err
    user, err = _require_allowed_user()
    if err:
        return err

    body = request.get_json(silent=True) or {}
    form_id = (body.get("form_id") or "").strip()
    if not form_id:
        return jsonify({"error": "form_id é obrigatório"}), 400

    student_id = (body.get("student_id") or "").strip() or None
    target_user_id = (body.get("user_id") or "").strip() or None
    if not student_id and not target_user_id:
        return jsonify({"error": "student_id ou user_id é obrigatório"}), 400

    responses = body.get("responses")
    if responses is None:
        return jsonify({"error": "Campo 'responses' é obrigatório"}), 400

    is_complete = bool(body.get("is_complete", False))

    try:
        result = submit_form_response(
            form_id,
            responses=responses,
            is_complete=is_complete,
            form_content_version=body.get("form_content_version"),
            student_id=student_id,
            user_id=target_user_id,
        )
        result["device_id"] = device_id
        result["offline_submission_id"] = body.get("offline_submission_id")
        db.session.commit()
        return jsonify(result), 200
    except SocioeconomicFormMobileError as e:
        db.session.rollback()
        code = "FORM_VERSION_MISMATCH" if e.status_code == 409 else None
        payload = {"error": e.message}
        if code:
            payload["code"] = code
        return jsonify(payload), e.status_code
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao salvar formulário {form_id}: {e}", exc_info=True)
        return jsonify({"error": "Erro ao salvar respostas"}), 500


@mobile_bp.route("/socioeconomic-forms/batch", methods=["POST", "OPTIONS"])
@jwt_required(optional=True)
def mobile_submit_form_batch():
    if request.method == "OPTIONS":
        return "", 200
    if get_jwt_identity() is None:
        return jsonify({"error": "Token Bearer obrigatório"}), 401

    device_id, err = _require_device_header()
    if err:
        return err
    user, err = _require_allowed_user()
    if err:
        return err

    body = request.get_json(silent=True) or {}
    submissions = body.get("submissions")
    if not isinstance(submissions, list):
        return jsonify({"error": "submissions deve ser uma lista"}), 400

    results = []
    applied_count = 0
    error_count = 0

    for item in submissions:
        offline_id = item.get("offline_submission_id", "unknown")
        try:
            form_id = (item.get("form_id") or "").strip()
            if not form_id:
                raise ValueError("form_id é obrigatório")

            student_id = (item.get("student_id") or "").strip() or None
            target_user_id = (item.get("user_id") or "").strip() or None
            if not student_id and not target_user_id:
                raise ValueError("student_id ou user_id é obrigatório")

            responses = item.get("responses")
            if responses is None:
                raise ValueError("Campo 'responses' é obrigatório")

            result = submit_form_response(
                form_id,
                responses=responses,
                is_complete=bool(item.get("is_complete", False)),
                form_content_version=item.get("form_content_version"),
                student_id=student_id,
                user_id=target_user_id,
            )
            results.append({
                "offline_submission_id": offline_id,
                "status": "applied",
                "message": "Respostas registradas com sucesso",
                "data": result,
            })
            applied_count += 1
        except SocioeconomicFormMobileError as e:
            results.append({
                "offline_submission_id": offline_id,
                "status": "error",
                "code": "FORM_VERSION_MISMATCH" if e.status_code == 409 else f"form_error_{e.status_code}",
                "message": e.message,
            })
            error_count += 1
        except Exception as e:
            results.append({
                "offline_submission_id": offline_id,
                "status": "error",
                "code": "internal_error",
                "message": str(e),
            })
            error_count += 1
            logger.error(f"Erro em submission {offline_id}: {e}", exc_info=True)

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao commitar lote de formulários: {e}", exc_info=True)
        return jsonify({"error": "Erro ao salvar lote de respostas"}), 500

    logger.info(
        f"[mobile/socioeconomic-forms/batch] applied={applied_count} "
        f"errors={error_count} total={len(submissions)}"
    )
    return jsonify({"results": results}), 200
