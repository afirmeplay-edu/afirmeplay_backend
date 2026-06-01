# routes/usuario.py

from flask import Blueprint, jsonify
from app.decorators.role_required import get_current_user_from_token
from app.models.user import User
from app.models.city import City
from app.entitlements.plans import DEFAULT_PLAN_CODE
from app.entitlements.resolver import entitlements_for_city
import datetime
import jwt
import os

SECRET_KEY = os.getenv("JWT_SECRET_KEY")

bp = Blueprint('persist-user', __name__, url_prefix='/persist-user')


def _needs_onboarding(user_model):
    """True se o usuário ainda não concluiu o modal de primeiro acesso (usa avatar_config, sem migration)."""
    if not user_model or not user_model.avatar_config or not isinstance(user_model.avatar_config, dict):
        return True
    return user_model.avatar_config.get("onboarding_completed") is not True


@bp.route('/', methods=['GET'])
def me():
    user = get_current_user_from_token()
    if not user:
        return jsonify({"erro": "Não autenticado"}), 401

    userData = User.query.get(user.get("id"))
    if not userData:
        return jsonify({"erro": "Usuário não encontrado"}), 404

    plan_code = None
    entitlements = None
    if userData.city_id:
        city = City.query.get(userData.city_id)
        if city:
            plan_code = city.plan_code or DEFAULT_PLAN_CODE
            entitlements = entitlements_for_city(city)

    token_payload = {
        "sub": user.get("id"),
        "city_id": user.get("city_id") or userData.city_id,
        "role": user.get("role"),
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=3),
    }
    if plan_code:
        token_payload["plan_code"] = plan_code
    new_token = jwt.encode(token_payload, SECRET_KEY, algorithm='HS256')

    usuario_data = {
        "id": userData.id,
        "name": userData.name,
        "email": userData.email,
        "registration": userData.registration,
        "role": userData.role.value,
        "city_id": userData.city_id,
    }
    if plan_code:
        usuario_data["plan_code"] = plan_code
    if entitlements:
        usuario_data["entitlements"] = entitlements

    needs_onboarding = _needs_onboarding(userData)
    response = {
        "user": usuario_data,
        "token": new_token,
    }
    if needs_onboarding:
        response["needs_onboarding"] = True
        response["profile"] = {
            "name": userData.name,
            "birth_date": userData.birth_date.isoformat() if userData.birth_date else None,
            "phone": userData.phone,
            "gender": userData.gender,
            "nationality": userData.nationality,
            "address": userData.address,
            "traits": userData.traits,
            "avatar_config": userData.avatar_config,
        }
    else:
        response["needs_onboarding"] = False

    return jsonify(response)
