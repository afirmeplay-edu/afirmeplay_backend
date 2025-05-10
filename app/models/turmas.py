from app import db
import uuid

class Turma(db.Model):
    __tablename__ = 'turmas'

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    nome = db.Column(db.String(100), nullable=False)

    alunos = db.relationship('Aluno', backref='turma', lazy=True)
    professores = db.relationship('Professor', secondary='professor_turma', back_populates='turmas')