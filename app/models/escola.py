from app import db
import uuid

class Escola(db.Model):
    __tablename__ = 'escolas'

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    nome = db.Column(db.String, nullable=False)
    cidade = db.Column(db.String, nullable=False)
    estado = db.Column(db.String, nullable=False)
    dominio = db.Column(db.String, unique=True, nullable=False)
    criado_em = db.Column(db.DateTime, server_default=db.func.now())
