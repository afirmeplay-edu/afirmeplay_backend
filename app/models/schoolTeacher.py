from app import db
from sqlalchemy.dialects.postgresql import UUID
import uuid


class SchoolTeacher(db.Model):
    __tablename__ = 'school_teacher'

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    registration = db.Column(db.String)
    school_id = db.Column(db.String, db.ForeignKey('school.id'))
    teacher_id = db.Column(UUID(as_uuid=True), db.ForeignKey('teacher.id'))