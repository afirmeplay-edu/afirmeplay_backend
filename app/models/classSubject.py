from app import db
from sqlalchemy.dialects.postgresql import UUID
import uuid

class ClassSubject(db.Model):
    __tablename__ = 'class_subject'

    id =db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    class_id = db.Column(db.String, db.ForeignKey('class.id'))
    subject_id = db.Column(db.String, db.ForeignKey('subject.id'))
    teacher_id = db.Column(db.String, db.ForeignKey('teacher.id'))