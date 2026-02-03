# -*- coding: utf-8 -*-
"""
Rotas para API de Coins (moedas do aluno).
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.permissions import role_required, get_current_user_from_token
from app.models import CoinTransaction
from app.models.student import Student
from app.services.coin_service import CoinService, InsufficientBalanceError
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
import logging

bp = Blueprint('coins', __name__, url_prefix='/coins')


@bp.errorhandler(SQLAlchemyError)
def handle_db_error(error):
    db.session.rollback()
    logging.error(f"Database error: {str(error)}")
    return jsonify({"erro": "Erro no banco de dados", "detalhes": str(error)}), 500


@bp.errorhandler(IntegrityError)
def handle_integrity_error(error):
    db.session.rollback()
    logging.error(f"Integrity error: {str(error)}")
    return jsonify({"erro": "Erro de integridade de dados", "detalhes": str(error)}), 400


@bp.errorhandler(InsufficientBalanceError)
def handle_insufficient_balance(error):
    return jsonify({"erro": "Saldo insuficiente", "detalhes": str(error)}), 400


def _resolve_student_id():
    """
    Retorna (student_id, error_response).
    Se error_response não for None, o chamador deve retorná-lo.
    user_id do JWT; se role admin/coordenador/professor e query student_id, usa esse; senão student do user logado.
    """
    user_id = get_jwt_identity()
    user = get_current_user_from_token()
    if not user:
        return None, (jsonify({"erro": "Usuário não autenticado"}), 401)
    role = user.get('role', '')
    query_student_id = request.args.get('student_id')
    if query_student_id and role in ('admin', 'coordenador', 'professor', 'tecadm', 'diretor'):
        target_student_id = query_student_id
    else:
        student = Student.query.filter_by(user_id=user_id).first()
        if not student:
            return None, (jsonify({"erro": "Estudante não encontrado para este usuário"}), 404)
        target_student_id = student.id
    return target_student_id, None


@bp.route('/balance', methods=['GET'])
@jwt_required()
def get_balance():
    """
    Retorna saldo do aluno (ou do student_id em query se perfil permitir).
    """
    target_student_id, err = _resolve_student_id()
    if err is not None:
        return err
    balance = CoinService.get_balance(target_student_id)
    return jsonify({
        'balance': balance,
        'student_id': target_student_id
    }), 200


@bp.route('/transactions', methods=['GET'])
@jwt_required()
def get_transactions():
    """
    Lista histórico de transações com paginação (limit/offset).
    """
    target_student_id, err = _resolve_student_id()
    if err is not None:
        return err
    limit = int(request.args.get('limit', 50))
    offset = int(request.args.get('offset', 0))
    transactions = CoinService.get_transaction_history(target_student_id, limit=limit, offset=offset)
    return jsonify({
        'transactions': [
            {
                'id': t.id,
                'amount': t.amount,
                'reason': t.reason,
                'description': t.description,
                'balance_before': t.balance_before,
                'balance_after': t.balance_after,
                'created_at': t.created_at.isoformat() if t.created_at else None,
                'competition_id': t.competition_id,
                'test_session_id': t.test_session_id,
            }
            for t in transactions
        ],
        'limit': limit,
        'offset': offset
    }), 200


@bp.route('/transactions/<string:transaction_id>', methods=['GET'])
@jwt_required()
def get_transaction(transaction_id):
    """
    Detalhe de uma transação. Aluno só acessa suas próprias transações.
    """
    transaction = CoinTransaction.query.get(transaction_id)
    if not transaction:
        return jsonify({"erro": "Transação não encontrada"}), 404
    user_id = get_jwt_identity()
    student = Student.query.filter_by(user_id=user_id).first()
    if not student:
        return jsonify({"erro": "Estudante não encontrado"}), 404
    if transaction.student_id != student.id:
        return jsonify({"erro": "Acesso negado a esta transação"}), 403
    return jsonify(transaction.to_dict()), 200


@bp.route('/admin/credit', methods=['POST'])
@jwt_required()
@role_required('admin', 'coordenador')
def admin_credit_coins():
    """
    Credita moedas manualmente (admin/coordenador).
    Body: { "student_id", "amount", "reason", "description" (opcional) }
    """
    data = request.get_json()
    if not data:
        return jsonify({"erro": "Dados não fornecidos"}), 400
    student_id = data.get('student_id')
    amount = data.get('amount')
    if not student_id:
        return jsonify({"erro": "student_id é obrigatório"}), 400
    if amount is None:
        return jsonify({"erro": "amount é obrigatório"}), 400
    try:
        transaction = CoinService.credit_coins(
            student_id=student_id,
            amount=int(amount),
            reason=data.get('reason', 'admin_credit'),
            description=data.get('description'),
        )
        return jsonify({
            'message': 'Moedas creditadas com sucesso',
            'transaction_id': transaction.id,
            'new_balance': transaction.balance_after
        }), 201
    except ValueError as e:
        return jsonify({"erro": str(e)}), 400
    except Exception as e:
        logging.error(f"Erro ao creditar moedas: {str(e)}", exc_info=True)
        return jsonify({"erro": "Erro ao creditar moedas", "detalhes": str(e)}), 500
