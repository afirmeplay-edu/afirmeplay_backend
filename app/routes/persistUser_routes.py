# routes/usuario.py

from flask import Blueprint, jsonify
from app.decorators.role_required import get_current_user_from_token
from app.models.user import User
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
        "sub": user.get("id"),
        "city_id": user.get("city_id"),
        "role": user.get("role"),
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=1)
    }
    new_token = jwt.encode(token_payload, SECRET_KEY, algorithm='HS256')

    userData = User.query.get(user.get("id"))

    usuario_data = {
        "id": userData.id,
        "name": userData.name,
        "email": userData.email,
        "registration": userData.registration,
        "role": userData.role.value,
        "city_id": userData.city_id
    }

    return jsonify({
        "user": usuario_data,
        "token": new_token
    })
