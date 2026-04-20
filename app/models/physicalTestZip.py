# -*- coding: utf-8 -*-
"""
Modelo para armazenar a URL do ZIP de provas físicas (download all) por prova.
Domínio: app/physical_tests/ — não usa answer_sheet_gabaritos.
"""
from app import db
from datetime import datetime


class PhysicalTestZip(db.Model):
    """
    Uma linha por prova (test_id): minio_url, minio_object_name, minio_bucket, zip_generated_at.
    Preenchido pela task Celery após upload do all_forms.zip no MinIO.
    Usado pela rota GET download-all para devolver a URL pré-assinada.
    """
    __tablename__ = 'physical_test_zip'
    __table_args__ = {"schema": "tenant"}

    test_id = db.Column(db.String, db.ForeignKey('tenant.test.id'), primary_key=True)
    minio_url = db.Column(db.String(500), nullable=True)
    minio_object_name = db.Column(db.String(200), nullable=True)
    minio_bucket = db.Column(db.String(100), nullable=True)
    zip_generated_at = db.Column(db.DateTime, nullable=True)

    test = db.relationship('Test', backref=db.backref('physical_test_zip', uselist=False))

    def __repr__(self):
        return f'<PhysicalTestZip test_id={self.test_id}>'
