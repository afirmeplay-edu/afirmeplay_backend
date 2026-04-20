from app import db
import uuid
from sqlalchemy.dialects.postgresql import UUID

from app.models.school import School


class PlantaoOnline(db.Model):
    __tablename__ = 'plantao_online'
    __table_args__ = {"schema": "tenant"}

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    link = db.Column(db.Text, nullable=False)
    title = db.Column(db.Text, nullable=True)
    grade_id = db.Column(UUID(as_uuid=True), db.ForeignKey('public.grade.id'), nullable=False)
    subject_id = db.Column(db.String, db.ForeignKey('public.subject.id'), nullable=False)
    created_by = db.Column(db.String, db.ForeignKey('public.users.id'), nullable=False)
    created_at = db.Column(db.TIMESTAMP, server_default=db.text('CURRENT_TIMESTAMP'))
    
    # Relacionamentos
    grade = db.relationship('Grade', foreign_keys=[grade_id])
    subject = db.relationship('Subject', foreign_keys=[subject_id])
    creator = db.relationship('User', foreign_keys=[created_by])
    plantao_schools = db.relationship('PlantaoOnlineSchool', back_populates='plantao', cascade='all, delete-orphan')
    
    @property
    def schools(self):
        """Retorna as escolas associadas ao plantão"""
        return [ps.school for ps in self.plantao_schools]
    
    def __repr__(self):
        return f'<PlantaoOnline {self.id} - {self.title}>'

class PlantaoOnlineSchool(db.Model):
    __tablename__ = 'plantao_schools'
    __table_args__ = {"schema": "tenant"}

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    plantao_id = db.Column(db.String, db.ForeignKey(PlantaoOnline.__table__.c.id), nullable=False)
    # Explicitamente String(36) para garantir tipo correto (mesmo padrão do PlayTV)
    school_id = db.Column(db.String(36), db.ForeignKey(School.__table__.c.id), nullable=False)
    created_at = db.Column(db.TIMESTAMP, server_default=db.text('CURRENT_TIMESTAMP'))
    
    # Relacionamentos
    plantao = db.relationship('PlantaoOnline', back_populates='plantao_schools')
    school = db.relationship('School')
    
    def __repr__(self):
        return f'<PlantaoOnlineSchool {self.plantao_id} - {self.school_id}>'
