# -*- coding: utf-8 -*-
"""
Modelos para o sistema de competições
"""

from app import db
import uuid
from sqlalchemy.dialects.postgresql import UUID, JSON, ARRAY
from datetime import datetime
from enum import Enum


class ModoSelecaoEnum(Enum):
    """Modo de seleção de questões para a competição"""
    MANUAL = "manual"
    AUTOMATICO = "automatico"


class CompetitionStatusEnum(Enum):
    """Status da competição"""
    AGENDADA = "agendada"
    ABERTA = "aberta"
    EM_ANDAMENTO = "em_andamento"
    FINALIZADA = "finalizada"
    CANCELADA = "cancelada"


class EnrollmentStatusEnum(Enum):
    """Status da inscrição do aluno"""
    INSCRITO = "inscrito"
    INICIADO = "iniciado"
    FINALIZADO = "finalizado"
    CANCELADO = "cancelado"


class Competition(db.Model):
    """
    Modelo para competições
    Baseado em Test, mas com campos específicos para competições
    """
    __tablename__ = 'competitions'
    
    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(500))
    instrucoes = db.Column(db.String(500))
    
    # Campos específicos de competição
    recompensas = db.Column(JSON, nullable=True)  # {ouro: 100, prata: 50, bronze: 25, participacao: 10}
    modo_selecao = db.Column(db.String(20), default='manual')  # 'manual' | 'automatico'
    icone = db.Column(db.String(100), nullable=True)
    cor = db.Column(db.String(20), nullable=True)
    dificuldade = db.Column(ARRAY(db.String), nullable=True)  # ['facil', 'medio', 'dificil']
    participantes_atual = db.Column(db.Integer, default=0)
    total_moedas_distribuidas = db.Column(db.Integer, default=0)
    
    # Campos herdados de Test
    type = db.Column(db.String)
    max_score = db.Column(db.Float)
    time_limit = db.Column(db.TIMESTAMP)  # Data/hora limite para iniciar
    end_time = db.Column(db.TIMESTAMP)  # Data/hora de término
    duration = db.Column(db.Integer)  # Duração em minutos
    evaluation_mode = db.Column(db.String(20), default='virtual')
    created_by = db.Column(db.String, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.TIMESTAMP, server_default=db.text('CURRENT_TIMESTAMP'))
    updated_at = db.Column(db.TIMESTAMP, server_default=db.text('CURRENT_TIMESTAMP'), onupdate=db.text('CURRENT_TIMESTAMP'))
    subject = db.Column(db.String, db.ForeignKey('subject.id'), nullable=True)
    grade_id = db.Column(UUID(as_uuid=True), db.ForeignKey("grade.id"))
    
    # Campos de escopo (herdados de Test)
    municipalities = db.Column(JSON)
    schools = db.Column(JSON)
    classes = db.Column(JSON)
    course = db.Column(db.String(100))
    model = db.Column(db.String(50))
    subjects_info = db.Column(JSON)
    status = db.Column(db.String(20), default='agendada')  # agendada, aberta, em_andamento, finalizada, cancelada
    grade_calculation_type = db.Column(db.String(20), default='complex')
    
    # Limite de participantes
    max_participantes = db.Column(db.Integer, nullable=True)
    
    # Relacionamentos
    creator = db.relationship('User', foreign_keys=[created_by])
    subject_rel = db.relationship('Subject', foreign_keys=[subject])
    grade = db.relationship('Grade', foreign_keys=[grade_id])
    # Reutiliza ClassTest - relacionamento via test_id (competition.id será usado como test_id)
    class_tests = db.relationship("ClassTest", foreign_keys="ClassTest.test_id", primaryjoin="Competition.id == ClassTest.test_id", viewonly=True)
    
    # Relacionamento many-to-many com Question através da tabela de associação específica para competições
    competition_questions = db.relationship('CompetitionQuestion', back_populates='competition', cascade='all, delete-orphan')
    
    # Relacionamentos específicos de competição
    enrollments = db.relationship('CompetitionEnrollment', back_populates='competition', cascade='all, delete-orphan')
    results = db.relationship('CompetitionResult', back_populates='competition', cascade='all, delete-orphan')
    
    @property
    def questions(self):
        """Retorna as questões ordenadas"""
        from app.models.question import Question
        
        competition_questions = CompetitionQuestion.query.filter_by(competition_id=self.id).order_by(CompetitionQuestion.order).all()
        question_ids = [cq.question_id for cq in competition_questions]
        
        if not question_ids:
            return []
        
        questions = Question.query.filter(Question.id.in_(question_ids)).all()
        questions_dict = {q.id: q for q in questions}
        ordered_questions = []
        for cq in competition_questions:
            if cq.question_id in questions_dict:
                ordered_questions.append(questions_dict[cq.question_id])
        
        return ordered_questions
    
    def __repr__(self):
        return f'<Competition {self.id}: {self.title}>'


