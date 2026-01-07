from app import db
import uuid

class School(db.Model):
    __tablename__ = 'school'

    # ✅ CORRIGIDO: Explicitamente String(36) para garantir tipo correto no mapper
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(100))
    address = db.Column(db.String(200))
    domain = db.Column(db.String(100))
    created_at = db.Column(db.TIMESTAMP, server_default=db.func.now())

    city_id = db.Column(db.String, db.ForeignKey('city.id'))
    # ✅ CORRIGIDO: Relationship unidirecional (Class usa property em vez de relationship)
    # Isso evita problemas de tipo UUID vs VARCHAR no lazy load
    classes = db.relationship("Class", foreign_keys="Class._school_id", primaryjoin="School.id == Class._school_id", viewonly=True)
    school_teachers = db.relationship("SchoolTeacher", backref="school")
    students = db.relationship("Student", backref="school")
    # Relacionamento com cursos vinculados (não usar backref aqui para evitar conflito)
