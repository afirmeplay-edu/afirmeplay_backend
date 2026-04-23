from app import db
from sqlalchemy.dialects.postgresql import UUID
import uuid

class StudentPasswordLog(db.Model):
    __tablename__ = 'student_password_log'
    __table_args__ = {"schema": "tenant"}

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    student_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=True)
    password = db.Column(db.String, nullable=False)  # Senha em texto plano
    registration = db.Column(db.String(50), nullable=True)
    
    # Relacionamentos com outras tabelas
    user_id = db.Column(db.String, db.ForeignKey('public.users.id'), nullable=True)
    student_id = db.Column(db.String, db.ForeignKey('tenant.student.id'), nullable=True)
    class_id = db.Column(UUID(as_uuid=True), db.ForeignKey('tenant.class.id'), nullable=True)
    grade_id = db.Column(UUID(as_uuid=True), db.ForeignKey('public.grade.id'), nullable=True)
    # ✅ CORRIGIDO: Explicitamente String(36) para garantir tipo correto
    school_id = db.Column(db.String(36), db.ForeignKey('tenant.school.id'), nullable=True)
    city_id = db.Column(db.String, db.ForeignKey('public.city.id'), nullable=True)
    
    created_at = db.Column(db.TIMESTAMP, server_default=db.func.now())
    
    # Relacionamentos (opcional, para facilitar consultas)
    user = db.relationship('User', backref='student_password_logs')
    student = db.relationship('Student', backref='password_logs')
    class_obj = db.relationship('Class', backref='student_password_logs')
    grade = db.relationship('Grade', backref='student_password_logs')
    school = db.relationship('School', backref='student_password_logs')
    city = db.relationship('City', backref='student_password_logs')

