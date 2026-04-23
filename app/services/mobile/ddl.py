"""
DDL das tabelas mobile por schema de município (city_xxx).
Usado em provision_city_schema, scripts/create_mobile_tables.py e testes.
Não usar schema public.
"""


def get_mobile_tables_ddl(schema: str) -> str:
    if not schema.replace("_", "").isalnum() or not schema.startswith("city_"):
        raise ValueError(f"Schema inválido: {schema}")
    return f"""
CREATE TABLE IF NOT EXISTS "{schema}".mobile_device (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    device_id VARCHAR(64) NOT NULL,
    user_id VARCHAR NOT NULL REFERENCES public.users(id),
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_seen_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_mobile_device_device_id UNIQUE (device_id)
);
CREATE INDEX IF NOT EXISTS idx_mobile_device_user_id ON "{schema}".mobile_device(user_id);

CREATE TABLE IF NOT EXISTS "{schema}".mobile_sync_submission (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    submission_id UUID NOT NULL,
    device_id VARCHAR(64) NOT NULL,
    user_id VARCHAR NOT NULL REFERENCES public.users(id),
    received_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20) NOT NULL,
    CONSTRAINT uq_mobile_sync_submission_id UNIQUE (submission_id)
);
CREATE INDEX IF NOT EXISTS idx_mobile_sync_submission_user ON "{schema}".mobile_sync_submission(user_id);

CREATE TABLE IF NOT EXISTS "{schema}".mobile_sync_bundle_generation (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    school_id VARCHAR(36) NOT NULL REFERENCES "{schema}".school(id),
    sync_bundle_version BIGINT NOT NULL,
    bundle_valid_until TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_mobile_bundle_school_ver UNIQUE (school_id, sync_bundle_version)
);
CREATE INDEX IF NOT EXISTS idx_mobile_bundle_school ON "{schema}".mobile_sync_bundle_generation(school_id);

CREATE TABLE IF NOT EXISTS "{schema}".mobile_offline_pack_code (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    code_hash VARCHAR(128) NOT NULL,
    scope_json JSONB NOT NULL,
    created_by_user_id VARCHAR REFERENCES public.users(id),
    expires_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    max_redemptions INTEGER NOT NULL DEFAULT 50,
    revoked_at TIMESTAMP WITHOUT TIME ZONE,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_mobile_offline_pack_code_hash UNIQUE (code_hash)
);
COMMENT ON TABLE "{schema}".mobile_offline_pack_code IS 'Códigos de ativação para download de pacote offline (escopo no JSON)';
CREATE INDEX IF NOT EXISTS idx_mobile_offline_pack_expires ON "{schema}".mobile_offline_pack_code(expires_at);
CREATE INDEX IF NOT EXISTS idx_mobile_offline_pack_created_by ON "{schema}".mobile_offline_pack_code(created_by_user_id);

CREATE TABLE IF NOT EXISTS "{schema}".mobile_offline_pack_redeem_device (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    pack_id UUID NOT NULL REFERENCES "{schema}".mobile_offline_pack_code(id) ON DELETE CASCADE,
    device_id VARCHAR(64) NOT NULL,
    first_redeem_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_mobile_offline_pack_device UNIQUE (pack_id, device_id)
);
COMMENT ON TABLE "{schema}".mobile_offline_pack_redeem_device IS 'Dispositivos que já resgataram um código (limite max_redemptions)';
CREATE INDEX IF NOT EXISTS idx_mobile_offline_pack_redeem_pack ON "{schema}".mobile_offline_pack_redeem_device(pack_id);
"""

