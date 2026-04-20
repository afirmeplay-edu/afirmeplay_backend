# -*- coding: utf-8 -*-
"""
Resolução de tenant a partir do request Flask.

Reutiliza a lógica já validada em `app.utils.tenant_middleware.resolve_tenant_context`.
"""

from __future__ import annotations

import os
import uuid
from typing import TYPE_CHECKING, Any, Optional

from app.multitenant.request_context import RequestContext

if TYPE_CHECKING:
    from flask import Request


class TenantResolver:
    """
    Encapsula a resolução de município/schema e metadados do usuário (JWT / headers / host).
    """

    @staticmethod
    def request_context_from_tenant_context(tc: Any, request: "Request") -> RequestContext:
        """Constroi `RequestContext` a partir do `TenantContext` já resolvido (uma única resolução por request)."""
        rid = request.environ.get("HTTP_X_REQUEST_ID") or str(uuid.uuid4())
        schema = getattr(tc, "schema", None) or "public"
        has_ctx = bool(getattr(tc, "has_tenant_context", False))
        has_tenant = bool(has_ctx and schema and schema != "public")
        return RequestContext(
            request_id=str(rid),
            user_id=getattr(tc, "user_id", None),
            role=getattr(tc, "user_role", None),
            tenant_schema=schema,
            has_tenant=has_tenant,
            city_id=getattr(tc, "city_id", None),
            city_slug=getattr(tc, "city_slug", None),
            is_admin=bool(getattr(tc, "is_admin", False)),
        )

    @staticmethod
    def resolve_from_flask_request(request: "Request") -> RequestContext:
        # Import tardio para evitar ciclo: tenant_middleware ↔ multitenant
        from app.utils.tenant_middleware import resolve_tenant_context

        tc = resolve_tenant_context()
        return TenantResolver.request_context_from_tenant_context(tc, request)

    @staticmethod
    def legacy_search_path_enabled() -> bool:
        """Descontinuado: o middleware não usa mais ``SET search_path`` (só ``schema_translate_map``)."""
        return os.getenv("LEGACY_SEARCH_PATH_ENABLED", "false").lower() in (
            "1",
            "true",
            "yes",
        )
