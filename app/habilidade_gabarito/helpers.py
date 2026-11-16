# -*- coding: utf-8 -*-
"""Montagem das linhas do Relatório de habilidade e gabarito."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple
from uuid import UUID

from app.mapa_questoes.helpers import join_habilidade_campos
from app.services.skills_map_service import (
    _extract_skill_ids_from_question_field,
    _habilidade_codigo_e_descricao,
    _norm_skill_key,
)

REPORT_NAME = "Relatório de habilidade e gabarito"


def escopo_payload(
    estado: str,
    municipio_id: str,
    escola_ids: Optional[Sequence[str]] = None,
    serie_ids: Optional[Sequence[str]] = None,
    turma_ids: Optional[Sequence[str]] = None,
    report_entity_type: Optional[str] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "estado": estado,
        "municipio_id": str(municipio_id),
        "escolas": [str(x) for x in (escola_ids or [])],
        "series": [str(x) for x in (serie_ids or [])],
        "turmas": [str(x) for x in (turma_ids or [])],
    }
    if report_entity_type:
        payload["report_entity_type"] = report_entity_type
    return payload


def questao_row(
    numero: int,
    habilidade: str,
    descricao: str,
    gabarito: Optional[str],
) -> Dict[str, Any]:
    letra = (str(gabarito).strip().upper() if gabarito else "")
    return {
        "numero": int(numero),
        "habilidade": habilidade or "N/A",
        "descricao_habilidade": descricao or "",
        "gabarito": letra,
    }


def _lookup_skill(sid: str, skills_db: Dict[str, Any]):
    return skills_db.get(_norm_skill_key(sid)) or skills_db.get(str(sid))


def skill_texts_digital(raw_skill: Any, skills_db: Dict[str, Any]) -> Tuple[str, str]:
    """Código e descrição a partir de Question.skill (id, código ou lista)."""
    raw_ids = _extract_skill_ids_from_question_field(raw_skill)
    pairs: List[Tuple[str, str]] = []
    for sid in raw_ids:
        obj = _lookup_skill(sid, skills_db)
        if obj:
            pairs.append(_habilidade_codigo_e_descricao(str(sid), obj))
            continue
        try:
            UUID(str(sid).strip())
            pairs.append(
                (
                    "N/A",
                    "Esta habilidade não foi encontrada na base de habilidades.",
                )
            )
        except ValueError:
            pairs.append((str(sid).strip() or "N/A", ""))
    return join_habilidade_campos(pairs)


def skill_texts_answer_sheet(
    skill_ids: Sequence[str], skills_db: Dict[str, Any]
) -> Tuple[str, str]:
    pairs = [
        _habilidade_codigo_e_descricao(str(sid), _lookup_skill(str(sid), skills_db))
        for sid in skill_ids
        if sid
    ]
    return join_habilidade_campos(pairs)
