from app import db
from sqlalchemy.dialects.postgresql import UUID
import uuid

class Skill(db.Model):
    __tablename__ = "skills"
    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text, nullable=False)

    subject_id = db.Column(db.Text, db.ForeignKey('subject.id'))
    grade_id =  db.Column(UUID(as_uuid=True), db.ForeignKey('grade.id'))

    # subject = db.relationship("Subject", back_populates="skills")
    # grade = db.relationship("Grade", back_populates="skills")