# -*- coding: utf-8 -*-
"""Agregados de recorte: participação, distribuição, IFL e taxas."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, replace
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from app.utils.decimal_helpers import round_to_two_decimals
from app.afirme_ler.scoring.levels import (
    LEVEL_CODES,
    LEVEL_LF,
    PRE_LEITOR_CODES,
    nivel_label,
)
from app.afirme_ler.scoring.params import DEFAULT_PARAMS, FluencyScoringParams
from app.afirme_ler.scoring.student import StudentReadingScore


def _pct(parte: int, todo: int) -> float:
    if todo <= 0:
        return 0.0
    return round_to_two_decimals(100.0 * parte / todo)


def _media(valores: Sequence[float]) -> float:
    if not valores:
        return 0.0
    return round_to_two_decimals(sum(valores) / len(valores))


@dataclass(frozen=True)
class DistributionBand:
    code: str
    label: str
    estudantes: int
    percentual: float
    percentual_anterior: Optional[float] = None
    delta: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "label": self.label,
            "estudantes": self.estudantes,
            "percentual": self.percentual,
            "percentualAnterior": self.percentual_anterior,
            "delta": self.delta,
            "lista": [],
        }


@dataclass(frozen=True)
class AggregateIndicators:
    previstos: int
    avaliados: int
    participacao: float
    ifl: float
    leitores_fluentes_pct: float
    pre_leitores_pct: float
    ppm_medio: float
    precisao_media: float
    velocidade_adequada_pct: float
    precisao_adequada_pct: float
    prosodia_adequada_pct: float
    distribuicao: Tuple[DistributionBand, ...]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "previstos": self.previstos,
            "avaliados": self.avaliados,
            "participacao": self.participacao,
            "ifl": self.ifl,
            "leitoresFluentesPct": self.leitores_fluentes_pct,
            "preLeitoresPct": self.pre_leitores_pct,
            "ppmMedio": self.ppm_medio,
            "precisaoMedia": self.precisao_media,
            "velocidadeAdequadaPct": self.velocidade_adequada_pct,
            "precisaoAdequadaPct": self.precisao_adequada_pct,
            "prosodiaAdequadaPct": self.prosodia_adequada_pct,
            "distribuicao": [band.to_dict() for band in self.distribuicao],
        }


def _empty_distribuicao() -> Tuple[DistributionBand, ...]:
    return tuple(
        DistributionBand(
            code=code,
            label=nivel_label(code),
            estudantes=0,
            percentual=0.0,
        )
        for code in LEVEL_CODES
    )


def agregar(
    scores: Iterable[StudentReadingScore],
    previstos: int,
    params: Optional[FluencyScoringParams] = None,
) -> AggregateIndicators:
    """
    Agrega um recorte.

    ``previstos`` = roster (presente + ausente + não avaliado + não elegível).
    Só ``avaliado`` (presente) entra em perfil, IFL, médias e taxas.
    """
    params = params or DEFAULT_PARAMS
    previstos_n = max(0, int(previstos or 0))
    presentes = [row for row in scores if row.avaliado]
    avaliados = len(presentes)
    participacao = _pct(avaliados, previstos_n)

    if avaliados == 0:
        return AggregateIndicators(
            previstos=previstos_n,
            avaliados=0,
            participacao=participacao,
            ifl=0.0,
            leitores_fluentes_pct=0.0,
            pre_leitores_pct=0.0,
            ppm_medio=0.0,
            precisao_media=0.0,
            velocidade_adequada_pct=0.0,
            precisao_adequada_pct=0.0,
            prosodia_adequada_pct=0.0,
            distribuicao=_empty_distribuicao(),
        )

    counts = {code: 0 for code in LEVEL_CODES}
    for row in presentes:
        if row.nivel in counts:
            counts[row.nivel] += 1

    bands = []
    ifl_acc = 0.0
    for code in LEVEL_CODES:
        percentual = _pct(counts[code], avaliados)
        bands.append(
            DistributionBand(
                code=code,
                label=nivel_label(code),
                estudantes=counts[code],
                percentual=percentual,
            )
        )
        ifl_acc += percentual * params.peso(code)

    pre_leitores = sum(counts[code] for code in PRE_LEITOR_CODES)
    vel_ok = sum(1 for row in presentes if row.velocidade_adequada)
    prec_ok = sum(1 for row in presentes if row.precisao_adequada)
    pros_ok = sum(1 for row in presentes if row.prosodia_adequada)

    return AggregateIndicators(
        previstos=previstos_n,
        avaliados=avaliados,
        participacao=participacao,
        ifl=round_to_two_decimals(ifl_acc / 100.0),
        leitores_fluentes_pct=_pct(counts[LEVEL_LF], avaliados),
        pre_leitores_pct=_pct(pre_leitores, avaliados),
        ppm_medio=_media([row.ppm for row in presentes]),
        precisao_media=_media([row.precisao for row in presentes]),
        velocidade_adequada_pct=_pct(vel_ok, avaliados),
        precisao_adequada_pct=_pct(prec_ok, avaliados),
        prosodia_adequada_pct=_pct(pros_ok, avaliados),
        distribuicao=tuple(bands),
    )


def agregar_por(
    pares: Sequence[Tuple[Any, StudentReadingScore]],
    previstos_por_grupo: Mapping[Any, int],
    params: Optional[FluencyScoringParams] = None,
) -> Dict[Any, AggregateIndicators]:
    """Agrupa por chave (escola, turma, …) e chama ``agregar`` em cada grupo."""
    grupos: Dict[Any, List[StudentReadingScore]] = defaultdict(list)
    for chave, score in pares:
        grupos[chave].append(score)
    return {
        chave: agregar(
            rows,
            int(previstos_por_grupo.get(chave, 0) or 0),
            params,
        )
        for chave, rows in grupos.items()
    }


def aplicar_delta(
    atual: AggregateIndicators,
    anterior: Optional[AggregateIndicators],
) -> AggregateIndicators:
    """Preenche percentualAnterior e delta nas 6 faixas. Sem anterior → None."""
    if anterior is None:
        return atual
    prev_by_code = {band.code: band.percentual for band in anterior.distribuicao}
    novas = []
    for band in atual.distribuicao:
        pct_ant = prev_by_code.get(band.code)
        if pct_ant is None:
            novas.append(band)
            continue
        novas.append(
            replace(
                band,
                percentual_anterior=pct_ant,
                delta=round_to_two_decimals(band.percentual - pct_ant),
            )
        )
    return replace(atual, distribuicao=tuple(novas))
