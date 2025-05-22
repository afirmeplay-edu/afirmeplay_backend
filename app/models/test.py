from app import db
import uuid
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime

class Test(db.Model):
    __tablename__ = 'test'

    id = db.Column(db.String, primary_key=True,default=lambda: str(uuid.uuid4()))
    title = db.Column(db.String(100))
    description = db.Column(db.String(500))
    intructions = db.Column(db.String(500))
    type = db.Column(db.String)
    max_score = db.Column(db.Float)
    time_limit = db.Column(db.DateTime)
    created_by = db.Column(db.String, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    subject = db.Column(db.String, db.ForeignKey('subject.id'))
    grade_id = db.Column(UUID(as_uuid=True), db.ForeignKey("grade.id"))

    questions = db.relationship("Question", backref="test")
    class_tests = db.relationship("ClassTest", backref="test")
    # titulo = db.Column(db.String, nullable=False)
    # descricao = db.Column(db.Text)
    # tipo = db.Column(db.String, nullable=False)
    # assunto = db.Column(db.String, nullable=False)
    # grade_level = db.Column(db.String, nullable=False)
    # status = db.Column(db.String, nullable=False)
    # total_points = db.Column(db.Double, nullable=False)
    # time_limit = db.Column(db.DateTime, nullable=False)
    # passing_score = db.Column(db.Double, nullable=False)
    # random_questions = db.Column(db.Boolean, nullable=False)
    # show_results_immediately = db.Column(db.Boolean, nullable=False)
    # allow_review = db.Column(db.Boolean, nullable=False)
    # instructions = db.Column(db.Text)
    # data_aplicacao = db.Column(db.Date)
    # escola_id = db.Column(db.String, db.ForeignKey('escolas.id'), nullable=False)