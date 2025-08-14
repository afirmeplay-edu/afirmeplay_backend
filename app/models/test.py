from app import db
import uuid
from sqlalchemy.dialects.postgresql import UUID, JSON
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
    end_time = db.Column(db.DateTime)
    duration = db.Column(db.Integer)  # Duração em minutos
    evaluation_mode = db.Column(db.String(20), default='virtual')  # virtual, physical
    created_by = db.Column(db.String, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, server_default=db.text('CURRENT_TIMESTAMP'))
    updated_at = db.Column(db.DateTime, server_default=db.text('CURRENT_TIMESTAMP'), onupdate=db.text('CURRENT_TIMESTAMP'))
    subject = db.Column(db.String, db.ForeignKey('subject.id'), nullable=True)
    grade_id = db.Column(UUID(as_uuid=True), db.ForeignKey("grade.id"))
    
    # Novos campos
    municipalities = db.Column(JSON)  # Lista de municípios
    schools = db.Column(JSON)  # Lista de escolas
    course = db.Column(db.String(100))  # Curso (Ensino Fundamental, etc)
    model = db.Column(db.String(50))  # SAEB, PROVA, etc
    subjects_info = db.Column(JSON)  # Informações sobre as disciplinas e quantidade de questões
    status = db.Column(db.String(20), default='pendente')  # agendada, em_andamento, concluida, cancelada
    grade_calculation_type = db.Column(db.String(20), default='complex')  # complex, simple

    # Relacionamentos
    creator = db.relationship('User', foreign_keys=[created_by])
    subject_rel = db.relationship('Subject', foreign_keys=[subject])
    grade = db.relationship('Grade', foreign_keys=[grade_id])
    class_tests = db.relationship("ClassTest", backref="test")
    
    # Relacionamento many-to-many com Question através da tabela de associação
    test_questions = db.relationship('TestQuestion', back_populates='test', cascade='all, delete-orphan')
    
    @property
    def questions(self):
        """Retorna as questões ordenadas"""
        return [tq.question for tq in sorted(self.test_questions, key=lambda x: x.order or 0)]
    
    # Relacionamento para acessar as classes onde a avaliação foi aplicada
    @property
    def applied_classes(self):
        """Retorna as classes onde esta avaliação foi aplicada."""
        from app.models.studentClass import Class
        from app.models.classTest import ClassTest
        
        class_ids = [ct.class_id for ct in self.class_tests]
        return Class.query.filter(Class.id.in_(class_ids)).all() if class_ids else []
    
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