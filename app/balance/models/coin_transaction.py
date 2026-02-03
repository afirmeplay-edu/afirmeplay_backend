# -*- coding: utf-8 -*-
"""
Modelo para transações de moedas do aluno.
"""
from app import db
import uuid


class CoinTransaction(db.Model):
    __tablename__ = 'coin_transactions'

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id = db.Column(db.String, db.ForeignKey('student.id'), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    balance_before = db.Column(db.Integer, nullable=False)
    balance_after = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.String, nullable=False)
    competition_id = db.Column(
        db.String,
        db.ForeignKey('competitions.id', ondelete='SET NULL'),
        nullable=True,
    )
    test_session_id = db.Column(
        db.String,
        db.ForeignKey('test_sessions.id', ondelete='SET NULL'),
        nullable=True,
    )
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.TIMESTAMP, server_default=db.text('CURRENT_TIMESTAMP'))

    student = db.relationship('Student', backref='coin_transactions')
    competition = db.relationship('Competition', backref='coin_transactions')
    test_session = db.relationship('TestSession', backref='coin_transactions')

    def to_dict(self):
        """Converte o objeto para dicionário."""
        return {
            'id': self.id,
            'amount': self.amount,
            'reason': self.reason,
            'description': self.description,
            'balance_before': self.balance_before,
            'balance_after': self.balance_after,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'competition_id': self.competition_id,
            'test_session_id': self.test_session_id,
        }

    def __repr__(self):
        return f'<CoinTransaction student_id={self.student_id} amount={self.amount}>'
