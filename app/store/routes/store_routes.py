# -*- coding: utf-8 -*-
"""
Rotas da Loja: listar itens e comprar com afirmecoins.
Admin/tec adm/diretor/coordenador/professor: CRUD de itens com escopo por perfil.
"""
from flask import Blueprint, request, jsonify, g
from flask_jwt_extended import jwt_required, get_jwt_identity
from app import db
from app.permissions import get_current_user_from_token, role_required
from app.utils.tenant_middleware import ensure_tenant_schema_for_user, set_search_path
from app.models.student import Student
from app.store.services.store_service import (
    StoreService,
    StoreItemNotFoundError,
)
from app.balance.services.coin_service import InsufficientBalanceError
from app.store.store_scope_permissions import get_allowed_store_scopes
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
import logging

bp = Blueprint('store', __name__, url_prefix='/store')


@bp.errorhandler(SQLAlchemyError)
def handle_db_error(error):
    db.session.rollback()
    logging.error("Database error: %s", str(error))
    return jsonify({"erro": "Erro no banco de dados", "detalhes": str(error)}), 500


@bp.errorhandler(IntegrityError)
def handle_integrity_error(error):
    db.session.rollback()
    logging.error("Integrity error: %s", str(error))
    return jsonify({"erro": "Erro de integridade de dados", "detalhes": str(error)}), 400


@bp.errorhandler(StoreItemNotFoundError)
def handle_item_not_found(error):
    return jsonify({"erro": "Item não encontrado ou indisponível", "detalhes": str(error)}), 404


@bp.errorhandler(InsufficientBalanceError)
def handle_insufficient_balance(error):
    return jsonify({"erro": "Saldo insuficiente", "detalhes": str(error)}), 400


@bp.errorhandler(PermissionError)
def handle_permission_error(error):
    return jsonify({"erro": "Sem permissão", "detalhes": str(error)}), 403


def _current_student_id():
    """
    Retorna student_id do usuário logado (aluno) ou (None, error_response).
    Para compra, apenas o próprio aluno pode comprar.
    """
    user_id = get_jwt_identity()
    user = get_current_user_from_token()
    if not user:
        return None, (jsonify({"erro": "Usuário não autenticado"}), 401)
    if not ensure_tenant_schema_for_user(user_id):
        return None, (jsonify({"erro": "Contexto do município não disponível. Acesse pelo subdomínio da cidade."}), 400)
    student = Student.query.filter_by(user_id=user_id).first()
    if not student:
        return None, (jsonify({"erro": "Estudante não encontrado para este usuário"}), 404)
    return student.id, None


def _scope_context_for_student(student_id):
    """Retorna (scope_city_id, scope_school_id, scope_class_id) para filtrar itens visíveis ao aluno."""
    ctx = getattr(g, 'tenant_context', None)
    scope_city_id = ctx.city_id if ctx and getattr(ctx, 'city_id', None) else None
    student = Student.query.get(student_id) if student_id else None
    scope_school_id = str(student.school_id) if student and getattr(student, 'school_id', None) else None
    scope_class_id = str(student.class_id) if student and getattr(student, 'class_id', None) else None
    return scope_city_id, scope_school_id, scope_class_id


@bp.route('/items', methods=['GET'])
@jwt_required(optional=True)
def list_items():
    """
    Lista itens da loja visíveis para o contexto (cidade/escola/turma do aluno).
    Query: category, physical_only. Opcional: student_id para "já comprado".
    """
    active_only = request.args.get('active_only', 'true').lower() != 'false'
    category = request.args.get('category') or None
    physical_only = request.args.get('physical_only')
    if physical_only is not None:
        physical_only = physical_only.lower() == 'true'

    scope_city_id, scope_school_id, scope_class_id = None, None, None
    student_id = None
    user_id = get_jwt_identity()
    user = get_current_user_from_token() if user_id else None
    if user_id and user:
        role = user.get('role', '')
        query_student_id = request.args.get('student_id')
        if query_student_id and role in ('admin', 'coordenador', 'professor', 'tecadm', 'diretor'):
            student_id = query_student_id
        else:
            if ensure_tenant_schema_for_user(user_id):
                student = Student.query.filter_by(user_id=user_id).first()
                student_id = student.id if student else None
            else:
                student_id = None
        if student_id:
            scope_city_id, scope_school_id, scope_class_id = _scope_context_for_student(student_id)

    # Tabelas da loja (store_items, student_purchases) estão em public
    set_search_path("public")
    items = StoreService.list_items(
        active_only=active_only,
        category=category,
        physical_only=physical_only,
        scope_city_id=scope_city_id,
        scope_school_id=scope_school_id,
        scope_class_id=scope_class_id,
    )
    result = [item.to_dict() for item in items]

    if student_id:
        for it in result:
            it['already_purchased'] = StoreService.has_purchased(student_id, it['id'])
    for it in result:
        it.setdefault('already_purchased', False)

    return jsonify({'items': result}), 200


@bp.route('/purchase', methods=['POST'])
@jwt_required()
def purchase():
    """
    Compra um item da loja. Debita afirmecoins do aluno e registra a compra.
    Body: { "store_item_id": "uuid" }
    Apenas o próprio aluno (token) pode comprar.
    """
    student_id, err = _current_student_id()
    if err is not None:
        return err

    data = request.get_json()
    if not data:
        return jsonify({"erro": "Dados não fornecidos"}), 400
    store_item_id = data.get('store_item_id')
    if not store_item_id:
        return jsonify({"erro": "store_item_id é obrigatório"}), 400

    scope_city_id, scope_school_id, scope_class_id = _scope_context_for_student(student_id)
    # Tabelas da loja e de coins (store_items, student_purchases, etc.) estão em public
    set_search_path("public")
    try:
        purchase_record, coin_transaction = StoreService.purchase(
            student_id,
            store_item_id,
            scope_city_id=scope_city_id,
            scope_school_id=scope_school_id,
            scope_class_id=scope_class_id,
        )
        return jsonify({
            'message': 'Compra realizada com sucesso',
            'purchase': purchase_record.to_dict(),
            'new_balance': coin_transaction.balance_after,
            'reward_type': purchase_record.store_item.reward_type,
            'reward_data': purchase_record.store_item.reward_data,
        }), 201
    except StoreItemNotFoundError:
        raise
    except InsufficientBalanceError:
        raise


