# -*- coding: utf-8 -*-
from app import db
import uuid
from sqlalchemy.dialects.postgresql import JSON, UUID


class ReadingEvaluation(db.Model):
    __tablename__ = "reading_evaluation"
    __table_args__ = {"schema": "tenant"}

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    reading_text_id = db.Column(db.String, nullable=False)
    words_word_list_id = db.Column(db.String, nullable=True)
    uncommon_word_list_id = db.Column(db.String, nullable=True)
    grade_id = db.Column(UUID(as_uuid=True), db.ForeignKey("public.grade.id"), nullable=True)
    class_ids = db.Column(JSON, nullable=False, default=list)
    school_ids = db.Column(JSON, nullable=True)
    assessment_type = db.Column(db.String(20), nullable=False, default="completa")
    status = db.Column(db.String(20), nullable=False, default="rascunho")
    application_start = db.Column(db.TIMESTAMP, nullable=True)
    application_end = db.Column(db.TIMESTAMP, nullable=True)
    timezone = db.Column(db.String(50), default="America/Sao_Paulo")
    created_by = db.Column(db.String, db.ForeignKey("public.users.id"), nullable=False)
    created_at = db.Column(db.TIMESTAMP, server_default=db.text("CURRENT_TIMESTAMP"))
    updated_at = db.Column(
        db.TIMESTAMP,
        server_default=db.text("CURRENT_TIMESTAMP"),
        onupdate=db.text("CURRENT_TIMESTAMP"),
    )

    grade = db.relationship("Grade", foreign_keys=[grade_id])
    creator = db.relationship("User", foreign_keys=[created_by])
    sessions = db.relationship(
        "ReadingEvaluationSession",
        back_populates="evaluation",
        cascade="all, delete-orphan",
    )

    def to_dict(self, include_sessions=False):
        data = {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "readingTextId": self.reading_text_id,
            "wordsWordListId": self.words_word_list_id,
            "uncommonWordListId": self.uncommon_word_list_id,
            "gradeId": str(self.grade_id) if self.grade_id else None,
            "grade": (
                {"id": str(self.grade.id), "name": self.grade.name}
                if self.grade
                else None
            ),
            "classIds": self.class_ids if isinstance(self.class_ids, list) else [],
            "schoolIds": self.school_ids if isinstance(self.school_ids, list) else [],
            "assessmentType": self.assessment_type,
            "status": self.status,
            "applicationStart": (
                self.application_start.isoformat() if self.application_start else None
            ),
            "applicationEnd": (
                self.application_end.isoformat() if self.application_end else None
            ),
            "timezone": self.timezone,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_sessions:
            data["sessions"] = [session.to_dict() for session in (self.sessions or [])]
        return data
