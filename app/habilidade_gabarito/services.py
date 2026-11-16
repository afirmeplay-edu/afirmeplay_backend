# -*- coding: utf-8 -*-
"""Relatório de habilidade e gabarito — prova digital."""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set

from sqlalchemy.orm import joinedload

from app.habilidade_gabarito.helpers import (
    REPORT_NAME,
    escopo_payload,
    questao_row,
    skill_texts_digital,
)
from app.mapa_questoes.helpers import gabarito_letter
from app.models.city import City
from app.models.test import Test
from app.models.testQuestion import TestQuestion
from app.participation_report.services import _fetch_class_tests
from app.permissions import get_user_permission_scope
from app.services.skills_map_service import (
    _extract_skill_ids_from_question_field,
    _fetch_skills_batch,
)
from app.utils.tenant_middleware import city_id_to_schema_name, set_search_path

logger = logging.getLogger(__name__)


def _ensure_tenant_schema(municipio_id: str) -> None:
    set_search_path(city_id_to_schema_name(str(municipio_id).strip()))


def _assert_municipio(user: dict, permissao: dict, municipio_id: str) -> None:
    if not permissao.get("permitted"):
        raise PermissionError(permissao.get("error") or "Sem permissão")
    city = City.query.get(municipio_id)
    if not city:
        raise ValueError("Município não encontrado")
    if permissao.get("scope") != "all":
        user_city = str(user.get("city_id") or user.get("tenant_id") or "")
        if user_city != str(city.id):
            raise PermissionError("Sem permissão para este município")


def build_habilidade_gabarito_digital(
    user: dict,
    estado: str,
    municipio_id: str,
    avaliacao_ids: List[str],
    escola_ids: Optional[List[str]] = None,
    serie_ids: Optional[List[str]] = None,
    turma_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Uma entrada por avaliação aplicada no recorte.
    Avaliação fora do escopo (ou inexistente) não entra na lista.
    """
    if not avaliacao_ids:
        raise ValueError("Informe ao menos uma avaliação")

    permissao = get_user_permission_scope(user)
    _assert_municipio(user, permissao, municipio_id)
    _ensure_tenant_schema(municipio_id)

    order = [str(x) for x in avaliacao_ids]
    class_tests = _fetch_class_tests(
        municipio_id,
        user,
        permissao,
        avaliacao_ids=order,
        escola_ids=escola_ids or None,
        serie_ids=serie_ids or None,
        turma_ids=turma_ids or None,
    )
    applied: Set[str] = {str(ct.test_id) for ct in class_tests if ct.test_id}
    selected = [tid for tid in order if tid in applied]

    payload: Dict[str, Any] = {
        "nome": REPORT_NAME,
        "escopo": escopo_payload(
            estado,
            municipio_id,
            escola_ids,
            serie_ids,
            turma_ids,
            report_entity_type="digital",
        ),
        "avaliacoes": [],
    }
    if not selected:
        return payload

    tests = Test.query.filter(Test.id.in_(selected)).all()
    tests_by_id = {str(t.id): t for t in tests}

    question_rows = (
        TestQuestion.query.filter(TestQuestion.test_id.in_(selected))
        .options(joinedload(TestQuestion.question))
        .order_by(TestQuestion.order)
        .all()
    )
    by_test: Dict[str, List[TestQuestion]] = defaultdict(list)
    skill_ids: Set[str] = set()
    for tq in question_rows:
        by_test[str(tq.test_id)].append(tq)
        question = tq.question
        if not question:
            continue
        for sid in _extract_skill_ids_from_question_field(getattr(question, "skill", None)):
            skill_ids.add(sid)
    skills_db = _fetch_skills_batch(skill_ids)

    avaliacoes: List[Dict[str, Any]] = []
    for tid in selected:
        test = tests_by_id.get(tid)
        if not test:
            continue
        questoes: List[Dict[str, Any]] = []
        for idx, tq in enumerate(by_test.get(tid, []), start=1):
            question = tq.question
            if not question:
                continue
            numero = int(tq.order) if tq.order is not None else idx
            codigo, descricao = skill_texts_digital(question.skill, skills_db)
            letra = gabarito_letter(question.correct_answer, question.alternatives)
            questoes.append(questao_row(numero, codigo, descricao, letra))
        questoes.sort(key=lambda row: row["numero"])
        avaliacoes.append(
            {
                "id": tid,
                "titulo": test.title or "",
                "questoes": questoes,
            }
        )

    payload["avaliacoes"] = avaliacoes
    logger.info(
        "habilidade_gabarito digital municipio=%s avaliacoes=%s",
        municipio_id,
        len(avaliacoes),
    )
    return payload
