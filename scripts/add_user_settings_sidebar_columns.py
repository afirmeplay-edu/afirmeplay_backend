#!/usr/bin/env python3
"""
Adiciona as colunas sidebar_theme_id, frame_id e stamp_id na tabela user_settings
se ainda não existirem. Use quando a migração Alembic não puder ser aplicada
ou para corrigir o banco rapidamente.

Uso (na raiz do projeto, com o mesmo Python do backend):
  python scripts/add_user_settings_sidebar_columns.py
"""
import sys
import os

# Garantir que o app está no path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app import create_app, db

SQL_ADD_COLUMNS = [
    "ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS sidebar_theme_id VARCHAR(128);",
    "ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS frame_id VARCHAR(128);",
    "ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS stamp_id VARCHAR(128);",
]


def main():
    app = create_app()
    with app.app_context():
        for sql in SQL_ADD_COLUMNS:
            db.session.execute(text(sql))
        db.session.commit()
        print("Colunas sidebar_theme_id, frame_id e stamp_id adicionadas/verificadas em user_settings.")


if __name__ == "__main__":
    main()
