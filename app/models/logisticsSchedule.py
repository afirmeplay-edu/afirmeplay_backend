# -*- coding: utf-8 -*-
"""Cronograma de logística de aplicação de avaliação.

Pode referenciar Test (avaliação do sistema), AnswerSheetGabarito (cartão-resposta)
ou só um título/formato (personalizada). Não altera ClassTest.
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

LOGISTICS_ORIGEM_MANUAL = "manual"
LOGISTICS_ORIGEM_AUTO = "auto"
LOGISTICS_ORIGINS = (LOGISTICS_ORIGEM_MANUAL, LOGISTICS_ORIGEM_AUTO)

LOGISTICS_SOURCE_AVALIACAO = "avaliacao"
LOGISTICS_SOURCE_CARTAO = "cartao_resposta"
LOGISTICS_SOURCE_PERSONALIZADA = "personalizada"
LOGISTICS_SOURCES = (
    LOGISTICS_SOURCE_AVALIACAO,
    LOGISTICS_SOURCE_CARTAO,
    LOGISTICS_SOURCE_PERSONALIZADA,
)

LOGISTICS_EVAL_VIRTUAL = "virtual"
LOGISTICS_EVAL_PHYSICAL = "physical"
LOGISTICS_EVAL_MODES = (LOGISTICS_EVAL_VIRTUAL, LOGISTICS_EVAL_PHYSICAL)


class LogisticsSchedule(db.Model):
    __tablename__ = "logistics_schedule"
    __table_args__ = (
        db.CheckConstraint(
            "status IN ('rascunho', 'publicado', 'cancelado')",
            name="ck_logistics_schedule_status",
        ),
        db.CheckConstraint(
            "source IN ('avaliacao', 'cartao_resposta', 'personalizada')",
            name="ck_logistics_schedule_source",
        ),
        db.CheckConstraint(
            "("
            " (source = 'avaliacao' AND test_id IS NOT NULL)"
            " OR (source = 'cartao_resposta' AND test_id IS NULL)"
            " OR (source = 'personalizada' AND test_id IS NULL AND gabarito_id IS NULL"
            "     AND title IS NOT NULL AND btrim(title) <> '')"
            ")",
            name="ck_logistics_schedule_source_links",
        ),
        db.CheckConstraint(
            "evaluation_mode IS NULL OR evaluation_mode IN ('virtual', 'physical')",
            name="ck_logistics_schedule_evaluation_mode",
        ),
        db.Index("idx_logistics_schedule_gabarito_id", "gabarito_id"),
        {"schema": "tenant"},
    )

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source = db.Column(
        db.String(30),
        nullable=False,
        default=LOGISTICS_SOURCE_AVALIACAO,
        server_default=LOGISTICS_SOURCE_AVALIACAO,
    )
    test_id = db.Column(
        db.String, db.ForeignKey("tenant.test.id", ondelete="CASCADE"), nullable=True
    )
    gabarito_id = db.Column(
        db.String(36),
        db.ForeignKey("tenant.answer_sheet_gabaritos.id", ondelete="SET NULL"),
        nullable=True,
    )
    evaluation_mode = db.Column(db.String(20), nullable=True)
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
        db.CheckConstraint(
            "origem IN ('manual', 'auto')",
            name="ck_logistics_item_origem",
        ),
        db.Index("idx_logistics_item_applicator_user_id", "applicator_user_id"),
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
    applicator_user_id = db.Column(
        db.String,
        db.ForeignKey("public.users.id", ondelete="SET NULL"),
        nullable=True,
    )
    origem = db.Column(
        db.String(20),
        nullable=False,
        default=LOGISTICS_ORIGEM_MANUAL,
        server_default=LOGISTICS_ORIGEM_MANUAL,
    )
    editado_manualmente = db.Column(
        db.Boolean, nullable=False, default=False, server_default=db.text("false")
    )
    created_at = db.Column(db.TIMESTAMP, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.TIMESTAMP, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )
