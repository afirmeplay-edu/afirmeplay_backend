from app import db
import uuid
from datetime import datetime

class PhysicalTestAnswer(db.Model):
    """
    Modelo para armazenar respostas de formulários físicos
    Cada resposta marcada pelo aluno em um formulário físico
    """
    __tablename__ = 'physical_test_answers'
    __table_args__ = {"schema": "tenant"}

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    physical_form_id = db.Column(db.String, db.ForeignKey('tenant.physical_test_forms.id'), nullable=False)
    question_id = db.Column(db.String, db.ForeignKey('public.question.id'), nullable=False)
    
    # Resposta marcada pelo aluno
    marked_answer = db.Column(db.String, nullable=True)  # A, B, C, D, E ou null se não marcada
    correct_answer = db.Column(db.String, nullable=False)  # Resposta correta da questão
    
    # Resultado da correção
    is_correct = db.Column(db.Boolean, nullable=True)  # True se correta, False se incorreta, None se não respondida
    confidence_score = db.Column(db.Float, nullable=True)  # Confiança da detecção (0-100%)
    
    # Coordenadas da marcação detectada
    detection_coordinates = db.Column(db.JSON, nullable=True)  # Coordenadas da marcação detectada
    
    # Metadados
    detected_at = db.Column(db.DateTime, default=datetime.utcnow)
    corrected_at = db.Column(db.DateTime, nullable=True)
    
    # Relacionamentos
    question = db.relationship('Question', backref='physical_answers')
    
    def __repr__(self):
        return f'<PhysicalTestAnswer {self.id}: Question {self.question_id}, Answer {self.marked_answer}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'physical_form_id': self.physical_form_id,
            'question_id': self.question_id,
            'marked_answer': self.marked_answer,
            'correct_answer': self.correct_answer,
            'is_correct': self.is_correct,
            'confidence_score': self.confidence_score,
            'detection_coordinates': self.detection_coordinates,
            'detected_at': self.detected_at.isoformat() if self.detected_at else None,
            'corrected_at': self.corrected_at.isoformat() if self.corrected_at else None
        }
