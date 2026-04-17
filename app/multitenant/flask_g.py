# -*- coding: utf-8 -*-
"""Leitores opcionais para sessões multi-tenant registradas em `flask.g`."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.multitenant.request_context import RequestContext


def get_request_context() -> Optional["RequestContext"]:
    from flask import g

    return getattr(g, "request_context", None)


def get_g_public_session() -> Optional["Session"]:
    from flask import g

    return getattr(g, "public_session", None)


def get_g_tenant_session() -> Optional["Session"]:
    from flask import g

    return getattr(g, "tenant_session", None)


def get_orm_session() -> "Session":
    """
    Sessão ORM do request: em HTTP é `db.session` (`TenantAwareSession` aplica
    schema_translate_map do nome lógico `tenant` para o schema físico `city_*` em
    `g.request_context.tenant_schema`).

    Mantém compatibilidade se `g.tenant_session` for definido em algum fluxo legado.
    """
    from flask import has_request_context, g

    from app import db

    if has_request_context():
        ts = getattr(g, "tenant_session", None)
        if ts is not None:
            return ts
    return db.session
