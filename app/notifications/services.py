# -*- coding: utf-8 -*-
"""
Serviço genérico de notificações (sininho).

create_notification não faz commit: entra na transação de quem chama, para que a
notificação e a operação de origem sejam gravadas juntas (ou nenhuma delas).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

from sqlalchemy import func, or_

from app import db
from app.models.notification import Notification, NotificationRecipient
from app.utils.uuid_helpers import ensure_uuid


class NotificationError(Exception):
    status_code = 400


class NotificationNotFound(NotificationError):
    status_code = 404


RecipientInput = Union[str, Dict[str, Any]]
ReferenceInput = Union[None, Tuple[Optional[str], Any], Dict[str, Any]]

MAX_PER_PAGE = 50


def _normalize_reference(reference: ReferenceInput) -> Tuple[Optional[str], Optional[str]]:
    if not reference:
        return None, None
    if isinstance(reference, dict):
        ref_type, ref_id = reference.get("type"), reference.get("id")
    else:
        ref_type, ref_id = reference
    return (str(ref_type) if ref_type else None), (str(ref_id) if ref_id is not None else None)


def _normalize_recipients(recipients: Iterable[RecipientInput]) -> List[Dict[str, Any]]:
    """Um registro por user_id; em duplicidade vale a primeira ocorrência."""
    seen: Dict[str, Dict[str, Any]] = {}
    for raw in recipients or []:
        if isinstance(raw, dict):
            user_id = raw.get("user_id")
            school_id = raw.get("school_id")
            role = raw.get("role")
        else:
            user_id, school_id, role = raw, None, None
        if not user_id:
            continue
        key = str(user_id)
        if key in seen:
            continue
        seen[key] = {
            "user_id": key,
            "school_id": str(school_id) if school_id else None,
            "role": (str(role)[:20] if role else None),
        }
    return list(seen.values())


def create_notification(
    type: str,
    title: str,
    message: Optional[str],
    payload: Optional[Dict[str, Any]],
    reference: ReferenceInput,
    recipients: Iterable[RecipientInput],
    *,
    action_url: Optional[str] = None,
    created_by: Optional[str] = None,
    expires_at: Optional[datetime] = None,
) -> Optional[Notification]:
    """
    Cria a notificação e uma linha de destinatário por usuário.

    recipients: user_ids ou dicts {'user_id', 'school_id'?, 'role'?}.
    reference: (reference_type, reference_id) ou {'type', 'id'}.
    Sem destinatários válidos, nada é criado e devolve None.
    """
    if not type or not str(type).strip():
        raise NotificationError("type é obrigatório.")
    if not title or not str(title).strip():
        raise NotificationError("title é obrigatório.")

    rows = _normalize_recipients(recipients)
    if not rows:
        return None

    ref_type, ref_id = _normalize_reference(reference)
    notification = Notification(
        type=str(type).strip()[:50],
        title=str(title).strip()[:200],
        message=message,
        payload=payload,
        reference_type=ref_type,
        reference_id=ref_id,
        action_url=action_url,
        created_by=created_by,
        expires_at=expires_at,
    )
    db.session.add(notification)
    db.session.flush()
    db.session.add_all(
        [
            NotificationRecipient(
                notification_id=notification.id,
                user_id=r["user_id"],
                school_id=r["school_id"],
                role_snapshot=r["role"],
            )
            for r in rows
        ]
    )
    db.session.flush()
    return notification


# ---------------------------------------------------------------------------
# Leitura e estado por usuário
# ---------------------------------------------------------------------------

def _visible_query(user_id: str):
    now = datetime.utcnow()
    return (
        db.session.query(NotificationRecipient, Notification)
        .join(Notification, Notification.id == NotificationRecipient.notification_id)
        .filter(
            NotificationRecipient.user_id == str(user_id),
            NotificationRecipient.dismissed_at.is_(None),
            or_(Notification.expires_at.is_(None), Notification.expires_at > now),
        )
    )


def _iso(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value else None


def _serialize(recipient: NotificationRecipient, notification: Notification) -> Dict[str, Any]:
    return {
        "id": str(notification.id),
        "type": notification.type,
        "title": notification.title,
        "message": notification.message,
        "payload": notification.payload,
        "reference_type": notification.reference_type,
        "reference_id": notification.reference_id,
        "action_url": notification.action_url,
        "created_at": _iso(notification.created_at),
        "expires_at": _iso(notification.expires_at),
        "school_id": recipient.school_id,
        "read_at": _iso(recipient.read_at),
        "is_read": recipient.read_at is not None,
    }


def unread_count(user_id: str) -> int:
    return (
        _visible_query(user_id)
        .filter(NotificationRecipient.read_at.is_(None))
        .with_entities(func.count(NotificationRecipient.id))
        .scalar()
        or 0
    )


def _parse_positive_int(value: Any, default: int, field: str) -> int:
    if value in (None, ""):
        return default
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise NotificationError(f"{field} inválido.")
    if number < 1:
        raise NotificationError(f"{field} deve ser maior que zero.")
    return number


def list_notifications(user_id: str, args) -> Dict[str, Any]:
    """Paginado, mais recentes primeiro. Params: page, per_page (máx. 50), unread_only, type."""
    page = _parse_positive_int(args.get("page"), 1, "page")
    per_page = min(_parse_positive_int(args.get("per_page"), 20, "per_page"), MAX_PER_PAGE)

    query = _visible_query(user_id)
    if str(args.get("unread_only") or "").strip().lower() in ("1", "true", "sim"):
        query = query.filter(NotificationRecipient.read_at.is_(None))
    type_filter = (args.get("type") or "").strip()
    if type_filter:
        query = query.filter(Notification.type == type_filter)

    total = query.with_entities(func.count(NotificationRecipient.id)).scalar() or 0
    rows = (
        query.order_by(Notification.created_at.desc(), Notification.id.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return {
        "items": [_serialize(r, n) for r, n in rows],
        "page": page,
        "per_page": per_page,
        "total": total,
        "has_next": page * per_page < total,
    }


def mark_read(user_id: str, notification_id: Any) -> Dict[str, Any]:
    nid = ensure_uuid(notification_id)
    recipient = (
        NotificationRecipient.query.filter_by(notification_id=nid, user_id=str(user_id)).first()
        if nid
        else None
    )
    if not recipient:
        raise NotificationNotFound("Notificação não encontrada.")
    try:
        if recipient.read_at is None:
            recipient.read_at = datetime.utcnow()
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return {"id": str(nid), "read_at": _iso(recipient.read_at)}


def mark_all_read(user_id: str) -> int:
    try:
        updated = (
            NotificationRecipient.query.filter(
                NotificationRecipient.user_id == str(user_id),
                NotificationRecipient.read_at.is_(None),
            ).update({NotificationRecipient.read_at: datetime.utcnow()}, synchronize_session=False)
        )
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return int(updated or 0)
