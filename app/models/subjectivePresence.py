# -*- coding: utf-8 -*-
"""
Presença do aluno numa avaliação subjetiva (ver app.models.subjectiveTest).

Independente da rubrica lançada por questão: um aluno ausente não deve ser
contado no cálculo de nota/proficiência da turma (ver SubjectiveEvaluationService).
"""
from app import db
from datetime import datetime
import uuid


class SubjectivePresence(db.Model):
    __tablename__ = 'subjective_presences'
    __table_args__ = (
        db.UniqueConstraint('subjective_test_id', 'student_id', name='uq_subjective_presence_test_student'),
        {"schema": "tenant"},
    )

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    subjective_test_id = db.Column(db.String, db.ForeignKey('tenant.subjective_tests.id'), nullable=False)
    student_id = db.Column(db.String, db.ForeignKey('tenant.student.id'), nullable=False)
    present = db.Column(db.Boolean, nullable=False, default=True)
    updated_by = db.Column(db.String, db.ForeignKey('public.users.id'), nullable=True)
    updated_at = db.Column(db.TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __init__(self, subjective_test_id, student_id, present=True, updated_by=None, **kwargs):
        self.subjective_test_id = subjective_test_id
        self.student_id = student_id
        self.present = present
        self.updated_by = updated_by
        self.updated_at = datetime.utcnow()
        for key, val in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, val)

    def to_dict(self):
        return {
            'id': self.id,
            'subjective_test_id': self.subjective_test_id,
            'student_id': self.student_id,
            'present': self.present,
            'updated_by': self.updated_by,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f'<SubjectivePresence {self.id}: Test {self.subjective_test_id}, Student {self.student_id} = {self.present}>'
