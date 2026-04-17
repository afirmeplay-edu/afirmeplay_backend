from app import db
from datetime import datetime
import uuid

class StudentAnswer(db.Model):
    __tablename__ = 'student_answers'
    __table_args__ = {"schema": "tenant"}

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id = db.Column(db.String, db.ForeignKey('tenant.student.id'), nullable=False)
    test_id = db.Column(db.String, db.ForeignKey('tenant.test.id'), nullable=False)
    question_id = db.Column(db.String, db.ForeignKey('public.question.id'), nullable=False)
    answer = db.Column(db.Text, nullable=False)
    answered_at = db.Column(db.TIMESTAMP, default=datetime.utcnow)
    
    # Campos para correção manual
    is_correct = db.Column(db.Boolean, nullable=True)  # Se a resposta está correta
    manual_score = db.Column(db.Float, nullable=True)  # Pontuação manual atribuída pelo professor
    feedback = db.Column(db.Text, nullable=True)  # Feedback específico da questão
    corrected_by = db.Column(db.String, db.ForeignKey('public.users.id'), nullable=True)  # Professor que corrigiu
    corrected_at = db.Column(db.TIMESTAMP, nullable=True)  # Data da correção
    
    # Relacionamentos
    # student = db.relationship('Student', backref='student_answers')  # Removido - agora definido no modelo Student
    # test = db.relationship('Test', backref='student_answers')  # Removido - agora definido no modelo Test
    # question = db.relationship('Question', backref='student_answers')  # Removido - agora definido no modelo Question
    
    def __init__(self, student_id, test_id, question_id, answer, **kwargs):
        """
        Construtor customizado para StudentAnswer
        """
        self.student_id = student_id
        self.test_id = test_id
        self.question_id = question_id
        self.answer = answer
        self.answered_at = datetime.utcnow()  # Fix: setar explicitamente (column default só aplica no INSERT)
        
        # Aplicar qualquer outro parâmetro
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value) 