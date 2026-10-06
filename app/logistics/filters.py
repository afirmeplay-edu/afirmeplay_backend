# -*- coding: utf-8 -*-
"""
Opções de filtro em cascata para o cronograma de logística.

Hierarquia: Etapa → Avaliação → Escolas → Séries → Turmas (município = tenant atual).
A etapa é resolvida por Class.grade_id → Grade.education_stage_id (Test.course é texto livre).
As turmas de uma avaliação vêm de tenant.class_test (somente leitura).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from sqlalchemy import String, cast

from app import db
from app.models.classTest import ClassTest
from app.models.educationStage import EducationStage
from app.models.grades import Grade
from app.models.school import School
from app.models.studentClass import Class
from app.models.test import Test
from app.utils.class_label_helpers import normalize_shift
from app.utils.uuid_helpers import ensure_uuid, ensure_uuid_list


def parse_id_list(*raw_values: Optional[str]) -> List[str]:
    """Aceita CSV e/ou parâmetros repetidos. Ignora 'all' / 'todas' / vazio."""
    ids: List[str] = []
    seen: Set[str] = set()
    for raw in raw_values:
        if raw is None:
            continue
        for part in str(raw).split(","):
            value = part.strip()
            if not value or value.lower() in ("all", "todas"):
                continue
            if value not in seen:
                seen.add(value)
                ids.append(value)
    return ids


def multi_arg(args, *keys: str) -> List[str]:
    values: List[Optional[str]] = []
    for key in keys:
        values.append(args.get(key))
        getlist = getattr(args, "getlist", None)
        if callable(getlist):
            values.extend(getlist(key))
    return parse_id_list(*values)


def _class_test_scope(query, city_id: str, etapa_id: Optional[str] = None):
    """Restringe uma query já ligada a Class/School ao município e (opcional) à etapa."""
    query = query.filter(School.city_id == city_id)
    if etapa_id:
        etapa_uuid = ensure_uuid(etapa_id)
        if not etapa_uuid:
            return query.filter(False)
        query = query.filter(Grade.education_stage_id == etapa_uuid)
    return query


def obter_etapas(city_id: str) -> List[Dict[str, Any]]:
    rows = (
        db.session.query(EducationStage.id, EducationStage.name)
        .join(Grade, Grade.education_stage_id == EducationStage.id)
        .join(Class, Class.grade_id == Grade.id)
        .join(ClassTest, ClassTest.class_id == Class.id)
        .join(School, School.id == cast(Class.school_id, String))
        .filter(School.city_id == city_id)
        .distinct()
        .order_by(EducationStage.name.asc())
        .all()
    )
    return [{"id": str(r[0]), "nome": r[1]} for r in rows]


def obter_avaliacoes(city_id: str, etapa_id: Optional[str] = None) -> List[Dict[str, Any]]:
    query = (
        db.session.query(Test.id, Test.title, Test.evaluation_mode)
        .join(ClassTest, ClassTest.test_id == Test.id)
        .join(Class, Class.id == ClassTest.class_id)
        .join(School, School.id == cast(Class.school_id, String))
        .outerjoin(Grade, Grade.id == Class.grade_id)
    )
    query = _class_test_scope(query, city_id, etapa_id)
    rows = query.distinct().order_by(Test.title.asc()).all()
    return [
        {"id": str(r[0]), "titulo": r[1], "evaluation_mode": r[2] or "virtual"}
        for r in rows
    ]


def obter_escolas(
    city_id: str, avaliacao_id: str, etapa_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    query = (
        db.session.query(School.id, School.name)
        .join(Class, School.id == cast(Class.school_id, String))
        .join(ClassTest, ClassTest.class_id == Class.id)
        .outerjoin(Grade, Grade.id == Class.grade_id)
        .filter(ClassTest.test_id == str(avaliacao_id))
    )
    query = _class_test_scope(query, city_id, etapa_id)
    rows = query.distinct().order_by(School.name.asc()).all()
    return [{"id": str(r[0]), "nome": r[1]} for r in rows]


def obter_series(
    city_id: str,
    avaliacao_id: str,
    etapa_id: Optional[str] = None,
    escola_ids: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    query = (
        db.session.query(Grade.id, Grade.name)
        .join(Class, Class.grade_id == Grade.id)
        .join(ClassTest, ClassTest.class_id == Class.id)
        .join(School, School.id == cast(Class.school_id, String))
        .filter(ClassTest.test_id == str(avaliacao_id))
    )
    query = _class_test_scope(query, city_id, etapa_id)
    if escola_ids:
        query = query.filter(School.id.in_([str(e) for e in escola_ids]))
    rows = query.distinct().order_by(Grade.name.asc()).all()
    return [{"id": str(r[0]), "nome": r[1]} for r in rows]


def obter_turmas(
    city_id: str,
    avaliacao_id: str,
    etapa_id: Optional[str] = None,
    escola_ids: Optional[List[str]] = None,
    serie_ids: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    query = (
        db.session.query(
            Class.id, Class.name, Class.shift, School.id, School.name, Grade.id, Grade.name
        )
        .join(ClassTest, ClassTest.class_id == Class.id)
        .join(School, School.id == cast(Class.school_id, String))
        .outerjoin(Grade, Grade.id == Class.grade_id)
        .filter(ClassTest.test_id == str(avaliacao_id))
    )
    query = _class_test_scope(query, city_id, etapa_id)
    if escola_ids:
        query = query.filter(School.id.in_([str(e) for e in escola_ids]))
    if serie_ids:
        serie_uuids = ensure_uuid_list(serie_ids)
        if not serie_uuids:
            return []
        query = query.filter(Grade.id.in_(serie_uuids))
    rows = query.distinct().order_by(School.name.asc(), Grade.name.asc(), Class.name.asc()).all()
    return [
        {
            "id": str(r[0]),
            "name": (r[1] or "").strip() or f"Turma {r[0]}",
            "shift": normalize_shift(r[2]) or "",
            "school_id": str(r[3]),
            "school_name": r[4],
            "grade_id": str(r[5]) if r[5] else None,
            "grade_name": r[6],
        }
        for r in rows
    ]


def build_filter_options(city_id: str, args) -> Dict[str, Any]:
    """Resposta incremental: cada nível só aparece quando o anterior foi informado."""
    etapa_id = (args.get("etapa") or "").strip() or None
    avaliacao_id = (args.get("avaliacao") or "").strip() or None
    escola_ids = multi_arg(args, "escolas", "escola")
    serie_ids = multi_arg(args, "series", "serie")

    response: Dict[str, Any] = {
        "etapas": obter_etapas(city_id),
        "avaliacoes": obter_avaliacoes(city_id, etapa_id),
    }
    if not avaliacao_id:
        return response

    response["escolas"] = obter_escolas(city_id, avaliacao_id, etapa_id)
    response["series"] = obter_series(
        city_id, avaliacao_id, etapa_id, escola_ids=escola_ids or None
    )
    if escola_ids or serie_ids:
        response["turmas"] = obter_turmas(
            city_id,
            avaliacao_id,
            etapa_id,
            escola_ids=escola_ids or None,
            serie_ids=serie_ids or None,
        )
    return response
