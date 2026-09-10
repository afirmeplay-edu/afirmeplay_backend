# -*- coding: utf-8 -*-
"""
Grupo de critérios (marcações) de uma avaliação subjetiva.

Uma avaliação pode ter vários grupos (ex.: alfabetização vs. interpretação),
cada um com suas marcações. Cada questão aponta para um grupo via
`subjective_questions.rubric_group_id`.
"""
from app import db
import uuid


class SubjectiveRubricGroup(db.Model):
    __tablename__ = 'subjective_rubric_groups'
    __table_args__ = (
        {"schema": "tenant"},
    )

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    subjective_test_id = db.Column(db.String, db.ForeignKey('tenant.subjective_tests.id'), nullable=False)
    name = db.Column(db.String(120), nullable=False, default='Grupo de critérios')
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.TIMESTAMP, server_default=db.text('CURRENT_TIMESTAMP'))

    marks = db.relationship(
        'SubjectiveRubricMark',
        backref='rubric_group',
        lazy='joined',
        cascade='all, delete-orphan',
        order_by='SubjectiveRubricMark.sort_order',
    )

    def __init__(self, subjective_test_id, name='Grupo de critérios', sort_order=0, **kwargs):
        self.subjective_test_id = subjective_test_id
        self.name = name
        self.sort_order = sort_order
        for key, val in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, val)

    def to_dict(self, include_marks=True):
        payload = {
            'id': self.id,
            'subjective_test_id': self.subjective_test_id,
            'name': self.name,
            'sort_order': self.sort_order,
        }
        if include_marks:
            marks = sorted(self.marks or [], key=lambda m: (m.sort_order, m.code or ''))
            payload['marks'] = [m.to_dict() for m in marks]
        return payload

    def __repr__(self):
        return f'<SubjectiveRubricGroup {self.name} test={self.subjective_test_id}>'
