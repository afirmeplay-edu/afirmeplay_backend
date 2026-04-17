from app import db
import uuid
from sqlalchemy.dialects.postgresql import UUID, JSON, BYTEA
from datetime import datetime

class Question(db.Model):
    __tablename__ = 'question'
    __table_args__ = {"schema": "public"}

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    number = db.Column(db.Integer)  # Número da questão
    text = db.Column(db.String)  # Texto simples da questão
    formatted_text = db.Column(db.Text)  # Texto formatado em HTML
    secondstatement = db.Column(db.String)
    images = db.Column(JSON)  # Array de objetos com informações das imagens (armazenadas no MinIO)
    # Estrutura: id, type, width, height, minio_bucket, minio_object_name (sem "data").
    # Exemplo: {"id": "uuid", "type": "image/png", "width": 300, "height": 200,
    #           "minio_bucket": "question-images", "minio_object_name": "{question_id}/{image_id}.png"}
    subject_id = db.Column(db.String, db.ForeignKey('public.subject.id'))
    title = db.Column(db.String)
    description = db.Column(db.String)
    command = db.Column(db.String)
    subtitle = db.Column(db.String)
    alternatives = db.Column(db.JSON)  # Array de opções com formatação
    skill = db.Column(db.String)
    grade_level = db.Column(UUID(as_uuid=True), db.ForeignKey('public.grade.id'))
    education_stage_id = db.Column(UUID(as_uuid=True), db.ForeignKey('public.education_stage.id'))
    difficulty_level = db.Column(db.String)
    correct_answer = db.Column(db.String)
    formatted_solution = db.Column(db.Text)  # Solução formatada em HTML
    # test_id = db.Column(db.String, db.ForeignKey('tenant.test.id'))  # REMOVIDO - agora usamos tabela de associação
    question_type = db.Column(db.String)  # multipleChoice, essay, etc
    value = db.Column(db.Float)  # Valor da questão
    topics = db.Column(db.JSON)  # Array de tópicos
    version = db.Column(db.Integer, default=1)  # Versão da questão
    created_by = db.Column(db.String, db.ForeignKey('public.users.id'))
    created_at = db.Column(db.TIMESTAMP, server_default=db.text('CURRENT_TIMESTAMP'))
    updated_at = db.Column(db.TIMESTAMP, server_default=db.text('CURRENT_TIMESTAMP'), onupdate=db.text('CURRENT_TIMESTAMP'))
    last_modified_by = db.Column(db.String, db.ForeignKey('public.users.id'))
    
    # Campos de escopo multitenant
    scope_type = db.Column(db.String, default='GLOBAL')  # 'GLOBAL', 'CITY' ou 'PRIVATE'
    owner_city_id = db.Column(db.String, db.ForeignKey('public.city.id'))  # ID do município dono (para CITY)
    owner_user_id = db.Column(db.String, db.ForeignKey('public.users.id'))  # ID do usuário dono (para PRIVATE)
    approved_by = db.Column(db.String, db.ForeignKey('public.users.id'))  # Quem aprovou para uso global
    approved_at = db.Column(db.TIMESTAMP)  # Data de aprovação para uso global
    
    # Relacionamentos
    subject = db.relationship('Subject', backref='questions')
    grade = db.relationship('Grade', backref='questions')
    education_stage = db.relationship('EducationStage', backref='questions')
    # test = db.relationship('Test', backref='questions')  # REMOVIDO - agora usamos tabela de associação
    
    # Relacionamento many-to-many com Test através da tabela de associação
    test_questions = db.relationship('TestQuestion', back_populates='question', cascade='all, delete-orphan')

    # Relacionamento com StudentAnswer para permitir exclusão em cascata
    student_answers = db.relationship('StudentAnswer', backref='question', cascade='all, delete-orphan')
    
    @property
    def tests(self):
        """Retorna os testes que usam esta questão"""
        return [tq.test for tq in self.test_questions]
    
    creator = db.relationship('User', foreign_keys=[created_by])
    last_modifier = db.relationship('User', foreign_keys=[last_modified_by])
    
    