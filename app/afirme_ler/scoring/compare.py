# -*- coding: utf-8 -*-
"""Comparação de perfil entre edições (evolução)."""
from __future__ import annotations

from typing import Optional

from app.afirme_ler.scoring.levels import LEVEL_RANK
from app.afirme_ler.scoring.params import DEFAULT_PARAMS, FluencyScoringParams

EVOLUCAO_AVANCO = "avanco"
EVOLUCAO_REGRESSAO = "regressao"
EVOLUCAO_MANUTENCAO = "manutencao"


def evolucao(
    nivel_atual: Optional[str],
    nivel_anterior: Optional[str],
) -> Optional[str]:
    """
    Compara índices na ordem PL1 < PL2 < PL3 < PL4 < LI < LF.

    Sem um dos perfis → None. O front só pinta; não recalcula.
    """
    if not nivel_atual or not nivel_anterior:
        return None
    if nivel_atual not in LEVEL_RANK or nivel_anterior not in LEVEL_RANK:
        return None
    atual = LEVEL_RANK[nivel_atual]
    anterior = LEVEL_RANK[nivel_anterior]
    if atual > anterior:
        return EVOLUCAO_AVANCO
    if atual < anterior:
        return EVOLUCAO_REGRESSAO
    return EVOLUCAO_MANUTENCAO


def ifl_do_nivel(
    nivel: Optional[str],
    params: Optional[FluencyScoringParams] = None,
) -> Optional[float]:
    if not nivel:
        return None
    params = params or DEFAULT_PARAMS
    if nivel not in params.pesos_ifl:
        return None
    return float(params.peso(nivel))
