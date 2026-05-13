# -*- coding: utf-8 -*-
"""Histórico de vínculo aluno–escola–turma (matrícula); valid_to nulo = vigente."""
import uuid
from datetime import datetime

from app import db
from sqlalchemy.dialects.postgresql import UUID as PGUUID


class StudentSchoolEnrollment(db.Model):
    __tablename__ = "student_school_enrollment"
    __table_args__ = {"schema": "tenant"}

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id = db.Column(db.String, db.ForeignKey("tenant.student.id", ondelete="CASCADE"), nullable=False)
    school_id = db.Column(db.String(36), db.ForeignKey("tenant.school.id"), nullable=True)
    class_id = db.Column(PGUUID(as_uuid=True), db.ForeignKey("tenant.class.id"), nullable=True)
    valid_from = db.Column(db.TIMESTAMP, nullable=False, default=datetime.utcnow)
    valid_to = db.Column(db.TIMESTAMP, nullable=True)
    created_at = db.Column(db.TIMESTAMP, nullable=False, server_default=db.func.now())

    student = db.relationship("Student", backref=db.backref("school_enrollments", lazy="dynamic"))
