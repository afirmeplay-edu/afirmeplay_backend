"""
Cria índice em student_password_log.user_id em todos os schemas `city_*`.

Motivação:
- O DELETE por user_id pode varrer tabela grande sem índice e parecer "travado".
- Esse índice também reduz contenção/tempo de locks durante limpezas.

Uso:
  (venv) python scripts/add_student_password_log_user_id_index_all_schemas.py
"""

from __future__ import annotations

import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text


def main() -> None:
    # Carregar env do projeto (mantém consistência com app/config.py)
    load_dotenv("app/.env")

    url = os.getenv("DATABASE_URL")
    if not url:
        raise SystemExit("DATABASE_URL não definido")

    engine = create_engine(url, isolation_level="AUTOCOMMIT", pool_pre_ping=True)

    with engine.connect() as conn:
        schemas = conn.execute(
            text(
                """
                SELECT nspname
                FROM pg_namespace
                WHERE nspname LIKE 'city\\_%'
                ORDER BY nspname
                """
            )
        ).fetchall()

        for (schema,) in schemas:
            # Índice parcial (user_id não-nulo) reduz tamanho e foca no caso real.
            conn.execute(
                text(
                    f"""
                    CREATE INDEX IF NOT EXISTS {schema}_idx_student_password_log_user_id_not_null
                    ON "{schema}".student_password_log (user_id)
                    WHERE user_id IS NOT NULL
                    """
                )
            )

    print("OK: índices criados/confirmados em todos os schemas city_*")


if __name__ == "__main__":
    main()

