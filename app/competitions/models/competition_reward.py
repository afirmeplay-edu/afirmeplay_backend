# -*- coding: utf-8 -*-
"""Modelo de Recompensa de Competição - controle de moedas de participação (Etapa 2)."""
from app import db
import uuid


class CompetitionReward(db.Model):
    __tablename__ = 'competition_rewards'

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    competition_id = db.Column(
        db.String,
        db.ForeignKey('competitions.id', ondelete='CASCADE'),
        nullable=False,
    )
    student_id = db.Column(
        db.String,
        db.ForeignKey('student.id', ondelete='CASCADE'),
        nullable=False,
    )
    participation_paid_at = db.Column(db.TIMESTAMP, nullable=True)
    created_at = db.Column(db.TIMESTAMP, server_default=db.text('CURRENT_TIMESTAMP'), nullable=True)
    updated_at = db.Column(db.TIMESTAMP, server_default=db.text('CURRENT_TIMESTAMP'), nullable=True)

    __table_args__ = (
        db.UniqueConstraint('competition_id', 'student_id', name='uq_competition_rewards_competition_student'),
    )

    # Relacionamentos
    competition = db.relationship('Competition', backref=db.backref('rewards', lazy='dynamic', passive_deletes=True))
    student = db.relationship('Student', backref=db.backref('competition_rewards', lazy='dynamic', passive_deletes=True))
