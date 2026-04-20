# -*- coding: utf-8 -*-
"""
Modelo para armazenar dados salvos da Calculadora de Metas IDEB por contexto.
Usa o município (City) e o nível (ex.: Anos Iniciais, Anos Finais) do sistema.
Um registro por (city_id, level), compartilhado entre todos os usuários.
"""
from app import db
import uuid
from sqlalchemy.dialects.postgresql import JSON


class IdebMetaSave(db.Model):
    """
    Persistência dos dados da Calculadora de Metas IDEB.
    Contexto: city_id (município do sistema) + level (ex.: Anos Iniciais, Anos Finais).
    """
    __tablename__ = 'ideb_meta_saves'
    __table_args__ = (
        db.UniqueConstraint('city_id', 'level', name='uq_ideb_meta_saves_context'),
        {"schema": "tenant"},
    )

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    city_id = db.Column(db.String, db.ForeignKey('public.city.id'), nullable=False)
    level = db.Column(db.String(100), nullable=False)
    payload = db.Column(JSON, nullable=False)
    updated_at = db.Column(
        db.TIMESTAMP,
        server_default=db.func.now(),
        onupdate=db.func.now(),
        nullable=False,
    )

    city = db.relationship('City', backref=db.backref('ideb_meta_saves', lazy='dynamic'))

    def to_dict(self):
        return {
            'id': self.id,
            'city_id': self.city_id,
            'level': self.level,
            'payload': self.payload,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
