# -*- coding: utf-8 -*-
from app import db
import uuid


class ReadingGuidedAutoWord(db.Model):
    __tablename__ = "reading_guided_auto_word"
    __table_args__ = {"schema": "tenant"}

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = db.Column(
        db.String,
        db.ForeignKey("tenant.reading_guided_auto_session.id", ondelete="CASCADE"),
        nullable=False,
    )
    part = db.Column(db.String(20), nullable=False, default="text")
    position = db.Column(db.Integer, nullable=False)
    expected_token = db.Column(db.String(255), nullable=True)
    recognized_token = db.Column(db.String(255), nullable=True)
    similarity = db.Column(db.Float, nullable=True)
    phonetic_expected = db.Column(db.String(255), nullable=True)
    phonetic_recognized = db.Column(db.String(255), nullable=True)
    match_type = db.Column(db.String(20), nullable=False)
    start_ms = db.Column(db.Integer, nullable=True)
    end_ms = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.TIMESTAMP, server_default=db.text("CURRENT_TIMESTAMP"))

    session = db.relationship("ReadingGuidedAutoSession", back_populates="words")

    def to_dict(self):
        return {
            "id": self.id,
            "sessionId": self.session_id,
            "part": self.part,
            "position": self.position,
            "expectedToken": self.expected_token,
            "recognizedToken": self.recognized_token,
            "similarity": self.similarity,
            "phoneticExpected": self.phonetic_expected,
            "phoneticRecognized": self.phonetic_recognized,
            "matchType": self.match_type,
            "startMs": self.start_ms,
            "endMs": self.end_ms,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }
