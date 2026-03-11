# -*- coding: utf-8 -*-
"""Modelo de Inscrição em Competição (Etapa 2)."""
from app import db
import uuid


class CompetitionEnrollment(db.Model):
    __tablename__ = 'competition_enrollments'

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    # Sem FK: competição pode estar em public; enrollment fica no tenant (cross-schema).
    competition_id = db.Column(db.String, nullable=False)
    student_id = db.Column(
        db.String,
        db.ForeignKey('student.id', ondelete='CASCADE'),
        nullable=False,
    )
    enrolled_at = db.Column(
        db.TIMESTAMP,
        server_default=db.text('CURRENT_TIMESTAMP'),
        nullable=False,
    )
    status = db.Column(db.String, nullable=False, default='inscrito')  # inscrito, cancelado

    __table_args__ = (
        db.UniqueConstraint('competition_id', 'student_id', name='uq_competition_enrollments_competition_student'),
    )

    # Relacionamentos (competition_id sem FK no banco; primaryjoin/foreign_keys para o ORM)
    competition = db.relationship(
        'Competition',
        primaryjoin='CompetitionEnrollment.competition_id == Competition.id',
        foreign_keys=[competition_id],
        backref=db.backref('enrollments', lazy='dynamic', passive_deletes=True),
    )
    student = db.relationship('Student', backref=db.backref('competition_enrollments', lazy='dynamic', passive_deletes=True))
