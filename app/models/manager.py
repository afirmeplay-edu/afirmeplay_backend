from app import db
import uuid
from datetime import datetime

class Manager(db.Model):
    __tablename__ = 'manager'
    # Manager é global (não-tenant): vive no schema public.
    __table_args__ = {"schema": "public"}

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(100), nullable=False)
    profile_picture = db.Column(db.String)
    registration = db.Column(db.String(50), nullable=True, unique=True)
    birth_date = db.Column(db.Date)
    created_at = db.Column(db.TIMESTAMP, server_default=db.func.now())
    updated_at = db.Column(db.TIMESTAMP, server_default=db.func.now(), onupdate=db.func.now())

    # Relacionamento com User
    user_id = db.Column(db.String, db.ForeignKey('public.users.id'), unique=True)
    
    # Relacionamento com School (para diretores e coordenadores)
    # Nota: `school` é por-tenant (`city_*`). Não existe FK estável de `public.manager.school_id`
    # para `tenant.school.id` porque o schema físico varia por município.
    school_id = db.Column(db.String(36), nullable=True)
    
    # Relacionamento com City (para tecadm)
    city_id = db.Column(db.String, db.ForeignKey('public.city.id'), nullable=True)
    
    # Relacionamentos
    user = db.relationship('User', backref='manager')
    city = db.relationship('City', backref='managers')
