# -*- coding: utf-8 -*-
"""
Infraestrutura multi-tenant: no PostgreSQL os schemas de município são sempre
``city_<uuid>``; nos models o placeholder lógico é ``schema="tenant"``, traduzido
via schema_translate_map em ``TenantAwareSession`` / ``g.request_context``.
"""

from app.multitenant.request_context import RequestContext
from app.multitenant.tenant_resolver import TenantResolver
from app.multitenant.db_session_factory import DatabaseSessionFactory, LOGICAL_TENANT_SCHEMA
from app.multitenant import flask_g

__all__ = [
    "RequestContext",
    "TenantResolver",
    "DatabaseSessionFactory",
    "LOGICAL_TENANT_SCHEMA",
    "flask_g",
]
