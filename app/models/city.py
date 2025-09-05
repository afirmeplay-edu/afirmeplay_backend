from app import db
import uuid

class City(db.Model):
    __tablename__ = 'city'

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(100))
    state = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.TIMESTAMP, server_default=db.func.now())

    schools = db.relationship("School", backref="city")