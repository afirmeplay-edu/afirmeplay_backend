# -*- coding: utf-8 -*-
from .test_routes import bp as test_bp
from .question_routes import bp as question_bp
from .student_answer_routes import bp as student_answer_bp
from .subjective_test_routes import bp as subjective_test_bp

__all__ = ["test_bp", "question_bp", "student_answer_bp", "subjective_test_bp"]
