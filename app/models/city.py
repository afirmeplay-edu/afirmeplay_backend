from app import db
import uuid

class City(db.Model):
    __tablename__ = 'city'
    __table_args__ = {"schema": "public"}

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(100))
    state = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(100), unique=True, nullable=False)
    created_at = db.Column(db.TIMESTAMP, server_default=db.func.now())

    # Chaves de objeto no bucket MUNICIPALITY_LOGOS (ex.: cities/<id>/logo.png)
    logo_url = db.Column(db.Text, nullable=True)
    letterhead_image_url = db.Column(db.Text, nullable=True)
    letterhead_pdf_url = db.Column(db.Text, nullable=True)

    schools = db.relationship("School", backref="city")