# -*- coding: utf-8 -*-
"""
"Questão" da avaliação subjetiva (SubjectiveTest): apenas a estrutura, sem conteúdo.

A prova física em papel fica fora do sistema — aqui só guardamos, por posição, o
código (livre, ex.: "Q01" ou "EF06MA01") e a habilidade que aquela questão avalia,
digitada manualmente pelo usuário (sem usar a tabela `skills`). Não há enunciado,
alternativas, gabarito estruturado nem tipo de interação — diferente de `Question`.
"""
from app import db
import uuid


class SubjectiveQuestion(db.Model):
    __tablename__ = 'subjective_questions'
    __table_args__ = (
        db.UniqueConstraint('subjective_test_id', 'number', name='uq_subjective_question_test_number'),
        {"schema": "tenant"},
    )

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    subjective_test_id = db.Column(db.String, db.ForeignKey('tenant.subjective_tests.id'), nullable=False)
    number = db.Column(db.Integer, nullable=False)  # posição da questão (Q1, Q2, ...)
    code = db.Column(db.String(50))  # ex.: "Q01" ou código de habilidade "EF06MA01"
    skill_description = db.Column(db.String(500), nullable=False)  # habilidade digitada manualmente
    created_at = db.Column(db.TIMESTAMP, server_default=db.text('CURRENT_TIMESTAMP'))

    def __init__(self, subjective_test_id, number, skill_description, code=None, **kwargs):
        self.subjective_test_id = subjective_test_id
        self.number = number
        self.skill_description = skill_description
        self.code = code
        for key, val in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, val)

    def to_dict(self):
        return {
            'id': self.id,
            'subjective_test_id': self.subjective_test_id,
            'number': self.number,
            'code': self.code,
            'skill_description': self.skill_description,
        }

    def __repr__(self):
        return f'<SubjectiveQuestion {self.id}: Q{self.number} ({self.code}) - {self.skill_description}>'
