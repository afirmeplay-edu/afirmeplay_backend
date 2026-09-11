# -*- coding: utf-8 -*-
"""Importação em lote de questões via arquivo DOCX."""

from app.services.question_import.constants import ALLOWED_DIFFICULTIES
from app.services.question_import.docx_template import build_questions_import_template
from app.services.question_import.importer import (
    import_questions_from_docx,
    normalize_difficulty,
    parse_indexes_from_request,
    validate_import_defaults,
)

__all__ = [
    "ALLOWED_DIFFICULTIES",
    "build_questions_import_template",
    "import_questions_from_docx",
    "normalize_difficulty",
    "parse_indexes_from_request",
    "validate_import_defaults",
]
