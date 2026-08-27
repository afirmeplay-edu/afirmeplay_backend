# -*- coding: utf-8 -*-
"""
Cálculo canônico de fluência leitora (IFL / PL1–LF).

Use ``FluencyScoring`` em qualquer relatório. Não duplique as fórmulas.
"""
from app.afirme_ler.scoring.aggregate import AggregateIndicators, DistributionBand
from app.afirme_ler.scoring.calculator import FluencyScoring
from app.afirme_ler.scoring.compare import (
    EVOLUCAO_AVANCO,
    EVOLUCAO_MANUTENCAO,
    EVOLUCAO_REGRESSAO,
)
from app.afirme_ler.scoring.levels import (
    LEVEL_CODES,
    LEVEL_LABELS,
    SEM_PERFIL_LABEL,
)
from app.afirme_ler.scoring.params import FluencyScoringParams, IFL_ALGORITHM_VERSION
from app.afirme_ler.scoring.student import StudentReadingInput, StudentReadingScore

__all__ = [
    "FluencyScoring",
    "FluencyScoringParams",
    "StudentReadingInput",
    "StudentReadingScore",
    "AggregateIndicators",
    "DistributionBand",
    "LEVEL_CODES",
    "LEVEL_LABELS",
    "SEM_PERFIL_LABEL",
    "IFL_ALGORITHM_VERSION",
    "EVOLUCAO_AVANCO",
    "EVOLUCAO_REGRESSAO",
    "EVOLUCAO_MANUTENCAO",
]
