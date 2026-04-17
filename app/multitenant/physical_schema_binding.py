# -*- coding: utf-8 -*-
"""
Substituição de `SET search_path` no PostgreSQL por override explícito do schema físico
usado em `TenantAwareSession` (`schema_translate_map`: lógico ``tenant`` → ``city_*``).

- ``None`` / ausência de override: usa ``g.request_context.tenant_schema`` (fluxo HTTP/Celery com contexto).
- Override ``city_<uuid>``: força o mapeamento para esse schema (troca temporária entre municípios / competição).
- ``public`` no sentido legado de "voltar ao contexto do request": chame ``clear_physical_schema_override()``.
"""

from __future__ import annotations

from flask import g, has_app_context

_G_OVERRIDE = "_mt_physical_schema_override"
# Mesmo nome usado em tenant_aware_session (invalidação do cache de Engine por request)
_G_BIND_CACHE = "_sqlalchemy_tenant_translate_bind_cache"


def _g_active() -> bool:
    return has_app_context()


def invalidate_tenant_bind_cache() -> None:
    if _g_active() and hasattr(g, _G_BIND_CACHE):
        delattr(g, _G_BIND_CACHE)


def clear_physical_schema_override() -> None:
    """Remove override; o bind volta a seguir só ``g.request_context``."""
    if _g_active() and hasattr(g, _G_OVERRIDE):
        delattr(g, _G_OVERRIDE)
    invalidate_tenant_bind_cache()


def set_physical_schema_override(schema: str | None) -> None:
    """
    Força o schema físico para tabelas com ``schema=\"tenant\"`` no modelo.
    ``schema`` em ``None`` ou ``\"public\"`` limpa o override (usa só o request context).
    """
    if not _g_active():
        return
    if not schema or str(schema).strip().lower() in ("", "public"):
        clear_physical_schema_override()
        return
    setattr(g, _G_OVERRIDE, str(schema).strip())
    invalidate_tenant_bind_cache()


def get_effective_tenant_physical_schema() -> str:
    """
    Schema físico usado para traduzir o nome lógico ``tenant`` (ex.: ``city_...`` ou ``public``).
    """
    if not _g_active():
        return "public"
    ov = getattr(g, _G_OVERRIDE, None)
    if ov is not None:
        return ov if ov != "public" else "public"
    rc = getattr(g, "request_context", None)
    if rc is not None:
        return getattr(rc, "tenant_schema", None) or "public"
    return "public"
