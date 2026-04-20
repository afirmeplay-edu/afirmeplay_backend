from app import db
from sqlalchemy.dialects.postgresql import UUID
import uuid


class SchoolTeacher(db.Model):
    __tablename__ = 'school_teacher'
    __table_args__ = {"schema": "tenant"}

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    registration = db.Column(db.String)
    # ✅ CORRIGIDO: Explicitamente String(36) para garantir tipo correto
    school_id = db.Column(db.String(36), db.ForeignKey('tenant.school.id'))
    teacher_id = db.Column(db.String, db.ForeignKey('tenant.teacher.id'))
    created_at = db.Column(db.TIMESTAMP, server_default=db.text('CURRENT_TIMESTAMP'))
    updated_at = db.Column(db.TIMESTAMP, server_default=db.text('CURRENT_TIMESTAMP'), onupdate=db.text('CURRENT_TIMESTAMP'))