from app import db
import uuid
from sqlalchemy.dialects.postgresql import UUID, JSON, BYTEA
from datetime import datetime

class Question(db.Model):
    __tablename__ = 'question'

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    number = db.Column(db.Integer)  # Número da questão
    text = db.Column(db.String)  # Texto simples da questão
    formatted_text = db.Column(db.Text)  # Texto formatado em HTML
    images = db.Column(JSON)  # Array de objetos com informações das imagens
    # Exemplo de estrutura do images:
    # [
    #   {
    #     "id": "uuid",
    #     "name": "nome_do_arquivo.jpg",
    #     "type": "image/jpeg",
    #     "size": 12345,
    #     "url": "caminho/para/imagem.jpg" ou null se armazenada em BYTEA
    #     "data": "base64_ou_bytes" ou null se armazenada em URL
    #   }
    # ]
    subject_id = db.Column(db.String, db.ForeignKey('subject.id'))
    title = db.Column(db.String)
    description = db.Column(db.String)
    command = db.Column(db.String)
    subtitle = db.Column(db.String)
    alternatives = db.Column(db.JSON)  # Array de opções com formatação
    skill = db.Column(db.String)
    grade_level = db.Column(UUID(as_uuid=True), db.ForeignKey('grade.id'))
    education_stage_id = db.Column(UUID(as_uuid=True), db.ForeignKey('education_stage.id'))
    difficulty_level = db.Column(db.String)
    correct_answer = db.Column(db.String)
    formatted_solution = db.Column(db.Text)  # Solução formatada em HTML
    test_id = db.Column(db.String, db.ForeignKey('test.id'))
    question_type = db.Column(db.String)  # multipleChoice, essay, etc
    value = db.Column(db.Float)  # Valor da questão
    topics = db.Column(db.JSON)  # Array de tópicos
    version = db.Column(db.Integer, default=1)  # Versão da questão
    created_by = db.Column(db.String, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, server_default=db.text('CURRENT_TIMESTAMP'))
    updated_at = db.Column(db.DateTime, server_default=db.text('CURRENT_TIMESTAMP'), onupdate=db.text('CURRENT_TIMESTAMP'))
    last_modified_by = db.Column(db.String, db.ForeignKey('users.id'))
    
    # Relacionamentos
    subject = db.relationship('Subject', backref='questions')
    grade = db.relationship('Grade', backref='questions')
    education_stage = db.relationship('EducationStage', backref='questions')
    test = db.relationship('Test', backref='questions')
    creator = db.relationship('User', foreign_keys=[created_by])
    last_modifier = db.relationship('User', foreign_keys=[last_modified_by])
    
    # title = db.Column(db.String, nullable=False)
    # description = db.Column(db.Text)
    # command = db.Column(db.Text)  # Enunciado principal
    # subtitle = db.Column(db.String)  # Subtítulo ou descrição adicional
    # alternativas = db.Column(db.JSON)
    # skill = db.Column(db.String)  # Habilidade ou competência
    # subject = db.Column(db.String)  # Matéria
    # question_type = db.Column(db.Enum('multiplaescolha', 'verdadeirofalso', 'dissertativa', name='question_type_enum'), nullable=False)
    # grade_level = db.Column(db.String)  # Série ou ano escolar
    # difficulty_level = db.Column(db.String)  # Ex: fácil, médio, difícil
    # correct_answer = db.Column(db.Text)  # Pode ser string, boolean ou texto dissertativo
    # avaliacao_id = db.Column(db.String, db.ForeignKey('avaliacoes.id'))
    # criado_em = db.Column(db.DateTime, server_default=db.func.now())
    # created_by = db.Column(db.String)  # ID do criador (usuário)
    # updated_at = db.Column(db.DateTime, onupdate=db.func.now())
    
    # resource_type = db.Column(db.Enum('text', 'image', name='resource_type_enum'), nullable=True)
    # resource_content = db.Column(db.Text)  # Pode ser texto ou caminho de imagem
    # status = db.Column(db.Enum('active', 'inactive', name='status_enum'), default='active')
    # tags = db.Column(db.ARRAY(db.String))  # Lista de tags
    # escola_id = db.Column(db.String, db.ForeignKey('escolas.id'), nullable=False)