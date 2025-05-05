from app import db
import uuid

class Questao(db.Model):
    __tablename__ = 'questoes'

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title = db.Column(db.String, nullable=False)
    description = db.Column(db.Text)
    resource_type = db.Column(db.Enum('text', 'image', name='resource_type_enum'), nullable=True)
    resource_content = db.Column(db.Text)  # Pode ser texto ou caminho de imagem
    command = db.Column(db.Text)  # Enunciado principal
    question_type = db.Column(db.Enum('multiplaescolha', 'verdadeirofalso', 'dissertativa', name='question_type_enum'), nullable=False)
    subject = db.Column(db.String)  # Matéria
    grade_level = db.Column(db.String)  # Série ou ano escolar
    difficulty_level = db.Column(db.String)  # Ex: fácil, médio, difícil
    status = db.Column(db.Enum('active', 'inactive', name='status_enum'), default='active')
    correct_answer = db.Column(db.Text)  # Pode ser string, boolean ou texto dissertativo
    tags = db.Column(db.ARRAY(db.String))  # Lista de tags
    avaliacao_id = db.Column(db.String, db.ForeignKey('avaliacoes.id'))
    alternativas = db.Column(db.JSON)
    tenant_id = db.Column(db.String, db.ForeignKey('escolas.id'), nullable=False)
    criado_em = db.Column(db.DateTime, server_default=db.func.now())
    created_by = db.Column(db.String)  # ID do criador (usuário)
    updated_at = db.Column(db.DateTime, onupdate=db.func.now())