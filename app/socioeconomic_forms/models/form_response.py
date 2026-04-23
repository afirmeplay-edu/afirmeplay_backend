# -*- coding: utf-8 -*-
"""
Modelo para armazenar respostas de questionários socioeconômicos
"""

from app import db
import uuid
from sqlalchemy.dialects.postgresql import JSON
from datetime import datetime

from .form import Form
from .form_recipient import FormRecipient


class FormResponse(db.Model):
    """
    Modelo para armazenar respostas de questionários socioeconômicos
    Cada registro representa as respostas de um usuário a um questionário
    """
    __tablename__ = 'form_responses'
    __table_args__ = (
        db.UniqueConstraint('form_id', 'user_id', name='unique_form_user_response'),
        {"schema": "tenant"},
    )

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Vinculação com formulário, usuário e destinatário
    form_id = db.Column(db.String, db.ForeignKey(Form.__table__.c.id, ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.String, db.ForeignKey('public.users.id', ondelete='CASCADE'), nullable=False)
    recipient_id = db.Column(db.String, db.ForeignKey(FormRecipient.__table__.c.id, ondelete='CASCADE'), nullable=False)
    
    # Respostas e status
    status = db.Column(db.String(20), default='in_progress', nullable=False)  # in_progress, completed
    responses = db.Column(JSON, nullable=False)  # Dicionário com as respostas: {"q1": "valor", "q2": "valor"}
    progress = db.Column(db.Numeric(5, 2), default=0.00, nullable=False)  # Percentual de conclusão (0-100)
    
    # Timestamps
    started_at = db.Column(db.TIMESTAMP, server_default=db.func.now(), nullable=False)
    updated_at = db.Column(db.TIMESTAMP, server_default=db.func.now(), onupdate=db.func.now(), nullable=False)
    completed_at = db.Column(db.TIMESTAMP, nullable=True)
    time_spent = db.Column(db.Integer, default=0, nullable=False)  # Tempo gasto em segundos
    
    # Relacionamentos
    user = db.relationship('User', foreign_keys=[user_id])
    
    def to_dict(self, include_responses=True):
        """Converte o objeto para dicionário"""
        data = {
            'id': self.id,
            'formId': self.form_id,
            'userId': self.user_id,
            'status': self.status,
            'progress': float(self.progress),
            'startedAt': self.started_at.isoformat() if self.started_at else None,
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None,
            'completedAt': self.completed_at.isoformat() if self.completed_at else None,
            'timeSpent': self.time_spent
        }
        
        if include_responses:
            data['responses'] = self.responses or {}
        
        return data
    
    def __repr__(self):
        return f'<FormResponse {self.id}: Form {self.form_id}, User {self.user_id}, Status {self.status}>'

