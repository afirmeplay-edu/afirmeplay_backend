# -*- coding: utf-8 -*-
"""Notificações do sininho (tabela central, genérica por tipo).

reference_type/reference_id apontam para o objeto de origem sem FK (polimórfico).
"""
import uuid
from datetime import datetime

from app import db
from sqlalchemy.dialects.postgresql import JSONB, UUID


class Notification(db.Model):
    __tablename__ = "notification"
    __table_args__ = {"schema": "tenant"}

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    type = db.Column(db.String(50), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=True)
    payload = db.Column(JSONB, nullable=True)
    reference_type = db.Column(db.String(50), nullable=True)
    reference_id = db.Column(db.String(64), nullable=True)
    action_url = db.Column(db.String(500), nullable=True)
    created_by = db.Column(
        db.String, db.ForeignKey("public.users.id", ondelete="SET NULL"), nullable=True
    )
    created_at = db.Column(db.TIMESTAMP, nullable=False, default=datetime.utcnow)
    expires_at = db.Column(db.TIMESTAMP, nullable=True)

    recipients = db.relationship(
        "NotificationRecipient",
        backref="notification",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class NotificationRecipient(db.Model):
    __tablename__ = "notification_recipient"
    __table_args__ = (
        db.UniqueConstraint("notification_id", "user_id", name="uq_notification_recipient_user"),
        db.Index("idx_notification_recipient_user_read", "user_id", "read_at"),
        {"schema": "tenant"},
    )

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    notification_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("tenant.notification.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id = db.Column(
        db.String, db.ForeignKey("public.users.id", ondelete="CASCADE"), nullable=False
    )
    school_id = db.Column(
        db.String(36), db.ForeignKey("tenant.school.id", ondelete="CASCADE"), nullable=True
    )
    role_snapshot = db.Column(db.String(20), nullable=True)
    read_at = db.Column(db.TIMESTAMP, nullable=True)
    dismissed_at = db.Column(db.TIMESTAMP, nullable=True)
