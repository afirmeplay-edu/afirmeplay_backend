from app import db
import uuid


class Subject(db.Model):
    __tablename__ = 'subject'

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(100))

    # tests = db.relationship("Test", backref="subject")
    questions = db.relationship("Question", backref="subject")
    class_subjects = db.relationship("ClassSubject", backref="subject")