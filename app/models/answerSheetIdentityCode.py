# -*- coding: utf-8 -*-
"""Token OMR do ID-Grid (6 hex) associado 1:1:1 a aluno + gabarito/prova."""

from app import db
import uuid
from datetime import datetime


class AnswerSheetIdentityCode(db.Model):
    """
    Código impresso nas 24 bolhas do ID-Grid.

    Espelha a identidade do QR: student_id + (gabarito_id XOR test_id).
    Reimpressão reutiliza o mesmo code.
    """

    __tablename__ = "answer_sheet_identity_codes"
    __table_args__ = {"schema": "tenant"}

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    code = db.Column(db.String(6), nullable=False, unique=True, index=True)
    kind = db.Column(db.String(1), nullable=False)  # '1' gabarito | '2' prova
    student_id = db.Column(
        db.String, db.ForeignKey("tenant.student.id"), nullable=False, index=True
    )
    gabarito_id = db.Column(
        db.String,
        db.ForeignKey("tenant.answer_sheet_gabaritos.id"),
        nullable=True,
        index=True,
    )
    test_id = db.Column(
        db.String, db.ForeignKey("tenant.test.id"), nullable=True, index=True
    )
    created_at = db.Column(db.TIMESTAMP, default=datetime.utcnow)

    student = db.relationship("Student", foreign_keys=[student_id])
    gabarito = db.relationship("AnswerSheetGabarito", foreign_keys=[gabarito_id])
    test = db.relationship("Test", foreign_keys=[test_id])

    def to_identity_dict(self):
        return {
            "kind": self.kind,
            "student_id": self.student_id,
            "gabarito_id": self.gabarito_id,
            "test_id": self.test_id,
            "raw": self.code,
            "source": "token",
        }

    def __repr__(self):
        sid = (self.student_id or "")[:8]
        return f"<AnswerSheetIdentityCode {self.code} kind={self.kind} student={sid}>"
