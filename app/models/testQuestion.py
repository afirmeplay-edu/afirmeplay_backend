from app import db
import uuid
from datetime import datetime

class TestQuestion(db.Model):
    __tablename__ = 'test_questions'
    
    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    test_id = db.Column(db.String, db.ForeignKey('test.id'), nullable=False)
    question_id = db.Column(db.String, db.ForeignKey('question.id'), nullable=False)
    order = db.Column(db.Integer, nullable=True)  # Para manter ordem das questões
    created_at = db.Column(db.DateTime, server_default=db.text('CURRENT_TIMESTAMP'))
    
    # Relacionamentos
    test = db.relationship('Test', back_populates='test_questions')
    question = db.relationship('Question', back_populates='test_questions')
    
    def __repr__(self):
        return f'<TestQuestion {self.test_id} - {self.question_id}>'
