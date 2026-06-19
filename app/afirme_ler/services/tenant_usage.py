# -*- coding: utf-8 -*-
"""Consultas cross-schema para uso de catálogo public em avaliações tenant."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import text

from app import db
from app.models.city import City
from app.utils.tenant_middleware import city_id_to_schema_name


def _schema_has_reading_evaluation_table(schema: str) -> bool:
    row = db.session.execute(
        text(
            """
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = :schema AND table_name = 'reading_evaluation'
            LIMIT 1
            """
        ),
        {"schema": schema},
    ).first()
    return row is not None


def count_evaluations_using_text(
    reading_text_id: str,
    *,
    city_id: Optional[str] = None,
) -> int:
    """Conta avaliações que referenciam um texto (um município ou todos)."""
    total = 0
    if city_id:
        schemas = [city_id_to_schema_name(city_id)]
    else:
        schemas = [city_id_to_schema_name(c.id) for c in City.query.all()]

    for schema in schemas:
        if schema == "public" or not _schema_has_reading_evaluation_table(schema):
            continue
        count = db.session.execute(
            text(
                f'SELECT COUNT(*) FROM "{schema}".reading_evaluation '
                "WHERE reading_text_id = :text_id"
            ),
            {"text_id": reading_text_id},
        ).scalar()
        total += int(count or 0)
    return total


def question_has_answers_in_tenant(
    reading_text_question_id: str,
    *,
    city_id: Optional[str] = None,
) -> bool:
    schemas = [city_id_to_schema_name(city_id)] if city_id else [
        city_id_to_schema_name(c.id) for c in City.query.all()
    ]
    for schema in schemas:
        if schema == "public":
            continue
        if not db.session.execute(
            text(
                """
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = :schema AND table_name = 'reading_comprehension_answer'
                LIMIT 1
                """
            ),
            {"schema": schema},
        ).first():
            continue
        found = db.session.execute(
            text(
                f'SELECT 1 FROM "{schema}".reading_comprehension_answer '
                "WHERE reading_text_question_id = :qid LIMIT 1"
            ),
            {"qid": reading_text_question_id},
        ).first()
        if found:
            return True
    return False
