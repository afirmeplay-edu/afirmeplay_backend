"""
Índice global (schema public): code_hash -> município + id do pacote no schema city_*.
Permite resgatar o código no mobile sem informar X-City-ID (apenas o código + device).
"""
from app import db
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import text


class MobileOfflinePackRegistry(db.Model):
    __tablename__ = "mobile_offline_pack_registry"
    __table_args__ = {"schema": "public"}

    code_hash = db.Column(db.String(128), primary_key=True)
    city_id = db.Column(db.String, db.ForeignKey("public.city.id"), nullable=False)
    pack_id = db.Column(UUID(as_uuid=True), nullable=False)
    created_at = db.Column(db.TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))
