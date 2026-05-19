"""
Usuários com role aplicador: login por prefixo de e-mail, senha offline em texto claro.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.models.user import User, RoleEnum


def email_login_prefix(email: Optional[str]) -> Optional[str]:
    if not email or "@" not in email:
        return None
    part = email.split("@", 1)[0].strip()
    return part or None


def assert_email_prefix_unique_in_city(
    email: str, city_id: str, exclude_user_id: Optional[str] = None
) -> None:
    prefix = email_login_prefix(email)
    if not prefix:
        raise ValueError("e-mail inválido")
    prefix_lower = prefix.lower()
    q = User.query.filter(User.city_id == str(city_id), User.email.isnot(None))
    if exclude_user_id:
        q = q.filter(User.id != exclude_user_id)
    for u in q.all():
        if not u.email:
            continue
        other = email_login_prefix(u.email)
        if other and other.lower() == prefix_lower:
            raise ValueError(
                f"o prefixo de login '{prefix}' já está em uso neste município "
                f"({u.email})"
            )


def sync_offline_password_if_aplicador(user: User, plain_password: str) -> None:
    if user.role == RoleEnum.APLICADOR:
        user.offline_password = plain_password


def apply_aplicador_credentials(user: User, plain_password: str) -> None:
    """Define hash (web/mobile online) e senha offline em texto claro."""
    from app.utils.auth import hash_password

    user.password_hash = hash_password(plain_password)
    user.offline_password = plain_password


def resolve_user_by_login_ident(
    ident: str, city_id: Optional[str] = None
) -> Optional[User]:
    """
    Matrícula, e-mail completo ou prefixo antes do @ (com city_id desambigua).
    """
    ident = (ident or "").strip()
    if not ident:
        return None

    usuario = User.query.filter_by(registration=ident).first()
    if usuario:
        return usuario

    usuario = User.query.filter(User.email.ilike(ident)).first()
    if usuario:
        return usuario

    if "@" in ident:
        return None

    q = User.query.filter(User.email.ilike(f"{ident}@%"))
    if city_id:
        q = q.filter(User.city_id == str(city_id))
    candidates = q.all()
    if len(candidates) == 1:
        return candidates[0]
    return None


def collect_aplicadores_for_city(city_id: str) -> List[Dict[str, Any]]:
    """Todos os aplicadores do município (Opção A) para o pacote offline."""
    rows = (
        User.query.filter_by(city_id=str(city_id), role=RoleEnum.APLICADOR)
        .order_by(User.name.asc())
        .all()
    )
    out: List[Dict[str, Any]] = []
    for u in rows:
        login = email_login_prefix(u.email) or (
            str(u.registration).strip() if u.registration else None
        )
        if not login:
            continue
        out.append(
            {
                "user_id": u.id,
                "name": u.name or "",
                "email": u.email,
                "login": login,
                "role": RoleEnum.APLICADOR.value,
                "offline_password": u.offline_password or "",
            }
        )
    return out
