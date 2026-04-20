# -*- coding: utf-8 -*-
"""
Modelo para templates de certificados
"""
from app import db
from app.services.storage.minio_service import MinIOService
from app.models.test import Test
import uuid
from datetime import datetime
from typing import Optional


def _certificate_asset_proxy_path_if_minio(raw_url: Optional[str], evaluation_id: str, kind: str):
    if not raw_url:
        return None
    marker = f"{MinIOService.BUCKETS['CERTIFICATE_TEMPLATES']}/"
    if marker in raw_url:
        return f"/certificates/template/{evaluation_id}/{kind}"
    return raw_url


class CertificateTemplate(db.Model):
    __tablename__ = 'certificate_templates'

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    evaluation_id = db.Column(db.String, db.ForeignKey(Test.__table__.c.id), nullable=False)
    title = db.Column(db.String(255), nullable=True)
    text_content = db.Column(db.Text, nullable=False)  # Suporta {{nome_aluno}}
    background_color = db.Column(db.String(7), nullable=False)  # Hex color
    text_color = db.Column(db.String(7), nullable=False)  # Hex color
    accent_color = db.Column(db.String(7), nullable=False)  # Hex color
    logo_url = db.Column(db.String(500), nullable=True)
    signature_url = db.Column(db.String(500), nullable=True)
    custom_date = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.TIMESTAMP, server_default=db.text('CURRENT_TIMESTAMP'))
    updated_at = db.Column(db.TIMESTAMP, server_default=db.text('CURRENT_TIMESTAMP'), onupdate=db.text('CURRENT_TIMESTAMP'))
    
    # Relacionamentos
    evaluation = db.relationship('Test', foreign_keys=[evaluation_id])
    # back_populates: Certificate já define `template`; não usar backref='template' (conflito de nome).
    certificates = db.relationship(
        'Certificate',
        back_populates='template',
        cascade='all, delete-orphan',
    )

    __table_args__ = (
        db.UniqueConstraint('evaluation_id', name='uq_certificate_template_evaluation'),
        {'schema': 'tenant'},
    )
    
    def to_dict(self):
        """Converte o objeto para dicionário"""
        return {
            'id': self.id,
            'evaluation_id': self.evaluation_id,
            'title': self.title,
            'text_content': self.text_content,
            'background_color': self.background_color,
            'text_color': self.text_color,
            'accent_color': self.accent_color,
            'logo_url': _certificate_asset_proxy_path_if_minio(
                self.logo_url, self.evaluation_id, 'logo'
            ),
            'signature_url': _certificate_asset_proxy_path_if_minio(
                self.signature_url, self.evaluation_id, 'signature'
            ),
            'custom_date': self.custom_date,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    def __repr__(self):
        return f'<CertificateTemplate {self.id}: Evaluation {self.evaluation_id}>'
