 # -*- coding: utf-8 -*-
"""
Modelo para armazenar coordenadas dos formulários de resposta
"""
from app import db
from datetime import datetime
import uuid

class FormCoordinates(db.Model):
    __tablename__ = 'form_coordinates'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    test_id = db.Column(db.String(36), db.ForeignKey('tenant.test.id'), nullable=False)
    form_type = db.Column(db.String(50), nullable=False, default='physical_test')  # NOVO: tipo do formulário
    qr_code_id = db.Column(db.String(36), nullable=True)  # OPCIONAL: para formulários específicos de aluno
    student_id = db.Column(db.String(36), db.ForeignKey('tenant.student.id'), nullable=True)  # OPCIONAL: para formulários específicos de aluno
    coordinates = db.Column(db.JSON, nullable=False)  # Coordenadas mapeadas
    num_questions = db.Column(db.Integer, nullable=True)  # Número de questões no formulário
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # NOVO: Índice único para test_id + form_type (um template por prova)
    __table_args__ = (
        db.UniqueConstraint('test_id', 'form_type', name='unique_test_form_type'),
        {"schema": "tenant"},
    )
    
    def to_dict(self):
        return {
            'id': self.id,
            'test_id': self.test_id,
            'form_type': self.form_type,
            'qr_code_id': self.qr_code_id,
            'student_id': self.student_id,
            'coordinates': self.coordinates,
            'num_questions': self.num_questions,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def __repr__(self):
        return f'<FormCoordinates {self.id}: {self.test_id} - {self.form_type}>'
