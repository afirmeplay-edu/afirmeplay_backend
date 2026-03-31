"""
Cria public.mobile_offline_pack_registry (índice code_hash -> city_id, pack_id).

Idempotente: CREATE TABLE IF NOT EXISTS.

Uso (raiz do repositório):
    python scripts/create_mobile_offline_pack_registry.py

Requer DATABASE_URL / app/.env via create_app.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db  # noqa: E402


DDL = """
CREATE TABLE IF NOT EXISTS public.mobile_offline_pack_registry (
    code_hash VARCHAR(128) NOT NULL PRIMARY KEY,
    city_id VARCHAR NOT NULL REFERENCES public.city(id),
    pack_id UUID NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE public.mobile_offline_pack_registry IS
    'Mapeia hash do código offline para município e UUID do registro em city_*.mobile_offline_pack_code';
CREATE INDEX IF NOT EXISTS idx_mobile_offline_pack_registry_city
    ON public.mobile_offline_pack_registry(city_id);
"""


def main():
    app = create_app()
    with app.app_context():
        raw = db.engine.raw_connection()
        try:
            raw.set_isolation_level(0)
            cur = raw.cursor()
            cur.execute(DDL)
            print("OK: public.mobile_offline_pack_registry")
        finally:
            raw.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
