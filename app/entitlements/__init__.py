"""
Pacote de planos/features municipais.

Resolver e decorators importam City — carregados sob demanda para não circular com app.models.
"""

from .plans import (
    DEFAULT_PLAN_CODE,
    PLAN_BASIC,
    PLAN_PLUS,
    VALID_PLAN_CODES,
    normalize_plan_code,
)
from .features import (
    ALL_KNOWN_FEATURES,
    BASIC_FEATURES,
    PLUS_ONLY_FEATURES,
    build_entitlements_payload,
    features_for_plan,
    is_known_feature,
    plan_includes_feature,
)

_LAZY_EXPORTS = {
    "check_feature_access",
    "check_plan_access",
    "entitlements_for_city",
    "get_city_for_request",
    "plan_denied_response",
    "resolve_city_id_for_request",
    "require_feature",
    "require_plan",
}

__all__ = [
    "DEFAULT_PLAN_CODE",
    "PLAN_BASIC",
    "PLAN_PLUS",
    "VALID_PLAN_CODES",
    "normalize_plan_code",
    "ALL_KNOWN_FEATURES",
    "BASIC_FEATURES",
    "PLUS_ONLY_FEATURES",
    "build_entitlements_payload",
    "features_for_plan",
    "is_known_feature",
    "plan_includes_feature",
    *_LAZY_EXPORTS,
]


def __getattr__(name: str):
    if name in _LAZY_EXPORTS:
        from . import resolver, decorators

        _map = {
            "check_feature_access": resolver.check_feature_access,
            "check_plan_access": resolver.check_plan_access,
            "entitlements_for_city": resolver.entitlements_for_city,
            "get_city_for_request": resolver.get_city_for_request,
            "plan_denied_response": resolver.plan_denied_response,
            "resolve_city_id_for_request": resolver.resolve_city_id_for_request,
            "require_feature": decorators.require_feature,
            "require_plan": decorators.require_plan,
        }
        return _map[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
