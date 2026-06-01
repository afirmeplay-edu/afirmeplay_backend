from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from app.permissions import get_current_user_from_token, role_required
from app.services.termo_compromisso_service import (
    TermoCompromissoService,
    TermoCompromissoValidationError,
)

bp = Blueprint("termo_compromisso", __name__, url_prefix="/documentos/termo-compromisso")


def _error_response(error: Exception, fallback: str):
    if isinstance(error, TermoCompromissoValidationError):
        return jsonify({"error": error.message}), 400
    return jsonify({"error": fallback, "details": str(error)}), 500


@bp.route("/dados", methods=["GET"])
@jwt_required()
@role_required("admin", "professor", "coordenador", "diretor", "tecadm")
def get_termo_compromisso_dados():
    try:
        user = get_current_user_from_token()
        if not user:
            return jsonify({"error": "Usuário não encontrado"}), 401
        data = TermoCompromissoService.get_dados(user, request.args.to_dict())
        return jsonify(data), 200
    except Exception as error:
        return _error_response(error, "Erro ao carregar dados do termo de compromisso")
