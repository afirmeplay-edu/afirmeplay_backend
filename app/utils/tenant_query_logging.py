# -*- coding: utf-8 -*-
"""
Log por query SQL em requests HTTP: tenant, usuário e path — facilita debug multi-tenant.

- **Ligado:** ``TENANT_QUERY_LOG=1`` (ou ``true``/``yes``/``on``), ou ``APP_ENV=development``,
  ou ``app.debug=True``.
- **Desligado:** ``TENANT_QUERY_LOG=0`` (ou ``false``/``no``/``off``) — útil em homolog/prod
  mesmo com outros flags de dev.
"""

from __future__ import annotations

import logging
import os

from sqlalchemy import event

logger = logging.getLogger("innovaplay.tenant_query")

_REGISTERED = "_innovaplay_tenant_query_listener_registered"


def _is_enabled(app) -> bool:
    v = os.getenv("TENANT_QUERY_LOG", "").strip().lower()
    if v in ("0", "false", "no", "off"):
        return False
    if v in ("1", "true", "yes", "on"):
        return True
    if os.getenv("APP_ENV", "").strip().lower() == "development":
        return True
    return bool(app.debug)


def register_tenant_query_logging(app, db) -> None:
    """
    Registra ``before_cursor_execute`` em todos os engines do SQLAlchemy.

    Uma linha INFO por statement enviado ao DB (pode ser verboso).
    """
    if not _is_enabled(app):
        return

    def _before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        from flask import g, has_request_context, request

        if not has_request_context():
            return
        try:
            rc = getattr(g, "request_context", None)
            tenant = getattr(rc, "tenant_schema", None) if rc else None
            user = getattr(rc, "user_id", None) if rc else None
            endpoint = getattr(request, "path", None) or "-"
            tenant_s = tenant if tenant else "public"
            user_s = str(user) if user is not None else "-"
            logger.info("tenant=%s user=%s endpoint=%s", tenant_s, user_s, endpoint)
        except Exception:
            logger.debug("Falha ao logar contexto tenant da query", exc_info=True)

    with app.app_context():
        for eng in db.engines.values():
            if getattr(eng, _REGISTERED, False):
                continue
            event.listen(eng, "before_cursor_execute", _before_cursor_execute)
            setattr(eng, _REGISTERED, True)

    logger.propagate = True

    app.logger.info(
        "tenant_query: log por SQL ativo (tenant= user= endpoint=) — "
        "desligue com TENANT_QUERY_LOG=0 se não quiser ruído"
    )
