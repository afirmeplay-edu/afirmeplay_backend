"""
Modelos ORM para tabelas mobile (um conjunto por schema city_xxx).
Consultas devem ocorrer com search_path já definido para o tenant.
"""
from app import db
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy import text


class MobileDevice(db.Model):
    __tablename__ = "mobile_device"
    __table_args__ = {"schema": "tenant"}

    id = db.Column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    device_id = db.Column(db.String(64), nullable=False, unique=True)
    user_id = db.Column(db.String, db.ForeignKey("public.users.id"), nullable=False)
    created_at = db.Column(db.TIMESTAMP, server_default=db.func.now())
    last_seen_at = db.Column(db.TIMESTAMP, server_default=db.func.now())


class MobileSyncSubmission(db.Model):
    __tablename__ = "mobile_sync_submission"
    __table_args__ = {"schema": "tenant"}

    id = db.Column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    submission_id = db.Column(UUID(as_uuid=True), nullable=False, unique=True)
    device_id = db.Column(db.String(64), nullable=False)
    user_id = db.Column(db.String, db.ForeignKey("public.users.id"), nullable=False)
    received_at = db.Column(db.TIMESTAMP, server_default=db.func.now())
    status = db.Column(db.String(20), nullable=False)


class MobileSyncBundleGeneration(db.Model):
    __tablename__ = "mobile_sync_bundle_generation"
    __table_args__ = (
        db.UniqueConstraint("school_id", "sync_bundle_version", name="uq_mobile_bundle_school_ver"),
        {"schema": "tenant"},
    )

    id = db.Column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    school_id = db.Column(db.String(36), db.ForeignKey("tenant.school.id"), nullable=False)
    sync_bundle_version = db.Column(db.BigInteger, nullable=False)
    bundle_valid_until = db.Column(db.TIMESTAMP, nullable=False)
    created_at = db.Column(db.TIMESTAMP, server_default=db.func.now())

class MobileOfflinePackCode(db.Model):
    __tablename__ = "mobile_offline_pack_code"
    __table_args__ = {"schema": "tenant"}

    id = db.Column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    code_hash = db.Column(db.String(128), nullable=False, unique=True)
    scope_json = db.Column(JSONB, nullable=False)
    created_by_user_id = db.Column(db.String, db.ForeignKey("public.users.id"), nullable=True)
    expires_at = db.Column(db.TIMESTAMP, nullable=False)
    max_redemptions = db.Column(db.Integer, nullable=False)
    revoked_at = db.Column(db.TIMESTAMP, nullable=True)
    created_at = db.Column(db.TIMESTAMP, server_default=db.func.now())


class MobileOfflinePackRedeemDevice(db.Model):
    __tablename__ = "mobile_offline_pack_redeem_device"
    __table_args__ = (
        db.UniqueConstraint("pack_id", "device_id", name="uq_mobile_offline_pack_device"),
        {"schema": "tenant"},
    )

    id = db.Column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    pack_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("tenant.mobile_offline_pack_code.id", ondelete="CASCADE"),
        nullable=False,
    )
    device_id = db.Column(db.String(64), nullable=False)
    first_redeem_at = db.Column(db.TIMESTAMP, server_default=db.func.now())

