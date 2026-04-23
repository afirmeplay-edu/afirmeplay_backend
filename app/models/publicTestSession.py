from app import db
from datetime import datetime
import uuid


class PublicTestSession(db.Model):
    """
    Sessão de prova no schema public (ex.: competições/escopos globais).

    Mantida separada de `TestSession` (tenant) para evitar misturar schema lógico `tenant`
    com tabelas físicas em `public`.
    """

    __tablename__ = "test_sessions"
    __table_args__ = {"schema": "public"}

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id = db.Column(db.String, nullable=False)
    test_id = db.Column(db.String, nullable=False)

    started_at = db.Column(db.TIMESTAMP, nullable=True)
    actual_start_time = db.Column(db.TIMESTAMP, nullable=True)
    submitted_at = db.Column(db.TIMESTAMP, nullable=True)
    time_limit_minutes = db.Column(db.Integer, nullable=True)

    status = db.Column(db.String(20), default="em_andamento")

    total_questions = db.Column(db.Integer, nullable=True)
    correct_answers = db.Column(db.Integer, nullable=True)
    score = db.Column(db.Float, nullable=True)
    grade = db.Column(db.Float, nullable=True)
    manual_score = db.Column(db.Numeric(5, 2), nullable=True)

    feedback = db.Column(db.Text, nullable=True)
    corrected_by = db.Column(db.String, db.ForeignKey("public.users.id"), nullable=True)
    corrected_at = db.Column(db.TIMESTAMP, nullable=True)

    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.TIMESTAMP, default=datetime.utcnow)
    updated_at = db.Column(db.TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def duration_minutes(self):
        if not self.started_at:
            return 0
        try:
            from datetime import timezone

            end_time = self.submitted_at or datetime.utcnow()
            start = self.started_at
            if start.tzinfo and not getattr(end_time, "tzinfo", None):
                end_time = end_time.replace(tzinfo=timezone.utc)
            elif getattr(end_time, "tzinfo", None) and not start.tzinfo:
                start = start.replace(tzinfo=timezone.utc) if hasattr(start, "replace") else start
            duration = end_time - start
            return int(duration.total_seconds() / 60)
        except (TypeError, AttributeError):
            return 0

    def start_session(self):
        if not self.started_at:
            self.started_at = datetime.utcnow()

    def finalize_session(self, correct_answers=None, total_questions=None):
        self.submitted_at = datetime.utcnow()
        self.status = "finalizada"
        if correct_answers is not None:
            self.correct_answers = correct_answers
        if total_questions is not None:
            self.total_questions = total_questions
        if self.correct_answers is not None and self.total_questions and self.total_questions > 0:
            self.score = (self.correct_answers / self.total_questions) * 100
            self.grade = round(((self.score or 0) / 100) * 10, 2)

