# -*- coding: utf-8 -*-
"""
Modelo para saldo de moedas do aluno.
"""
from app import db
import uuid

from app.models.student import Student


class StudentCoins(db.Model):
    __tablename__ = 'student_coins'
    __table_args__ = {"schema": "tenant"}

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id = db.Column(db.String, db.ForeignKey(Student.__table__.c.id), nullable=False, unique=True)
    balance = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.TIMESTAMP, server_default=db.text('CURRENT_TIMESTAMP'))
    updated_at = db.Column(
        db.TIMESTAMP,
        server_default=db.text('CURRENT_TIMESTAMP'),
        onupdate=db.text('CURRENT_TIMESTAMP'),
    )

    student = db.relationship('Student', backref=db.backref('coins', uselist=False))

    def __repr__(self):
        return f'<StudentCoins student_id={self.student_id} balance={self.balance}>'
