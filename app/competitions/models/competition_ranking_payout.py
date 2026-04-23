# -*- coding: utf-8 -*-
"""Modelo de Pagamento de Ranking - auditoria de moedas por posição (Etapa 2)."""
from app import db
import uuid

from app.competitions.models.competition import Competition
from app.models.student import Student


class CompetitionRankingPayout(db.Model):
    __tablename__ = 'competition_ranking_payouts'

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    competition_id = db.Column(db.String, db.ForeignKey(Competition.__table__.c.id), nullable=False)
    student_id = db.Column(db.String, db.ForeignKey(Student.__table__.c.id), nullable=False)
    position = db.Column(db.Integer, nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    paid_at = db.Column(db.TIMESTAMP, nullable=False)
    created_at = db.Column(db.TIMESTAMP, server_default=db.text('CURRENT_TIMESTAMP'), nullable=True)

    __table_args__ = (
        db.UniqueConstraint('competition_id', 'student_id', name='uq_competition_ranking_payouts_competition_student'),
    )

    # Relacionamentos
    competition = db.relationship('Competition', backref=db.backref('ranking_payouts', lazy='dynamic'))
    student = db.relationship('Student', backref=db.backref('competition_ranking_payouts', lazy='dynamic'))
