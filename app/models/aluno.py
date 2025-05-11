from app import db
import uuid

class Aluno(db.Model):
    __tablename__ = 'alunos'
  
    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    senha_hash = db.Column(db.String, nullable=False)
    usuario_id = db.Column(db.String, db.ForeignKey('usuario.id'), nullable=False, unique=True)
    profile_picture = db.Column(db.String)
    birth_date = db.Column(db.Date)
    matricula = db.Column(db.String(50), nullable=False, unique=True)
    criado_em = db.Column(db.DateTime, server_default=db.func.now())
    education_stage_id = db.Column(db.String, db.ForeignKey('education_stages.id'))
    grade_id = db.Column(db.String, db.ForeignKey('grades.id'))
    turma_id = db.Column(db.String, db.ForeignKey('turmas.id'))
    escola_id = db.Column(db.String, db.ForeignKey('escolas.id'), nullable=False)
    tenant_id = db.Column(db.String, db.ForeignKey('municipios.id'), nullable=False)
    
 