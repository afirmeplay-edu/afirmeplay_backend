from app import db
import uuid

class EducationStage(db.Model):
    __tablename__ = 'education_stages'

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String, nullable=False, unique=True)

    # Relacionamento: uma etapa tem várias séries
    grades = db.relationship('Grade', backref='education_stage', cascade='all, delete-orphan', lazy=True)

    def __repr__(self):
        return f"<EducationStage {self.name}>"