# -*- coding: utf-8 -*-
"""
Fonte da verdade do IFL / perfil de fluência leitora (MVP).

Relatórios (tela, perfil do aluno, Excel, consolidado) devem chamar esta classe.
Não recalcular PPM, classificação ou IFL em rotas ou exportações.

ICA / Leiturômetro continuam em ``fluency_metrics_service`` — são outro índice.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, Mapping, Optional, Sequence, Tuple

from app.afirme_ler.scoring.aggregate import (
    AggregateIndicators,
    agregar,
    agregar_por,
    aplicar_delta,
)
from app.afirme_ler.scoring.compare import evolucao, ifl_do_nivel
from app.afirme_ler.scoring.from_session import input_from_session
from app.afirme_ler.scoring.levels import LEVEL_CODES, LEVEL_LABELS, SEM_PERFIL_LABEL
from app.afirme_ler.scoring.params import (
    DEFAULT_PARAMS,
    IFL_ALGORITHM_VERSION,
    FluencyScoringParams,
)
from app.afirme_ler.scoring.student import (
    StudentReadingInput,
    StudentReadingScore,
    classificar,
    score_student,
)


class FluencyScoring:
    """Fachada estável para todos os relatórios de fluência leitora."""

    VERSION = IFL_ALGORITHM_VERSION
    PARAMS = DEFAULT_PARAMS
    LEVEL_CODES = LEVEL_CODES
    LEVEL_LABELS = LEVEL_LABELS
    SEM_PERFIL_LABEL = SEM_PERFIL_LABEL

    @classmethod
    def score_student(
        cls,
        data: StudentReadingInput,
        params: Optional[FluencyScoringParams] = None,
    ) -> StudentReadingScore:
        return score_student(data, params or cls.PARAMS)

    @classmethod
    def classificar(
        cls,
        data: StudentReadingInput,
        params: Optional[FluencyScoringParams] = None,
    ) -> Optional[str]:
        return classificar(data, params or cls.PARAMS)

    @classmethod
    def from_session(
        cls,
        session: Any,
        params: Optional[FluencyScoringParams] = None,
    ) -> StudentReadingScore:
        return cls.score_student(input_from_session(session), params)

    @classmethod
    def agregar(
        cls,
        scores: Iterable[StudentReadingScore],
        previstos: int,
        params: Optional[FluencyScoringParams] = None,
    ) -> AggregateIndicators:
        return agregar(scores, previstos, params or cls.PARAMS)

    @classmethod
    def agregar_por(
        cls,
        pares: Sequence[Tuple[Any, StudentReadingScore]],
        previstos_por_grupo: Mapping[Any, int],
        params: Optional[FluencyScoringParams] = None,
    ) -> Dict[Any, AggregateIndicators]:
        return agregar_por(pares, previstos_por_grupo, params or cls.PARAMS)

    @classmethod
    def aplicar_delta(
        cls,
        atual: AggregateIndicators,
        anterior: Optional[AggregateIndicators],
    ) -> AggregateIndicators:
        return aplicar_delta(atual, anterior)

    @classmethod
    def evolucao(
        cls,
        nivel_atual: Optional[str],
        nivel_anterior: Optional[str],
    ) -> Optional[str]:
        return evolucao(nivel_atual, nivel_anterior)

    @classmethod
    def ifl_do_nivel(
        cls,
        nivel: Optional[str],
        params: Optional[FluencyScoringParams] = None,
    ) -> Optional[float]:
        return ifl_do_nivel(nivel, params or cls.PARAMS)
