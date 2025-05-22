from app import db
import uuid
from sqlalchemy.dialects.postgresql import UUID

class Grade(db.Model):
    __tablename__ = 'grade'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = db.Column(db.String(100))
    education_stage_id = db.Column(UUID(as_uuid=True), db.ForeignKey('education_stage.id'))

    classes = db.relationship("Class", backref="grade")
    students = db.relationship("Student", backref="grade")
    tests = db.relationship("Test", backref="grade")
    # questions = db.relationship("Question", backref="grade_level")