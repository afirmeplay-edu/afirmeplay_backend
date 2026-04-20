# -*- coding: utf-8 -*-
"""Modelo de Resultado de Competição - snapshot ao finalizar (Etapa 2)."""
from app import db
import uuid

from app.models.student import Student
from app.models.testSession import TestSession


class CompetitionResult(db.Model):
    __tablename__ = 'competition_results'

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    # Sem FK: competição pode estar em public; results ficam no tenant (cross-schema).
    competition_id = db.Column(db.String, nullable=False)
    student_id = db.Column(
        db.String,
        db.ForeignKey(Student.__table__.c.id, ondelete='CASCADE'),
        nullable=False,
    )
    session_id = db.Column(
        db.String,
        db.ForeignKey(TestSession.__table__.c.id, ondelete='CASCADE'),
        nullable=False,
    )
    correct_answers = db.Column(db.Integer, nullable=False)
    total_questions = db.Column(db.Integer, nullable=False)
    score_percentage = db.Column(db.Float, nullable=False)
    grade = db.Column(db.Float, nullable=False)
    proficiency = db.Column(db.Float, nullable=True)
    classification = db.Column(db.String, nullable=True)
    posicao = db.Column(db.Integer, nullable=False)
    moedas_ganhas = db.Column(db.Integer, nullable=False, default=0)
    tempo_gasto = db.Column(db.Integer, nullable=True)
    acertos = db.Column(db.Integer, nullable=False)
    erros = db.Column(db.Integer, nullable=False)
    em_branco = db.Column(db.Integer, nullable=False)
    calculated_at = db.Column(db.TIMESTAMP, nullable=False)

    __table_args__ = (
        db.UniqueConstraint('competition_id', 'student_id', name='uq_competition_results_competition_student'),
    )

    # Relacionamentos (competition_id sem FK no banco; primaryjoin/foreign_keys para o ORM)
    competition = db.relationship(
        'Competition',
        primaryjoin='CompetitionResult.competition_id == Competition.id',
        foreign_keys=[competition_id],
        backref=db.backref('results', lazy='dynamic', passive_deletes=True),
    )
    student = db.relationship('Student', backref=db.backref('competition_results', lazy='dynamic', passive_deletes=True))
    test_session = db.relationship('TestSession', backref=db.backref('competition_results', lazy='dynamic', passive_deletes=True))
