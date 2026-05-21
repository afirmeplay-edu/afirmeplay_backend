from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from app import db
from app.permissions import get_current_user_from_token, role_required
from app.services.saved_ata_service import SavedAtaService, SavedAtaValidationError

bp = Blueprint("saved_ata", __name__, url_prefix="/documentos/ata-sala")


def _error_response(error: Exception, fallback: str, status: int = 500):
    if isinstance(error, SavedAtaValidationError):
        return jsonify({"error": error.message}), 404 if "não encontrada" in error.message.lower() else 400
    db.session.rollback()
    return jsonify({"error": fallback, "details": str(error)}), status


@bp.route("/salvas", methods=["GET"])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def list_saved_atas():
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401
        data = SavedAtaService.list_saved(user, request.args.to_dict())
        return jsonify(data), 200
    except Exception as error:
        return _error_response(error, "Erro ao listar atas salvas")


@bp.route("/salvas", methods=["POST"])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def create_saved_ata():
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401
        payload = request.get_json(silent=True) or {}
        data = SavedAtaService.create_saved(user, payload)
        return jsonify(data), 201
    except Exception as error:
        return _error_response(error, "Erro ao salvar ata")


@bp.route("/salvas/<string:ata_id>", methods=["GET"])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def get_saved_ata(ata_id):
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401
        data = SavedAtaService.get_saved(user, ata_id)
        return jsonify(data), 200
    except Exception as error:
        return _error_response(error, "Erro ao carregar ata salva")


@bp.route("/salvas/<string:ata_id>", methods=["PUT"])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def update_saved_ata(ata_id):
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401
        payload = request.get_json(silent=True) or {}
        data = SavedAtaService.update_saved(user, ata_id, payload)
        return jsonify(data), 200
    except Exception as error:
        return _error_response(error, "Erro ao atualizar ata")


@bp.route("/salvas/<string:ata_id>", methods=["DELETE"])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def delete_saved_ata(ata_id):
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401
        data = SavedAtaService.delete_saved(user, ata_id)
        return jsonify(data), 200
    except Exception as error:
        return _error_response(error, "Erro ao excluir ata")
