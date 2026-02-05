# -*- coding: utf-8 -*-
"""
Modelo para cache de resultados de formulários socioeconômicos
"""

from app import db
import uuid
import hashlib
import json
from sqlalchemy.dialects.postgresql import JSON
from datetime import datetime


class FormResultCache(db.Model):
    """
    Modelo para cache de resultados de relatórios socioeconômicos.
    Similar ao ReportAggregate, mas específico para formulários socioeconômicos.
    """
    __tablename__ = 'form_result_cache'

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Vinculação com formulário
    form_id = db.Column(db.String, db.ForeignKey('forms.id', ondelete='CASCADE'), nullable=False)
    
    # Tipo de relatório
    report_type = db.Column(db.String(50), nullable=False)  # 'indices', 'profiles'
    
    # Filtros aplicados
    filters_hash = db.Column(db.String(64), nullable=False)  # MD5 dos filtros para busca rápida
    filters = db.Column(JSON, nullable=False)  # {state, municipio, escola, serie, turma}
    
    # Resultado calculado
    result = db.Column(JSON, nullable=True)  # Resultado do relatório
    student_count = db.Column(db.Integer, default=0, nullable=False)  # Total de alunos no escopo
    
    # Status
    is_dirty = db.Column(db.Boolean, default=False, nullable=False)  # Se precisa recalcular
    
    # Timestamps
    created_at = db.Column(db.TIMESTAMP, server_default=db.func.now(), nullable=False)
    updated_at = db.Column(db.TIMESTAMP, nullable=True)
    
    __table_args__ = (
        db.UniqueConstraint('form_id', 'report_type', 'filters_hash', name='uq_form_report_filters'),
        db.Index('idx_form_result_cache_form_type', 'form_id', 'report_type'),
        db.Index('idx_form_result_cache_dirty', 'is_dirty'),
    )
    
    @staticmethod
    def generate_filters_hash(filters):
        """
        Gera hash MD5 dos filtros para identificação única.
        
        Args:
            filters: Dicionário com filtros
            
        Returns:
            str: Hash MD5 dos filtros
        """
        # Normalizar filtros: remover None e ordenar
        normalized = {k: v for k, v in sorted(filters.items()) if v is not None}
        filters_str = json.dumps(normalized, sort_keys=True)
        return hashlib.md5(filters_str.encode()).hexdigest()
    
    def mark_dirty(self):
        """Marca cache como desatualizado"""
        self.is_dirty = True
        self.updated_at = datetime.utcnow()
    
    def to_dict(self):
        """Converte objeto para dicionário"""
        return {
            'id': self.id,
            'formId': self.form_id,
            'reportType': self.report_type,
            'filters': self.filters,
            'studentCount': self.student_count,
            'isDirty': self.is_dirty,
            'createdAt': self.created_at.isoformat() if self.created_at else None,
            'updatedAt': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def __repr__(self):
        return f'<FormResultCache {self.id}: Form {self.form_id}, Type {self.report_type}, Dirty {self.is_dirty}>'
