from app import db
import uuid

class Aluno(db.Model):
    __tablename__ = 'alunos'

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    usuario_id = db.Column(db.String, db.ForeignKey('usuario.id'), nullable=False, unique=True)
    matricula = db.Column(db.String, nullable=False, unique=True)
    classe_id = db.Column(db.String, db.ForeignKey('classes.id'))  # se estiver usando Classe
    tenant_id = db.Column(db.String, db.ForeignKey('escolas.id'), nullable=False)
    criado_em = db.Column(db.DateTime, server_default=db.func.now())

    usuario = db.relationship("Usuario", backref="aluno", uselist=False)
