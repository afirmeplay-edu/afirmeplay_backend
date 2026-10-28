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


PRINT_RUN_PENDING = "pendente"
PRINT_RUN_PROCESSING = "processando"
PRINT_RUN_DONE = "concluido"
PRINT_RUN_ERROR = "erro"


class ReadingWrittenTestPrintRun(db.Model):
    """Geração dos cartões-resposta (ZIP no MinIO) e o mapa do cartão para a correção futura."""

    __tablename__ = "reading_written_test_print_run"
    __table_args__ = {"schema": "tenant"}

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    written_test_id = db.Column(
        db.String,
        db.ForeignKey("tenant.reading_written_test.id", ondelete="CASCADE"),
        nullable=False,
    )
    # NULL = todas as turmas aplicadas.
    class_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("tenant.class.id", ondelete="CASCADE"),
        nullable=True,
    )
    status = db.Column(db.String(20), nullable=False, default=PRINT_RUN_PENDING)
    task_id = db.Column(db.String(64), nullable=True)
    total_students = db.Column(db.Integer, nullable=False, default=0)
    generated_count = db.Column(db.Integer, nullable=False, default=0)
    error_message = db.Column(db.Text, nullable=True)
    minio_bucket = db.Column(db.String(100), nullable=True)
    minio_object_name = db.Column(db.String(500), nullable=True)
    answer_sheet_map = db.Column(db.JSON, nullable=True)
    created_by = db.Column(db.String, db.ForeignKey("public.users.id"), nullable=False)
    created_at = db.Column(db.TIMESTAMP, server_default=db.text("CURRENT_TIMESTAMP"))
    started_at = db.Column(db.TIMESTAMP, nullable=True)
    finished_at = db.Column(db.TIMESTAMP, nullable=True)


class ReadingWrittenTestCorrection(db.Model):
    """Leitura de um cartão: letras das objetivas e imagens do ditado e do bilhete."""

    __tablename__ = "reading_written_test_correction"
    __table_args__ = (
        db.UniqueConstraint(
            "written_test_id", "student_id", name="uq_reading_written_test_correction"
        ),
        {"schema": "tenant"},
    )

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    written_test_id = db.Column(
        db.String,
        db.ForeignKey("tenant.reading_written_test.id", ondelete="CASCADE"),
        nullable=False,
    )
    student_id = db.Column(
        db.String,
        db.ForeignKey("tenant.student.id"),
        nullable=False,
    )
    answers = db.Column(db.JSON, nullable=False, default=dict)
    blank = db.Column(db.JSON, nullable=False, default=list)
    invalid = db.Column(db.JSON, nullable=False, default=list)
    crops = db.Column(db.JSON, nullable=False, default=dict)
    pages = db.Column(db.JSON, nullable=False, default=list)
    # Nota das 16 objetivas, calculada pelo gabarito. A IA não preenche este campo.
    objective = db.Column(db.JSON, nullable=False, default=dict)
    # Nota do ditado e do bilhete: IA quando o cartão foi enviado, ou lançamento do professor.
    writing = db.Column(db.JSON, nullable=False, default=dict)
    created_at = db.Column(db.TIMESTAMP, server_default=db.text("CURRENT_TIMESTAMP"))
    updated_at = db.Column(
        db.TIMESTAMP,
        server_default=db.text("CURRENT_TIMESTAMP"),
        onupdate=db.text("CURRENT_TIMESTAMP"),
    )
