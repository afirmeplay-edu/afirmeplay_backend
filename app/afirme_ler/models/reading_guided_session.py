# -*- coding: utf-8 -*-
from app import db
import uuid
from sqlalchemy.dialects.postgresql import UUID


class ReadingGuidedSession(db.Model):
    __tablename__ = "reading_guided_session"
    __table_args__ = {"schema": "tenant"}

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id = db.Column(db.String, db.ForeignKey("tenant.student.id"), nullable=False)
    class_id = db.Column(UUID(as_uuid=True), db.ForeignKey("tenant.class.id"), nullable=True)
    reading_text_id = db.Column(db.String, nullable=False)
    words_read = db.Column(db.Integer, nullable=False)
    reading_time_seconds = db.Column(db.Integer, nullable=False)
    errors_count = db.Column(db.Integer, nullable=False, default=0)
    prosody_level = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="finalizada")
    calculated_plcm = db.Column(db.Float, nullable=True)
    calculated_accuracy = db.Column(db.Float, nullable=True)
    comprehension_correct_count = db.Column(db.Integer, nullable=True)
    comprehension_total = db.Column(db.Integer, nullable=True)
    comprehension_score = db.Column(db.Float, nullable=True)
    audio_bucket = db.Column(db.String(100), nullable=True)
    audio_key = db.Column(db.Text, nullable=True)
    audio_mime_type = db.Column(db.String(100), nullable=True)
    audio_size_bytes = db.Column(db.Integer, nullable=True)
    applied_by = db.Column(db.String, db.ForeignKey("public.users.id"), nullable=True)
    submitted_at = db.Column(db.TIMESTAMP, nullable=True)
    created_at = db.Column(db.TIMESTAMP, server_default=db.text("CURRENT_TIMESTAMP"))
    updated_at = db.Column(
        db.TIMESTAMP,
        server_default=db.text("CURRENT_TIMESTAMP"),
        onupdate=db.text("CURRENT_TIMESTAMP"),
    )

    student = db.relationship("Student", foreign_keys=[student_id])
    applier = db.relationship("User", foreign_keys=[applied_by])
    answers = db.relationship(
        "ReadingGuidedComprehensionAnswer",
        back_populates="session",
        cascade="all, delete-orphan",
    )

    def to_dict(self, include_answers=False, audio_url=None):
        data = {
            "id": self.id,
            "studentId": self.student_id,
            "classId": str(self.class_id) if self.class_id else None,
            "readingTextId": self.reading_text_id,
            "wordsRead": self.words_read,
            "readingTimeSeconds": self.reading_time_seconds,
            "errorsCount": self.errors_count,
            "prosodyLevel": self.prosody_level,
            "status": self.status,
            "calculatedPlcm": self.calculated_plcm,
            "calculatedAccuracy": self.calculated_accuracy,
            "comprehensionCorrectCount": self.comprehension_correct_count,
            "comprehensionTotal": self.comprehension_total,
            "comprehensionScore": self.comprehension_score,
            "audioUrl": audio_url,
            "audioMimeType": self.audio_mime_type,
            "audioSizeBytes": self.audio_size_bytes,
            "hasAudio": bool(self.audio_key),
            "appliedBy": self.applied_by,
            "submittedAt": self.submitted_at.isoformat() if self.submitted_at else None,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }
        if self.student:
            data["studentName"] = self.student.name
        if include_answers:
            data["answers"] = [answer.to_dict() for answer in (self.answers or [])]
        return data
