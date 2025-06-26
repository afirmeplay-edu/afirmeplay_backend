from app import db
import uuid
from sqlalchemy.dialects.postgresql import UUID
class Teacher(db.Model):
    __tablename__ = 'teacher'

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(100), nullable=False)
    profile_picture = db.Column(db.String)
    registration = db.Column(db.String(50), nullable=True, unique=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    # grades = db.relationship('Grade', secondary='professor_grade', back_populates='professores')
    # turmas = db.relationship('Turma', secondary='professor_turma', back_populates='professores')
    
    birth_date = db.Column(db.Date)
    user_id = db.Column(db.String, db.ForeignKey('users.id'), unique=True)

    school_teachers = db.relationship("SchoolTeacher", backref="teacher")
    class_subjects = db.relationship("ClassSubject", backref="teacher")