from app import db
from datetime import datetime
import uuid

class StudentAnswer(db.Model):
    __tablename__ = 'student_answers'
    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id = db.Column(db.String, db.ForeignKey('student.id'), nullable=False)
    test_id = db.Column(db.String, db.ForeignKey('test.id'), nullable=False)
    question_id = db.Column(db.String, db.ForeignKey('question.id'), nullable=False)
    answer = db.Column(db.Text, nullable=False)
    answered_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __init__(self, student_id, test_id, question_id, answer, **kwargs):
        """
        Construtor customizado para StudentAnswer
        """
        self.student_id = student_id
        self.test_id = test_id
        self.question_id = question_id
        self.answer = answer
        
        # Aplicar qualquer outro parâmetro
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value) 