# -*- coding: utf-8 -*-
"""Helpers puros do boletim do aluno."""
from __future__ import annotations

from typing import Any, Dict, Optional

from app.mapa_questoes.helpers import percentual
from app.utils.decimal_helpers import round_to_two_decimals

DEFAULT_PER_PAGE = 20
MAX_PER_PAGE = 100


def parse_pagination(
    page_raw: Any,
    per_page_raw: Any,
    default_per_page: int = DEFAULT_PER_PAGE,
    max_per_page: int = MAX_PER_PAGE,
) -> tuple:
    try:
        page = int(page_raw if page_raw not in (None, "") else 1)
    except (TypeError, ValueError):
        page = 1
    try:
        per_page = int(per_page_raw if per_page_raw not in (None, "") else default_per_page)
    except (TypeError, ValueError):
        per_page = default_per_page
    return max(page, 1), min(max(per_page, 1), max_per_page)


def pagination_meta(total: int, page: int, per_page: int) -> Dict[str, int]:
    if per_page <= 0 or total <= 0:
        total_pages = 0
    else:
        total_pages = (total + per_page - 1) // per_page
    return {
        "page": page,
        "per_page": per_page,
        "total": int(total),
        "total_pages": total_pages,
    }


def parse_aluno_param(raw_ids: list) -> Optional[str]:
    """
    None = todos os alunos (paginado).
    str = um aluno específico.
    """
    cleaned = [str(x).strip() for x in (raw_ids or []) if str(x).strip()]
    cleaned = [x for x in cleaned if x.lower() not in ("all", "todos", "todas")]
    if not cleaned:
        return None
    if len(cleaned) > 1:
        raise ValueError("Informe no máximo um aluno (ou omita para todos)")
    return cleaned[0]


def build_questao_boletim(
    *,
    numero: int,
    habilidade: str,
    resposta: Optional[str],
    gabarito: Optional[str],
    acertou: bool,
    respondeu: bool,
) -> Dict[str, Any]:
    return {
        "numero": numero,
        "habilidade": habilidade or "N/A",
        "resposta": resposta,
        "gabarito": gabarito or "",
        "acertou": bool(acertou),
        "respondeu": bool(respondeu),
    }


def build_cards(
    acertou: int,
    total: int,
    nota: Any,
    proficiencia: Any,
    nivel: Any,
) -> Dict[str, Any]:
    return {
        "acertos_totais": {
            "acertou": int(acertou),
            "total": int(total),
            "percentual": percentual(int(acertou), int(total)),
        },
        "nota": round_to_two_decimals(float(nota or 0)),
        "proficiencia": round_to_two_decimals(float(proficiencia or 0)),
        "nivel": nivel,
    }


def empty_boletim_payload(
    estado: str,
    municipio_id: str,
    avaliacao_id: str,
    escola_ids=None,
    serie_ids=None,
    turma_ids=None,
    aluno_id: Optional[str] = None,
    page: int = 1,
    per_page: int = DEFAULT_PER_PAGE,
) -> Dict[str, Any]:
    return {
        "escopo": {
            "estado": estado,
            "municipio_id": str(municipio_id),
            "avaliacao_id": str(avaliacao_id),
            "escolas": list(escola_ids or []),
            "series": list(serie_ids or []),
            "turmas": [str(t) for t in (turma_ids or [])],
            "aluno_id": aluno_id,
        },
        "avaliacao": {"id": str(avaliacao_id), "nome": ""},
        "paginacao": pagination_meta(0, page, per_page),
        "boletins": [],
    }
