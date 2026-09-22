# -*- coding: utf-8 -*-
"""Constantes da loja: faixas, classificações e tipos de requisito (fonte única)."""
from app.services.competition_student_ranking_service import RANK_BANDS
from app.services.achievement_service import (
    ACHIEVEMENTS_CONFIG,
    MEDAL_ORDER,
    PERFEccionISTA_CONFIG,
)

REQUIREMENT_TYPE_COMPETITION_BAND = 'competition_band'
REQUIREMENT_TYPE_EVAL_MIN_GRADE = 'eval_min_grade'
REQUIREMENT_TYPE_EVAL_CLASSIFICATION = 'eval_classification'
REQUIREMENT_TYPE_ACHIEVEMENT = 'achievement'

REQUIREMENT_TYPES = (
    REQUIREMENT_TYPE_COMPETITION_BAND,
    REQUIREMENT_TYPE_EVAL_MIN_GRADE,
    REQUIREMENT_TYPE_EVAL_CLASSIFICATION,
    REQUIREMENT_TYPE_ACHIEVEMENT,
)

COMPETITION_BAND_NAMES = [band.name for band in RANK_BANDS]

EVAL_CLASSIFICATIONS = [
    'Abaixo do Básico',
    'Básico',
    'Adequado',
    'Avançado',
]

MEDAL_NAMES = list(MEDAL_ORDER)

MEDAL_LABELS = {
    'bronze': 'Bronze',
    'prata': 'Prata',
    'ouro': 'Ouro',
    'platina': 'Platina',
}


def achievement_catalog():
    """Lista de conquistas disponíveis para o seletor admin (inclui perfeccionista)."""
    items = [{'id': cfg['id'], 'nome': cfg.get('nome') or cfg['id']} for cfg in ACHIEVEMENTS_CONFIG]
    items.append({
        'id': PERFEccionISTA_CONFIG['id'],
        'nome': PERFEccionISTA_CONFIG.get('nome') or PERFEccionISTA_CONFIG['id'],
    })
    return items
