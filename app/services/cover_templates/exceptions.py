# -*- coding: utf-8 -*-


class CoverTemplateError(Exception):
    """Erro de template de capa."""


class CoverTemplateValidationError(CoverTemplateError):
    def __init__(self, message: str, code: str = "VALIDATION_ERROR"):
        super().__init__(message)
        self.message = message
        self.code = code


class CoverTemplateNotFound(CoverTemplateError):
    def __init__(self, message: str = "Template de capa não encontrado"):
        super().__init__(message)
        self.message = message
        self.code = "NOT_FOUND"
