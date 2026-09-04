# -*- coding: utf-8 -*-
"""
Modelo para jobs de geração de cartões resposta (tabela em public).
Persistido para que todas as instâncias da API e Celery vejam o mesmo estado.
"""

from app import db
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime


class AnswerSheetGenerationJob(db.Model):
    """
    Job de geração de cartões resposta. Tabela em public para multi-instância.
    """
    __tablename__ = 'answer_sheet_generation_jobs'
    __table_args__ = {'schema': 'public'}

    job_id = db.Column(db.String(36), primary_key=True)
    city_id = db.Column(db.String(36), nullable=False, index=True)
    gabarito_id = db.Column(db.String(36), nullable=False, index=True)
    user_id = db.Column(db.String(36), nullable=False)
    task_ids = db.Column(JSONB, nullable=True)  # lista de IDs das tasks Celery
    total = db.Column(db.Integer, nullable=False)
    completed = db.Column(db.Integer, default=0, nullable=False)
    successful = db.Column(db.Integer, default=0, nullable=False)
    failed = db.Column(db.Integer, default=0, nullable=False)
    status = db.Column(db.String(20), default='processing', nullable=False)
    progress_current = db.Column(db.Integer, default=0, nullable=False)
    progress_percentage = db.Column(db.Integer, default=0, nullable=False)
    scope_type = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    completed_at = db.Column(db.DateTime, nullable=True)
    total_students_generated = db.Column(db.Integer, nullable=True)
    classes_generated = db.Column(db.Integer, nullable=True)

    def to_dict(self):
        """Converte para o formato esperado por get_job / progress_store."""
        return {
            'job_id': self.job_id,
            'total': self.total,
            'completed': self.completed,
            'successful': self.successful,
            'failed': self.failed,
            'status': self.status,
            'test_id': None,
            'gabarito_id': self.gabarito_id,
            'user_id': self.user_id,
            'task_ids': self.task_ids or [],
            'warnings': [],
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'items': {},
            'results': [],
            'progress_current': self.progress_current,
            'progress_percentage': self.progress_percentage,
            'scope_type': self.scope_type,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'total_students_generated': self.total_students_generated,
            'classes_generated': self.classes_generated,
        }
