from app import db
import uuid
from datetime import datetime


class Game(db.Model):
    __tablename__ = 'games'
    
    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    url = db.Column(db.String(500), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    iframeHtml = db.Column(db.Text, nullable=False)
    thumbnail = db.Column(db.String(500), nullable=True)
    author = db.Column(db.String(200), nullable=True)
    provider = db.Column(db.String(50), nullable=False, default='wordwall')
    subject = db.Column(db.String(100), nullable=False)
    userId = db.Column(db.String, db.ForeignKey('users.id'), nullable=False)
    createdAt = db.Column(db.DateTime, server_default=db.func.now())
    updatedAt = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())
    
    # Relacionamento com User
    user = db.relationship("User", backref="games") 