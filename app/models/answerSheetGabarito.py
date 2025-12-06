# -*- coding: utf-8 -*-
"""
Modelo para armazenar gabaritos de cartões resposta
"""

from app import db
import uuid
from sqlalchemy.dialects.postgresql import JSON
from datetime import datetime


class AnswerSheetGabarito(db.Model):
    """
    Modelo para gerenciar gabaritos de cartões resposta
    Armazena as respostas corretas e configurações do cartão
    """
    __tablename__ = 'answer_sheet_gabaritos'

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Vinculação opcional com prova ou turma
    test_id = db.Column(db.String, db.ForeignKey('test.id'), nullable=True)
    class_id = db.Column(db.String, db.ForeignKey('class.id'), nullable=True)
    
    # Configuração do cartão
    num_questions = db.Column(db.Integer, nullable=False)
    use_blocks = db.Column(db.Boolean, default=False)
    blocks_config = db.Column(JSON, nullable=True)  # {num_blocks, questions_per_block, separate_by_subject}
    
    # Gabarito: {1: "A", 2: "B", ...}
    correct_answers = db.Column(JSON, nullable=False)
    
    # Metadados
    title = db.Column(db.String(200), nullable=True)  # Título do cartão resposta
    created_at = db.Column(db.TIMESTAMP, server_default=db.text('CURRENT_TIMESTAMP'))
    created_by = db.Column(db.String, db.ForeignKey('users.id'), nullable=True)
    
    # Relacionamentos
    test = db.relationship('Test', foreign_keys=[test_id])
    class_ = db.relationship('Class', foreign_keys=[class_id])
    creator = db.relationship('User', foreign_keys=[created_by])
