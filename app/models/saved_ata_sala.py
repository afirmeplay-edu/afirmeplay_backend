from datetime import datetime
import uuid

from app import db


class SavedAtaSala(db.Model):
    __tablename__ = "saved_ata_sala"
    __table_args__ = {"schema": "tenant"}

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String, db.ForeignKey("public.users.id"), nullable=False)
    created_by_name = db.Column(db.String(255), nullable=False)
    city_id = db.Column(db.String, nullable=False)
    school_id = db.Column(db.String(36), db.ForeignKey("tenant.school.id"), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    modo_lista = db.Column(db.String(30), nullable=False)
    filters = db.Column(db.JSON, nullable=False)
    content = db.Column(db.JSON, nullable=False)
    created_at = db.Column(db.TIMESTAMP, server_default=db.text("CURRENT_TIMESTAMP"))
    updated_at = db.Column(
        db.TIMESTAMP,
        server_default=db.text("CURRENT_TIMESTAMP"),
        onupdate=db.text("CURRENT_TIMESTAMP"),
    )

    author = db.relationship("User", foreign_keys=[user_id])
    school = db.relationship("School", foreign_keys=[school_id])
