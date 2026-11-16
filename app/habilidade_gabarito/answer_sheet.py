# -*- coding: utf-8 -*-
"""Relatório de habilidade e gabarito — cartão-resposta."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Set

from app.habilidade_gabarito.helpers import (
    REPORT_NAME,
    escopo_payload,
    questao_row,
    skill_texts_answer_sheet,
)
from app.habilidade_gabarito.services import _assert_municipio, _ensure_tenant_schema
from app.models.answerSheetGabarito import AnswerSheetGabarito
from app.participation_report.answer_sheet import _filter_classes
from app.permissions import get_user_permission_scope
from app.report_analysis.answer_sheet_report_builder import (
    ordered_question_numbers_for_gabarito,
    question_skills_map_for_answer_sheet,
)
from app.services.skills_map_service import _fetch_skills_batch, _gabarito_answer_map
from app.utils.uuid_helpers import ensure_uuid_list

logger = logging.getLogger(__name__)


def _normalize_turma_ids(turma_ids: Optional[List[str]]) -> List[str]:
    if not turma_ids:
        return []
    normalized = [str(x) for x in (ensure_uuid_list(turma_ids) or [])]
    if normalized:
        return normalized
    return [str(x) for x in turma_ids]


def build_habilidade_gabarito_answer_sheet(
    user: dict,
    estado: str,
    municipio_id: str,
    gabarito_ids: List[str],
    escola_ids: Optional[List[str]] = None,
    serie_ids: Optional[List[str]] = None,
    turma_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Uma entrada por gabarito aplicado no recorte.
    Gabarito fora do escopo (ou inexistente) não entra na lista.
    """
    from app.routes.answer_sheet_evaluation_listing import (
        answer_sheet_target_classes_visible_for_user,
    )

    if not gabarito_ids:
        raise ValueError("Informe ao menos uma avaliação")

    permissao = get_user_permission_scope(user)
    _assert_municipio(user, permissao, municipio_id)
    _ensure_tenant_schema(municipio_id)

    escola_ids_norm = [str(x) for x in (escola_ids or [])]
    serie_ids_norm = [str(x) for x in (serie_ids or [])]
    turma_ids_norm = _normalize_turma_ids(turma_ids)

    payload: Dict[str, Any] = {
        "nome": REPORT_NAME,
        "escopo": escopo_payload(
            estado,
            municipio_id,
            escola_ids_norm,
            serie_ids_norm,
            turma_ids_norm,
            report_entity_type="answer_sheet",
        ),
        "avaliacoes": [],
    }

    avaliacoes: List[Dict[str, Any]] = []
    for raw_id in gabarito_ids:
        gabarito_id = str(raw_id)
        gab = AnswerSheetGabarito.query.get(gabarito_id)
        if not gab:
            continue

        classes = answer_sheet_target_classes_visible_for_user(
            gab, user, permissao, municipio_id
        )
        classes = _filter_classes(
            classes,
            escola_ids_norm or None,
            serie_ids_norm or None,
            turma_ids_norm or None,
        )
        if not classes:
            continue

        gab_map = _gabarito_answer_map(gab)
        question_numbers = ordered_question_numbers_for_gabarito(gab)
        q_skills = question_skills_map_for_answer_sheet(gab)
        skill_ids: Set[str] = set()
        for sids in q_skills.values():
            for sid in sids or []:
                skill_ids.add(str(sid))
        skills_db = _fetch_skills_batch(skill_ids)

        questoes: List[Dict[str, Any]] = []
        for numero in question_numbers:
            codigo, descricao = skill_texts_answer_sheet(q_skills.get(numero) or [], skills_db)
            letra = (gab_map.get(numero) or "").strip().upper() or None
            questoes.append(questao_row(numero, codigo, descricao, letra))

        avaliacoes.append(
            {
                "id": gabarito_id,
                "titulo": gab.title or "",
                "questoes": questoes,
            }
        )

    payload["avaliacoes"] = avaliacoes
    logger.info(
        "habilidade_gabarito answer_sheet municipio=%s avaliacoes=%s",
        municipio_id,
        len(avaliacoes),
    )
    return payload
