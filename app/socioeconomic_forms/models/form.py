# -*- coding: utf-8 -*-
"""
Modelo para armazenar questionários socioeconômicos
"""

from app import db
import uuid
from sqlalchemy.dialects.postgresql import JSON
from datetime import datetime
from enum import Enum


class FormTypeEnum(Enum):
    """Tipos de questionários socioeconômicos"""
    ALUNO_JOVEM = "aluno-jovem"
    ALUNO_VELHO = "aluno-velho"
    PROFESSOR = "professor"
    DIRETOR = "diretor"
    SECRETARIO = "secretario"


class Form(db.Model):
    """
    Modelo para armazenar questionários socioeconômicos
    """
    __tablename__ = 'forms'
    __table_args__ = {"schema": "tenant"}

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Informações básicas
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    form_type = db.Column(db.String(50), nullable=False)  # aluno-jovem, aluno-velho, professor, diretor, secretario
    instructions = db.Column(db.Text, nullable=True)
    
    # Configuração de destino
    target_groups = db.Column(JSON, nullable=False, default=list)  # ["alunos"], ["professores"], etc.
    selected_schools = db.Column(JSON, nullable=True)  # Lista de IDs de escolas
    selected_grades = db.Column(JSON, nullable=True)  # Lista de IDs de séries (apenas para aluno-jovem e aluno-velho)
    selected_classes = db.Column(JSON, nullable=True)  # Lista de IDs de turmas
    selected_tecadmin_users = db.Column(JSON, nullable=True)  # Lista de IDs de usuários TecAdmin (para secretários)
    filters = db.Column(JSON, nullable=True)  # Filtros hierárquicos: {estado, municipio, escola, serie, turma}
    
    # Status e prazos
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    deadline = db.Column(db.TIMESTAMP, nullable=True)
    
    # Metadados
    created_by = db.Column(db.String, db.ForeignKey('public.users.id'), nullable=False)
    created_at = db.Column(db.TIMESTAMP, server_default=db.func.now(), nullable=False)
    updated_at = db.Column(db.TIMESTAMP, server_default=db.func.now(), onupdate=db.func.now(), nullable=False)
    
    # Relacionamentos
    creator = db.relationship('User', foreign_keys=[created_by])
    questions = db.relationship('FormQuestion', backref='form', cascade='all, delete-orphan', order_by='FormQuestion.question_order')
    recipients = db.relationship('FormRecipient', backref='form', cascade='all, delete-orphan')
    responses = db.relationship('FormResponse', backref='form', cascade='all, delete-orphan')
    
    def to_dict(self, include_questions=False, include_statistics=False):
        """Converte o objeto para dicionário"""
        data = {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'formType': self.form_type,
            'targetGroups': self.target_groups or [],
            'selectedSchools': self.selected_schools or [],
            'selectedGrades': self.selected_grades or [],
            'selectedClasses': self.selected_classes or [],
            'selectedTecAdminUsers': self.selected_tecadmin_users or [],
            'filters': self.filters or {},
            'isActive': self.is_active,
            'deadline': self.deadline.isoformat() if self.deadline else None,
            'instructions': self.instructions,
            'createdAt': self.created_at.isoformat() if self.created_at else None,
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None,
            'createdBy': self.created_by
        }
        
        # Adicionar informações de envio se houver recipients
        if self.recipients:
            data['recipientsCount'] = len(self.recipients)
            first_sent = min([r.sent_at for r in self.recipients if r.sent_at], default=None)
            if first_sent:
                data['sentAt'] = first_sent.isoformat()
        
        if include_questions:
            data['questions'] = [q.to_dict() for q in self.questions]
            data['totalQuestions'] = len(self.questions)
        
        if include_statistics:
            total_recipients = len(self.recipients)
            completed = len([r for r in self.recipients if r.status == 'completed'])
            in_progress = len([r for r in self.recipients if r.status == 'in_progress'])
            pending = len([r for r in self.recipients if r.status == 'pending'])
            
            data['statistics'] = {
                'totalRecipients': total_recipients,
                'totalResponses': completed + in_progress,
                'completedResponses': completed,
                'partialResponses': in_progress,
                'pendingResponses': pending,
                'completionRate': round((completed / total_recipients * 100) if total_recipients > 0 else 0, 2)
            }
        
        return data
    
    def __repr__(self):
        return f'<Form {self.id}: {self.title} ({self.form_type})>'

