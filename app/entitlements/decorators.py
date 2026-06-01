"""
Decoradores de plano/feature municipal.

Uso (quando existir rota plus):
    @jwt_required()
    @role_required("admin", "tecadm")
    @require_plan(PLAN_PLUS)
    def rota_plus(): ...

    @require_feature("ai_coach")  # após cadastrar em PLUS_ONLY_FEATURES
"""

from functools import wraps

from flask import jsonify

from app.entitlements.resolver import check_feature_access, check_plan_access
from app.permissions.decorators import get_current_user_from_token


def require_plan(*plan_codes):
    """Exige que o município em contexto tenha um dos planos listados (ex.: 'plus')."""
    plans = tuple(plan_codes)

    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            user = get_current_user_from_token()
            if not user:
                return jsonify({
                    "erro": "Acesso negado.",
                    "mensagem": "Token inválido, expirado ou não informado.",
                }), 403
            denied = check_plan_access(user, *plans)
            if denied:
                return denied
            return f(*args, **kwargs)

        return wrapper

    return decorator


def require_feature(feature: str):
    """Exige feature conhecida incluída no plano do município em contexto."""
    code = str(feature).strip().lower()

    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            user = get_current_user_from_token()
            if not user:
                return jsonify({
                    "erro": "Acesso negado.",
                    "mensagem": "Token inválido, expirado ou não informado.",
                }), 403
            denied = check_feature_access(user, code)
            if denied:
                return denied
            return f(*args, **kwargs)

        return wrapper

    return decorator
