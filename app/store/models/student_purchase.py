# -*- coding: utf-8 -*-
"""
Registro de compra do aluno na loja (aluno gastou afirmecoins e recebeu o item).
"""
from app import db
import uuid


class StudentPurchase(db.Model):
    __tablename__ = 'student_purchases'

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    student_id = db.Column(db.String, db.ForeignKey('student.id'), nullable=False)
    store_item_id = db.Column(db.String, db.ForeignKey('store_items.id'), nullable=False)
    price_paid = db.Column(db.Integer, nullable=False)  # valor pago no momento da compra
    created_at = db.Column(db.TIMESTAMP, server_default=db.func.now())

    student = db.relationship('Student', backref='store_purchases')

    def to_dict(self):
        return {
            'id': self.id,
            'student_id': self.student_id,
            'store_item_id': self.store_item_id,
            'price_paid': self.price_paid,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f'<StudentPurchase student_id={self.student_id} store_item_id={self.store_item_id}>'
