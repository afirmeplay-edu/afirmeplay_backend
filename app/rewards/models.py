# -*- coding: utf-8 -*-
"""Sessões e recompensas de conteúdo (Jogos / Play TV)."""
from app import db
import uuid

from app.models.student import Student
from app.balance.models import CoinTransaction


class ContentSession(db.Model):
    __tablename__ = "content_sessions"
    __table_args__ = {"schema": "tenant"}

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id = db.Column(
        db.String,
        db.ForeignKey(Student.__table__.c.id, ondelete="CASCADE"),
        nullable=False,
    )
    content_type = db.Column(db.String(16), nullable=False)
    content_id = db.Column(db.String, nullable=False)
    started_at = db.Column(db.TIMESTAMP, nullable=False)
    created_at = db.Column(db.TIMESTAMP, server_default=db.text("CURRENT_TIMESTAMP"))

    student = db.relationship("Student", backref=db.backref("content_sessions", lazy="dynamic"))


class ContentReward(db.Model):
    __tablename__ = "content_rewards"
    __table_args__ = (
        db.UniqueConstraint(
            "student_id",
            "content_type",
            "content_id",
            name="uq_content_rewards_student_type_id",
        ),
        {"schema": "tenant"},
    )

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id = db.Column(
        db.String,
        db.ForeignKey(Student.__table__.c.id, ondelete="CASCADE"),
        nullable=False,
    )
    content_type = db.Column(db.String(16), nullable=False)
    content_id = db.Column(db.String, nullable=False)
    coins = db.Column(db.Integer, nullable=False)
    coin_transaction_id = db.Column(
        db.String,
        db.ForeignKey(CoinTransaction.__table__.c.id, ondelete="SET NULL"),
        nullable=True,
    )
    paid_at = db.Column(db.TIMESTAMP, nullable=False)

    student = db.relationship("Student", backref=db.backref("content_rewards", lazy="dynamic"))
    coin_transaction = db.relationship("CoinTransaction")
