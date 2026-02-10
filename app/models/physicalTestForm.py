from app import db
import uuid
from datetime import datetime
from sqlalchemy.dialects.postgresql import UUID, JSON

class PhysicalTestForm(db.Model):
    """
    Modelo para gerenciar formulários físicos de provas
    Armazena informações sobre formulários gerados para cada aluno
    """
    __tablename__ = 'physical_test_forms'

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    test_id = db.Column(db.String, db.ForeignKey('test.id'), nullable=False)
    student_id = db.Column(db.String, db.ForeignKey('student.id'), nullable=False)
    class_test_id = db.Column(db.String, db.ForeignKey('class_test.id'), nullable=False)
    
    # Dados dos arquivos gerados (salvos no banco)
    form_pdf_data = db.Column(db.LargeBinary, nullable=True)  # PDF com prova + formulário (bytes)
    answer_sheet_data = db.Column(db.LargeBinary, nullable=True)  # Gabarito de resposta (bytes)
    correction_image_data = db.Column(db.LargeBinary, nullable=True)  # Imagem corrigida (bytes)
    
    # URLs dos arquivos (opcional, para compatibilidade)
    form_pdf_url = db.Column(db.String, nullable=True)  # URL do PDF com prova + formulário
    answer_sheet_url = db.Column(db.String, nullable=True)  # URL do gabarito de resposta
    correction_image_url = db.Column(db.String, nullable=True)  # URL da imagem corrigida
    
    # Dados do QR Code
    qr_code_data = db.Column(db.String, nullable=False)  # Dados únicos do QR Code
    qr_code_coordinates = db.Column(db.JSON, nullable=True)  # Coordenadas do QR Code no formulário
    
    # Status do formulário
    status = db.Column(db.String, default='gerado')  # gerado, preenchido, corrigido, processado
    is_corrected = db.Column(db.Boolean, default=False)
    form_type = db.Column(db.String, default='institutional')  # institutional, projeto_style
    
    # =========================================================================
    # ✅ CAMPOS PARA CORREÇÃO (adicionados para separar de AnswerSheetGabarito)
    # =========================================================================
    # Configuração do formulário físico (similar ao AnswerSheetGabarito)
    num_questions = db.Column(db.Integer, nullable=True)  # Total de questões
    use_blocks = db.Column(db.Boolean, default=False)  # Se usa blocos
    blocks_config = db.Column(JSON, nullable=True)  # {num_blocks, questions_per_block, topology: {...}}
    correct_answers = db.Column(JSON, nullable=True)  # {1: "A", 2: "B", ...}
    # =========================================================================
    
    # Metadados
    generated_at = db.Column(db.DateTime, default=datetime.utcnow)
    corrected_at = db.Column(db.DateTime, nullable=True)
    processed_at = db.Column(db.DateTime, nullable=True)
    answer_sheet_sent_at = db.Column(db.DateTime, nullable=True)  # Data em que o formulário foi marcado como enviado
    
    # Relacionamentos
    test = db.relationship('Test', backref='physical_forms')
    student = db.relationship('Student', backref='physical_forms')
    class_test = db.relationship('ClassTest', backref='physical_forms')
    
    # Relacionamento com respostas físicas
    physical_answers = db.relationship('PhysicalTestAnswer', backref='physical_form', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<PhysicalTestForm {self.id}: Student {self.student_id}, Test {self.test_id}>'
    
    def to_dict(self):
        # Para formulários combinados (QR code = 'combined'), usar nome da prova
        if self.qr_code_data == 'combined':
            # Buscar nome da prova
            test_name = None
            if self.test_id:
                from app.models.test import Test
                test = Test.query.get(self.test_id)
                if test:
                    test_name = test.title
            
            student_name = test_name or 'Prova Completa'
        else:
            # Para formulários individuais, buscar nome do aluno
            student_name = None
            if self.student_id:
                from app.models.student import Student
                student = Student.query.get(self.student_id)
                if student:
                    student_name = student.name
        
        return {
            'id': self.id,
            'test_id': self.test_id,
            'student_id': self.student_id,
            'student_name': student_name,  # Nome da prova para combinados, nome do aluno para individuais
            'class_test_id': self.class_test_id,
            'form_pdf_url': self.form_pdf_url,
            'answer_sheet_url': self.answer_sheet_url,
            'correction_image_url': self.correction_image_url,
            'has_pdf_data': self.form_pdf_data is not None,
            'has_answer_sheet_data': self.answer_sheet_data is not None,
            'has_correction_data': self.correction_image_data is not None,
            'qr_code_data': self.qr_code_data,
            'qr_code_coordinates': self.qr_code_coordinates,
            'status': self.status,
            'is_corrected': self.is_corrected,
            'form_type': self.form_type,
            'generated_at': self.generated_at.isoformat() if self.generated_at else None,
            'corrected_at': self.corrected_at.isoformat() if self.corrected_at else None,
            'processed_at': self.processed_at.isoformat() if self.processed_at else None,
            'answer_sheet_sent_at': self.answer_sheet_sent_at.isoformat() if self.answer_sheet_sent_at else None,
            'created_at': self.generated_at.isoformat() if self.generated_at else None  # Alias para compatibilidade
        }
