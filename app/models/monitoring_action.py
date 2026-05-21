from datetime import datetime
import uuid

from app import db
from sqlalchemy.dialects.postgresql import UUID


class MonitoringAction(db.Model):
    __tablename__ = "monitoring_action"
    __table_args__ = {"schema": "tenant"}

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    source_type = db.Column(db.String(30), nullable=False)  # avaliacao | cartao_resposta
    source_id = db.Column(db.String, nullable=False)  # test_id | gabarito_id
    student_id = db.Column(db.String, db.ForeignKey("tenant.student.id"), nullable=False)
    school_id = db.Column(db.String(36), db.ForeignKey("tenant.school.id"), nullable=True)
    class_id = db.Column(UUID(as_uuid=True), db.ForeignKey("tenant.class.id"), nullable=True)
    grade_id = db.Column(UUID(as_uuid=True), db.ForeignKey("public.grade.id"), nullable=True)
    discipline = db.Column(db.String(120), nullable=True)

    coordinator_id = db.Column(db.String, db.ForeignKey("public.users.id"), nullable=True)
    pedagogical_action = db.Column(db.Text, nullable=True)
    responsible_id = db.Column(db.String, db.ForeignKey("public.users.id"), nullable=True)
    deadline = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(30), nullable=False, default="pendente")
    completed_at = db.Column(db.Date, nullable=True)
    done_by_school = db.Column(db.Boolean, nullable=False, default=False)
    seen_by_semed = db.Column(db.Boolean, nullable=False, default=False)
    note = db.Column(db.Text, nullable=True)

    created_by = db.Column(db.String, db.ForeignKey("public.users.id"), nullable=True)
    updated_by = db.Column(db.String, db.ForeignKey("public.users.id"), nullable=True)
    created_at = db.Column(db.TIMESTAMP, server_default=db.text("CURRENT_TIMESTAMP"))
    updated_at = db.Column(
        db.TIMESTAMP,
        server_default=db.text("CURRENT_TIMESTAMP"),
        onupdate=db.text("CURRENT_TIMESTAMP"),
    )

    student = db.relationship("Student", backref="monitoring_actions")
    school = db.relationship("School", foreign_keys=[school_id])
    class_ = db.relationship("Class", foreign_keys=[class_id])
    grade = db.relationship("Grade", foreign_keys=[grade_id])
    coordinator = db.relationship("User", foreign_keys=[coordinator_id])
    responsible = db.relationship("User", foreign_keys=[responsible_id])

    def to_dict(self):
        return {
            "id": self.id,
            "source_type": self.source_type,
            "source_id": self.source_id,
            "student_id": self.student_id,
            "school_id": self.school_id,
            "class_id": str(self.class_id) if self.class_id else None,
            "grade_id": str(self.grade_id) if self.grade_id else None,
            "discipline": self.discipline,
            "coordinator_id": self.coordinator_id,
            "pedagogical_action": self.pedagogical_action,
            "responsible_id": self.responsible_id,
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "status": self.status,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "done_by_school": bool(self.done_by_school),
            "seen_by_semed": bool(self.seen_by_semed),
            "note": self.note,
            "created_by": self.created_by,
            "updated_by": self.updated_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
