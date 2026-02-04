# -*- coding: utf-8 -*-
"""Exceções do módulo de competições (evita import circular entre services)."""


class ValidationError(Exception):
    """Erro de validação."""
    pass
