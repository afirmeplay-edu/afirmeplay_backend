from app import db
import uuid

class Classe(db.Model):
    __tablename__ = 'classes'
    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    nome = db.Column(db.String, nullable=False)