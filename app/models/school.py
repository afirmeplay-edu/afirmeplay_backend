from app import db
import uuid
from sqlalchemy.dialects.postgresql import UUID

class School(db.Model):
    __tablename__ = 'school'

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(100))
    address = db.Column(db.String(200))
    domain = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    city_id = db.Column(db.String, db.ForeignKey('city.id'))
    classes = db.relationship("Class", backref="school")
    school_teachers = db.relationship("SchoolTeacher", backref="school")
