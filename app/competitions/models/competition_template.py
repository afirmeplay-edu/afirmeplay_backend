# -*- coding: utf-8 -*-
"""Modelo mínimo para competition_templates (expandido na Etapa 6)."""
from app import db


class CompetitionTemplate(db.Model):
    __tablename__ = 'competition_templates'

    id = db.Column(db.String, primary_key=True)
