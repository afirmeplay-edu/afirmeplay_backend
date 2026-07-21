# -*- coding: utf-8 -*-
"""
Rubrica de correção manual da avaliação subjetiva (ver app.models.subjectiveTest).

Não existe resposta online do aluno nesse fluxo: o professor aplica a avaliação
(impressa/presencial) e lança o resultado diretamente aqui, célula por célula
(aluno x questão), usando a rubrica SIM / PARCIAL / NAO / BRANCO.
"""
from app import db
from datetime import datetime
import uuid

# SIM: habilidade plenamente demonstrada. PARCIAL: parcialmente demonstrada.
# NAO: não demonstrada. BRANCO: questão não respondida pelo aluno (presente na prova).
RUBRIC_VALUES = ('SIM', 'PARCIAL', 'NAO', 'BRANCO')

RUBRIC_WEIGHTS = {
    'SIM': 1.0,
    'PARCIAL': 0.5,
    'NAO': 0.0,
    'BRANCO': 0.0,
}


class SubjectiveResult(db.Model):
    __tablename__ = 'subjective_results'
    __table_args__ = (
        db.UniqueConstraint(
            'subjective_test_id', 'subjective_question_id', 'student_id',
            name='uq_subjective_result_test_question_student',
        ),
        {"schema": "tenant"},
    )

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    subjective_test_id = db.Column(db.String, db.ForeignKey('tenant.subjective_tests.id'), nullable=False)
    subjective_question_id = db.Column(db.String, db.ForeignKey('tenant.subjective_questions.id'), nullable=False)
    student_id = db.Column(db.String, db.ForeignKey('tenant.student.id'), nullable=False)
    value = db.Column(db.String(10), nullable=False)  # SIM, PARCIAL, NAO, BRANCO
    corrected_by = db.Column(db.String, db.ForeignKey('public.users.id'), nullable=True)
    corrected_at = db.Column(db.TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __init__(self, subjective_test_id, subjective_question_id, student_id, value, corrected_by=None, **kwargs):
        self.subjective_test_id = subjective_test_id
        self.subjective_question_id = subjective_question_id
        self.student_id = student_id
        self.value = value
        self.corrected_by = corrected_by
        self.corrected_at = datetime.utcnow()
        for key, val in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, val)

    def to_dict(self):
        return {
            'id': self.id,
            'subjective_test_id': self.subjective_test_id,
            'subjective_question_id': self.subjective_question_id,
            'student_id': self.student_id,
            'value': self.value,
            'corrected_by': self.corrected_by,
            'corrected_at': self.corrected_at.isoformat() if self.corrected_at else None,
        }

    def __repr__(self):
        return (
            f'<SubjectiveResult {self.id}: Test {self.subjective_test_id}, '
            f'Question {self.subjective_question_id}, Student {self.student_id} = {self.value}>'
        )
