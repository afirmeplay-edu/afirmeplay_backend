from app import db
import uuid

class Professor(db.Model):
    __tablename__ = 'professores'

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    senha_hash = db.Column(db.String, nullable=False)
    usuario_id = db.Column(db.String, db.ForeignKey('usuario.id'), nullable=False, unique=True)
    profile_picture = db.Column(db.String)
    birth_date = db.Column(db.Date)
    matricula = db.Column(db.String(50), nullable=False, unique=True)
    criado_em = db.Column(db.DateTime, server_default=db.func.now())
    tenant_id = db.Column(db.String, db.ForeignKey('municipios.id'), nullable=False)

    escolas = db.relationship('Escola', secondary='professor_escola', back_populates='professores')
    grades = db.relationship('Grade', secondary='professor_grade', back_populates='professores')
    turmas = db.relationship('Turma', secondary='professor_turma', back_populates='professores')
    
    professor_escola = db.Table('professor_escola',
        db.Column('id', db.String, primary_key=True, default=lambda: str(uuid.uuid4())),
        db.Column('professor_id', db.String, db.ForeignKey('professores.id'), nullable=False),
        db.Column('escola_id', db.String, db.ForeignKey('escolas.id'), nullable=False)
    )

    professor_grade = db.Table('professor_grade',
        db.Column('id', db.String, primary_key=True, default=lambda: str(uuid.uuid4())),
        db.Column('professor_id', db.String, db.ForeignKey('professores.id'), nullable=False),
        db.Column('grade_id', db.String, db.ForeignKey('grades.id'), nullable=False)
    )

    professor_turma = db.Table('professor_turma',
        db.Column('id', db.String, primary_key=True, default=lambda: str(uuid.uuid4())),
        db.Column('professor_id', db.String, db.ForeignKey('professores.id'), nullable=False),
        db.Column('turma_id', db.String, db.ForeignKey('turmas.id'), nullable=False)
    )