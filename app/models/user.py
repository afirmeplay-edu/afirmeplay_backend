from enum import Enum
from flask_sqlalchemy import SQLAlchemy
from app import db
import uuid
from datetime import datetime


class RoleEnum(Enum):
    ALUNO = "aluno"
    PROFESSOR = "professor"
    COORDENADOR = "coordenador"
    DIRETOR = "diretor"
    ADMIN = "admin"
    TECADM = "tecadm"

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(100))
    email = db.Column(db.String(100), unique=True)
    password_hash = db.Column(db.String)
    registration = db.Column(db.String(50), nullable=True, unique=True)
    role = db.Column(db.Enum(RoleEnum), nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    student = db.relationship("Student", backref="users", uselist=False)
    teacher = db.relationship("Teacher", backref="users", uselist=False)
    city_id = db.Column(db.String, db.ForeignKey('city.id'), nullable=True)