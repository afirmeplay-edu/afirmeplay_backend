# -*- coding: utf-8 -*-
"""
Modelo para armazenar dados salvos da Calculadora de Metas IDEB por contexto.
Um registro por (state_id, municipality_id, level), compartilhado entre todos os usuários.
"""
from app import db
import uuid
from sqlalchemy.dialects.postgresql import JSON


class IdebMetaSave(db.Model):
    """
    Persistência dos dados da Calculadora de Metas IDEB.
    Contexto: state_id, municipality_id, level (ex.: Anos Iniciais, Anos Finais).
    """
    __tablename__ = 'ideb_meta_saves'

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    state_id = db.Column(db.String(50), nullable=False)
    municipality_id = db.Column(db.String(50), nullable=False)
    level = db.Column(db.String(100), nullable=False)
    payload = db.Column(JSON, nullable=False)
    updated_at = db.Column(
        db.TIMESTAMP,
        server_default=db.func.now(),
        onupdate=db.func.now(),
        nullable=False,
    )

    __table_args__ = (
        db.UniqueConstraint(
            'state_id', 'municipality_id', 'level',
            name='uq_ideb_meta_saves_context',
        ),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'state_id': self.state_id,
            'municipality_id': self.municipality_id,
            'level': self.level,
            'payload': self.payload,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
