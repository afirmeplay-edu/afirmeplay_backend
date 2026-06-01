"""Resolução de município e checagem de plano/feature no request."""

from typing import Optional, Tuple

from flask import g, jsonify

from app.entitlements.features import (
    build_entitlements_payload,
    is_known_feature,
    plan_includes_feature,
)
from app.entitlements.plans import DEFAULT_PLAN_CODE, PLAN_BASIC, PLAN_PLUS, normalize_plan_code
from app.models.city import City
from app.permissions.roles import Roles


def resolve_city_id_for_request(user: dict) -> Optional[str]:
    """
    city_id do município em contexto.
    Admin sem contexto retorna None (bypass nas checagens de plano).
    """
    role = Roles.normalize(user.get("role") or "")
    if role == Roles.ADMIN:
        ctx = getattr(g, "tenant_context", None)
        if ctx and getattr(ctx, "city_id", None):
            return str(ctx.city_id)
        header_city = __import__("flask").request.headers.get("X-City-ID")
        if header_city:
            return str(header_city)
        return None

    ctx = getattr(g, "tenant_context", None)
    if ctx and getattr(ctx, "city_id", None):
        return str(ctx.city_id)
    return user.get("tenant_id") or user.get("city_id")


def get_city_for_request(user: dict) -> Tuple[Optional[City], Optional[str]]:
    """
    Retorna (city, city_id). Para admin sem contexto: (None, None) — bypass.
    """
    city_id = resolve_city_id_for_request(user)
    if city_id is None and Roles.normalize(user.get("role") or "") == Roles.ADMIN:
        return None, None
    if not city_id:
        return None, None
    city = City.query.get(city_id)
    return city, city_id


def plan_denied_response(
    *,
    plan_code: str,
    required_plan: Optional[str] = None,
    feature: Optional[str] = None,
):
    code = normalize_plan_code(plan_code)
    body = {
        "erro": "Plano insuficiente",
        "mensagem": (
            f"Esta funcionalidade requer o plano {required_plan}."
            if required_plan
            else "Seu município não tem acesso a esta funcionalidade."
        ),
        "plan_code": code,
    }
    if required_plan:
        body["required_plan"] = required_plan
    if feature:
        body["feature"] = feature
    return jsonify(body), 403


def city_satisfies_plan(plan_code: str, required_plan: str) -> bool:
    """Plus satisfaz exigência de basic; basic não satisfaz exigência de plus."""
    current = normalize_plan_code(plan_code)
    required = normalize_plan_code(required_plan)
    if required == PLAN_BASIC:
        return current in (PLAN_BASIC, PLAN_PLUS)
    return current == required


def check_plan_access(user: dict, *required_plans: str) -> Optional[Tuple]:
    """
    None se permitido; senão (response, status) 403/400.
    Admin sem city em contexto: permitido.
    """
    city, city_id = get_city_for_request(user)
    if city is None and city_id is None:
        if Roles.normalize(user.get("role") or "") == Roles.ADMIN:
            return None
        return jsonify({
            "erro": "Contexto de município obrigatório",
            "mensagem": "Não foi possível identificar o município para validar o plano.",
        }), 400

    if not city:
        return jsonify({"erro": "Município não encontrado"}), 404

    current = normalize_plan_code(city.plan_code or DEFAULT_PLAN_CODE)
    if any(city_satisfies_plan(current, rp) for rp in required_plans):
        return None
    required_label = required_plans[0] if len(required_plans) == 1 else ", ".join(required_plans)
    return plan_denied_response(plan_code=current, required_plan=required_label)


def check_feature_access(user: dict, feature: str) -> Optional[Tuple]:
    """None se permitido; senão (response, status)."""
    feature = str(feature).strip().lower()
    if not is_known_feature(feature):
        return jsonify({
            "erro": "Feature desconhecida",
            "mensagem": f"Código de feature inválido: '{feature}'.",
        }), 400

    city, city_id = get_city_for_request(user)
    if city is None and city_id is None:
        if Roles.normalize(user.get("role") or "") == Roles.ADMIN:
            return None
        return jsonify({
            "erro": "Contexto de município obrigatório",
            "mensagem": "Não foi possível identificar o município para validar a feature.",
        }), 400

    if not city:
        return jsonify({"erro": "Município não encontrado"}), 404

    plan_code = normalize_plan_code(city.plan_code or DEFAULT_PLAN_CODE)
    if plan_includes_feature(plan_code, feature):
        return None
    return plan_denied_response(
        plan_code=plan_code,
        required_plan=PLAN_PLUS,
        feature=feature,
    )


def entitlements_for_city(city: City) -> dict:
    return build_entitlements_payload(city.plan_code or DEFAULT_PLAN_CODE)
