# -*- coding: utf-8 -*-
"""
Marcação configurável da rubrica de uma avaliação subjetiva.

Substitui o enum fixo SIM/PARCIAL/NAO/BRANCO: cada avaliação tem N marcações
com rótulo, sigla, cor e peso. O lançamento em subjective_results.value guarda
o `code` (sigla) da marcação.
"""
from app import db
import uuid

# Template inicial (avaliações novas e migração das já existentes).
# Peso 1.0 = acerto pleno do item; 0.5 = meio acerto; 0 = não demonstra.
DEFAULT_RUBRIC_MARKS = (
    {"code": "SIM", "label": "Sim", "color": "#22c55e", "weight": 1.0, "sort_order": 0},
    {"code": "PARCIAL", "label": "Parcial", "color": "#eab308", "weight": 0.5, "sort_order": 1},
    {"code": "NAO", "label": "Não", "color": "#ef4444", "weight": 0.0, "sort_order": 2},
    {"code": "BRANCO", "label": "Branco", "color": "#94a3b8", "weight": 0.0, "sort_order": 3},
)


class SubjectiveRubricMark(db.Model):
    __tablename__ = 'subjective_rubric_marks'
    __table_args__ = (
        db.UniqueConstraint('subjective_test_id', 'code', name='uq_subjective_rubric_mark_test_code'),
        {"schema": "tenant"},
    )

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    subjective_test_id = db.Column(db.String, db.ForeignKey('tenant.subjective_tests.id'), nullable=False)
    code = db.Column(db.String(20), nullable=False)
    label = db.Column(db.String(80), nullable=False)
    color = db.Column(db.String(20), nullable=False, default='#64748b')
    weight = db.Column(db.Float, nullable=False, default=0.0)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.TIMESTAMP, server_default=db.text('CURRENT_TIMESTAMP'))

    def __init__(self, subjective_test_id, code, label, color='#64748b', weight=0.0, sort_order=0, **kwargs):
        self.subjective_test_id = subjective_test_id
        self.code = code
        self.label = label
        self.color = color
        self.weight = weight
        self.sort_order = sort_order
        for key, val in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, val)

    def to_dict(self):
        return {
            'id': self.id,
            'subjective_test_id': self.subjective_test_id,
            'code': self.code,
            'label': self.label,
            'color': self.color,
            'weight': self.weight,
            'sort_order': self.sort_order,
        }

    def __repr__(self):
        return f'<SubjectiveRubricMark {self.code} w={self.weight} test={self.subjective_test_id}>'
