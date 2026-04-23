# -*- coding: utf-8 -*-
from app import db
from datetime import datetime
import uuid
from sqlalchemy.dialects.postgresql import JSONB

from app.models.testSession import TestSession

class EvaluationResult(db.Model):
    __tablename__ = 'evaluation_results'
    __table_args__ = {"schema": "tenant"}

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    test_id = db.Column(db.String, db.ForeignKey('tenant.test.id'), nullable=False)
    student_id = db.Column(db.String, db.ForeignKey('tenant.student.id'), nullable=False)
    # Sessões municipais ficam em `tenant.test_sessions` (traduzido para `city_*` via schema_translate_map).
    # Usar referência direta à coluna do model evita NoReferencedTableError no metadata.
    session_id = db.Column(db.String, db.ForeignKey(TestSession.__table__.c.id), nullable=False)
    
    # Dados de cálculo gerais
    correct_answers = db.Column(db.Integer, nullable=False)
    total_questions = db.Column(db.Integer, nullable=False)
    score_percentage = db.Column(db.Float, nullable=False)
    grade = db.Column(db.Float, nullable=False)
    proficiency = db.Column(db.Float, nullable=False)
    classification = db.Column(db.String(50), nullable=False)
    
    # Resultados por disciplina (JSONB para evitar nova tabela)
    # Formato: {"subject_id": {"grade": 2.5, "proficiency": 250.0, "classification": "Básico", ...}}
    subject_results = db.Column(JSONB, nullable=True)
    
    # Metadados
    calculated_at = db.Column(db.TIMESTAMP, default=datetime.utcnow)
    
    # Relacionamentos
    test = db.relationship('Test', backref='evaluation_results')
    student = db.relationship('Student', backref='evaluation_results')
    # Tabela em tenant.*; test_sessions está em public.* — o ORM não infere o join só pela FK.
    session = db.relationship(
        TestSession,
        foreign_keys=[session_id],
        primaryjoin=session_id == TestSession.id,
        backref='evaluation_results',
    )
    
    def __init__(self, test_id, student_id, session_id, correct_answers, total_questions, 
                 score_percentage, grade, proficiency, classification, **kwargs):
        """
        Construtor customizado para EvaluationResult
        """
        self.test_id = test_id
        self.student_id = student_id
        self.session_id = session_id
        self.correct_answers = correct_answers
        self.total_questions = total_questions
        self.score_percentage = score_percentage
        self.grade = grade
        self.proficiency = proficiency
        self.classification = classification
        
        # Aplicar qualquer outro parâmetro
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
    
    def to_dict(self):
        """Converte o objeto para dicionário"""
        return {
            'id': self.id,
            'test_id': self.test_id,
            'student_id': self.student_id,
            'session_id': self.session_id,
            'correct_answers': self.correct_answers,
            'total_questions': self.total_questions,
            'score_percentage': self.score_percentage,
            'grade': self.grade,
            'proficiency': self.proficiency,
            'classification': self.classification,
            'subject_results': self.subject_results,
            'calculated_at': self.calculated_at.isoformat() if self.calculated_at else None
        }
    
    def __repr__(self):
        return f'<EvaluationResult {self.id}: Test {self.test_id}, Student {self.student_id}>' 