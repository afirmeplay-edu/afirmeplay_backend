from app import db
from datetime import datetime
import uuid

class TestSession(db.Model):
    """
    Modelo para rastrear sessões de prova dos alunos
    """
    __tablename__ = 'test_sessions'
    
    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id = db.Column(db.String, db.ForeignKey('student.id'), nullable=False)
    test_id = db.Column(db.String, db.ForeignKey('test.id'), nullable=False)
    
    # Controle de tempo
    started_at = db.Column(db.DateTime, nullable=True)  # Só definido quando efetivamente iniciar
    submitted_at = db.Column(db.DateTime, nullable=True)
    time_limit_minutes = db.Column(db.Integer, nullable=True)  # tempo limite em minutos
    actual_start_time = db.Column(db.DateTime, nullable=True)  # Momento real que o aluno iniciou
    
    # Status da sessão
    status = db.Column(db.String(20), default='em_andamento')  # em_andamento, finalizada, expirada, corrigida, revisada
    
    # Resultados
    total_questions = db.Column(db.Integer, nullable=True)
    correct_answers = db.Column(db.Integer, nullable=True)
    score = db.Column(db.Float, nullable=True)
    grade = db.Column(db.Float, nullable=True)  # nota final (0-10)
    
    # Campos para correção
    feedback = db.Column(db.Text, nullable=True)  # Feedback geral do professor
    corrected_by = db.Column(db.String, db.ForeignKey('users.id'), nullable=True)  # Professor que corrigiu
    corrected_at = db.Column(db.DateTime, nullable=True)  # Data da correção
    
    # Metadados
    ip_address = db.Column(db.String(45), nullable=True)  # IP do aluno
    user_agent = db.Column(db.Text, nullable=True)  # navegador usado
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    student = db.relationship('Student', backref='test_sessions')
    test = db.relationship('Test', backref='test_sessions')
    
    def __init__(self, student_id, test_id, time_limit_minutes=None, ip_address=None, user_agent=None, **kwargs):
        """
        Construtor customizado para TestSession
        """
        self.student_id = student_id
        self.test_id = test_id
        self.time_limit_minutes = time_limit_minutes
        self.ip_address = ip_address
        self.user_agent = user_agent
        
        # Definir started_at automaticamente quando a sessão é criada
        self.started_at = datetime.utcnow()
        
        # Aplicar qualquer outro parâmetro
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
    
    @property
    def is_expired(self):
        """Verifica se a sessão expirou baseado no tempo limite"""
        if not self.time_limit_minutes or self.status != 'em_andamento' or not self.actual_start_time:
            return False
        
        from datetime import timedelta
        limit = self.actual_start_time + timedelta(minutes=self.time_limit_minutes)
        return datetime.utcnow() > limit
    
    @property
    def remaining_time_minutes(self):
        """Retorna o tempo restante em minutos"""
        if not self.time_limit_minutes or self.status != 'em_andamento' or not self.actual_start_time:
            return self.time_limit_minutes  # Retorna tempo total se ainda não iniciou
        
        from datetime import timedelta
        limit = self.actual_start_time + timedelta(minutes=self.time_limit_minutes)
        remaining = limit - datetime.utcnow()
        
        if remaining.total_seconds() <= 0:
            return 0
        
        return int(remaining.total_seconds() / 60)
    
    @property
    def duration_minutes(self):
        """Retorna a duração da sessão em minutos"""
        if not self.actual_start_time:
            return 0  # Se não iniciou efetivamente, duração é 0
        
        end_time = self.submitted_at or datetime.utcnow()
        duration = end_time - self.actual_start_time
        return int(duration.total_seconds() / 60)
    
    def calculate_grade(self):
        """Calcula a nota final baseada nos acertos"""
        if not self.total_questions or not self.correct_answers:
            return None
        
        percentage = (self.correct_answers / self.total_questions) * 100
        grade = (percentage / 100) * 10  # nota de 0 a 10
        return round(grade, 2)
    
    def start_timer(self):
        """Inicia efetivamente o cronômetro da avaliação"""
        if not self.actual_start_time:
            self.actual_start_time = datetime.utcnow()
            if not self.started_at:  # Para compatibilidade
                self.started_at = self.actual_start_time
    
    def finalize_session(self, correct_answers=None, total_questions=None):
        """Finaliza a sessão e calcula a nota"""
        self.submitted_at = datetime.utcnow()
        self.status = 'finalizada'
        
        if correct_answers is not None:
            self.correct_answers = correct_answers
        if total_questions is not None:
            self.total_questions = total_questions
            
        if self.correct_answers and self.total_questions:
            self.score = (self.correct_answers / self.total_questions) * 100
            self.grade = self.calculate_grade()
    
    def __repr__(self):
        return f'<TestSession {self.id}: Student {self.student_id}, Test {self.test_id}>' 