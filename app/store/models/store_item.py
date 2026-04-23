# -*- coding: utf-8 -*-
"""
Modelo de item da loja (comprável com afirmecoins).

Categorias atuais (digitais): frame (moldura), stamp (selo), sidebar_theme (tema da sidebar).
Futuro: itens físicos (is_physical=True) com entrega no mundo real.
"""
from app import db
import uuid

# Categorias de exibição/filtro na loja
STORE_CATEGORY_FRAME = 'frame'           # moldura
STORE_CATEGORY_STAMP = 'stamp'           # selo
STORE_CATEGORY_SIDEBAR_THEME = 'sidebar_theme'  # tema da sidebar
STORE_CATEGORY_PHYSICAL = 'physical'     # item físico (futuro)

# Escopos de visibilidade: quem vê o item (admin=sistema, tecadm=município, diretor/coordenador=escola, professor=turma)
STORE_SCOPE_SYSTEM = 'system'
STORE_SCOPE_CITY = 'city'
STORE_SCOPE_SCHOOL = 'school'
STORE_SCOPE_CLASS = 'class'


class StoreItem(db.Model):
    """
    Item disponível na loja. O aluno gasta afirmecoins (balance) e recebe
    algo em troca (digital: moldura/selo/tema; futuro: itens físicos).
    """
    __tablename__ = 'store_items'
    __table_args__ = {"schema": "public"}

    id = db.Column(db.String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    price = db.Column(db.Integer, nullable=False)  # preço em afirmecoins
    # Categoria na loja: frame, stamp, sidebar_theme, physical (futuro)
    category = db.Column(db.String(64), nullable=False)
    # Tipo técnico do prêmio (como aplicar): igual à category para digitais
    reward_type = db.Column(db.String(64), nullable=False)
    # Dados do prêmio (JSON ou identificador): ex. {"theme_id": "dark"} ou "frame_gold"
    reward_data = db.Column(db.Text, nullable=True)
    # True = item físico (entrega real); False = digital (moldura, selo, tema)
    is_physical = db.Column(db.Boolean, default=False, nullable=False)
    # Escopo: system=todo o sistema, city=município, school=escola, class=turma
    scope_type = db.Column(db.String(32), default=STORE_SCOPE_SYSTEM, nullable=False)
    # IDs conforme escopo: {"city_ids": [], "school_ids": [], "class_ids": []}
    scope_filter = db.Column(db.JSON, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    sort_order = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.TIMESTAMP, server_default=db.func.now())
    updated_at = db.Column(db.TIMESTAMP, server_default=db.func.now(), onupdate=db.func.now())

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'price': self.price,
            'category': self.category,
            'reward_type': self.reward_type,
            'reward_data': self.reward_data,
            'is_physical': self.is_physical,
            'scope_type': self.scope_type or STORE_SCOPE_SYSTEM,
            'scope_filter': self.scope_filter,
            'is_active': self.is_active,
            'sort_order': self.sort_order,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f'<StoreItem id={self.id} name={self.name} price={self.price}>'
