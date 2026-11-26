#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Aplica soft delete (student.is_active) e student_name_snapshot em todos os city_*."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    from app import create_app, db
    from app.services.city_schema_service import ensure_student_soft_delete_and_name_snapshot
    from sqlalchemy import text

    app = create_app()
    with app.app_context():
        rows = db.session.execute(
            text(
                "SELECT schema_name FROM information_schema.schemata "
                "WHERE schema_name LIKE 'city_%' ORDER BY 1"
            )
        ).fetchall()
        schemas = [r[0] for r in rows]
        print(f"Schemas encontrados: {len(schemas)}")
        if not schemas:
            print("Nenhum schema city_* encontrado.")
            return 0

        for schema in schemas:
            print(f"Applying soft-delete + name snapshot on {schema}...")
            ensure_student_soft_delete_and_name_snapshot(schema)
            # Backfill não destrutivo do nome histórico.
            db.session.execute(
                text(
                    f"""
                    UPDATE "{schema}".evaluation_results er
                    SET student_name_snapshot = s.name
                    FROM "{schema}".student s
                    WHERE er.student_id = s.id
                      AND er.student_name_snapshot IS NULL
                      AND s.name IS NOT NULL
                    """
                )
            )
            db.session.execute(
                text(
                    f"""
                    UPDATE "{schema}".answer_sheet_results ar
                    SET student_name_snapshot = s.name
                    FROM "{schema}".student s
                    WHERE ar.student_id = s.id
                      AND ar.student_name_snapshot IS NULL
                      AND s.name IS NOT NULL
                    """
                )
            )
            db.session.commit()
            print(f"  OK {schema}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
