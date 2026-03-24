
from app import db
from sqlalchemy.dialects.postgresql import UUID
import uuid

# Tabela de associação N:N entre Skill e Grade (schema public)
skill_grade = db.Table(
    "skill_grade",
    db.metadata,
    db.Column("skill_id", UUID(as_uuid=True), db.ForeignKey("public.skills.id", ondelete="CASCADE"), primary_key=True),
    db.Column("grade_id", UUID(as_uuid=True), db.ForeignKey("public.grade.id", ondelete="CASCADE"), primary_key=True),
    schema="public"
)


class Skill(db.Model):
    __tablename__ = "skills"
    __table_args__ = {"schema": "public"}
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text, nullable=False)

    subject_id = db.Column(db.Text, db.ForeignKey("subject.id"))

    # Múltiplas grades: uma habilidade pode se enquadrar em várias turmas (ex.: compartilhada entre anos)
    grades = db.relationship(
        "Grade",
        secondary=skill_grade,
        backref=db.backref("skills", lazy="dynamic"),
        lazy="joined",
    )