# routes/usuario.py

from flask import Blueprint, jsonify
from app.utils.auth import get_current_user_from_cookie

bp = Blueprint('persist-user', __name__, url_prefix='/persist-user')

@bp.route('/', methods=['GET'])
def me():
    usuario = get_current_user_from_cookie()
    if not usuario:
        return jsonify({"erro": "Não autenticado"}), 401

    usuario_data = {
        "id": usuario.id,
        "nome": usuario.nome,
        "email": usuario.email,
        "matricula": usuario.matricula,
        "escola_id": usuario.escola_id,
        "role": usuario.role.value
    }

    return jsonify({"usuario": usuario_data})
