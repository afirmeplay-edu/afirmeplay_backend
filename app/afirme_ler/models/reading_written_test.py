# -*- coding: utf-8 -*-
"""Avaliação escrita do Afirme Ler (prova impressa) e as questões dela, no schema do município."""
from app import db
import uuid

WRITTEN_TEST_STATUS_DRAFT = "rascunho"
WRITTEN_TEST_STATUS_PUBLISHED = "publicada"
WRITTEN_TEST_STATUSES = (WRITTEN_TEST_STATUS_DRAFT, WRITTEN_TEST_STATUS_PUBLISHED)


class ReadingWrittenTest(db.Model):
    __tablename__ = "reading_written_test"
    __table_args__ = {"schema": "tenant"}

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    grade_ids = db.Column(db.JSON, nullable=False, default=list)
    school_ids = db.Column(db.JSON, nullable=False, default=list)
    class_ids = db.Column(db.JSON, nullable=False, default=list)
    status = db.Column(db.String(20), nullable=False, default=WRITTEN_TEST_STATUS_DRAFT)
    created_by = db.Column(db.String, db.ForeignKey("public.users.id"), nullable=False)
    created_at = db.Column(db.TIMESTAMP, server_default=db.text("CURRENT_TIMESTAMP"))
    updated_at = db.Column(
        db.TIMESTAMP,
        server_default=db.text("CURRENT_TIMESTAMP"),
        onupdate=db.text("CURRENT_TIMESTAMP"),
    )
    published_at = db.Column(db.TIMESTAMP, nullable=True)

    creator = db.relationship("User", foreign_keys=[created_by])
    questions = db.relationship(
        "ReadingWrittenTestQuestion",
        back_populates="written_test",
        cascade="all, delete-orphan",
        order_by="ReadingWrittenTestQuestion.order",
    )


class ReadingWrittenTestQuestion(db.Model):
    __tablename__ = "reading_written_test_question"
    __table_args__ = (
        db.UniqueConstraint(
            "written_test_id", "question_id", name="uq_reading_written_test_question"
        ),
        db.UniqueConstraint("written_test_id", "order", name="uq_reading_written_test_order"),
        {"schema": "tenant"},
    )

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    written_test_id = db.Column(
        db.String,
        db.ForeignKey("tenant.reading_written_test.id", ondelete="CASCADE"),
        nullable=False,
    )
    # public.question.id sem FK física: uma FK bloquearia a exclusão de questões no Afirme Play.
    question_id = db.Column(db.String, nullable=False)
    order = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.TIMESTAMP, server_default=db.text("CURRENT_TIMESTAMP"))

    written_test = db.relationship("ReadingWrittenTest", back_populates="questions")
