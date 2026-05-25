from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from app.permissions import get_current_user_from_token, role_required
from app.services.folha_rascunho_service import FolhaRascunhoService, FolhaRascunhoValidationError

bp = Blueprint("folha_rascunho", __name__, url_prefix="/documentos/folha-rascunho")


def _error_response(error: Exception, fallback: str):
    if isinstance(error, FolhaRascunhoValidationError):
        return jsonify({"error": error.message}), 400
    return jsonify({"error": fallback, "details": str(error)}), 500


@bp.route("/dados", methods=["GET"])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def get_folha_rascunho_dados():
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401
        data = FolhaRascunhoService.get_dados(user, request.args.to_dict())
        return jsonify(data), 200
    except Exception as error:
        return _error_response(error, "Erro ao carregar dados da folha de rascunho")
