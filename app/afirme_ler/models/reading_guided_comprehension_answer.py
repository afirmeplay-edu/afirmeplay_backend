# -*- coding: utf-8 -*-
from app import db
import uuid


class ReadingGuidedComprehensionAnswer(db.Model):
    __tablename__ = "reading_guided_comprehension_answer"
    __table_args__ = {"schema": "tenant"}

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = db.Column(
        db.String,
        db.ForeignKey("tenant.reading_guided_session.id", ondelete="CASCADE"),
        nullable=False,
    )
    reading_text_question_id = db.Column(db.String, nullable=False)
    selected_option = db.Column(db.Integer, nullable=False)
    is_correct = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.TIMESTAMP, server_default=db.text("CURRENT_TIMESTAMP"))

    session = db.relationship("ReadingGuidedSession", back_populates="answers")

    def to_dict(self):
        return {
            "id": self.id,
            "sessionId": self.session_id,
            "readingTextQuestionId": self.reading_text_question_id,
            "selectedOption": self.selected_option,
            "isCorrect": bool(self.is_correct),
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }
