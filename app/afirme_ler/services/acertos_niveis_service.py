# -*- coding: utf-8 -*-
"""Orquestra o relatório Acertos e Níveis do Afirme Ler."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.afirme_ler.models.reading_written_test import ReadingWrittenTest
from app.afirme_ler.services.acertos_niveis_contract import (
    FONTE_ESCRITA,
    FONTE_FLUENCIA,
    FONTES,
    NIVEIS,
    build_report_payload,
)
from app.afirme_ler.services.acertos_niveis_ica_adapter import load_ica_bundle
from app.afirme_ler.services.written_test_service import WrittenTestService


def _param(filters: Dict[str, Any], *keys: str) -> Optional[str]:
    for key in keys:
        value = filters.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _normalize_fonte(raw: Optional[str]) -> str:
    if not raw:
        return FONTE_ESCRITA
    key = str(raw).strip().lower()
    aliases = {
        "escrita": FONTE_ESCRITA,
        "ica": FONTE_ESCRITA,
        "written": FONTE_ESCRITA,
        "written_test": FONTE_ESCRITA,
        "avaliacao_escrita": FONTE_ESCRITA,
        "fluencia": FONTE_FLUENCIA,
        "fluência": FONTE_FLUENCIA,
        "fluency": FONTE_FLUENCIA,
        "leitura": FONTE_FLUENCIA,
    }
    fonte = aliases.get(key, key)
    if fonte not in FONTES:
        raise ValueError(
            "fonte inválida. Valores permitidos: escrita, fluencia."
        )
    return fonte


def _avaliacao_id(filters: Dict[str, Any]) -> str:
    value = _param(
        filters,
        "avaliacaoId",
        "avaliacao_id",
        "writtenTestId",
        "written_test_id",
        "avaliacao",
    )
    if not value:
        raise ValueError("avaliacaoId é obrigatório.")
    return value


def catalog(filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Catálogo de filtros para o front (fase 1: só escrita)."""
    filters = dict(filters or {})
    fonte = _normalize_fonte(_param(filters, "fonte", "source"))
    if fonte == FONTE_FLUENCIA:
        return {
            "fonte": fonte,
            "disponivel": False,
            "mensagem": "Fonte fluencia ainda não implementada neste relatório.",
            "niveis": [],
            "avaliacoes": [],
        }

    list_filters = {"status": "publicada", "page": "1", "per_page": "100"}
    for key in ("q", "grade_id", "school_id"):
        if filters.get(key):
            list_filters[key] = filters[key]
    listed = WrittenTestService.list_tests(list_filters)
    avaliacoes: List[Dict[str, Any]] = []
    for item in listed.get("data") or []:
        avaliacoes.append(
            {
                "id": item.get("id"),
                "titulo": item.get("title") or item.get("titulo"),
                "status": item.get("status"),
                "fonte": FONTE_ESCRITA,
            }
        )

    return {
        "fonte": fonte,
        "disponivel": True,
        "fontes": [
            {"id": FONTE_ESCRITA, "label": "Avaliação escrita (ICA)", "disponivel": True},
            {"id": FONTE_FLUENCIA, "label": "Fluência leitora", "disponivel": False},
        ],
        "niveis": list(NIVEIS),
        "avaliacoes": avaliacoes,
        "pagination": listed.get("pagination"),
    }


def report(filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    filters = dict(filters or {})
    fonte = _normalize_fonte(_param(filters, "fonte", "source"))
    if fonte == FONTE_FLUENCIA:
        raise ValueError(
            "Fonte fluencia ainda não implementada. Use fonte=escrita."
        )

    avaliacao_id = _avaliacao_id(filters)
    loaded, alunos_raw, habilidades_raw = load_ica_bundle(avaliacao_id, filters)
    written_test: ReadingWrittenTest = loaded["written_test"]
    scope = loaded.get("scope") or {}

    escola_id = scope.get("escolaId")
    serie_id = scope.get("serieId")
    turma_id = scope.get("turmaId")
    estudante_id = scope.get("estudanteId")
    nivel_granularidade = scope.get("level") or "municipio"
    serie_label = scope.get("serieName")

    turno = _param(filters, "turno", "shift")
    nivel = _param(filters, "nivel", "nivel_aprendizagem", "nivelAprendizagem")

    return build_report_payload(
        fonte=fonte,
        meta={
            "titulo": written_test.title or "Avaliação escrita",
            "avaliacao_id": str(written_test.id),
            "written_test_id": str(written_test.id),
            "estado": loaded.get("uf"),
            "municipio": loaded.get("municipio"),
            "escola": scope.get("escolaName"),
            "escola_id": escola_id,
            "serie": serie_label,
            "serie_id": serie_id,
            "turma": scope.get("turmaName"),
            "turma_id": turma_id,
            "estudante_id": estudante_id,
            "estudante": scope.get("estudanteName"),
            "total_itens": 34,
            "escala": "ica",
            "rede": (
                f"Secretaria Municipal de Educação de {loaded['municipio']}"
                if loaded.get("municipio")
                else None
            ),
        },
        filtros_aplicados={
            "fonte": fonte,
            "avaliacaoId": str(written_test.id),
            "escolaId": escola_id,
            "serieId": serie_id,
            "turmaId": turma_id,
            "estudanteId": estudante_id,
            "turno": turno,
            "nivel": nivel,
            "status": _param(filters, "status"),
        },
        alunos_raw=alunos_raw,
        habilidades_raw=habilidades_raw,
        turno_filtro=turno,
        nivel_filtro=nivel,
        serie_label=serie_label,
        nivel_granularidade=nivel_granularidade,
        niveis=NIVEIS,
    )
