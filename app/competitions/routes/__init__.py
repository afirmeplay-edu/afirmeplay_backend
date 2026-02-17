# -*- coding: utf-8 -*-
"""
Rotas de competições.
"""

from .competition_routes import bp as competitions_bp
from .competition_template_routes import bp as competition_templates_bp

__all__ = ["competitions_bp", "competition_templates_bp"]

