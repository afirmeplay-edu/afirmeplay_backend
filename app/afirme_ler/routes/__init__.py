# -*- coding: utf-8 -*-
from flask import Blueprint

bp = Blueprint("afirme_ler", __name__, url_prefix="/afirme-reading")

AFIRME_LER_ROLES = (
    "admin",
    "tecadm",
    "professor",
    "coordenador",
    "diretor",
    "aplicador",
)

from app.afirme_ler.routes import (  # noqa: E402, F401
    texts_routes,
    word_lists_routes,
    evaluations_routes,
    guided_sessions_routes,
    guided_auto_sessions_routes,
    fluency_sessions_routes,
)

__all__ = ["bp", "AFIRME_LER_ROLES"]
