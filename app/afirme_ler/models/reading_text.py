# -*- coding: utf-8 -*-
from app import db
import uuid
from sqlalchemy.dialects.postgresql import JSON, UUID


class ReadingText(db.Model):
    __tablename__ = "reading_text"
    __table_args__ = {"schema": "public"}

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title = db.Column(db.String(500), nullable=False)
    content = db.Column(db.Text, nullable=False)
    grade_id = db.Column(UUID(as_uuid=True), db.ForeignKey("public.grade.id"), nullable=False)
    difficulty_level = db.Column(db.String(20), nullable=False)
    target_skills = db.Column(JSON, nullable=False, default=list)
    source = db.Column(db.String(500), nullable=True)
    is_calibrated = db.Column(db.Boolean, nullable=False, default=False)
    scope_type = db.Column(db.String(20), nullable=False, default="GLOBAL")
    owner_city_id = db.Column(db.String, db.ForeignKey("public.city.id"), nullable=True)
    owner_user_id = db.Column(db.String, db.ForeignKey("public.users.id"), nullable=True)
    created_by = db.Column(db.String, db.ForeignKey("public.users.id"), nullable=False)
    created_at = db.Column(db.TIMESTAMP, server_default=db.text("CURRENT_TIMESTAMP"))
    updated_at = db.Column(
        db.TIMESTAMP,
        server_default=db.text("CURRENT_TIMESTAMP"),
        onupdate=db.text("CURRENT_TIMESTAMP"),
    )

    grade = db.relationship("Grade", foreign_keys=[grade_id])
    creator = db.relationship("User", foreign_keys=[created_by])
    questions = db.relationship(
        "ReadingTextQuestion",
        back_populates="reading_text",
        cascade="all, delete-orphan",
        order_by="ReadingTextQuestion.created_at",
    )

    def to_dict(self, include_questions=False):
        data = {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "gradeId": str(self.grade_id) if self.grade_id else None,
            "grade": (
                {"id": str(self.grade.id), "name": self.grade.name}
                if self.grade
                else None
            ),
            "difficultyLevel": self.difficulty_level,
            "targetSkills": self.target_skills if isinstance(self.target_skills, list) else [],
            "source": self.source,
            "isCalibrated": bool(self.is_calibrated),
            "scopeType": self.scope_type,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_questions:
            data["questions"] = [q.to_dict() for q in (self.questions or [])]
        return data
