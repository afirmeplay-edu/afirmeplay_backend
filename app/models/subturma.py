# -*- coding: utf-8 -*-
"""Subturma ADAP dentro de uma turma regular.

O nome exibido não é coluna: deriva de support_level ("ADAP 1", "ADAP 2", "ADAP 3").
Nesta etapa a tabela fica vazia. Nenhum aluno é vinculado.
"""
import uuid
from datetime import datetime

from app import db
from sqlalchemy.dialects.postgresql import UUID


class Subturma(db.Model):
    __tablename__ = "subturma"
    __table_args__ = (
        db.UniqueConstraint("class_id", "support_level", name="uq_subturma_class_support_level"),
        db.CheckConstraint("support_level IN (1, 2, 3)", name="ck_subturma_support_level"),
        {"schema": "tenant"},
    )

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    class_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("tenant.class.id", ondelete="CASCADE"),
        nullable=False,
    )
    support_level = db.Column(db.SmallInteger, nullable=False)
    created_at = db.Column(db.TIMESTAMP, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.TIMESTAMP,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    turma = db.relationship("Class", foreign_keys=[class_id])

    @property
    def display_name(self) -> str:
        return f"ADAP {int(self.support_level)}"
