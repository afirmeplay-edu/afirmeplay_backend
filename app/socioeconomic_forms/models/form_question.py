# -*- coding: utf-8 -*-
"""
Modelo para armazenar questões de questionários socioeconômicos
"""

from app import db
import uuid
from sqlalchemy.dialects.postgresql import JSON
from datetime import datetime


class FormQuestion(db.Model):
    """
    Modelo para armazenar questões de questionários socioeconômicos
    """
    __tablename__ = 'form_questions'

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Vinculação com formulário
    form_id = db.Column(db.String, db.ForeignKey('forms.id', ondelete='CASCADE'), nullable=False)
    
    # Identificação da questão
    question_id = db.Column(db.String(50), nullable=False)  # ID único da questão (ex: "q1", "q5a")
    
    # Conteúdo da questão
    text = db.Column(db.Text, nullable=False)
    type = db.Column(db.String(50), nullable=False)  # selecao_unica, multipla_escolha, matriz_selecao, etc.
    
    # Opções e configurações
    options = db.Column(JSON, nullable=True)  # Lista de opções para seleção
    sub_questions = db.Column(JSON, nullable=True)  # Subperguntas para multipla_escolha e matriz_selecao
    min_value = db.Column(db.Integer, nullable=True)  # Para slider
    max_value = db.Column(db.Integer, nullable=True)  # Para slider
    option_id = db.Column(db.String(50), nullable=True)  # Para slider_com_opcao
    option_text = db.Column(db.String(255), nullable=True)  # Para slider_com_opcao
    
    # Validação e ordem
    required = db.Column(db.Boolean, default=False, nullable=False)
    question_order = db.Column(db.Integer, nullable=False)
    depends_on = db.Column(JSON, nullable=True)  # Dependências de outras questões
    
    def to_dict(self):
        """Converte o objeto para dicionário"""
        data = {
            'id': self.question_id,
            'text': self.text,
            'type': self.type,
            'required': self.required,
            'order': self.question_order
        }
        
        if self.options:
            data['options'] = self.options
        
        if self.sub_questions:
            data['subQuestions'] = self.sub_questions
        
        if self.min_value is not None:
            data['min'] = self.min_value
        
        if self.max_value is not None:
            data['max'] = self.max_value
        
        if self.option_id:
            data['optionId'] = self.option_id
        
        if self.option_text:
            data['optionText'] = self.option_text
        
        if self.depends_on:
            data['dependsOn'] = self.depends_on
        
        return data
    
    def __repr__(self):
        return f'<FormQuestion {self.question_id}: {self.text[:50]}...>'

