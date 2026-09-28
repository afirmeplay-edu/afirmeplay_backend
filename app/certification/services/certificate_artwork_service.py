from __future__ import annotations

import os
import uuid
from typing import Optional

from app import db
from app.certification.models import CertificateArtwork
from app.models.test import Test
from app.services.storage.minio_service import MinIOService
from .certificate_file_normalizer import normalize_upload


class CertificateArtworkService:
    bucket = MinIOService.BUCKETS['CERTIFICATE_TEMPLATES']

    @staticmethod
    def _require_evaluation(evaluation_id: str) -> Test:
        evaluation = Test.query.get(evaluation_id)
        if not evaluation:
            raise ValueError('Avaliação não encontrada')
        return evaluation

    @classmethod
    def list_for_evaluation(cls, evaluation_id: str):
        cls._require_evaluation(evaluation_id)
        return CertificateArtwork.query.filter_by(evaluation_id=evaluation_id).order_by(
            CertificateArtwork.created_at.desc()
        ).all()

    @classmethod
    def get(cls, evaluation_id: str, artwork_id: str) -> CertificateArtwork:
        cls._require_evaluation(evaluation_id)
        artwork = CertificateArtwork.query.filter_by(id=artwork_id, evaluation_id=evaluation_id).first()
        if not artwork:
            raise ValueError('Modelo de certificado não encontrado')
        return artwork

    @classmethod
    def create_from_upload(cls, evaluation_id: str, file_storage, name: Optional[str], created_by: Optional[str]):
        evaluation = cls._require_evaluation(evaluation_id)
        if not file_storage or not getattr(file_storage, 'filename', None):
            raise ValueError('Arquivo do modelo é obrigatório')
        data = file_storage.read()
        filename = os.path.basename(file_storage.filename or 'certificado')
        normalized = normalize_upload(filename, data)
        artwork_id = str(uuid.uuid4())
        ext = {'pdf': 'pdf', 'jpeg': 'jpg', 'png': 'png'}[normalized['source_kind']]
        original_object = f'{evaluation.id}/artworks/{artwork_id}/original.{ext}'
        normalized_object = f'{evaluation.id}/artworks/{artwork_id}/normalized.pdf'
        minio = MinIOService()
        if not minio.upload_file(cls.bucket, original_object, data, normalized['mime_type']):
            raise ValueError('Falha ao armazenar o modelo original')
        if not minio.upload_file(cls.bucket, normalized_object, normalized['normalized_pdf'], 'application/pdf'):
            minio.delete_file(cls.bucket, original_object)
            raise ValueError('Falha ao armazenar o modelo normalizado')
        artwork = CertificateArtwork(
            id=artwork_id,
            evaluation_id=evaluation.id,
            name=(name or '').strip() or filename,
            status='draft',
            original_filename=filename,
            mime_type=normalized['mime_type'],
            source_kind=normalized['source_kind'],
            minio_bucket=cls.bucket,
            minio_object_name=original_object,
            normalized_object_name=normalized_object,
            page_count=normalized['page_count'],
            page_width_pt=normalized['page_width_pt'],
            page_height_pt=normalized['page_height_pt'],
            rotation=normalized['rotation'],
            fields={'fields': []},
            created_by=created_by,
        )
        db.session.add(artwork)
        db.session.commit()
        return artwork

    @classmethod
    def activate(cls, evaluation_id: str, artwork_id: str):
        artwork = cls.get(evaluation_id, artwork_id)
        CertificateArtwork.query.filter(
            CertificateArtwork.evaluation_id == evaluation_id,
            CertificateArtwork.id != artwork_id,
        ).update({'status': 'inactive'}, synchronize_session=False)
        artwork.status = 'active'
        db.session.commit()
        return artwork

    @classmethod
    def delete(cls, evaluation_id: str, artwork_id: str):
        artwork = cls.get(evaluation_id, artwork_id)
        minio = MinIOService()
        for object_name in (artwork.minio_object_name, artwork.normalized_object_name):
            if object_name:
                minio.delete_file(artwork.minio_bucket, object_name)
        db.session.delete(artwork)
        db.session.commit()

    @classmethod
    def load_original(cls, artwork: CertificateArtwork):
        data = MinIOService().download_file(artwork.minio_bucket, artwork.minio_object_name)
        return data, artwork.mime_type
