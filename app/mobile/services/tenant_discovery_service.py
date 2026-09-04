"""
Listagem pública de municípios para discovery no app mobile (catálogo mobile_city_directory).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from app.mobile.models.mobile_city_directory import MobileCityDirectory

API_CONTRACT_VERSION = "1.0"
VALID_HOSTING_MODES = frozenset({"shared", "dedicated"})


def _normalize_api_base_url(url: str) -> str:
    return (url or "").strip().rstrip("/")


def list_available_cities() -> List[MobileCityDirectory]:
    return (
        MobileCityDirectory.query.filter_by(
            mobile_visible=True,
            is_active=True,
        )
        .order_by(
            MobileCityDirectory.sort_order.asc(),
            MobileCityDirectory.city_name.asc(),
        )
        .all()
    )


def serialize_city_entry(row: MobileCityDirectory) -> Dict[str, Any]:
    hosting = (row.hosting_mode or "shared").strip().lower()
    if hosting not in VALID_HOSTING_MODES:
        hosting = "shared"
    return {
        "id": str(row.id),
        "tenant_code": row.tenant_code,
        "slug": row.city_slug,
        "name": row.city_name,
        "hosting_mode": hosting,
        "api_base_url": _normalize_api_base_url(row.api_base_url),
    }


def build_available_cities_response() -> Dict[str, Any]:
    rows = list_available_cities()
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    if not generated_at.endswith("Z"):
        generated_at = generated_at.replace("+00:00", "Z")
    return {
        "api_contract_version": API_CONTRACT_VERSION,
        "generated_at": generated_at,
        "cities": [serialize_city_entry(r) for r in rows],
    }
