# -*- coding: utf-8 -*-
from app import db
import uuid
from sqlalchemy.dialects.postgresql import JSON, UUID


class ReadingEvaluationSession(db.Model):
    __tablename__ = "reading_evaluation_session"
    __table_args__ = {"schema": "tenant"}

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    reading_evaluation_id = db.Column(
        db.String,
        db.ForeignKey("tenant.reading_evaluation.id", ondelete="CASCADE"),
        nullable=False,
    )
    student_id = db.Column(db.String, db.ForeignKey("tenant.student.id"), nullable=False)
    class_id = db.Column(UUID(as_uuid=True), db.ForeignKey("tenant.class.id"), nullable=True)
    status = db.Column(db.String(20), nullable=False, default="pendente")
    fluency_data = db.Column(JSON, nullable=True)
    comprehension_correct_count = db.Column(db.Integer, nullable=True)
    comprehension_total = db.Column(db.Integer, nullable=True)
    comprehension_score = db.Column(db.Float, nullable=True)
    started_at = db.Column(db.TIMESTAMP, nullable=True)
    submitted_at = db.Column(db.TIMESTAMP, nullable=True)
    applied_by = db.Column(db.String, db.ForeignKey("public.users.id"), nullable=True)
    created_at = db.Column(db.TIMESTAMP, server_default=db.text("CURRENT_TIMESTAMP"))
    updated_at = db.Column(
        db.TIMESTAMP,
        server_default=db.text("CURRENT_TIMESTAMP"),
        onupdate=db.text("CURRENT_TIMESTAMP"),
    )

    evaluation = db.relationship("ReadingEvaluation", back_populates="sessions")
    student = db.relationship("Student", foreign_keys=[student_id])
    applier = db.relationship("User", foreign_keys=[applied_by])
    answers = db.relationship(
        "ReadingComprehensionAnswer",
        back_populates="session",
        cascade="all, delete-orphan",
    )

    def to_dict(self, include_answers=False):
        data = {
            "id": self.id,
            "readingEvaluationId": self.reading_evaluation_id,
            "studentId": self.student_id,
            "classId": str(self.class_id) if self.class_id else None,
            "status": self.status,
            "fluencyData": self.fluency_data,
            "comprehensionCorrectCount": self.comprehension_correct_count,
            "comprehensionTotal": self.comprehension_total,
            "comprehensionScore": self.comprehension_score,
            "startedAt": self.started_at.isoformat() if self.started_at else None,
            "submittedAt": self.submitted_at.isoformat() if self.submitted_at else None,
            "appliedBy": self.applied_by,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }
        if self.student:
            data["studentName"] = self.student.name
        if include_answers:
            data["answers"] = [answer.to_dict() for answer in (self.answers or [])]
        return data
