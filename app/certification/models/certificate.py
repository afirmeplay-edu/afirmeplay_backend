# -*- coding: utf-8 -*-
"""
Modelo para certificados emitidos
"""
from app import db
import uuid
from datetime import datetime
from enum import Enum

from app.models.student import Student
from app.models.test import Test
from app.certification.models.certificate_template import CertificateTemplate

class CertificateStatusEnum(Enum):
    """Status do certificado"""
    PENDING = "pending"
    APPROVED = "approved"

class Certificate(db.Model):
    __tablename__ = 'certificates'
    __table_args__ = (
        db.UniqueConstraint('student_id', 'evaluation_id', name='uq_certificate_student_evaluation'),
        {"schema": "tenant"},
    )

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id = db.Column(db.String, db.ForeignKey(Student.__table__.c.id), nullable=False)
    student_name = db.Column(db.String(200), nullable=False)  # Cache do nome
    evaluation_id = db.Column(db.String, db.ForeignKey(Test.__table__.c.id), nullable=False)
    evaluation_title = db.Column(db.String(200), nullable=False)  # Cache do título
    grade = db.Column(db.Float, nullable=False)
    template_id = db.Column(db.String, db.ForeignKey(CertificateTemplate.__table__.c.id), nullable=False)
    issued_at = db.Column(db.TIMESTAMP, server_default=db.text('CURRENT_TIMESTAMP'))
    status = db.Column(db.String(20), nullable=False, default='pending')  # 'pending' | 'approved'
    created_at = db.Column(db.TIMESTAMP, server_default=db.text('CURRENT_TIMESTAMP'))
    
    # Relacionamentos
    student = db.relationship('Student', foreign_keys=[student_id])
    evaluation = db.relationship('Test', foreign_keys=[evaluation_id])
    template = db.relationship(
        'CertificateTemplate',
        foreign_keys=[template_id],
        back_populates='certificates',
    )

    def to_dict(self, include_template=False):
        """Converte o objeto para dicionário"""
        data = {
            'id': self.id,
            'student_id': self.student_id,
            'student_name': self.student_name,
            'evaluation_id': self.evaluation_id,
            'evaluation_title': self.evaluation_title,
            'grade': self.grade,
            'template_id': self.template_id,
            'issued_at': self.issued_at.isoformat() if self.issued_at else None,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
        
        if include_template and self.template:
            data['template'] = self.template.to_dict()
        
        return data
    
    def __repr__(self):
        return f'<Certificate {self.id}: Student {self.student_id}, Evaluation {self.evaluation_id}>'
