from app import db
from datetime import datetime
import uuid
import json

class BatchCorrectionJob(db.Model):
    """
    Modelo para armazenar jobs de correção em lote de formulários físicos
    """
    __tablename__ = 'batch_correction_jobs'
    __table_args__ = {"schema": "tenant"}

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    test_id = db.Column(db.String(36), nullable=False)  # db.ForeignKey('tests.id') removido temporariamente
    created_by = db.Column(db.String(36), nullable=False)  # db.ForeignKey('public.users.id') removido temporariamente
    
    # Status do job
    status = db.Column(db.String(20), nullable=False, default='pending')  # pending, processing, completed, failed, cancelled
    
    # Contadores
    total_images = db.Column(db.Integer, nullable=False, default=0)
    processed_images = db.Column(db.Integer, nullable=False, default=0)
    successful_corrections = db.Column(db.Integer, nullable=False, default=0)
    failed_corrections = db.Column(db.Integer, nullable=False, default=0)
    
    # Progresso atual
    current_student_id = db.Column(db.String(36), nullable=True)
    current_student_name = db.Column(db.String(255), nullable=True)
    progress_percentage = db.Column(db.Float, nullable=False, default=0.0)
    
    # Dados das imagens
    images_data = db.Column(db.Text, nullable=True)  # JSON com dados das imagens
    gabarito_data = db.Column(db.Text, nullable=True)  # JSON com dados do gabarito gerado
    
    # Resultados
    results = db.Column(db.Text, nullable=True)  # JSON com resultados de cada aluno
    errors = db.Column(db.Text, nullable=True)  # JSON com erros de cada imagem
    
    # Timestamps
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    
    # Estimativas
    estimated_completion = db.Column(db.DateTime, nullable=True)
    
    # Relacionamentos (comentados temporariamente até a migração)
    # test = db.relationship('Test', backref='batch_correction_jobs', foreign_keys=[test_id])
    # creator = db.relationship('User', backref='batch_correction_jobs', foreign_keys=[created_by])
    
    def __init__(self, test_id, created_by, total_images, images_data=None):
        self.test_id = test_id
        self.created_by = created_by
        self.total_images = total_images
        self.images_data = images_data
        self.status = 'pending'
        self.progress_percentage = 0.0
    
    def to_dict(self):
        """Converte o job para dicionário"""
        return {
            'id': self.id,
            'test_id': self.test_id,
            'created_by': self.created_by,
            'status': self.status,
            'total_images': self.total_images,
            'processed_images': self.processed_images,
            'successful_corrections': self.successful_corrections,
            'failed_corrections': self.failed_corrections,
            'current_student_id': self.current_student_id,
            'current_student_name': self.current_student_name,
            'progress_percentage': round(self.progress_percentage, 2),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'estimated_completion': self.estimated_completion.isoformat() if self.estimated_completion else None,
            'has_gabarito': self.gabarito_data is not None
        }
    
    def get_progress_data(self):
        """Retorna dados de progresso para SSE"""
        return {
            'job_id': self.id,
            'status': self.status,
            'total_images': self.total_images,
            'processed_images': self.processed_images,
            'successful_corrections': self.successful_corrections,
            'failed_corrections': self.failed_corrections,
            'current_student_id': self.current_student_id,
            'current_student_name': self.current_student_name,
            'progress_percentage': round(self.progress_percentage, 2),
            'estimated_completion': self.estimated_completion.isoformat() if self.estimated_completion else None
        }
    
    def get_results(self):
        """Retorna resultados finais"""
        results_data = []
        errors_data = []
        
        if self.results:
            try:
                results_data = json.loads(self.results)
            except:
                results_data = []
        
        if self.errors:
            try:
                errors_data = json.loads(self.errors)
            except:
                errors_data = []
        
        return {
            'job_id': self.id,
            'status': self.status,
            'summary': {
                'total_images': self.total_images,
                'processed_images': self.processed_images,
                'successful_corrections': self.successful_corrections,
                'failed_corrections': self.failed_corrections,
                'success_rate': round((self.successful_corrections / self.total_images) * 100, 2) if self.total_images > 0 else 0
            },
            'results': results_data,
            'errors': errors_data,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None
        }
    
    def update_progress(self, processed_images, successful_corrections, failed_corrections, 
                       current_student_id=None, current_student_name=None):
        """Atualiza progresso do job"""
        self.processed_images = processed_images
        self.successful_corrections = successful_corrections
        self.failed_corrections = failed_corrections
        self.current_student_id = current_student_id
        self.current_student_name = current_student_name
        
        if self.total_images > 0:
            self.progress_percentage = (processed_images / self.total_images) * 100
        
        db.session.commit()
    
    def set_status(self, status):
        """Atualiza status do job"""
        self.status = status
        
        if status == 'processing' and not self.started_at:
            self.started_at = datetime.utcnow()
        elif status in ['completed', 'failed', 'cancelled'] and not self.completed_at:
            self.completed_at = datetime.utcnow()
        
        db.session.commit()
    
    def add_result(self, student_id, student_name, result_data):
        """Adiciona resultado de um aluno"""
        results = []
        if self.results:
            try:
                results = json.loads(self.results)
            except:
                results = []
        
        results.append({
            'student_id': student_id,
            'student_name': student_name,
            'result': result_data,
            'processed_at': datetime.utcnow().isoformat()
        })
        
        self.results = json.dumps(results)
        db.session.commit()
    
    def add_error(self, image_index, error_message, student_id=None):
        """Adiciona erro de uma imagem"""
        errors = []
        if self.errors:
            try:
                errors = json.loads(self.errors)
            except:
                errors = []
        
        errors.append({
            'image_index': image_index,
            'student_id': student_id,
            'error': error_message,
            'occurred_at': datetime.utcnow().isoformat()
        })
        
        self.errors = json.dumps(errors)
        db.session.commit()
    
    def set_gabarito_data(self, gabarito_data):
        """Define dados do gabarito gerado"""
        self.gabarito_data = json.dumps(gabarito_data)
        db.session.commit()
    
    def get_gabarito_data(self):
        """Retorna dados do gabarito"""
        if self.gabarito_data:
            try:
                return json.loads(self.gabarito_data)
            except:
                return None
        return None
    
    def __repr__(self):
        return f'<BatchCorrectionJob {self.id}: {self.status} ({self.processed_images}/{self.total_images})>'

