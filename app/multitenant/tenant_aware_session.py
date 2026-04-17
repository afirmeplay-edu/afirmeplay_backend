# -*- coding: utf-8 -*-
"""
Sessão Flask-SQLAlchemy que aplica `schema_translate_map` no bind quando o request
tem município (`g.request_context.tenant_schema` ≠ public).

Assim `db.session` e `Model.query` geram SQL no schema físico (`city_*`), não no
nome literal `tenant`, sem precisar de `g.tenant_session` paralela.

**Cache do Engine com `execution_options`:** cada chamada a
``engine.execution_options(...)`` devolve um *novo* objeto Engine (irmão, mesmo pool).
Se ``get_bind`` devolver um Engine diferente a cada query, o ORM pode associar uma
conexão por bind e esgotar o QueuePool. Por isso guardamos um Engine por
``(id(bound), schema físico)`` em ``flask.g`` durante o request.
"""

from __future__ import annotations

from flask import g, has_app_context
from flask_sqlalchemy.session import Session as FlaskSQLAlchemySession

from app.multitenant.db_session_factory import LOGICAL_TENANT_SCHEMA
from app.multitenant.physical_schema_binding import get_effective_tenant_physical_schema

_G_BIND_CACHE = "_sqlalchemy_tenant_translate_bind_cache"


class TenantAwareSession(FlaskSQLAlchemySession):
    def get_bind(self, mapper=None, clause=None, bind=None, **kwargs):  # type: ignore[override]
        bound = super().get_bind(mapper=mapper, clause=clause, bind=bind, **kwargs)
        if not has_app_context():
            return bound

        physical = get_effective_tenant_physical_schema()
        if physical == "public":
            return bound

        if not hasattr(bound, "execution_options"):
            return bound

        cache = getattr(g, _G_BIND_CACHE, None)
        if cache is None:
            cache = {}
            setattr(g, _G_BIND_CACHE, cache)

        key = (id(bound), physical)
        translated = cache.get(key)
        if translated is None:
            translated = bound.execution_options(
                schema_translate_map={LOGICAL_TENANT_SCHEMA: physical}
            )
            cache[key] = translated
        return translated
