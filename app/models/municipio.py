from app import db
import uuid

class Municipio(db.Model):
    __tablename__ = 'municipios'

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    nome = db.Column(db.String(100), nullable=False)
    estado = db.Column(db.String(100), nullable=False)
    criado_em = db.Column(db.DateTime, server_default=db.func.now())

    escolas = db.relationship('Escola', backref='municipio', lazy=True)