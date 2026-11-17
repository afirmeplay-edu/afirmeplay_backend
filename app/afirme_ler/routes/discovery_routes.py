# -*- coding: utf-8 -*-
"""Rotas públicas de discovery do Afirme Ler (login, sem JWT)."""
from __future__ import annotations

import logging

from flask import jsonify, request

from app.afirme_ler.routes import bp
from app.afirme_ler.services import discovery_service as discovery_svc

logger = logging.getLogger(__name__)


@bp.route("/discovery/cities", methods=["GET", "OPTIONS"])
def discovery_cities():
    """
    Lista municípios com acesso ao Afirme Ler (feature afirme_reading).
    Público — usado na tela de login antes da autenticação.
    """
    if request.method == "OPTIONS":
        return "", 200

    try:
        payload = discovery_svc.build_discovery_cities_response()
        logger.debug(
            "afirme-ler discovery/cities: %d entries",
            len(payload.get("cities") or []),
        )
        return jsonify(payload), 200
    except Exception:
        logger.exception("afirme-ler discovery/cities failed")
        return jsonify({"error": "Erro ao listar municípios disponíveis"}), 500
