# -*- coding: utf-8 -*-
from app import db
import uuid
from sqlalchemy.dialects.postgresql import JSON


class ReadingTextQuestion(db.Model):
    __tablename__ = "reading_text_question"
    __table_args__ = {"schema": "public"}

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    reading_text_id = db.Column(
        db.String,
        db.ForeignKey("public.reading_text.id", ondelete="CASCADE"),
        nullable=False,
    )
    statement = db.Column(db.Text, nullable=False)
    options = db.Column(JSON, nullable=False, default=list)
    correct_option = db.Column(db.Integer, nullable=True)
    descriptor = db.Column(db.String(500), nullable=False)
    created_at = db.Column(db.TIMESTAMP, server_default=db.text("CURRENT_TIMESTAMP"))
    updated_at = db.Column(
        db.TIMESTAMP,
        server_default=db.text("CURRENT_TIMESTAMP"),
        onupdate=db.text("CURRENT_TIMESTAMP"),
    )

    reading_text = db.relationship("ReadingText", back_populates="questions")

    def to_dict(self):
        options = self.options if isinstance(self.options, list) else []
        return {
            "id": self.id,
            "readingTextId": self.reading_text_id,
            "statement": self.statement,
            "options": options,
            "correctOption": self.correct_option,
            "descriptor": self.descriptor,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }
