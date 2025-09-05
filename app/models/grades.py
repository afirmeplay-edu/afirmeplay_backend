from app import db
import uuid
from sqlalchemy.dialects.postgresql import UUID

class Grade(db.Model):
    __tablename__ = 'grade'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = db.Column(db.String, nullable=False)
    education_stage_id = db.Column(UUID(as_uuid=True), db.ForeignKey('education_stage.id'), nullable=False)

    classes = db.relationship("Class", backref="grade")
    students = db.relationship("Student", backref="grade")
    # questions = db.relationship("Question", backref="grade_level")