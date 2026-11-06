# -*- coding: utf-8 -*-
"""
Opções de filtro em cascata para o cronograma de logística.

Hierarquia: Avaliação → Escolas → Séries → Turmas (município = tenant atual).
As turmas de uma avaliação vêm de tenant.class_test (somente leitura).
O parâmetro etapa ainda é aceito na API por compatibilidade, mas não filtra.
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
from app.utils.uuid_helpers import ensure_uuid_list


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


def _class_test_scope(query, city_id: str):
    """Restringe uma query já ligada a Class/School ao município."""
    return query.filter(School.city_id == city_id)


def obter_etapas(city_id: str) -> List[Dict[str, Any]]:
    """Mantido por compatibilidade; a tela do editor não usa mais etapa."""
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


def obter_avaliacoes(city_id: str) -> List[Dict[str, Any]]:
    query = (
        db.session.query(Test.id, Test.title, Test.evaluation_mode)
        .join(ClassTest, ClassTest.test_id == Test.id)
        .join(Class, Class.id == ClassTest.class_id)
        .join(School, School.id == cast(Class.school_id, String))
    )
    query = _class_test_scope(query, city_id)
    rows = query.distinct().order_by(Test.title.asc()).all()
    return [
        {"id": str(r[0]), "titulo": r[1], "evaluation_mode": r[2] or "virtual"}
        for r in rows
    ]


def obter_escolas(city_id: str, avaliacao_id: str) -> List[Dict[str, Any]]:
    query = (
        db.session.query(School.id, School.name)
        .join(Class, School.id == cast(Class.school_id, String))
        .join(ClassTest, ClassTest.class_id == Class.id)
        .filter(ClassTest.test_id == str(avaliacao_id))
    )
    query = _class_test_scope(query, city_id)
    rows = query.distinct().order_by(School.name.asc()).all()
    return [{"id": str(r[0]), "nome": r[1]} for r in rows]


def obter_series(
    city_id: str,
    avaliacao_id: str,
    escola_ids: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    query = (
        db.session.query(Grade.id, Grade.name)
        .join(Class, Class.grade_id == Grade.id)
        .join(ClassTest, ClassTest.class_id == Class.id)
        .join(School, School.id == cast(Class.school_id, String))
        .filter(ClassTest.test_id == str(avaliacao_id))
    )
    query = _class_test_scope(query, city_id)
    if escola_ids:
        query = query.filter(School.id.in_([str(e) for e in escola_ids]))
    rows = query.distinct().order_by(Grade.name.asc()).all()
    return [{"id": str(r[0]), "nome": r[1]} for r in rows]


def obter_turmas(
    city_id: str,
    avaliacao_id: str,
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
    query = _class_test_scope(query, city_id)
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


def obter_escolas_municipio(city_id: str) -> List[Dict[str, Any]]:
    rows = (
        db.session.query(School.id, School.name)
        .join(Class, School.id == cast(Class.school_id, String))
        .filter(School.city_id == city_id)
        .distinct()
        .order_by(School.name.asc())
        .all()
    )
    return [{"id": str(r[0]), "nome": r[1]} for r in rows]


def obter_series_municipio(
    city_id: str, escola_ids: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    query = (
        db.session.query(Grade.id, Grade.name)
        .join(Class, Class.grade_id == Grade.id)
        .join(School, School.id == cast(Class.school_id, String))
        .filter(School.city_id == city_id)
    )
    if escola_ids:
        query = query.filter(School.id.in_([str(e) for e in escola_ids]))
    rows = query.distinct().order_by(Grade.name.asc()).all()
    return [{"id": str(r[0]), "nome": r[1]} for r in rows]


def obter_turmas_municipio(
    city_id: str,
    escola_ids: Optional[List[str]] = None,
    serie_ids: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    query = (
        db.session.query(
            Class.id, Class.name, Class.shift, School.id, School.name, Grade.id, Grade.name
        )
        .join(School, School.id == cast(Class.school_id, String))
        .outerjoin(Grade, Grade.id == Class.grade_id)
        .filter(School.city_id == city_id)
    )
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
    """Resposta incremental: cada nível só aparece quando o anterior foi informado.

    O parâmetro etapa é ignorado (compatibilidade com clientes antigos).
    Com source=cartao_resposta|personalizada, a cascata usa todas as turmas do município.
    """
    source = (args.get("source") or args.get("origem") or "").strip().lower() or None
    municipal = source in ("cartao_resposta", "personalizada", "cartao", "municipal")
    avaliacao_id = (args.get("avaliacao") or "").strip() or None
    escola_ids = multi_arg(args, "escolas", "escola")
    serie_ids = multi_arg(args, "series", "serie")

    response: Dict[str, Any] = {
        "etapas": obter_etapas(city_id),
        "avaliacoes": obter_avaliacoes(city_id),
        "source": source,
    }

    if municipal:
        response["escolas"] = obter_escolas_municipio(city_id)
        response["series"] = obter_series_municipio(city_id, escola_ids=escola_ids or None)
        if escola_ids or serie_ids:
            response["turmas"] = obter_turmas_municipio(
                city_id,
                escola_ids=escola_ids or None,
                serie_ids=serie_ids or None,
            )
        return response

    if not avaliacao_id:
        return response

    response["escolas"] = obter_escolas(city_id, avaliacao_id)
    response["series"] = obter_series(
        city_id, avaliacao_id, escola_ids=escola_ids or None
    )
    if escola_ids or serie_ids:
        response["turmas"] = obter_turmas(
            city_id,
            avaliacao_id,
            escola_ids=escola_ids or None,
            serie_ids=serie_ids or None,
        )
    return response
