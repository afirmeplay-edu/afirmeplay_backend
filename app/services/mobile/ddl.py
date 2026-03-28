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
"""

