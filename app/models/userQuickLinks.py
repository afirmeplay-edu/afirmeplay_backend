from flask_sqlalchemy import SQLAlchemy
from app import db
import uuid
from datetime import datetime


class UserQuickLinks(db.Model):
    __tablename__ = 'user_quick_links'
    
    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String, db.ForeignKey('users.id'), nullable=False)
    quickLinks = db.Column(db.JSON, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())
    
    # Relacionamento com a tabela users
    user = db.relationship("User", backref="quick_links") 