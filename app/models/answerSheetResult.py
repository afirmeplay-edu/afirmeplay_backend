# -*- coding: utf-8 -*-
"""
Modelo para armazenar resultados de correção de cartões resposta
Independente do sistema de provas (Test, StudentAnswer, EvaluationResult)
"""

from app import db
import uuid
from sqlalchemy.dialects.postgresql import JSON
from datetime import datetime


class AnswerSheetResult(db.Model):
    """
    Modelo para armazenar resultados de correção de cartões resposta
    Cada registro representa a correção de um cartão resposta de um aluno
    """
    __tablename__ = 'answer_sheet_results'

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Vinculação com gabarito e aluno
    gabarito_id = db.Column(db.String, db.ForeignKey('answer_sheet_gabaritos.id'), nullable=False)
    student_id = db.Column(db.String, db.ForeignKey('student.id'), nullable=False)
    
    # Respostas detectadas do aluno: {1: "A", 2: "B", 3: null, ...}
    detected_answers = db.Column(JSON, nullable=False)
    
    # Estatísticas de correção
    correct_answers = db.Column(db.Integer, nullable=False)  # Quantidade de acertos
    total_questions = db.Column(db.Integer, nullable=False)  # Total de questões
    incorrect_answers = db.Column(db.Integer, nullable=False)  # Quantidade de erros
    unanswered_questions = db.Column(db.Integer, nullable=False)  # Não respondidas
    answered_questions = db.Column(db.Integer, nullable=False)  # Total respondidas
    
    # Nota e classificação
    score_percentage = db.Column(db.Float, nullable=False)  # 0-100
    grade = db.Column(db.Float, nullable=False)  # Nota 0-10
    proficiency = db.Column(db.Float, nullable=True)  # Proficiência média geral (média das disciplinas)
    classification = db.Column(db.String(50), nullable=True)  # "Avançado", "Proficiente", "Básico", etc.
    # Proficiência por disciplina: { subject_id: { subject_name, proficiency, classification, correct_answers, total_questions } }
    proficiency_by_subject = db.Column(JSON, nullable=True)
    
    # Metadados
    corrected_at = db.Column(db.TIMESTAMP, default=datetime.utcnow)
    detection_method = db.Column(db.String(20), default='geometric')  # 'geometric' ou 'ia'
    
    # Relacionamentos
    gabarito = db.relationship('AnswerSheetGabarito', backref='results')
    student = db.relationship('Student', backref='answer_sheet_results')
    
    def to_dict(self):
        """Converte o objeto para dicionário"""
        return {
            'id': self.id,
            'gabarito_id': self.gabarito_id,
            'student_id': self.student_id,
            'detected_answers': self.detected_answers,
            'correct_answers': self.correct_answers,
            'total_questions': self.total_questions,
            'incorrect_answers': self.incorrect_answers,
            'unanswered_questions': self.unanswered_questions,
            'answered_questions': self.answered_questions,
            'score_percentage': self.score_percentage,
            'grade': self.grade,
            'proficiency': self.proficiency,
            'classification': self.classification,
            'proficiency_by_subject': self.proficiency_by_subject,
            'corrected_at': self.corrected_at.isoformat() if self.corrected_at else None,
            'detection_method': self.detection_method
        }
    
    def __repr__(self):
        return f'<AnswerSheetResult {self.id}: Gabarito {self.gabarito_id}, Student {self.student_id}>'

