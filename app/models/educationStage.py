from app import db
import uuid

class EducationStage(db.Model):
    __tablename__ = 'education_stage'

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(100))

    grades = db.relationship("Grade", backref="education_stage")
    questions = db.relationship("Question", backref="education_stage")