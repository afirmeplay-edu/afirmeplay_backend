from app import db
from sqlalchemy.dialects.postgresql import UUID
import uuid
from app.models.user import User

class Student(db.Model):
    __tablename__ = 'student'
  
    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(100))
    profile_picture = db.Column(db.String)
    registration = db.Column(db.String(50), nullable=True, unique=True)
    created_at = db.Column(db.TIMESTAMP, server_default=db.func.now())
    birth_date = db.Column(db.Date)

    user_id = db.Column(db.String, db.ForeignKey('users.id'), unique=True)
    user = db.relationship('User', back_populates='students')
    grade_id = db.Column(UUID(as_uuid=True), db.ForeignKey('grade.id'))
    class_id = db.Column(db.String, db.ForeignKey('class.id'))
    school_id = db.Column(db.String, db.ForeignKey('school.id'))

    # Relacionamento com StudentAnswer para permitir exclusão em cascata
    student_answers = db.relationship('StudentAnswer', backref='student', cascade='all, delete-orphan')
    
    
    