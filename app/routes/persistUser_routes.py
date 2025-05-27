# routes/usuario.py

from flask import Blueprint, jsonify
from app.decorators.role_required import get_current_user_from_token
import datetime
import jwt
import os

SECRET_KEY = os.getenv("JWT_SECRET_KEY")

bp = Blueprint('persist-user', __name__, url_prefix='/persist-user')

@bp.route('/', methods=['GET'])
def me():
    user = get_current_user_from_token()
    if not user:
        return jsonify({"erro": "Não autenticado"}), 401

    # Create new access token
    token_payload = {
        "sub": user["id"],
        "city_id": None,
        "role": user["role"],
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=1)
    }
    new_token = jwt.encode(token_payload, SECRET_KEY, algorithm='HS256')

    usuario_data = {
        "id": user["id"],
        "role": user["role"]
    }

    return jsonify({
        "usuario": usuario_data,
        "token": new_token
    })
