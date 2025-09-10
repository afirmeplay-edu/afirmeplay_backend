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
    test_id = db.Column(db.String(36), db.ForeignKey('test.id'), nullable=False)
    qr_code_id = db.Column(db.String(36), nullable=False, unique=True)
    student_id = db.Column(db.String(36), db.ForeignKey('student.id'), nullable=False)
    coordinates = db.Column(db.JSON, nullable=False)  # Coordenadas mapeadas
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'test_id': self.test_id,
            'qr_code_id': self.qr_code_id,
            'student_id': self.student_id,
            'coordinates': self.coordinates,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def __repr__(self):
        return f'<FormCoordinates {self.id}: {self.test_id} - {self.student_id}>'
