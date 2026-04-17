# -*- coding: utf-8 -*-
"""Modelo de Recompensa de Competição - controle de moedas de participação (Etapa 2)."""
from app import db
import uuid

from app.models.student import Student


class CompetitionReward(db.Model):
    __tablename__ = 'competition_rewards'

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    # Sem FK: competição pode estar em public; rewards ficam no tenant (cross-schema).
    competition_id = db.Column(db.String, nullable=False)
    student_id = db.Column(
        db.String,
        db.ForeignKey(Student.__table__.c.id, ondelete='CASCADE'),
        nullable=False,
    )
    participation_paid_at = db.Column(db.TIMESTAMP, nullable=True)
    created_at = db.Column(db.TIMESTAMP, server_default=db.text('CURRENT_TIMESTAMP'), nullable=True)
    updated_at = db.Column(db.TIMESTAMP, server_default=db.text('CURRENT_TIMESTAMP'), nullable=True)

    __table_args__ = (
        db.UniqueConstraint('competition_id', 'student_id', name='uq_competition_rewards_competition_student'),
    )

    # Relacionamentos (competition_id sem FK no banco; primaryjoin/foreign_keys para o ORM)
    competition = db.relationship(
        'Competition',
        primaryjoin='CompetitionReward.competition_id == Competition.id',
        foreign_keys=[competition_id],
        backref=db.backref('rewards', lazy='dynamic', passive_deletes=True),
    )
    student = db.relationship('Student', backref=db.backref('competition_rewards', lazy='dynamic', passive_deletes=True))
