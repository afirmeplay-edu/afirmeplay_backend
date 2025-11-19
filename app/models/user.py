from enum import Enum
from flask_sqlalchemy import SQLAlchemy
from app import db
import uuid
from datetime import datetime, date


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
    created_at = db.Column(db.TIMESTAMP, server_default=db.func.now())
    updated_at = db.Column(db.TIMESTAMP, server_default=db.func.now(), onupdate=db.func.now())
    
    # Campos para reset de senha
    reset_token = db.Column(db.String(255), unique=True, nullable=True)
    reset_token_expires = db.Column(db.TIMESTAMP, nullable=True)

    birth_date = db.Column(db.Date, nullable=True)
    nationality = db.Column(db.String(100), nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    gender = db.Column(db.String(30), nullable=True)
    traits = db.Column(db.JSON, nullable=True)
    avatar_config = db.Column(db.JSON, nullable=True)
    address = db.Column(db.String(255), nullable=True)

    student = db.relationship("Student", back_populates="user", uselist=False)
    teacher = db.relationship("Teacher", backref="users", uselist=False)
    city_id = db.Column(db.String, db.ForeignKey('city.id'), nullable=True)