# -*- coding: utf-8 -*-
"""Template de capa de prova física, associado a uma avaliação (tenant.test)."""
from app import db
import uuid
from sqlalchemy import Index, text
from sqlalchemy.dialects.postgresql import JSON


COVER_TEMPLATE_STATUSES = ("draft", "active", "inactive")


class CoverTemplate(db.Model):
    __tablename__ = "cover_templates"

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    test_id = db.Column(
        db.String,
        db.ForeignKey("tenant.test.id", ondelete="CASCADE"),
        nullable=False,
    )
    name = db.Column(db.String(200), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="draft")

    original_filename = db.Column(db.String(255), nullable=True)
    mime_type = db.Column(db.String(100), nullable=False)
    source_kind = db.Column(db.String(20), nullable=False)  # pdf | jpeg | png
    minio_bucket = db.Column(db.String(100), nullable=False)
    minio_object_name = db.Column(db.String(500), nullable=False)
    normalized_object_name = db.Column(db.String(500), nullable=True)

    page_count = db.Column(db.Integer, nullable=False, default=1)
    page_width_pt = db.Column(db.Float, nullable=False)
    page_height_pt = db.Column(db.Float, nullable=False)
    rotation = db.Column(db.Integer, nullable=False, default=0)

    fields = db.Column(JSON, nullable=False, default=lambda: {"fields": []})
    version = db.Column(db.Integer, nullable=False, default=1)

    created_by = db.Column(db.String, db.ForeignKey("public.users.id"), nullable=True)
    created_at = db.Column(db.TIMESTAMP, server_default=db.text("CURRENT_TIMESTAMP"))
    updated_at = db.Column(
        db.TIMESTAMP,
        server_default=db.text("CURRENT_TIMESTAMP"),
        onupdate=db.text("CURRENT_TIMESTAMP"),
    )

    test = db.relationship("Test", backref="cover_templates")
    creator = db.relationship("User", foreign_keys=[created_by])

    __table_args__ = (
        Index("ix_cover_templates_test_id", "test_id"),
        Index(
            "uq_cover_templates_one_active_per_test",
            "test_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
        {"schema": "tenant"},
    )

    def to_dict(self):
        return {
            "id": self.id,
            "test_id": self.test_id,
            "evaluation_id": self.test_id,
            "name": self.name,
            "status": self.status,
            "original_filename": self.original_filename,
            "mime_type": self.mime_type,
            "source_kind": self.source_kind,
            "minio_bucket": self.minio_bucket,
            "minio_object_name": self.minio_object_name,
            "normalized_object_name": self.normalized_object_name,
            "page_count": self.page_count,
            "page_width_pt": self.page_width_pt,
            "page_height_pt": self.page_height_pt,
            "page_width_mm": round(self.page_width_pt * 25.4 / 72.0, 3) if self.page_width_pt else None,
            "page_height_mm": round(self.page_height_pt * 25.4 / 72.0, 3) if self.page_height_pt else None,
            "rotation": self.rotation,
            "fields": self.fields or {"fields": []},
            "version": self.version,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f"<CoverTemplate {self.id}: test={self.test_id} status={self.status}>"
