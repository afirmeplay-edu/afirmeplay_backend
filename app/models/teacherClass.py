from app import db
from sqlalchemy.dialects.postgresql import UUID
import uuid


class TeacherClass(db.Model):
    __tablename__ = 'teacher_class'

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    teacher_id = db.Column(db.String, db.ForeignKey('teacher.id'))
    class_id = db.Column(db.String, db.ForeignKey('class.id'))
    created_at = db.Column(db.TIMESTAMP, server_default=db.text('CURRENT_TIMESTAMP'))
    updated_at = db.Column(db.TIMESTAMP, server_default=db.text('CURRENT_TIMESTAMP'), onupdate=db.text('CURRENT_TIMESTAMP')) 