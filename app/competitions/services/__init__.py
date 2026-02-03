# -*- coding: utf-8 -*-
"""
Serviços de competições.
"""
from .competition_service import CompetitionService, ValidationError, validate_reward_config

__all__ = [
    'CompetitionService',
    'ValidationError',
    'validate_reward_config',
]
