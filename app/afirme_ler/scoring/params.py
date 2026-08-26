# -*- coding: utf-8 -*-
"""Parâmetros oficiais do IFL / perfil de fluência (MVP)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict

from app.afirme_ler.scoring.levels import LEVEL_CODES, LEVEL_LF, LEVEL_LI, LEVEL_PL1, LEVEL_PL2, LEVEL_PL3, LEVEL_PL4

IFL_ALGORITHM_VERSION = "1.0.0"

# Escala 0–10. IFL = Σ (percentual[n] × peso[n]) / 100
DEFAULT_IFL_WEIGHTS: Dict[str, float] = {
    LEVEL_PL1: 0.0,
    LEVEL_PL2: 1.0,
    LEVEL_PL3: 2.5,
    LEVEL_PL4: 4.0,
    LEVEL_LI: 6.0,
    LEVEL_LF: 10.0,
}


@dataclass(frozen=True)
class FluencyScoringParams:
    """
    Limites do classificador first-match e pesos do IFL.

    ``limite_desconhecidas_pl4`` existe no MVP e **não** entra em ``classificar``.
    """

    limite_texto_fluente: int = 65
    precisao_minima_fluente: float = 90.0
    precisao_inclusiva: bool = True
    limite_palavras_li: int = 11
    limite_desconhecidas_li: int = 6
    limite_palavras_pl4: int = 10
    limite_desconhecidas_pl4: int = 0
    ppm_adequado: float = 60.0
    precisao_adequada_minima: float = 90.0
    pesos_ifl: Dict[str, float] = field(
        default_factory=lambda: dict(DEFAULT_IFL_WEIGHTS)
    )

    def peso(self, nivel: str) -> float:
        return float(self.pesos_ifl.get(nivel, 0.0))

    def precisao_atinge_fluente(self, precisao: float) -> bool:
        if self.precisao_inclusiva:
            return precisao >= self.precisao_minima_fluente
        return precisao > self.precisao_minima_fluente


DEFAULT_PARAMS = FluencyScoringParams()

assert tuple(DEFAULT_IFL_WEIGHTS) == LEVEL_CODES
