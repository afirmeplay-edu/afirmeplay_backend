from app import db
import uuid

class Avaliacao(db.Model):
    __tablename__ = 'avaliacoes'

    id = db.Column(db.String, primary_key=True,default=lambda: str(uuid.uuid4()))
    titulo = db.Column(db.String, nullable=False)
    descricao = db.Column(db.Text)
    tipo = db.Column(db.String, nullable=False)
    assunto = db.Column(db.String, nullable=False)
    grade_level = db.Column(db.String, nullable=False)
    status = db.Column(db.String, nullable=False)
    total_points = db.Column(db.Double, nullable=False)
    time_limit = db.Column(db.DateTime, nullable=False)
    passing_score = db.Column(db.Double, nullable=False)
    random_questions = db.Column(db.Boolean, nullable=False)
    show_results_immediately = db.Column(db.Boolean, nullable=False)
    allow_review = db.Column(db.Boolean, nullable=False)
    instructions = db.Column(db.Text)
    data_aplicacao = db.Column(db.Date)
    escola_id = db.Column(db.String, db.ForeignKey('escolas.id'), nullable=False)
    created_by = db.Column(db.String, nullable=False)
    updated_at = db.Column(db.DateTime, server_default=db.func.now())
    criado_em = db.Column(db.DateTime, server_default=db.func.now())

    questoes = db.relationship('Questao', backref='avaliacao', cascade='all, delete-orphan', lazy=True)