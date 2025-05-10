from app import db
import uuid

class Escola(db.Model):
    __tablename__ = 'escolas'

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    nome = db.Column(db.String(100), nullable=False)
    municipio_id = db.Column(db.String, db.ForeignKey('municipios.id'), nullable=False)
    endereco = db.Column(db.String(200))
    dominio = db.Column(db.String(100))
    criado_em = db.Column(db.DateTime, server_default=db.func.now())

    alunos = db.relationship('Aluno', backref='escola', lazy=True)
    professores = db.relationship('Professor', secondary='professor_escola', back_populates='escolas')
