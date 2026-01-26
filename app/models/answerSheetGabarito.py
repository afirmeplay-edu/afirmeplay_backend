# -*- coding: utf-8 -*-
"""
Modelo para armazenar gabaritos de cartões resposta
"""

from app import db
from sqlalchemy.dialects.postgresql import UUID, JSON
import uuid
from datetime import datetime


class AnswerSheetGabarito(db.Model):
    """
    Modelo para gerenciar gabaritos de cartões resposta
    Armazena as respostas corretas e configurações do cartão
    
    ✅ TEMPLATE REAL DIGITAL:
    Os campos template_block_1 a template_block_4 armazenam imagens PNG
    dos blocos de questões gerados pelo MESMO pipeline de correção.
    Isso elimina desalinhamento por DPI, escala e geometria.
    """
    __tablename__ = 'answer_sheet_gabaritos'

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Vinculação opcional com prova ou turma
    test_id = db.Column(db.String, db.ForeignKey('test.id'), nullable=True)
    class_id = db.Column(UUID(as_uuid=True), db.ForeignKey('class.id'), nullable=True)
    
    # Configuração do cartão
    num_questions = db.Column(db.Integer, nullable=False)
    use_blocks = db.Column(db.Boolean, default=False)
    blocks_config = db.Column(JSON, nullable=True)  # {num_blocks, questions_per_block, separate_by_subject}
    
    # Gabarito: {1: "A", 2: "B", ...}
    correct_answers = db.Column(JSON, nullable=False)
    
    # Coordenadas ROI das bolhas (geradas automaticamente)
    coordinates = db.Column(JSON, nullable=True)  # {"warped_size": [w, h], "questions": {...}}
    
    # =========================================================================
    # ✅ TEMPLATE REAL DIGITAL — Imagens PNG dos blocos (bytes diretos)
    # =========================================================================
    # Armazena imagens PNG dos blocos gerados pelo MESMO pipeline de correção.
    # - Formato: bytes PNG diretos (cv2.imencode(".png", img)[1].tobytes())
    # - NÃO usa base64 (risco de encoding/serialização)
    # - Cada bloco é salvo separadamente para facilitar acesso
    # - Até 4 blocos suportados (padrão do sistema)
    # =========================================================================
    template_block_1 = db.Column(db.LargeBinary, nullable=True)  # PNG bytes do bloco 1
    template_block_2 = db.Column(db.LargeBinary, nullable=True)  # PNG bytes do bloco 2
    template_block_3 = db.Column(db.LargeBinary, nullable=True)  # PNG bytes do bloco 3
    template_block_4 = db.Column(db.LargeBinary, nullable=True)  # PNG bytes do bloco 4
    
    # Metadados dos templates (para validação)
    template_generated_at = db.Column(db.TIMESTAMP, nullable=True)  # Quando os templates foram gerados
    template_dpi = db.Column(db.Integer, nullable=True)  # DPI usado na renderização (ex: 300)
    
    # Metadados
    title = db.Column(db.String(200), nullable=True)  # Título do cartão resposta
    created_at = db.Column(db.TIMESTAMP, server_default=db.text('CURRENT_TIMESTAMP'))
    created_by = db.Column(db.String, db.ForeignKey('users.id'), nullable=True)
    
    # Informações adicionais da avaliação (para relatórios e identificação)
    # ✅ CORRIGIDO: Explicitamente String(36) para garantir tipo correto
    school_id = db.Column(db.String(36), db.ForeignKey('school.id'), nullable=True)
    school_name = db.Column(db.String(200), nullable=True)  # Nome da escola
    municipality = db.Column(db.String(200), nullable=True)  # Município
    state = db.Column(db.String(100), nullable=True)  # Estado
    grade_name = db.Column(db.String(100), nullable=True)  # Série/turma (ex: "5º Ano")
    institution = db.Column(db.String(200), nullable=True)  # Instituição
    
    # =========================================================================
    # ✅ Campos MinIO para armazenamento de ZIPs de cartões resposta
    # =========================================================================
    minio_url = db.Column(db.String(500), nullable=True)  # URL completa do ZIP no MinIO
    minio_object_name = db.Column(db.String(200), nullable=True)  # Path do objeto no bucket
    minio_bucket = db.Column(db.String(100), nullable=True)  # Nome do bucket
    zip_generated_at = db.Column(db.DateTime, nullable=True)  # Timestamp de geração do ZIP
    
    # Relacionamentos
    test = db.relationship('Test', foreign_keys=[test_id])
    class_ = db.relationship('Class', foreign_keys=[class_id])
    creator = db.relationship('User', foreign_keys=[created_by])
    school = db.relationship('School', foreign_keys=[school_id])
    
    # =========================================================================
    # Métodos auxiliares para Template Real Digital
    # =========================================================================
    
    def get_template_block(self, block_num: int) -> bytes:
        """
        Retorna bytes PNG do template de um bloco específico.
        
        Args:
            block_num: Número do bloco (1-4)
            
        Returns:
            bytes PNG ou None se não existir
        """
        if block_num == 1:
            return self.template_block_1
        elif block_num == 2:
            return self.template_block_2
        elif block_num == 3:
            return self.template_block_3
        elif block_num == 4:
            return self.template_block_4
        return None
    
    def set_template_block(self, block_num: int, png_bytes: bytes) -> bool:
        """
        Define bytes PNG do template de um bloco específico.
        
        Args:
            block_num: Número do bloco (1-4)
            png_bytes: Bytes PNG da imagem
            
        Returns:
            True se sucesso, False se bloco inválido
        """
        if block_num == 1:
            self.template_block_1 = png_bytes
        elif block_num == 2:
            self.template_block_2 = png_bytes
        elif block_num == 3:
            self.template_block_3 = png_bytes
        elif block_num == 4:
            self.template_block_4 = png_bytes
        else:
            return False
        return True
    
    def has_templates(self) -> bool:
        """
        Verifica se o gabarito possui templates de blocos gerados.
        
        Returns:
            True se pelo menos um template existe
        """
        return any([
            self.template_block_1 is not None,
            self.template_block_2 is not None,
            self.template_block_3 is not None,
            self.template_block_4 is not None
        ])
    
    def get_template_count(self) -> int:
        """
        Retorna quantidade de templates de blocos salvos.
        
        Returns:
            Número de blocos com template (0-4)
        """
        count = 0
        if self.template_block_1 is not None:
            count += 1
        if self.template_block_2 is not None:
            count += 1
        if self.template_block_3 is not None:
            count += 1
        if self.template_block_4 is not None:
            count += 1
        return count
