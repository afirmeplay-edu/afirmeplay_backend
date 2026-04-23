from app import db
from sqlalchemy.dialects.postgresql import UUID
import uuid

class ClassSubject(db.Model):
    __tablename__ = 'class_subject'
    __table_args__ = {"schema": "tenant"}

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    class_id = db.Column(UUID(as_uuid=True), db.ForeignKey('tenant.class.id'))
    subject_id = db.Column(db.String, db.ForeignKey('public.subject.id'))
    teacher_id = db.Column(db.String, db.ForeignKey('tenant.teacher.id'))
    created_at = db.Column(db.TIMESTAMP, server_default=db.text('CURRENT_TIMESTAMP'))
    updated_at = db.Column(db.TIMESTAMP, server_default=db.text('CURRENT_TIMESTAMP'), onupdate=db.text('CURRENT_TIMESTAMP'))