@bp.route('/my-purchases', methods=['GET'])
@jwt_required()
def my_purchases():
    """
    Lista as compras do aluno logado (histórico da loja).
    """
    student_id, err = _current_student_id()
    if err is not None:
        return err

    # Tabelas da loja (student_purchases, store_items) estão em public
    set_search_path("public")
    limit = int(request.args.get('limit', 50))
    offset = int(request.args.get('offset', 0))
    purchases = StoreService.get_student_purchases(student_id, limit=limit, offset=offset)
    result = []
    for p in purchases:
        d = p.to_dict()
        d['item_name'] = p.store_item.name if p.store_item else None
        d['reward_type'] = p.store_item.reward_type if p.store_item else None
        d['reward_data'] = p.store_item.reward_data if p.store_item else None
        result.append(d)

    return jsonify({
        'purchases': result,
        'limit': limit,
        'offset': offset,
    }), 200


# ---------- Admin: CRUD de itens (admin, tecadm, diretor, coordenador, professor) ----------

def _user_dict_for_scope():
    """Monta o dict do usuário com city_id/tenant_id para validação de escopo."""
    user = get_current_user_from_token()
    if not user:
        return None
    ctx = getattr(g, 'tenant_context', None)
    if ctx and getattr(ctx, 'city_id', None):
        user = dict(user)
        user.setdefault('city_id', ctx.city_id)
        user.setdefault('tenant_id', ctx.city_id)
    return user


@bp.route('/admin/items', methods=['GET'])
@jwt_required()
@role_required('admin', 'tecadm', 'diretor', 'coordenador', 'professor')
def admin_list_items():
    """
    Lista itens que o usuário pode gerenciar.
    Query: active_only=true|false (opcional).
    """
    user = _user_dict_for_scope()
    if not user:
        return jsonify({"erro": "Usuário não autenticado"}), 401
    active_only = request.args.get('active_only')
    if active_only is not None:
        active_only = active_only.lower() == 'true'
    items = StoreService.list_items_for_admin(active_only=active_only, user=user)
    return jsonify({'items': [i.to_dict() for i in items]}), 200


@bp.route('/admin/items', methods=['POST'])
@jwt_required()
@role_required('admin', 'tecadm', 'diretor', 'coordenador', 'professor')
def admin_create_item():
    """
    Cria item na loja. Body: name, description?, price, category, reward_type?, reward_data?,
    is_physical?, scope_type (system|city|school|class), scope_filter? { city_ids?, school_ids?, class_ids? }.
    """
    user = _user_dict_for_scope()
    if not user:
        return jsonify({"erro": "Usuário não autenticado"}), 401
    data = request.get_json()
    if not data:
        return jsonify({"erro": "Dados não fornecidos"}), 400
    if not data.get('name'):
        return jsonify({"erro": "name é obrigatório"}), 400
    if data.get('price') is None:
        return jsonify({"erro": "price é obrigatório"}), 400
    if not data.get('category'):
        return jsonify({"erro": "category é obrigatório"}), 400
    try:
        item = StoreService.create_item(data, user)
        return jsonify(item.to_dict()), 201
    except ValueError as e:
        return jsonify({"erro": str(e)}), 400


@bp.route('/admin/items/<item_id>', methods=['PUT'])
@jwt_required()
@role_required('admin', 'tecadm', 'diretor', 'coordenador', 'professor')
def admin_update_item(item_id):
    """Atualiza item. Apenas campos enviados são alterados."""
    user = _user_dict_for_scope()
    if not user:
        return jsonify({"erro": "Usuário não autenticado"}), 401
    data = request.get_json()
    if not data:
        return jsonify({"erro": "Dados não fornecidos"}), 400
    try:
        item = StoreService.update_item(item_id, data, user)
        if item is None:
            return jsonify({"erro": "Item não encontrado"}), 404
        return jsonify(item.to_dict()), 200
    except PermissionError as e:
        return jsonify({"erro": str(e)}), 403
    except ValueError as e:
        return jsonify({"erro": str(e)}), 400


@bp.route('/admin/items/<item_id>', methods=['DELETE'])
@jwt_required()
@role_required('admin', 'tecadm', 'diretor', 'coordenador', 'professor')
def admin_delete_item(item_id):
    """Remove item da loja."""
    user = _user_dict_for_scope()
    if not user:
        return jsonify({"erro": "Usuário não autenticado"}), 401
    try:
        ok = StoreService.delete_item(item_id, user)
        if not ok:
            return jsonify({"erro": "Item não encontrado"}), 404
        return jsonify({"message": "Item removido"}), 200
    except PermissionError as e:
        return jsonify({"erro": str(e)}), 403


@bp.route('/admin/allowed-scopes', methods=['GET'])
@jwt_required()
@role_required('admin', 'tecadm', 'diretor', 'coordenador', 'professor')
def admin_allowed_scopes():
    """Retorna os escopos que o usuário pode usar ao criar/editar item (para montar o select no front)."""
    user = _user_dict_for_scope()
    if not user:
        return jsonify({"erro": "Usuário não autenticado"}), 401
    allowed = get_allowed_store_scopes(user)
    return jsonify({'allowed_scopes': allowed}), 200