class CompetitionQuestion(db.Model):
    """
    Modelo para associação de questões com competições
    Similar a TestQuestion, mas específico para competições
    """
    __tablename__ = 'competition_questions'
    
    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    competition_id = db.Column(db.String, db.ForeignKey('competitions.id'), nullable=False)
    question_id = db.Column(db.String, db.ForeignKey('question.id'), nullable=False)
    order = db.Column(db.Integer, nullable=True)  # Para manter ordem das questões
    created_at = db.Column(db.TIMESTAMP, server_default=db.text('CURRENT_TIMESTAMP'))
    
    # Relacionamentos
    competition = db.relationship('Competition', back_populates='competition_questions')
    question = db.relationship('Question', backref='competition_questions')
    
    def __repr__(self):
        return f'<CompetitionQuestion {self.competition_id} - {self.question_id}>'


class CompetitionEnrollment(db.Model):
    """
    Modelo para inscrições de alunos em competições
    """
    __tablename__ = 'competition_enrollments'
    
    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    competition_id = db.Column(db.String, db.ForeignKey('competitions.id'), nullable=False)
    student_id = db.Column(db.String, db.ForeignKey('student.id'), nullable=False)
    enrolled_at = db.Column(db.TIMESTAMP, server_default=db.text('CURRENT_TIMESTAMP'))
    status = db.Column(db.String(20), default='inscrito')  # inscrito, iniciado, finalizado, cancelado
    
    # Constraint único para evitar inscrições duplicadas
    __table_args__ = (db.UniqueConstraint('competition_id', 'student_id', name='uq_competition_student'),)
    
    # Relacionamentos
    competition = db.relationship('Competition', back_populates='enrollments')
    student = db.relationship('Student', backref='competition_enrollments')
    
    def __repr__(self):
        return f'<CompetitionEnrollment {self.id}: Competition {self.competition_id}, Student {self.student_id}>'


class CompetitionResult(db.Model):
    """
    Modelo para resultados de competições
    Baseado em EvaluationResult, mas com campos específicos de competição
    """
    __tablename__ = 'competition_results'
    
    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    competition_id = db.Column(db.String, db.ForeignKey('competitions.id'), nullable=False)
    student_id = db.Column(db.String, db.ForeignKey('student.id'), nullable=False)
    session_id = db.Column(db.String, db.ForeignKey('test_sessions.id'), nullable=False)
    
    # Dados de cálculo (herdados de EvaluationResult)
    correct_answers = db.Column(db.Integer, nullable=False)
    total_questions = db.Column(db.Integer, nullable=False)
    score_percentage = db.Column(db.Float, nullable=False)
    grade = db.Column(db.Float, nullable=False)
    proficiency = db.Column(db.Float, nullable=False)
    classification = db.Column(db.String(50), nullable=False)
    
    # Campos específicos de competição
    posicao = db.Column(db.Integer, nullable=True)  # Ranking (1º, 2º, 3º, etc)
    moedas_ganhas = db.Column(db.Integer, default=0)
    tempo_gasto = db.Column(db.Integer, nullable=True)  # Tempo em segundos
    acertos = db.Column(db.Integer, nullable=False)  # Mesmo que correct_answers, mantido para compatibilidade
    erros = db.Column(db.Integer, nullable=False)
    em_branco = db.Column(db.Integer, nullable=False)
    
    # Metadados
    calculated_at = db.Column(db.TIMESTAMP, default=datetime.utcnow)
    
    # Relacionamentos
    competition = db.relationship('Competition', back_populates='results')
    student = db.relationship('Student', backref='competition_results')
    session = db.relationship('TestSession', backref='competition_results')
    
    def __init__(self, competition_id, student_id, session_id, correct_answers, total_questions,
                 score_percentage, grade, proficiency, classification, **kwargs):
        """
        Construtor customizado para CompetitionResult
        """
        self.competition_id = competition_id
        self.student_id = student_id
        self.session_id = session_id
        self.correct_answers = correct_answers
        self.acertos = correct_answers  # Mesmo valor
        self.total_questions = total_questions
        self.score_percentage = score_percentage
        self.grade = grade
        self.proficiency = proficiency
        self.classification = classification
        
        # Calcular erros e em branco se não fornecidos
        if 'erros' not in kwargs:
            self.erros = total_questions - correct_answers
        if 'em_branco' not in kwargs:
            self.em_branco = 0  # Será calculado depois
        
        # Aplicar qualquer outro parâmetro
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
    
    def to_dict(self):
        """Converte o objeto para dicionário"""
        return {
            'id': self.id,
            'competition_id': self.competition_id,
            'student_id': self.student_id,
            'session_id': self.session_id,
            'correct_answers': self.correct_answers,
            'total_questions': self.total_questions,
            'score_percentage': self.score_percentage,
            'grade': self.grade,
            'proficiency': self.proficiency,
            'classification': self.classification,
            'posicao': self.posicao,
            'moedas_ganhas': self.moedas_ganhas,
            'tempo_gasto': self.tempo_gasto,
            'acertos': self.acertos,
            'erros': self.erros,
            'em_branco': self.em_branco,
            'calculated_at': self.calculated_at.isoformat() if self.calculated_at else None
        }
    
    def __repr__(self):
        return f'<CompetitionResult {self.id}: Competition {self.competition_id}, Student {self.student_id}, Posição {self.posicao}>'

