"""
Rotas para avaliações - compatibilidade com frontend
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.models.studentAnswer import StudentAnswer
from app.models.testSession import TestSession
from app.models.test import Test
from app.models.question import Question
from app.models.student import Student
from app.decorators.role_required import role_required, get_current_user_from_token
from app.decorators import requires_city_context
from datetime import datetime, timedelta
import logging

bp = Blueprint('evaluations', __name__, url_prefix='/evaluations')

@bp.errorhandler(Exception)
def handle_evaluation_error(error):
    """Tratamento global de erros para evaluations"""
    logging.error(f"Erro em evaluations: {str(error)}", exc_info=True)
    return jsonify({
        "error": "Erro interno no servidor",
        "details": str(error)
    }), 500

@bp.route('/ping', methods=['GET'])
def ping_evaluations():
    """Rota de teste para verificar se o blueprint está funcionando"""
    return jsonify({"message": "Evaluations blueprint está funcionando!"}), 200

# Endpoint duplicado removido - usar /student-answers/submit em vez de /evaluations/{test_id}/answers 