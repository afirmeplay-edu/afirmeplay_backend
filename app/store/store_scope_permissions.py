# -*- coding: utf-8 -*-
"""
Permissões de escopo da loja por role.

- Admin: pode criar/editar itens para o sistema todo (scope_type=system).
- Tec adm: só para o município (scope_type=city, scope_filter.city_ids = [seu city_id]).
- Diretor/Coordenador: só para a escola (scope_type=school, scope_filter com sua school_id).
- Professor: só para suas turmas (scope_type=class, scope_filter.class_ids entre as que leciona).
"""
from typing import Dict, Any, List, Set

from app.permissions.roles import Roles
from app.permissions.utils import (
    get_teacher_schools,
    get_teacher_classes,
    get_manager_school,
)


STORE_SCOPE_OPTIONS = ['system', 'city', 'school', 'class']


def _norm_set(ids: Any) -> Set[str]:
    if ids is None:
        return set()
    if isinstance(ids, (list, tuple)):
        return {str(x).strip().lower() for x in ids if x is not None}
    return {str(ids).strip().lower()} if ids else set()


def get_allowed_store_scopes(user: Dict[str, Any]) -> List[str]:
    """Escopos que o usuário pode usar ao criar/editar item da loja."""
    if not user:
        return []
    role = Roles.normalize(user.get('role', ''))
    if role == Roles.ADMIN:
        return list(STORE_SCOPE_OPTIONS)
    if role == Roles.TECADM:
        return ['system', 'city']
    if role in (Roles.DIRETOR, Roles.COORDENADOR):
        return ['system', 'city', 'school']
    if role == Roles.PROFESSOR:
        return ['system', 'city', 'school', 'class']
    return []


def validate_store_scope_for_user(
    scope_type: str,
    scope_filter: Dict[str, Any],
    user: Dict[str, Any],
) -> None:
    """
    Valida se (scope_type, scope_filter) é permitido para o usuário.
    Levanta ValueError com mensagem clara se não for.
    """
    scope_type = (scope_type or 'system').strip().lower()
    if scope_type not in STORE_SCOPE_OPTIONS:
        raise ValueError(f"Escopo inválido: {scope_type}")

    allowed = get_allowed_store_scopes(user)
    if scope_type not in allowed:
        raise ValueError(
            f"Seu perfil não permite usar o escopo '{scope_type}'. "
            f"Permitidos: {', '.join(allowed)}."
        )

    sf = scope_filter or {}
    role = Roles.normalize(user.get('role', ''))

    if role == Roles.ADMIN:
        return

    if role == Roles.TECADM:
        city_id = (user.get('city_id') or user.get('tenant_id') or '').strip().lower()
        if not city_id:
            raise ValueError("Tec adm sem município vinculado.")
        if scope_type == 'city':
            ids = _norm_set(sf.get('city_ids') or sf.get('city_id'))
            if not ids or ids - {city_id}:
                raise ValueError("Tec adm só pode definir itens para o seu município.")
        return

    if role in (Roles.DIRETOR, Roles.COORDENADOR):
        school_id = get_manager_school(user['id'])
        school_id_str = (school_id or '').strip().lower()
        if not school_id_str:
            raise ValueError("Diretor/Coordenador sem escola vinculada.")
        if scope_type == 'school':
            ids = _norm_set(sf.get('school_ids') or sf.get('school_id'))
            if not ids or ids - {school_id_str}:
                raise ValueError("Diretor/Coordenador só pode definir itens para a sua escola.")
        if scope_type == 'class':
            from app.models.studentClass import Class
            class_ids = _norm_set(sf.get('class_ids') or sf.get('class_id'))
            if not class_ids:
                raise ValueError("Informe ao menos uma turma em scope_filter.")
            for cid in class_ids:
                cl = Class.query.get(cid)
                if not cl or str(getattr(cl, 'school_id', '')).strip().lower() != school_id_str:
                    raise ValueError("Só pode selecionar turmas da sua escola.")
        return

    if role == Roles.PROFESSOR:
        if scope_type != 'class':
            return
        teacher_class_ids = get_teacher_classes(user['id'])
        allowed_class_ids = {str(x).strip().lower() for x in (teacher_class_ids or [])}
        class_ids = _norm_set(sf.get('class_ids') or sf.get('class_id'))
        if not class_ids:
            raise ValueError("Informe ao menos uma turma em scope_filter.")
        if class_ids - allowed_class_ids:
            raise ValueError("Professor só pode definir itens para turmas em que você leciona.")


def can_manage_store_item(item: Any, user: Dict[str, Any]) -> bool:
    """
    Retorna True se o usuário pode editar/remover este item.
    Admin: todos. Tec adm: system ou city do seu município. Diretor: + school sua. Professor: + class suas.
    """
    if not user or not item:
        return False
    role = Roles.normalize(user.get('role', ''))
    if role == Roles.ADMIN:
        return True

    st = (getattr(item, 'scope_type', None) or 'system').strip().lower()
    sf = getattr(item, 'scope_filter', None) or {}

    if st == 'system':
        return True

    if role == Roles.TECADM:
        city_id = (user.get('city_id') or user.get('tenant_id') or '').strip().lower()
        if not city_id:
            return False
        if st == 'city':
            ids = _norm_set(sf.get('city_ids') or sf.get('city_id'))
            return city_id in ids
        return False

    if role in (Roles.DIRETOR, Roles.COORDENADOR):
        school_id = get_manager_school(user['id'])
        school_id_str = (school_id or '').strip().lower()
        if not school_id_str:
            return False
        if st == 'school':
            ids = _norm_set(sf.get('school_ids') or sf.get('school_id'))
            return school_id_str in ids
        if st == 'class':
            ids = _norm_set(sf.get('class_ids') or sf.get('class_id'))
            if not ids:
                return False
            from app.models.studentClass import Class
            for cid in ids:
                cl = Class.query.get(cid)
                if cl and str(getattr(cl, 'school_id', '')).strip().lower() == school_id_str:
                    return True
            return False
        return False

    if role == Roles.PROFESSOR:
        teacher_class_ids = get_teacher_classes(user['id'])
        allowed_class_ids = {str(x).strip().lower() for x in (teacher_class_ids or [])}
        if st == 'system':
            return True
        if st == 'class':
            ids = _norm_set(sf.get('class_ids') or sf.get('class_id'))
            return bool(ids and ids <= allowed_class_ids)
        return False

    return False


def filter_items_user_can_manage(items: List[Any], user: Dict[str, Any]) -> List[Any]:
    """Filtra a lista de itens para apenas os que o usuário pode gerenciar."""
    if not user:
        return []
    return [i for i in items if can_manage_store_item(i, user)]
