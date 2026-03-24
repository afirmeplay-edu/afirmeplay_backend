# -*- coding: utf-8 -*-
"""
Serviço da loja: listar itens e processar compras (débito de afirmecoins + registro).
"""
from app import db
from app.store.models import StoreItem, StudentPurchase, STORE_SCOPE_SYSTEM
from app.balance.services.coin_service import CoinService, InsufficientBalanceError


class StoreItemNotFoundError(Exception):
    """Item da loja não encontrado ou inativo."""
    pass


def _norm_id(x):
    if x is None:
        return None
    return str(x).strip().lower()


def _item_visible_for_scope(item, scope_city_id=None, scope_school_id=None, scope_class_id=None):
    """Retorna True se o item é visível para o contexto (cidade, escola, turma) do aluno."""
    st = (item.scope_type or STORE_SCOPE_SYSTEM).strip().lower()
    if st == STORE_SCOPE_SYSTEM:
        return True
    sf = item.scope_filter or {}
    if st == 'city':
        ids = sf.get('city_ids') or sf.get('city_id') or []
        if isinstance(ids, str):
            ids = [ids]
        return scope_city_id and _norm_id(scope_city_id) in {_norm_id(i) for i in ids}
    if st == 'school':
        ids = sf.get('school_ids') or sf.get('school_id') or []
        if isinstance(ids, str):
            ids = [ids]
        return scope_school_id and _norm_id(scope_school_id) in {_norm_id(i) for i in ids}
    if st == 'class':
        ids = sf.get('class_ids') or sf.get('class_id') or []
        if isinstance(ids, str):
            ids = [ids]
        return scope_class_id and _norm_id(scope_class_id) in {_norm_id(i) for i in ids}
    return True


