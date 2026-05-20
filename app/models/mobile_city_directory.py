"""
Catálogo público de municípios para discovery no app mobile (schema public).

Independente de City / administração web: define api_base_url e metadados de exibição.
"""
from app import db
import uuid
from sqlalchemy import text


class MobileCityDirectory(db.Model):
    __tablename__ = "mobile_city_directory"
    __table_args__ = {"schema": "public"}

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    city_name = db.Column(db.String(200), nullable=False)
    city_slug = db.Column(db.String(100), nullable=False, unique=True)
    tenant_code = db.Column(db.String(32), nullable=False, unique=True)
    api_base_url = db.Column(db.String(500), nullable=False)
    hosting_mode = db.Column(db.String(20), nullable=False, default="shared")
    is_active = db.Column(db.Boolean, nullable=False, default=True, server_default=text("true"))
    mobile_visible = db.Column(
        db.Boolean, nullable=False, default=True, server_default=text("true")
    )
    sort_order = db.Column(db.Integer, nullable=False, default=0, server_default=text("0"))
    created_at = db.Column(db.TIMESTAMP, server_default=db.func.now())
    updated_at = db.Column(
        db.TIMESTAMP, server_default=db.func.now(), onupdate=db.func.now()
    )
