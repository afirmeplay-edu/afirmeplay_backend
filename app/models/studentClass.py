from app import db
from sqlalchemy.dialects.postgresql import UUID
import uuid

class Class(db.Model):
    __tablename__ = 'class'

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(100))
    school_id = db.Column(db.String, db.ForeignKey('school.id'))
    grade_id = db.Column(UUID(as_uuid=True), db.ForeignKey('grade.id'))

    students = db.relationship("Student", backref="class_")
    class_subjects = db.relationship("ClassSubject", backref="class_")
    class_tests = db.relationship("ClassTest", backref="class_") 