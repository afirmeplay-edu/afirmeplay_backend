from app import db
from app.models.test import Test
import uuid


class CertificateArtwork(db.Model):
    __tablename__ = 'certificate_artworks'
    __table_args__ = (
        db.Index('idx_certificate_artworks_evaluation_status', 'evaluation_id', 'status'),
        {'schema': 'tenant'},
    )

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    evaluation_id = db.Column(db.String, db.ForeignKey(Test.__table__.c.id), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='draft')
    original_filename = db.Column(db.String(255), nullable=False)
    mime_type = db.Column(db.String(100), nullable=False)
    source_kind = db.Column(db.String(20), nullable=False)
    minio_bucket = db.Column(db.String(100), nullable=False)
    minio_object_name = db.Column(db.String(500), nullable=False)
    normalized_object_name = db.Column(db.String(500), nullable=True)
    page_count = db.Column(db.Integer, nullable=False, default=1)
    page_width_pt = db.Column(db.Float, nullable=False)
    page_height_pt = db.Column(db.Float, nullable=False)
    rotation = db.Column(db.Integer, nullable=False, default=0)
    fields = db.Column(db.JSON, nullable=False, default=lambda: {'fields': []})
    version = db.Column(db.Integer, nullable=False, default=1)
    created_by = db.Column(db.String, nullable=True)
    created_at = db.Column(db.TIMESTAMP, server_default=db.text('CURRENT_TIMESTAMP'))
    updated_at = db.Column(db.TIMESTAMP, server_default=db.text('CURRENT_TIMESTAMP'), onupdate=db.text('CURRENT_TIMESTAMP'))

    evaluation = db.relationship('Test', foreign_keys=[evaluation_id])

    def to_dict(self):
        return {
            'id': self.id,
            'evaluation_id': self.evaluation_id,
            'name': self.name,
            'status': self.status,
            'original_filename': self.original_filename,
            'mime_type': self.mime_type,
            'source_kind': self.source_kind,
            'page_count': self.page_count,
            'page_width_pt': self.page_width_pt,
            'page_height_pt': self.page_height_pt,
            'rotation': self.rotation,
            'fields': self.fields or {'fields': []},
            'version': self.version,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
