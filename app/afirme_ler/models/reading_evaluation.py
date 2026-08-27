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
    grade_ids = db.Column(JSON, nullable=False, default=list)
    class_ids = db.Column(JSON, nullable=False, default=list)
    school_ids = db.Column(JSON, nullable=True)
    student_ids = db.Column(JSON, nullable=False, default=list)
    evaluation_kind = db.Column(db.String(20), nullable=False, default="formativa")
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

    def grade_id_list(self):
        ids = self.grade_ids if isinstance(self.grade_ids, list) else []
        out = [str(item) for item in ids if item]
        if not out and self.grade_id:
            out = [str(self.grade_id)]
        return out

    def to_dict(self, include_sessions=False):
        from app.afirme_ler.services.parsing import EVALUATION_KIND_LABELS
        from app.models.grades import Grade

        grade_ids = self.grade_id_list()
        grades = []
        if grade_ids:
            rows = Grade.query.filter(Grade.id.in_(grade_ids)).all()
            by_id = {str(row.id): row for row in rows}
            grades = [
                {"id": gid, "name": by_id[gid].name if gid in by_id else None}
                for gid in grade_ids
            ]
        first_grade = grades[0] if grades else None

        data = {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "evaluationKind": self.evaluation_kind,
            "evaluationKindLabel": EVALUATION_KIND_LABELS.get(self.evaluation_kind),
            "readingTextId": self.reading_text_id,
            "knownWordListId": self.words_word_list_id,
            "wordsWordListId": self.words_word_list_id,
            "uncommonWordListId": self.uncommon_word_list_id,
            "gradeIds": grade_ids,
            "grades": grades,
            "gradeId": grade_ids[0] if grade_ids else None,
            "grade": first_grade,
            "classIds": self.class_ids if isinstance(self.class_ids, list) else [],
            "schoolIds": self.school_ids if isinstance(self.school_ids, list) else [],
            "studentIds": self.student_ids if isinstance(self.student_ids, list) else [],
            "status": self.status,
            "createdBy": (
                {"id": self.created_by, "name": self.creator.name}
                if self.creator
                else {"id": self.created_by, "name": None}
            ),
            "applicationStart": (
                self.application_start.isoformat() if self.application_start else None
            ),
            "applicationEnd": (
                self.application_end.isoformat() if self.application_end else None
            ),
            "timezone": self.timezone,
            "createdBy": (
                {
                    "id": self.creator.id,
                    "name": self.creator.name or "",
                }
                if self.creator
                else (
                    {"id": self.created_by, "name": ""}
                    if self.created_by
                    else None
                )
            ),
            "knownWordListId": self.words_word_list_id,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_sessions:
            data["sessions"] = [session.to_dict() for session in (self.sessions or [])]
        return data
