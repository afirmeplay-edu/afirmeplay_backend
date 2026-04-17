# -*- coding: utf-8 -*-
"""Contexto imutável por request (HTTP ou Celery com app context)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class RequestContext:
    """
    Snapshot do tenant e do usuário para o request atual.

    - `tenant_schema`: nome **físico** do schema no PostgreSQL: ``city_<uuid>`` (sempre
      prefixo ``city_``, nunca ``tenant_``) ou ``public``.
    - `has_tenant`: True quando há município resolvido (schema diferente de apenas public).
    """

    request_id: str
    user_id: Optional[str]
    role: Optional[str]
    tenant_schema: str
    has_tenant: bool
    city_id: Optional[str] = None
    city_slug: Optional[str] = None
    is_admin: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "user_id": self.user_id,
            "role": self.role,
            "tenant_schema": self.tenant_schema,
            "has_tenant": self.has_tenant,
            "city_id": self.city_id,
            "city_slug": self.city_slug,
            "is_admin": self.is_admin,
        }
