# -*- coding: utf-8 -*-
"""
Serviços de competições.
"""

from .competition_service import (
    CompetitionService,
    ValidationError,
    validate_reward_config,
)
from .question_rules_validator import validate_question_rules
from .competition_template_service import (
    compute_period_for_recurrence,
    select_questions_for_template,
    get_default_reward_config_for_recurrence,
    compute_next_edition,
)

__all__ = [
    "CompetitionService",
    "ValidationError",
    "validate_reward_config",
    "validate_question_rules",
    "compute_period_for_recurrence",
    "select_questions_for_template",
    "get_default_reward_config_for_recurrence",
    "compute_next_edition",
]

