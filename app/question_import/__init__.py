# -*- coding: utf-8 -*-
"""Módulo de importação em lote de questões via arquivo DOCX."""

from app.question_import.constants import ALLOWED_DIFFICULTIES
from app.question_import.docx_template import build_questions_import_template
from app.question_import.importer import (
    import_questions_from_docx,
    normalize_difficulty,
    parse_indexes_from_request,
    prepare_docx_questions,
    validate_import_defaults,
)
from app.question_import.routes import bp

__all__ = [
    "ALLOWED_DIFFICULTIES",
    "bp",
    "build_questions_import_template",
    "import_questions_from_docx",
    "normalize_difficulty",
    "parse_indexes_from_request",
    "prepare_docx_questions",
    "validate_import_defaults",
]
