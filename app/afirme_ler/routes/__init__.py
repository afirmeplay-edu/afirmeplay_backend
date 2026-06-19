# -*- coding: utf-8 -*-
from flask import Blueprint

bp = Blueprint("afirme_ler", __name__, url_prefix="/afirme-reading")

from app.afirme_ler.routes import texts_routes, word_lists_routes, evaluations_routes  # noqa: E402, F401

__all__ = ["bp"]
