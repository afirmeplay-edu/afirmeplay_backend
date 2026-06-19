# -*- coding: utf-8 -*-
"""Escopo GLOBAL / CITY / PRIVATE — espelha o padrão de public.question."""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from sqlalchemy import and_, or_

from app.permissions.roles import Roles
from app.utils.tenant_middleware import get_current_tenant_context
from app.afirme_ler.services.parsing import SCOPE_CITY, SCOPE_GLOBAL, SCOPE_PRIVATE


def _user_id(user: Dict[str, Any]) -> Optional[str]:
    return user.get("id") or user.get("user_id")


def _user_city_id(user: Dict[str, Any]) -> Optional[str]:
    return user.get("tenant_id") or user.get("city_id")


def resolve_scope_on_create(user: Dict[str, Any]) -> Tuple[str, Optional[str], Optional[str]]:
    role = Roles.normalize(user.get("role", ""))
    uid = _user_id(user)
    city_id = _user_city_id(user)

    if role == Roles.ADMIN:
        return SCOPE_GLOBAL, None, None
    if role == Roles.TECADM:
        if not city_id:
            raise ValueError("Não foi possível identificar o município para criar conteúdo municipal.")
        return SCOPE_CITY, str(city_id), None
    if role in (Roles.PROFESSOR, Roles.COORDENADOR, Roles.DIRETOR):
        if not uid:
            raise ValueError("Usuário inválido para criar conteúdo privado.")
        return SCOPE_PRIVATE, None, str(uid)
    raise ValueError("Seu perfil não pode cadastrar conteúdo de leitura.")


def apply_visibility_filter(query, model, user: Dict[str, Any]):
    context = get_current_tenant_context()
    city_id = None
    if context and context.city_id:
        city_id = str(context.city_id)
    if not city_id:
        city_id = _user_city_id(user)
        if city_id:
            city_id = str(city_id)

    uid = _user_id(user)
    scope_filters = [model.scope_type == SCOPE_GLOBAL]

    if city_id:
        scope_filters.append(
            and_(
                model.scope_type == SCOPE_CITY,
                model.owner_city_id == city_id,
            )
        )

    if uid:
        scope_filters.append(
            and_(
                model.scope_type == SCOPE_PRIVATE,
                model.owner_user_id == str(uid),
            )
        )

    return query.filter(or_(*scope_filters))


def user_can_modify(user: Dict[str, Any], entity) -> bool:
    role = Roles.normalize(user.get("role", ""))
    uid = _user_id(user)
    city_id = _user_city_id(user)

    if role == Roles.ADMIN:
        return True

    scope = entity.scope_type
    if scope == SCOPE_GLOBAL:
        return False

    if scope == SCOPE_CITY:
        if role != Roles.TECADM:
            return False
        return bool(city_id) and str(entity.owner_city_id) == str(city_id)

    if scope == SCOPE_PRIVATE:
        return bool(uid) and str(entity.owner_user_id) == str(uid)

    return False
