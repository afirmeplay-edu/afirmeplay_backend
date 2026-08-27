# -*- coding: utf-8 -*-
"""Textos e critérios do relatório de fluência (MVP / FluencyScoring)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.afirme_ler.scoring.params import DEFAULT_PARAMS, FluencyScoringParams

IFL_DESCRICAO = (
    "IFL = soma (percentual de cada nível × peso do nível) / 100. "
    "Escala 0 a 10. Só entram estudantes com status presente."
)
FLUENCIA_TEXTO = (
    "Leitor Fluente (LF): mais de 65 palavras corretas no texto e precisão ≥ 90%. "
    "PPM ≥ 60 indica velocidade adequada (não define o perfil). "
    "LI: ≥ 11 palavras corretas e ≥ 6 pseudopalavras corretas. "
    "PL4: 1 a 10 palavras corretas. PL3: silabação. PL2: soletração. PL1: demais."
)


def criterios_payload(params: Optional[FluencyScoringParams] = None) -> Dict[str, str]:
    params = params or DEFAULT_PARAMS
    pesos = (
        f"PL1: peso {params.peso('PL1'):g} · "
        f"PL2: peso {params.peso('PL2'):g} · "
        f"PL3: peso {params.peso('PL3'):g} · "
        f"PL4: peso {params.peso('PL4'):g} · "
        f"LI: peso {params.peso('LI'):g} · "
        f"LF: peso {params.peso('LF'):g}"
    )
    return {
        "pesosIfl": pesos.replace(".", ","),
        "iflDescricao": IFL_DESCRICAO,
        "fluencia": FLUENCIA_TEXTO,
    }


def leitura_analitica(
    *,
    titulo_edicao: str,
    previstos: int,
    avaliados: int,
    participacao: float,
    ifl: float,
) -> str:
    edicao = titulo_edicao[0].lower() + titulo_edicao[1:] if titulo_edicao else "recorte"
    return (
        f"Na {edicao}, foram previstos {previstos} estudantes. "
        f"{avaliados} foram avaliados ({_pct_pt(participacao)}%). "
        f"O IFL do recorte é {_num_pt(ifl)}."
    )


def alertas_from_indicadores(indicadores: Dict[str, Any]) -> List[Dict[str, Any]]:
    alertas: List[Dict[str, Any]] = []
    participacao = float(indicadores.get("participacao") or 0)
    previstos = int(indicadores.get("previstos") or 0)
    avaliados = int(indicadores.get("avaliados") or 0)
    if previstos > 0 and participacao < 80:
        alertas.append(
            {
                "id": "participacao-baixa",
                "severidade": "warning",
                "titulo": "Participação abaixo do esperado",
                "descricao": (
                    f"A participação está em {_pct_pt(participacao)}% "
                    f"({avaliados} de {previstos} previstos)."
                ),
                "nivelCode": None,
            }
        )
    ifl = float(indicadores.get("ifl") or 0)
    if avaliados > 0 and ifl < 4:
        alertas.append(
            {
                "id": "ifl-baixo",
                "severidade": "warning",
                "titulo": "IFL abaixo de 4",
                "descricao": (
                    f"O IFL do recorte é {_num_pt(ifl)} (escala 0 a 10)."
                ),
                "nivelCode": None,
            }
        )
    return alertas


def frase_analitica(
    *,
    nivel_label: str,
    ppm: float,
    precisao: float,
    avaliado: bool,
) -> str:
    if not avaliado:
        return "Estudante sem perfil nesta edição (não avaliado ou ausente)."
    return (
        f"Classificado como {nivel_label}, com PPM {_num_pt(ppm)} "
        f"e precisão {_pct_pt(precisao)}%."
    )


def _num_pt(value: float) -> str:
    text = f"{float(value):.2f}".rstrip("0").rstrip(".")
    return text.replace(".", ",")


def _pct_pt(value: float) -> str:
    return _num_pt(value)
