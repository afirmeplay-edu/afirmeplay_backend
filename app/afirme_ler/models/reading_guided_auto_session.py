# -*- coding: utf-8 -*-
from app import db
import uuid
from sqlalchemy.dialects.postgresql import JSON, UUID


class ReadingGuidedAutoSession(db.Model):
    __tablename__ = "reading_guided_auto_session"
    __table_args__ = {"schema": "tenant"}

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id = db.Column(db.String, db.ForeignKey("tenant.student.id"), nullable=False)
    class_id = db.Column(UUID(as_uuid=True), db.ForeignKey("tenant.class.id"), nullable=True)
    reading_text_id = db.Column(db.String, nullable=True)
    words_word_list_id = db.Column(db.String, nullable=True)
    uncommon_word_list_id = db.Column(db.String, nullable=True)
    expected_payload = db.Column(JSON, nullable=False, default=dict)
    part_results = db.Column(JSON, nullable=True)
    ica_breakdown = db.Column(JSON, nullable=True)
    status = db.Column(db.String(30), nullable=False, default="awaiting_audio")
    words_read = db.Column(db.Integer, nullable=True)
    errors_count = db.Column(db.Integer, nullable=True)
    omitted_count = db.Column(db.Integer, nullable=True)
    extra_count = db.Column(db.Integer, nullable=True)
    duration_seconds = db.Column(db.Float, nullable=True)
    calculated_plcm = db.Column(db.Float, nullable=True)
    calculated_accuracy = db.Column(db.Float, nullable=True)
    precision_level = db.Column(db.String(30), nullable=True)
    fluency_level = db.Column(db.String(30), nullable=True)
    comprehension_correct_count = db.Column(db.Integer, nullable=True)
    comprehension_total = db.Column(db.Integer, nullable=True)
    comprehension_score = db.Column(db.Float, nullable=True)
    ica_score = db.Column(db.Float, nullable=True)
    transcript_raw = db.Column(db.Text, nullable=True)
    stt_provider = db.Column(db.String(50), nullable=True)
    stt_model = db.Column(db.String(100), nullable=True)
    algorithm_version = db.Column(db.String(20), nullable=True)
    evaluation_version = db.Column(db.String(20), nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    audio_bucket = db.Column(db.String(100), nullable=True)
    audio_key = db.Column(db.Text, nullable=True)
    audio_mime_type = db.Column(db.String(100), nullable=True)
    audio_size_bytes = db.Column(db.Integer, nullable=True)
    part_audios = db.Column(JSON, nullable=True)
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
        "ReadingGuidedAutoComprehensionAnswer",
        back_populates="session",
        cascade="all, delete-orphan",
    )
    words = db.relationship(
        "ReadingGuidedAutoWord",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ReadingGuidedAutoWord.position",
    )

    def to_dict(self, include_answers=False, include_words=False, audio_url=None):
        data = {
            "id": self.id,
            "studentId": self.student_id,
            "classId": str(self.class_id) if self.class_id else None,
            "readingTextId": self.reading_text_id,
            "wordsWordListId": self.words_word_list_id,
            "uncommonWordListId": self.uncommon_word_list_id,
            "status": self.status,
            "wordsRead": self.words_read,
            "errorsCount": self.errors_count,
            "omittedCount": self.omitted_count,
            "extraCount": self.extra_count,
            "durationSeconds": self.duration_seconds,
            "calculatedPlcm": self.calculated_plcm,
            "calculatedAccuracy": self.calculated_accuracy,
            "precisionLevel": self.precision_level,
            "fluencyLevel": self.fluency_level,
            "comprehensionCorrectCount": self.comprehension_correct_count,
            "comprehensionTotal": self.comprehension_total,
            "comprehensionScore": self.comprehension_score,
            "icaScore": self.ica_score,
            "icaBreakdown": self.ica_breakdown,
            "partResults": self.part_results,
            "transcriptRaw": self.transcript_raw,
            "sttProvider": self.stt_provider,
            "sttModel": self.stt_model,
            "algorithmVersion": self.algorithm_version,
            "evaluationVersion": self.evaluation_version,
            "errorMessage": self.error_message,
            "audioUrl": audio_url,
            "audioMimeType": self.audio_mime_type,
            "audioSizeBytes": self.audio_size_bytes,
            "hasAudio": bool(self.audio_key) or bool(self.part_audios),
            "partAudios": self.part_audios,
            "appliedBy": self.applied_by,
            "submittedAt": self.submitted_at.isoformat() if self.submitted_at else None,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }
        if self.student:
            data["studentName"] = self.student.name
        if include_answers:
            data["answers"] = [answer.to_dict() for answer in (self.answers or [])]
        if include_words:
            data["words"] = [word.to_dict() for word in (self.words or [])]
        return data
