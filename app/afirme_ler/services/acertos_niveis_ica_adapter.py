# -*- coding: utf-8 -*-
"""Adapter ICA (avaliação escrita) → linhas brutas do Acertos e Níveis."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from app.afirme_ler.services.fluency_results_service import normalize_turno
from app.afirme_ler.services.written_test_ica_service import (
    TOTAL_MAX,
    _filter_people,
    _load,
    _parse_uuid_list,
    skill_map,
)
from app.models.studentClass import Class

COMPONENTE_ESCRITA = "Avaliação escrita"


def _turno_por_turma(class_ids: List[str]) -> Dict[str, str]:
    parsed = _parse_uuid_list([cid for cid in class_ids if cid])
    if not parsed:
        return {}
    out: Dict[str, str] = {}
    for row in (
        Class.query.with_entities(Class.id, Class.shift)
        .filter(Class.id.in_(parsed))
        .all()
    ):
        turno = normalize_turno(row[1])
        if turno:
            out[str(row[0])] = turno
    return out


def people_to_alunos_raw(people: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    class_ids = list({str(p.get("class_id") or "") for p in people if p.get("class_id")})
    turno_map = _turno_por_turma(class_ids)
    rows: List[Dict[str, Any]] = []
    for person in people:
        ica = person.get("ica") or {}
        avaliado = bool(ica.get("avaliado"))
        class_id = str(person.get("class_id") or "")
        rows.append(
            {
                "id": str(person.get("student_id") or ""),
                "nome": person.get("student_name") or "N/A",
                "escola_id": person.get("school_id"),
                "escola": person.get("school_name") or "N/A",
                "serie": person.get("serie_name") or "N/A",
                "turma": person.get("class_name") or "N/A",
                "turno": turno_map.get(class_id, ""),
                "total_acertos_geral": ica.get("pontos_34") or 0,
                "total_questoes_geral": TOTAL_MAX,
                "percentual_acertos_geral": ica.get("nota_100") or 0,
                "nota_geral": ica.get("nota_prof_0_10") or ica.get("nota_tct_0_10") or 0,
                "proficiencia_geral": ica.get("proficiencia") or 0,
                "nivel_proficiencia_geral": ica.get("nivel_aprendizagem"),
                "status_geral": "concluida" if avaliado else "pendente",
                "pontos_34": ica.get("pontos_34"),
            }
        )
    return rows


def skills_to_habilidades_raw(skills_payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for item in skills_payload.get("skills") or []:
        pct = item.get("performance_percentage")
        out.append(
            {
                "codigo": item.get("skill_code") or "",
                "descricao": item.get("skill_label") or "",
                "componente": COMPONENTE_ESCRITA,
                "percentual_acertos": float(pct) if pct is not None else 0.0,
                "serie": None,
            }
        )
    return out


def load_ica_bundle(
    written_test_id: str,
    filters: Optional[Dict[str, Any]] = None,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Carrega recorte ICA e devolve (loaded, alunos_raw, habilidades_raw).

    `loaded` mantém written_test, scope, municipio e people filtrados.
    """
    filters = filters or {}
    loaded = _load(written_test_id, filters)
    people = _filter_people(loaded["people"], filters)
    alunos_raw = people_to_alunos_raw(people)
    skills_payload = skill_map(written_test_id, filters)
    habilidades_raw = skills_to_habilidades_raw(skills_payload)
    loaded = dict(loaded)
    loaded["people"] = people
    return loaded, alunos_raw, habilidades_raw
