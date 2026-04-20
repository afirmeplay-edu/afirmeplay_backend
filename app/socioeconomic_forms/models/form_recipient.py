# -*- coding: utf-8 -*-
"""
Modelo para armazenar destinatários de questionários socioeconômicos
"""

from app import db
import uuid
from datetime import datetime

from app.models.school import School
from .form import Form


class FormRecipient(db.Model):
    """
    Modelo para armazenar destinatários de questionários socioeconômicos
    Cada registro representa um usuário que recebeu o questionário
    """
    __tablename__ = 'form_recipients'

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Vinculação com formulário e usuário
    form_id = db.Column(db.String, db.ForeignKey(Form.__table__.c.id, ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.String, db.ForeignKey('public.users.id', ondelete='CASCADE'), nullable=False)
    # ✅ CORRIGIDO: Explicitamente String(36) para garantir tipo correto
    school_id = db.Column(db.String(36), db.ForeignKey(School.__table__.c.id, ondelete='SET NULL'), nullable=True)
    
    # Status da resposta
    status = db.Column(db.String(20), default='pending', nullable=False)  # pending, in_progress, completed
    
    # Timestamps
    sent_at = db.Column(db.TIMESTAMP, server_default=db.func.now(), nullable=False)
    started_at = db.Column(db.TIMESTAMP, nullable=True)
    completed_at = db.Column(db.TIMESTAMP, nullable=True)
    
    # Relacionamentos
    user = db.relationship('User', foreign_keys=[user_id])
    school = db.relationship('School', foreign_keys=[school_id])
    response = db.relationship('FormResponse', backref='recipient', uselist=False, cascade='all, delete-orphan')
    
    __table_args__ = (
        db.UniqueConstraint('form_id', 'user_id', name='unique_form_user_recipient'),
        {"schema": "tenant"},
    )
    
    def to_dict(self, include_user_details=False):
        """Converte o objeto para dicionário"""
        data = {
            'id': self.id,
            'userId': self.user_id,
            'schoolId': self.school_id,
            'status': self.status,
            'sentAt': self.sent_at.isoformat() if self.sent_at else None,
            'startedAt': self.started_at.isoformat() if self.started_at else None,
            'completedAt': self.completed_at.isoformat() if self.completed_at else None
        }
        
        if include_user_details and self.user:
            data['userName'] = self.user.name
            data['userEmail'] = self.user.email
        
        if include_user_details and self.school:
            data['schoolName'] = self.school.name
        
        return data
    
    def __repr__(self):
        return f'<FormRecipient {self.id}: Form {self.form_id}, User {self.user_id}, Status {self.status}>'

