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
    
    # Controle de tempo simplificado
    started_at = db.Column(db.TIMESTAMP, nullable=True)  # Quando o aluno iniciou
    actual_start_time = db.Column(db.TIMESTAMP, nullable=True)  # Tempo real de início
    submitted_at = db.Column(db.TIMESTAMP, nullable=True)  # Quando o aluno finalizou
    time_limit_minutes = db.Column(db.Integer, nullable=True)  # Tempo limite em minutos
    # Pausa do timer: descomente após rodar a migration/SQL que adiciona as colunas em TODOS os schemas (public + city_xxx)
    # paused_at = db.Column(db.TIMESTAMP, nullable=True)
    # total_paused_seconds = db.Column(db.Integer, default=0, nullable=False)

    # Status da sessão
    status = db.Column(db.String(20), default='em_andamento')  # em_andamento, finalizada, expirada, corrigida, revisada
    
    # Resultados
    total_questions = db.Column(db.Integer, nullable=True)
    correct_answers = db.Column(db.Integer, nullable=True)
    score = db.Column(db.Float, nullable=True)
    grade = db.Column(db.Float, nullable=True)  # nota final (0-10)
    manual_score = db.Column(db.Numeric(5, 2), nullable=True)  # Nota manual do professor
    
    # Campos para correção
    feedback = db.Column(db.Text, nullable=True)  # Feedback geral do professor
    corrected_by = db.Column(db.String, db.ForeignKey('users.id'), nullable=True)  # Professor que corrigiu
    corrected_at = db.Column(db.TIMESTAMP, nullable=True)  # Data da correção
    
    # Metadados
    ip_address = db.Column(db.String(45), nullable=True)  # IP do aluno
    user_agent = db.Column(db.Text, nullable=True)  # navegador usado
    
    created_at = db.Column(db.TIMESTAMP, default=datetime.utcnow)
    updated_at = db.Column(db.TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow)
    
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
        
        # Aplicar qualquer outro parâmetro
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
    
    @property
    def duration_minutes(self):
        """Retorna a duração da sessão em minutos (tempo decorrido entre started_at e submitted_at ou agora)."""
        if not self.started_at:
            return 0
        try:
            from datetime import timezone
            end_time = self.submitted_at or datetime.utcnow()
            start = self.started_at
            if start.tzinfo and not getattr(end_time, 'tzinfo', None):
                end_time = end_time.replace(tzinfo=timezone.utc)
            elif getattr(end_time, 'tzinfo', None) and not start.tzinfo:
                start = start.replace(tzinfo=timezone.utc) if hasattr(start, 'replace') else start
            duration = end_time - start
            return int(duration.total_seconds() / 60)
        except (TypeError, AttributeError):
            return 0
    
    def calculate_grade(self):
        """Calcula a nota final baseada nos acertos"""
        if not self.total_questions or self.total_questions <= 0 or self.correct_answers is None:
            return None
        
        percentage = (self.correct_answers / self.total_questions) * 100
        grade = (percentage / 100) * 10  # nota de 0 a 10
        return round(grade, 2)
    
    def start_session(self):
        """Inicia a sessão (define started_at)"""
        if not self.started_at:
            self.started_at = datetime.utcnow()
    
    def finalize_session(self, correct_answers=None, total_questions=None):
        """Finaliza a sessão e calcula a nota"""
        self.submitted_at = datetime.utcnow()
        self.status = 'finalizada'
        
        if correct_answers is not None:
            self.correct_answers = correct_answers
        if total_questions is not None:
            self.total_questions = total_questions
            
        if self.correct_answers is not None and self.total_questions and self.total_questions > 0:
            self.score = (self.correct_answers / self.total_questions) * 100
            self.grade = self.calculate_grade()
    
    def __repr__(self):
        return f'<TestSession {self.id}: Student {self.student_id}, Test {self.test_id}>' 