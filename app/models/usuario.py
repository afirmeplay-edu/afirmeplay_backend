from enum import Enum
from flask_sqlalchemy import SQLAlchemy
from app import db
import uuid


class RoleEnum(Enum):
    ALUNO = "aluno"
    PROFESSOR = "professor"
    COORDENADOR = "coordenador"
    DIRETOR = "diretor"
    ADMIN = "admin"
    

class Usuario(db.Model):
    __tablename__ = 'usuario'

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String, nullable=False)
    matricula = db.Column(db.String(50), unique=True, nullable=True)
    senha_hash = db.Column(db.String, nullable=False)
    role = db.Column(db.Enum(RoleEnum), nullable=False)
    escola_id = db.Column(db.String, db.ForeignKey('escolas.id'), nullable=False)
    tenant_id = db.Column(db.String, db.ForeignKey('municipios.id'), nullable=False)

    aluno = db.relationship('Aluno', backref='usuario', uselist=False)
    professor = db.relationship('Professor', backref='usuario', uselist=False)
