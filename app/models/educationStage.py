from app import db
import uuid
from sqlalchemy.dialects.postgresql import UUID


class EducationStage(db.Model):
    __tablename__ = "education_stage"
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = db.Column(db.String, nullable=False)

    grades = db.relationship("Grade", backref="education_stage")
    # Relacionamento com escolas vinculadas (via SchoolCourse - backref já definido)
