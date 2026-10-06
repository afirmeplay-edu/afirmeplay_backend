# -*- coding: utf-8 -*-
"""Cronograma de logística de aplicação de avaliação.

Só referencia Test, School e Class; não altera ClassTest (janela online da prova).
"""
import uuid
from datetime import datetime

from app import db
from sqlalchemy.dialects.postgresql import UUID


LOGISTICS_STATUS_DRAFT = "rascunho"
LOGISTICS_STATUS_PUBLISHED = "publicado"
LOGISTICS_STATUS_CANCELLED = "cancelado"
LOGISTICS_STATUSES = (
    LOGISTICS_STATUS_DRAFT,
    LOGISTICS_STATUS_PUBLISHED,
    LOGISTICS_STATUS_CANCELLED,
)


class LogisticsSchedule(db.Model):
    __tablename__ = "logistics_schedule"
    __table_args__ = (
        db.CheckConstraint(
            "status IN ('rascunho', 'publicado', 'cancelado')",
            name="ck_logistics_schedule_status",
        ),
        {"schema": "tenant"},
    )

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    test_id = db.Column(
        db.String, db.ForeignKey("tenant.test.id", ondelete="CASCADE"), nullable=False
    )
    education_stage_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("public.education_stage.id", ondelete="SET NULL"),
        nullable=True,
    )
    title = db.Column(db.String(200), nullable=False)
    status = db.Column(db.String(20), nullable=False, default=LOGISTICS_STATUS_DRAFT)
    notes = db.Column(db.Text, nullable=True)
    created_by = db.Column(
        db.String, db.ForeignKey("public.users.id", ondelete="SET NULL"), nullable=True
    )
    created_at = db.Column(db.TIMESTAMP, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.TIMESTAMP, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    published_at = db.Column(db.TIMESTAMP, nullable=True)
    cancelled_at = db.Column(db.TIMESTAMP, nullable=True)

    items = db.relationship(
        "LogisticsScheduleItem",
        backref="schedule",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="LogisticsScheduleItem.scheduled_date",
    )


class LogisticsScheduleItem(db.Model):
    __tablename__ = "logistics_schedule_item"
    __table_args__ = (
        db.UniqueConstraint(
            "schedule_id",
            "class_id",
            "scheduled_date",
            name="uq_logistics_item_schedule_class_date",
        ),
        db.CheckConstraint(
            "students_count >= 0 AND tablets_qty >= 0 AND booklets_qty >= 0",
            name="ck_logistics_item_non_negative",
        ),
        {"schema": "tenant"},
    )

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    schedule_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("tenant.logistics_schedule.id", ondelete="CASCADE"),
        nullable=False,
    )
    school_id = db.Column(
        db.String(36), db.ForeignKey("tenant.school.id", ondelete="CASCADE"), nullable=False
    )
    grade_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("public.grade.id", ondelete="SET NULL"),
        nullable=True,
    )
    class_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("tenant.class.id", ondelete="CASCADE"),
        nullable=False,
    )
    scheduled_date = db.Column(db.Date, nullable=True)
    students_count = db.Column(db.Integer, nullable=False, default=0)
    tablets_qty = db.Column(db.Integer, nullable=False, default=0)
    booklets_qty = db.Column(db.Integer, nullable=False, default=0)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.TIMESTAMP, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.TIMESTAMP, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )
