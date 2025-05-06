from app import db
import uuid

class Aluno(db.Model):
    __tablename__ = 'alunos'
  
    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    nome = db.Column(db.String(100), nullable=False)
    birth_date = db.Column(db.Date, nullable=True)
    profile_picture = db.Column(db.String, nullable=True)
    email = db.Column(db.String, nullable=False)
    usuario_id = db.Column(db.String, db.ForeignKey('usuario.id'), nullable=False, unique=True)
    matricula = db.Column(db.String, nullable=False, unique=True)
    # classe_id = db.Column(db.String, db.ForeignKey('classes.id'))
    tenant_id = db.Column(db.String, db.ForeignKey('escolas.id'), nullable=False)
    criado_em = db.Column(db.DateTime, server_default=db.func.now())

    # Novos campos
    education_stage_id = db.Column(db.String, db.ForeignKey('education_stages.id'), nullable=False)
    grade_id = db.Column(db.String, db.ForeignKey('grades.id'), nullable=False)

    # Relacionamentos
    usuario = db.relationship("Usuario", backref="aluno", uselist=False)
    education_stage = db.relationship("EducationStage", backref="alunos")
    grade = db.relationship("Grade", backref="alunos")
 