class StoreService:
    @staticmethod
    def list_items(
        active_only=True,
        category=None,
        physical_only=None,
        scope_city_id=None,
        scope_school_id=None,
        scope_class_id=None,
    ):
        """
        Lista itens da loja visíveis para o contexto (aluno: sua cidade, escola, turma).
        """
        q = StoreItem.query
        if active_only:
            q = q.filter_by(is_active=True)
        if category:
            q = q.filter_by(category=category)
        if physical_only is not None:
            q = q.filter_by(is_physical=physical_only)
        items = q.order_by(StoreItem.sort_order.asc(), StoreItem.name.asc()).all()
        if scope_city_id is None and scope_school_id is None and scope_class_id is None:
            return items
        return [
            i for i in items
            if _item_visible_for_scope(i, scope_city_id, scope_school_id, scope_class_id)
        ]

    @staticmethod
    def get_item(item_id):
        """Retorna um item por ID ou None."""
        return StoreItem.query.filter_by(id=item_id).first()

    @staticmethod
    def list_items_for_admin(active_only=None, user=None):
        """
        Lista itens que o usuário pode gerenciar (admin: todos; tecadm: sistema + cidade; etc.).
        user: dict com role, city_id, id (user_id para manager/teacher).
        """
        from app.store.store_scope_permissions import filter_items_user_can_manage
        q = StoreItem.query.order_by(StoreItem.sort_order.asc(), StoreItem.name.asc())
        if active_only is not None:
            q = q.filter_by(is_active=active_only)
        items = q.all()
        if user:
            items = filter_items_user_can_manage(items, user)
        return items

    @staticmethod
    def create_item(data, user):
        """Cria item na loja. Valida escopo conforme perfil do user. Retorna o item criado."""
        from app.store.store_scope_permissions import validate_store_scope_for_user
        validate_store_scope_for_user(
            data.get('scope_type', 'system'),
            data.get('scope_filter') or {},
            user,
        )
        item = StoreItem(
            name=data['name'],
            description=data.get('description'),
            price=int(data['price']),
            category=data['category'],
            reward_type=data.get('reward_type', data['category']),
            reward_data=data.get('reward_data'),
            is_physical=bool(data.get('is_physical', False)),
            scope_type=(data.get('scope_type') or 'system').strip().lower(),
            scope_filter=data.get('scope_filter'),
            is_active=bool(data.get('is_active', True)),
            sort_order=int(data.get('sort_order', 0)),
        )
        db.session.add(item)
        db.session.commit()
        return item

    @staticmethod
    def update_item(item_id, data, user):
        """Atualiza item. Valida que o user pode gerenciar o item e que o novo escopo é permitido."""
        from app.store.store_scope_permissions import can_manage_store_item, validate_store_scope_for_user
        item = StoreItem.query.get(item_id)
        if not item:
            return None
        if not can_manage_store_item(item, user):
            raise PermissionError("Você não tem permissão para editar este item.")
        scope_type = (data.get('scope_type') or item.scope_type or 'system').strip().lower()
        scope_filter = data.get('scope_filter') if 'scope_filter' in data else item.scope_filter
        validate_store_scope_for_user(scope_type, scope_filter or {}, user)
        if 'name' in data:
            item.name = data['name']
        if 'description' in data:
            item.description = data['description']
        if 'price' in data:
            item.price = int(data['price'])
        if 'category' in data:
            item.category = data['category']
        if 'reward_type' in data:
            item.reward_type = data['reward_type']
        if 'reward_data' in data:
            item.reward_data = data['reward_data']
        if 'is_physical' in data:
            item.is_physical = bool(data['is_physical'])
        if 'scope_type' in data:
            item.scope_type = scope_type
        if 'scope_filter' in data:
            item.scope_filter = data['scope_filter']
        if 'is_active' in data:
            item.is_active = bool(data['is_active'])
        if 'sort_order' in data:
            item.sort_order = int(data['sort_order'])
        db.session.commit()
        return item

    @staticmethod
    def delete_item(item_id, user):
        """Remove item. Valida que o user pode gerenciar o item."""
        from app.store.store_scope_permissions import can_manage_store_item
        item = StoreItem.query.get(item_id)
        if not item:
            return False
        if not can_manage_store_item(item, user):
            raise PermissionError("Você não tem permissão para remover este item.")
        db.session.delete(item)
        db.session.commit()
        return True

    @staticmethod
    def purchase(
        student_id: str,
        store_item_id: str,
        scope_city_id=None,
        scope_school_id=None,
        scope_class_id=None,
    ):
        """
        Processa a compra: debita afirmecoins do aluno e registra a compra.
        Se escopo for passado, só permite comprar itens visíveis para esse escopo.
        """
        item = StoreItem.query.filter_by(id=store_item_id, is_active=True).first()
        if not item:
            raise StoreItemNotFoundError("Item não encontrado ou não está disponível.")
        if scope_city_id is not None or scope_school_id is not None or scope_class_id is not None:
            if not _item_visible_for_scope(item, scope_city_id, scope_school_id, scope_class_id):
                raise StoreItemNotFoundError("Item não disponível para o seu contexto (turma/escola/município).")

        # Débito de moedas (levanta InsufficientBalanceError se saldo insuficiente)
        transaction = CoinService.debit_coins(
            student_id=student_id,
            amount=item.price,
            reason='store_purchase',
            description=f"Loja: {item.name} (item_id={item.id})",
        )

        # Registrar compra
        purchase = StudentPurchase(
            student_id=student_id,
            store_item_id=item.id,
            price_paid=item.price,
        )
        db.session.add(purchase)
        db.session.commit()

        return purchase, transaction

    @staticmethod
    def get_student_purchases(student_id: str, limit: int = 50, offset: int = 0):
        """Lista compras do aluno (mais recentes primeiro)."""
        return (
            StudentPurchase.query.filter_by(student_id=student_id)
            .order_by(StudentPurchase.created_at.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )

    @staticmethod
    def has_purchased(student_id: str, store_item_id: str) -> bool:
        """Verifica se o aluno já comprou determinado item."""
        return (
            StudentPurchase.query.filter_by(
                student_id=student_id,
                store_item_id=store_item_id,
            ).first()
            is not None
        )
