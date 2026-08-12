# -*- coding: utf-8 -*-
from app import db
import uuid
from sqlalchemy.dialects.postgresql import JSON, UUID


class ReadingFluencySession(db.Model):
    """Sessão ad-hoc de Fluência Leitora (CAEd) — sem avaliação pré-aplicada."""

    __tablename__ = "reading_fluency_session"
    __table_args__ = {"schema": "tenant"}

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id = db.Column(db.String, db.ForeignKey("tenant.student.id"), nullable=False)
    class_id = db.Column(UUID(as_uuid=True), db.ForeignKey("tenant.class.id"), nullable=True)
    school_id = db.Column(db.String(36), nullable=True)
    reading_text_id = db.Column(db.String, nullable=False)
    words_word_list_id = db.Column(db.String, nullable=True)
    uncommon_word_list_id = db.Column(db.String, nullable=True)
    caderno = db.Column(db.String(8), nullable=False, default="A")
    status = db.Column(db.String(20), nullable=False, default="em_andamento")
    fluency_data = db.Column(JSON, nullable=True)
    part_audios = db.Column(JSON, nullable=True)
    calculated_plcm = db.Column(db.Float, nullable=True)
    calculated_accuracy = db.Column(db.Float, nullable=True)
    precision_level = db.Column(db.String(30), nullable=True)
    fluency_level = db.Column(db.String(30), nullable=True)
    ica_score = db.Column(db.Float, nullable=True)
    ica_breakdown = db.Column(JSON, nullable=True)
    prosody_level = db.Column(db.Integer, nullable=True)
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

    student = db.relationship("Student", foreign_keys=[student_id])
    applier = db.relationship("User", foreign_keys=[applied_by])
    answers = db.relationship(
        "ReadingFluencyComprehensionAnswer",
        back_populates="session",
        cascade="all, delete-orphan",
    )

    def to_dict(self, include_answers=False, audio_urls=None):
        audio_urls = audio_urls or {}
        part_audios = self.part_audios if isinstance(self.part_audios, dict) else {}
        data = {
            "id": self.id,
            "studentId": self.student_id,
            "classId": str(self.class_id) if self.class_id else None,
            "schoolId": str(self.school_id) if self.school_id else None,
            "readingTextId": self.reading_text_id,
            "wordsWordListId": self.words_word_list_id,
            "uncommonWordListId": self.uncommon_word_list_id,
            "caderno": self.caderno,
            "status": self.status,
            "fluencyData": self.fluency_data,
            "partAudios": part_audios,
            "calculatedPlcm": self.calculated_plcm,
            "calculatedAccuracy": self.calculated_accuracy,
            "precisionLevel": self.precision_level,
            "fluencyLevel": self.fluency_level,
            "icaScore": self.ica_score,
            "icaBreakdown": self.ica_breakdown,
            "prosodyLevel": self.prosody_level,
            "comprehensionCorrectCount": self.comprehension_correct_count,
            "comprehensionTotal": self.comprehension_total,
            "comprehensionScore": self.comprehension_score,
            "hasAudio": bool(part_audios),
            "audioUrls": audio_urls,
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
