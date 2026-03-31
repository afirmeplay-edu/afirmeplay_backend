"""
Modelos ORM para tabelas mobile (um conjunto por schema city_xxx).
Consultas devem ocorrer com search_path já definido para o tenant.
"""
from app import db
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import text


class MobileDevice(db.Model):
    __tablename__ = "mobile_device"

    id = db.Column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    device_id = db.Column(db.String(64), nullable=False, unique=True)
    user_id = db.Column(db.String, db.ForeignKey("public.users.id"), nullable=False)
    created_at = db.Column(db.TIMESTAMP, server_default=db.func.now())
    last_seen_at = db.Column(db.TIMESTAMP, server_default=db.func.now())


class MobileSyncSubmission(db.Model):
    __tablename__ = "mobile_sync_submission"

    id = db.Column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    submission_id = db.Column(UUID(as_uuid=True), nullable=False, unique=True)
    device_id = db.Column(db.String(64), nullable=False)
    user_id = db.Column(db.String, db.ForeignKey("public.users.id"), nullable=False)
    received_at = db.Column(db.TIMESTAMP, server_default=db.func.now())
    status = db.Column(db.String(20), nullable=False)


class MobileSyncBundleGeneration(db.Model):
    __tablename__ = "mobile_sync_bundle_generation"

    id = db.Column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    school_id = db.Column(db.String(36), db.ForeignKey("school.id"), nullable=False)
    sync_bundle_version = db.Column(db.BigInteger, nullable=False)
    bundle_valid_until = db.Column(db.TIMESTAMP, nullable=False)
    created_at = db.Column(db.TIMESTAMP, server_default=db.func.now())

    __table_args__ = (
        db.UniqueConstraint("school_id", "sync_bundle_version", name="uq_mobile_bundle_school_ver"),
    )
