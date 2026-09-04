# -*- coding: utf-8 -*-
from .evaluation_routes import bp as evaluation_bp
from .evaluation_results_routes import bp as evaluation_results_bp
from .evaluation_exam_pdf_routes import bp as evaluation_exam_pdf_bp

__all__ = ["evaluation_bp", "evaluation_results_bp", "evaluation_exam_pdf_bp"]
