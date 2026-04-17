from app import db
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy import cast, String
import uuid

class Class(db.Model):
    __tablename__ = 'class'
    __table_args__ = {"schema": "tenant"}

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = db.Column(db.String(100))
    # ✅ CORRIGIDO: Usar coluna privada para evitar cast automático do SQLAlchemy
    # O SQLAlchemy pode fazer cast automático de VARCHAR para UUID se detectar formato UUID
    # Usando coluna privada + hybrid_property para forçar sempre retornar string
    _school_id = db.Column('school_id', db.String(36), db.ForeignKey('tenant.school.id'))
    grade_id = db.Column(UUID(as_uuid=True), db.ForeignKey('public.grade.id'))

    # ✅ CORREÇÃO CRÍTICA: hybrid_property que sempre retorna string
    # Isso força que school_id seja sempre string, mesmo que SQLAlchemy carregue como UUID
    @hybrid_property
    def school_id(self):
        """Sempre retorna school_id como string, mesmo se SQLAlchemy carregar como UUID"""
        value = self._school_id
        if value is None:
            return None
        # Forçar conversão para string se SQLAlchemy retornou UUID
        return str(value) if not isinstance(value, str) else value
    
    @school_id.setter
    def school_id(self, value):
        """Setter que converte para string antes de salvar"""
        if value is None:
            self._school_id = None
        else:
            # Sempre converter para string antes de salvar
            self._school_id = str(value) if not isinstance(value, str) else value
    
    @school_id.expression
    def school_id(cls):
        """Expression para queries SQL - retorna a coluna real"""
        return cls._school_id

    # ✅ CORRIGIDO: Property que sempre faz busca manual para evitar problema de tipo UUID vs VARCHAR
    # O relationship padrão não funciona porque SQLAlchemy passa UUID como parâmetro mesmo que a coluna seja VARCHAR
    # Esta property sempre converte para string antes de fazer a query
    @property
    def school(self):
        """Property que sempre retorna School usando string, evitando problema de tipo UUID vs VARCHAR"""
        from app.models.school import School
        if self._school_id is None:
            return None
        # Sempre converter para string antes de fazer a query
        school_id_str = str(self._school_id) if not isinstance(self._school_id, str) else self._school_id
        return School.query.filter(School.id == school_id_str).first()
    
    @school.setter
    def school(self, value):
        """Setter que atualiza _school_id"""
        if value is None:
            self._school_id = None
        else:
            self._school_id = str(value.id) if hasattr(value, 'id') else str(value)
    
    students = db.relationship("Student", backref="class_")
    class_subjects = db.relationship("ClassSubject", backref="class_")
    class_tests = db.relationship("ClassTest", backref="class_") 