# -*- coding: utf-8 -*-
"""Subturmas ADAP dentro de uma turma regular."""
import logging

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from sqlalchemy.exc import IntegrityError

from app import db
from app.decorators.role_required import get_current_user_from_token, role_required
from app.models.student import Student
from app.models.studentClass import Class
from app.models.subturma import Subturma
from app.services.subturma_service import (
    SubturmaError,
    SubturmaPermissionError,
    authorize_subturma_access,
    create_subturma,
    link_student_to_subturma,
    list_subturma_payload,
    remove_subturma,
    unlink_student_from_subturma,
)
from app.utils.uuid_helpers import ensure_uuid

bp = Blueprint("subturmas", __name__)

_READ_ROLES = ("admin", "professor", "coordenador", "diretor", "tecadm")
_WRITE_ROLES = ("admin", "tecadm", "diretor", "coordenador")


def _class_or_404(class_id):
    class_uuid = ensure_uuid(class_id)
    if not class_uuid:
        return None, (jsonify({"error": "ID de turma inválido."}), 400)
    class_obj = Class.query.get(class_uuid)
    if not class_obj:
        return None, (jsonify({"error": "Turma não encontrada."}), 404)
    return class_obj, None


def _subturma_of_class(class_obj, subturma_id):
    sub_uuid = ensure_uuid(subturma_id)
    if not sub_uuid:
        return None, (jsonify({"error": "ID de subturma inválido."}), 400)
    row = Subturma.query.get(sub_uuid)
    if not row or str(row.class_id) != str(class_obj.id):
        return None, (jsonify({"error": "Subturma não encontrada nesta turma."}), 404)
    return row, None


def _guard(class_obj, *, write: bool):
    user = get_current_user_from_token()
    if not user:
        return jsonify({"error": "Usuário não encontrado."}), 404
    try:
        authorize_subturma_access(user, class_obj, write=write)
    except SubturmaPermissionError as exc:
        return jsonify({"error": str(exc)}), 403
    return None


@bp.route("/classes/<string:class_id>/subturmas", methods=["GET"])
@jwt_required()
@role_required(*_READ_ROLES)
def listar_subturmas(class_id):
    class_obj, error = _class_or_404(class_id)
    if error:
        return error
    denied = _guard(class_obj, write=False)
    if denied:
        return denied
    return jsonify({"subturmas": list_subturma_payload(class_obj)}), 200


@bp.route("/classes/<string:class_id>/subturmas", methods=["POST"])
@jwt_required()
@role_required(*_WRITE_ROLES)
def criar_subturma(class_id):
    class_obj, error = _class_or_404(class_id)
    if error:
        return error
    denied = _guard(class_obj, write=True)
    if denied:
        return denied
    data = request.get_json() or {}
    try:
        row = create_subturma(class_obj, data.get("support_level"))
        db.session.commit()
    except SubturmaError as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 400
    except IntegrityError:
        db.session.rollback()
        level = data.get("support_level")
        return jsonify({"error": f"Já existe ADAP {level} nesta turma."}), 400
    except Exception as exc:
        db.session.rollback()
        logging.error("Erro ao criar subturma: %s", exc, exc_info=True)
        return jsonify({"error": "Erro ao criar subturma.", "details": str(exc)}), 500
    return jsonify(
        {
            "id": str(row.id),
            "class_id": str(row.class_id),
            "support_level": int(row.support_level),
            "display_name": row.display_name,
            "alunos": [],
        }
    ), 201


@bp.route("/classes/<string:class_id>/subturmas/<string:subturma_id>", methods=["DELETE"])
@jwt_required()
@role_required(*_WRITE_ROLES)
def excluir_subturma(class_id, subturma_id):
    class_obj, error = _class_or_404(class_id)
    if error:
        return error
    denied = _guard(class_obj, write=True)
    if denied:
        return denied
    row, error = _subturma_of_class(class_obj, subturma_id)
    if error:
        return error
    try:
        remove_subturma(db.session, row)
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        logging.error("Erro ao excluir subturma: %s", exc, exc_info=True)
        return jsonify({"error": "Erro ao excluir subturma.", "details": str(exc)}), 500
    return jsonify({"message": "Subturma excluída. Os alunos continuam na turma."}), 200


@bp.route(
    "/classes/<string:class_id>/subturmas/<string:subturma_id>/alunos",
    methods=["POST"],
)
@jwt_required()
@role_required(*_WRITE_ROLES)
def vincular_aluno(class_id, subturma_id):
    class_obj, error = _class_or_404(class_id)
    if error:
        return error
    denied = _guard(class_obj, write=True)
    if denied:
        return denied
    row, error = _subturma_of_class(class_obj, subturma_id)
    if error:
        return error
    data = request.get_json() or {}
    student = Student.query.get(data.get("student_id"))
    if not student:
        return jsonify({"error": "Aluno não encontrado."}), 404
    try:
        link_student_to_subturma(student, row)
        db.session.commit()
    except SubturmaError as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        db.session.rollback()
        logging.error("Erro ao vincular aluno à subturma: %s", exc, exc_info=True)
        return jsonify({"error": "Erro ao vincular aluno.", "details": str(exc)}), 500
    return jsonify(
        {
            "message": f"Aluno vinculado a {row.display_name}.",
            "student_id": str(student.id),
            "subturma_id": str(row.id),
            "display_name": row.display_name,
        }
    ), 200


@bp.route(
    "/classes/<string:class_id>/subturmas/<string:subturma_id>/alunos/<string:student_id>",
    methods=["DELETE"],
)
@jwt_required()
@role_required(*_WRITE_ROLES)
def desvincular_aluno(class_id, subturma_id, student_id):
    class_obj, error = _class_or_404(class_id)
    if error:
        return error
    denied = _guard(class_obj, write=True)
    if denied:
        return denied
    row, error = _subturma_of_class(class_obj, subturma_id)
    if error:
        return error
    student = Student.query.get(student_id)
    if not student:
        return jsonify({"error": "Aluno não encontrado."}), 404
    try:
        unlink_student_from_subturma(student, row)
        db.session.commit()
    except SubturmaError as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        db.session.rollback()
        logging.error("Erro ao desvincular aluno da subturma: %s", exc, exc_info=True)
        return jsonify({"error": "Erro ao desvincular aluno.", "details": str(exc)}), 500
    return jsonify({"message": "Aluno removido da subturma. Ele continua na turma."}), 200
