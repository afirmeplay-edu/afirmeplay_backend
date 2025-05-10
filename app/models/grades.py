from app import db
import uuid

class Grade(db.Model):
    __tablename__ = 'grades'

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(100), nullable=False)
    education_stage_id = db.Column(db.String, db.ForeignKey('education_stages.id'), nullable=False)

    alunos = db.relationship('Aluno', backref='grade', lazy=True)
    professores = db.relationship('Professor', secondary='professor_grade', back_populates='grades')