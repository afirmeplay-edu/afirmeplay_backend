# -*- coding: utf-8 -*-
"""Discovery público de municípios para o login do Afirme Ler (sem JWT)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from app.entitlements.features import plan_includes_feature
from app.entitlements.plans import DEFAULT_PLAN_CODE
from app.models.city import City

FEATURE_CODE = "afirme_reading"
API_CONTRACT_VERSION = "1.0"
SOURCE = "afirme-ler"


def _plan_code(city: City) -> str:
    return (city.plan_code or DEFAULT_PLAN_CODE).strip().lower() or DEFAULT_PLAN_CODE


def list_cities_with_afirme_reading() -> List[City]:
    """Municípios de public.city cujo plano inclui a feature afirme_reading."""
    cities = City.query.order_by(City.state.asc(), City.name.asc()).all()
    return [c for c in cities if plan_includes_feature(_plan_code(c), FEATURE_CODE)]


def serialize_city(city: City) -> Dict[str, Any]:
    plan = _plan_code(city)
    return {
        "id": str(city.id),
        "name": city.name,
        "slug": city.slug,
        "state": city.state,
        "plan_code": plan,
    }


def build_discovery_cities_response() -> Dict[str, Any]:
    rows = list_cities_with_afirme_reading()
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    if not generated_at.endswith("Z"):
        generated_at = generated_at.replace("+00:00", "Z")
    return {
        "api_contract_version": API_CONTRACT_VERSION,
        "source": SOURCE,
        "feature": FEATURE_CODE,
        "generated_at": generated_at,
        "cities": [serialize_city(c) for c in rows],
    }
