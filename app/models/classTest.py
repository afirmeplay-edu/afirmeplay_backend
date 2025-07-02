from app import db
from sqlalchemy.dialects.postgresql import UUID
import uuid

class ClassTest(db.Model):
    __tablename__ = 'class_test'

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    class_id = db.Column(db.String, db.ForeignKey('class.id'))
    test_id = db.Column(db.String, db.ForeignKey('test.id'))
    status = db.Column(db.String, default='agendada')
    application = db.Column(db.DateTime)
    expiration = db.Column(db.DateTime)