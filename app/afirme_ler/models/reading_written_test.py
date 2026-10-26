# -*- coding: utf-8 -*-
"""Avaliação escrita do Afirme Ler (prova impressa), questões e aplicação por turma, no schema do município."""
from app import db
import uuid
from sqlalchemy.dialects.postgresql import UUID

WRITTEN_TEST_STATUS_DRAFT = "rascunho"
WRITTEN_TEST_STATUS_PUBLISHED = "publicada"
WRITTEN_TEST_STATUSES = (WRITTEN_TEST_STATUS_DRAFT, WRITTEN_TEST_STATUS_PUBLISHED)
DEFAULT_TIMEZONE = "America/Sao_Paulo"


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
    applications = db.relationship(
        "ReadingWrittenTestClass",
        back_populates="written_test",
        cascade="all, delete-orphan",
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


class ReadingWrittenTestClass(db.Model):
    """Aplicação da avaliação a uma turma. Os alunos vêm da turma atual (Student.class_id)."""

    __tablename__ = "reading_written_test_class"
    __table_args__ = (
        db.UniqueConstraint("written_test_id", "class_id", name="uq_reading_written_test_class"),
        {"schema": "tenant"},
    )

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    written_test_id = db.Column(
        db.String,
        db.ForeignKey("tenant.reading_written_test.id", ondelete="CASCADE"),
        nullable=False,
    )
    class_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("tenant.class.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Data/hora local (sem fuso) no fuso de `timezone`, como em reading_evaluation.
    application_start = db.Column(db.TIMESTAMP, nullable=False)
    application_end = db.Column(db.TIMESTAMP, nullable=True)
    timezone = db.Column(db.String(50), nullable=False, default=DEFAULT_TIMEZONE)
    created_by = db.Column(db.String, db.ForeignKey("public.users.id"), nullable=False)
    created_at = db.Column(db.TIMESTAMP, server_default=db.text("CURRENT_TIMESTAMP"))
    updated_at = db.Column(
        db.TIMESTAMP,
        server_default=db.text("CURRENT_TIMESTAMP"),
        onupdate=db.text("CURRENT_TIMESTAMP"),
    )

    written_test = db.relationship("ReadingWrittenTest", back_populates="applications")
