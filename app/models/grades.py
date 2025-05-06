from app import db
import uuid

class Grade(db.Model):
    __tablename__ = 'grades'

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String, nullable=False)

    # Chave estrangeira para a etapa de ensino
    education_stage_id = db.Column(db.String, db.ForeignKey('education_stages.id'), nullable=False)

    def __repr__(self):
        return f"<Grade {self.name} ({self.education_stage.name})>"