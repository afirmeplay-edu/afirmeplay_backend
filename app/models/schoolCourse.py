from app import db
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime

class SchoolCourse(db.Model):
    __tablename__ = 'school_course'
    
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    school_id = db.Column(db.String, db.ForeignKey('school.id'), nullable=False)
    education_stage_id = db.Column(UUID(as_uuid=True), db.ForeignKey('education_stage.id'), nullable=False)
    created_at = db.Column(db.TIMESTAMP, server_default=db.func.now())
    
    # Relacionamentos
    school = db.relationship("School", backref="school_courses")
    education_stage = db.relationship("EducationStage", backref="school_courses")
    
    # Constraint único para evitar duplicatas
    __table_args__ = (
        db.UniqueConstraint('school_id', 'education_stage_id', name='uq_school_education_stage'),
    )

