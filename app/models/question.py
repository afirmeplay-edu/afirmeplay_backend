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
    secondstatement = db.Column(db.String)
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
    
    