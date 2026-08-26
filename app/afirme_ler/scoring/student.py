# -*- coding: utf-8 -*-
"""Métricas individuais e classificação first-match PL1…LF."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from app.utils.decimal_helpers import round_to_two_decimals
from app.afirme_ler.scoring.levels import (
    is_presente,
    nivel_label,
    normalize_status,
)
from app.afirme_ler.scoring.params import DEFAULT_PARAMS, FluencyScoringParams


def palavras_corretas_texto(texto_palavras_lidas: int, texto_erros: int) -> int:
    return max(0, int(texto_palavras_lidas or 0) - int(texto_erros or 0))


def calcular_ppm(texto_corretas: int, tempo_segundos: float) -> float:
    tempo = float(tempo_segundos or 0)
    if tempo <= 0:
        return 0.0
    return round_to_two_decimals((texto_corretas / tempo) * 60.0)


def calcular_precisao(texto_corretas: int, texto_palavras_lidas: int) -> float:
    lidas = int(texto_palavras_lidas or 0)
    if lidas <= 0:
        return 0.0
    return round_to_two_decimals(100.0 * texto_corretas / lidas)


def calcular_compreensao_pct(acertos: int, validas: int) -> float:
    total = int(validas or 0)
    if total <= 0:
        return 0.0
    return round_to_two_decimals(100.0 * int(acertos or 0) / total)


@dataclass(frozen=True)
class StudentReadingInput:
    """Contagens brutas já decididas pelo aplicador (uma edição)."""

    status: str = "não avaliado"
    palavras_corretas: int = 0
    silabacoes: int = 0
    soletracoes: int = 0
    desconhecidas_corretas: int = 0
    texto_palavras_lidas: int = 0
    texto_erros: int = 0
    tempo_segundos: float = 0.0
    prosodia_adequada: bool = False
    compreensao_acertos: int = 0
    compreensao_validas: int = 0


@dataclass(frozen=True)
class StudentReadingScore:
    status: str
    avaliado: bool
    palavras_corretas: int
    silabacoes: int
    soletracoes: int
    desconhecidas_corretas: int
    texto_palavras_lidas: int
    texto_erros: int
    tempo_segundos: float
    prosodia_adequada: bool
    compreensao_acertos: int
    compreensao_validas: int
    palavras_corretas_texto: int
    ppm: float
    precisao: float
    compreensao_pct: float
    nivel: Optional[str]
    nivel_label: str
    peso_ifl: float
    velocidade_adequada: bool
    precisao_adequada: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "avaliado": self.avaliado,
            "status": self.status,
            "nivel": self.nivel,
            "nivelLabel": self.nivel_label,
            "ppm": self.ppm,
            "precisao": self.precisao,
            "prosodiaAdequada": self.prosodia_adequada,
            "prosodiaLabel": "Adequada" if self.prosodia_adequada else "Não adequada",
            "palavrasCorretas": self.palavras_corretas,
            "silabacoes": self.silabacoes,
            "soletracoes": self.soletracoes,
            "desconhecidasCorretas": self.desconhecidas_corretas,
            "textoPalavrasLidas": self.texto_palavras_lidas,
            "textoErros": self.texto_erros,
            "compreensaoAcertos": self.compreensao_acertos,
            "compreensaoValidas": self.compreensao_validas,
            "compreensaoPct": self.compreensao_pct,
            "pesoIfl": self.peso_ifl,
        }


def classificar(
    data: StudentReadingInput,
    params: Optional[FluencyScoringParams] = None,
) -> Optional[str]:
    """
    First-match: LF → LI → PL4 → PL3 → PL2 → PL1.

    Só classifica ``presente``. PPM, prosódia e compreensão não entram.
    """
    params = params or DEFAULT_PARAMS
    if not is_presente(data.status):
        return None

    texto_corretas = palavras_corretas_texto(
        data.texto_palavras_lidas, data.texto_erros
    )
    precisao = calcular_precisao(texto_corretas, data.texto_palavras_lidas)

    if (
        texto_corretas > params.limite_texto_fluente
        and params.precisao_atinge_fluente(precisao)
    ):
        return "LF"
    if (
        data.palavras_corretas >= params.limite_palavras_li
        and data.desconhecidas_corretas >= params.limite_desconhecidas_li
    ):
        return "LI"
    if 0 < data.palavras_corretas <= params.limite_palavras_pl4:
        return "PL4"
    if data.silabacoes > 0:
        return "PL3"
    if data.soletracoes > 0:
        return "PL2"
    return "PL1"


def score_student(
    data: StudentReadingInput,
    params: Optional[FluencyScoringParams] = None,
) -> StudentReadingScore:
    params = params or DEFAULT_PARAMS
    status = normalize_status(data.status)
    avaliado = is_presente(status)

    texto_corretas = palavras_corretas_texto(
        data.texto_palavras_lidas, data.texto_erros
    )
    if avaliado:
        ppm = calcular_ppm(texto_corretas, data.tempo_segundos)
        precisao = calcular_precisao(texto_corretas, data.texto_palavras_lidas)
        compreensao_pct = calcular_compreensao_pct(
            data.compreensao_acertos, data.compreensao_validas
        )
        nivel = classificar(data, params)
        peso = params.peso(nivel) if nivel else 0.0
        velocidade = ppm >= params.ppm_adequado
        precisao_ok = precisao >= params.precisao_adequada_minima
        prosodia = bool(data.prosodia_adequada)
    else:
        ppm = 0.0
        precisao = 0.0
        compreensao_pct = 0.0
        nivel = None
        peso = 0.0
        velocidade = False
        precisao_ok = False
        prosodia = False

    return StudentReadingScore(
        status=status,
        avaliado=avaliado,
        palavras_corretas=int(data.palavras_corretas or 0),
        silabacoes=int(data.silabacoes or 0),
        soletracoes=int(data.soletracoes or 0),
        desconhecidas_corretas=int(data.desconhecidas_corretas or 0),
        texto_palavras_lidas=int(data.texto_palavras_lidas or 0),
        texto_erros=int(data.texto_erros or 0),
        tempo_segundos=float(data.tempo_segundos or 0),
        prosodia_adequada=prosodia,
        compreensao_acertos=int(data.compreensao_acertos or 0),
        compreensao_validas=int(data.compreensao_validas or 0),
        palavras_corretas_texto=texto_corretas if avaliado else 0,
        ppm=ppm,
        precisao=precisao,
        compreensao_pct=compreensao_pct,
        nivel=nivel,
        nivel_label=nivel_label(nivel),
        peso_ifl=peso,
        velocidade_adequada=velocidade,
        precisao_adequada=precisao_ok,
    )
