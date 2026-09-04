# -*- coding: utf-8 -*-
"""
Opções de filtro hierárquicas para o relatório de participação.

Hierarquia: Estado → Município → Avaliação → Escola → Série → Turma
Multi-select (CSV) em: avaliações, escolas, séries, turmas.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from sqlalchemy import String, and_, cast, func, or_
from sqlalchemy.orm import joinedload

from app import db
from app.models.city import City
from app.exams.models.classTest import ClassTest
from app.models.grades import Grade
from app.models.school import School
from app.models.studentClass import Class
from app.models.subject import Subject
from app.exams.models.test import Test
from app.permissions import (
    get_manager_school,
    get_teacher_classes,
    get_user_permission_scope,
)
from app.permissions.roles import Roles
from app.utils.class_label_helpers import class_filter_option
from app.utils.uuid_helpers import ensure_uuid_list


def parse_id_list(*raw_values: Optional[str]) -> List[str]:
    """
    Aceita CSV e/ou parâmetros repetidos: 'a,b' + 'c' → ['a', 'b', 'c'].
    Ignora 'all' / 'todas' / vazio.
    """
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


def _user_city_id(user: dict) -> Optional[str]:
    cid = user.get("city_id") or user.get("tenant_id")
    return str(cid) if cid else None


def _filtros_avaliacao_permitida():
    """Exclui olimpíada e espelhos de avaliação subjetiva (por enquanto)."""
    return and_(
        or_(Test.type.is_(None), func.upper(Test.type) != "OLIMPIADA"),
        or_(Test.evaluation_mode.is_(None), func.lower(Test.evaluation_mode) != "subjective"),
    )


def _apply_role_class_school_filters(query, user: dict, permissao: dict):
    """Restringe Class/School conforme escopo do usuário."""
    role = Roles.normalize(user.get("role", ""))
    if permissao.get("scope") != "escola":
        return query

    if role in (Roles.DIRETOR, Roles.COORDENADOR):
        school_id = get_manager_school(user["id"])
        if not school_id:
            return query.filter(False)
        return query.filter(School.id == school_id)

    if role == Roles.PROFESSOR:
        class_ids = get_teacher_classes(user["id"])
        if not class_ids:
            return query.filter(False)
        return query.filter(Class.id.in_(class_ids))

    return query


def _can_access_municipio(user: dict, permissao: dict, municipio_id: str) -> bool:
    city = City.query.get(municipio_id)
    if not city:
        return False
    if permissao.get("scope") == "all":
        return True
    return _user_city_id(user) == str(city.id)


def obter_estados(user: dict, permissao: dict) -> List[Dict[str, Any]]:
    if permissao.get("scope") == "all":
        rows = db.session.query(City.state).distinct().filter(City.state.isnot(None)).all()
    else:
        rows = (
            db.session.query(City.state)
            .distinct()
            .filter(City.state.isnot(None), City.id == user.get("city_id"))
            .all()
        )
    return [{"id": r[0], "nome": r[0]} for r in rows]


def obter_municipios(estado: str, user: dict, permissao: dict) -> List[Dict[str, Any]]:
    if permissao.get("scope") == "all":
        municipios = City.query.filter(City.state.ilike(f"%{estado}%")).all()
    else:
        municipios = City.query.filter(
            City.state.ilike(f"%{estado}%"),
            City.id == user.get("city_id"),
        ).all()
    return [{"id": str(m.id), "nome": m.name} for m in municipios]


def obter_avaliacoes(
    municipio_id: str,
    user: dict,
    permissao: dict,
    escola_ids: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    if not _can_access_municipio(user, permissao, municipio_id):
        return []

    query = (
        Test.query.with_entities(Test.id, Test.title, Subject.name)
        .outerjoin(Subject, Subject.id == Test.subject)
        .join(ClassTest, Test.id == ClassTest.test_id)
        .join(Class, ClassTest.class_id == Class.id)
        .join(School, School.id == cast(Class.school_id, String))
        .join(City, School.city_id == City.id)
        .filter(City.id == municipio_id, _filtros_avaliacao_permitida())
    )
    query = _apply_role_class_school_filters(query, user, permissao)
    if escola_ids:
        query = query.filter(School.id.in_([str(e) for e in escola_ids]))

    rows = query.distinct().all()
    return _format_avaliacoes(rows)


def _format_avaliacoes(rows: List) -> List[Dict[str, Any]]:
    from app.utils.response_formatters import _get_all_subjects_from_test

    if not rows:
        return []

    test_ids = [str(r[0]) for r in rows]
    tests = (
        Test.query.filter(Test.id.in_(test_ids))
        .options(joinedload(Test.subject_rel))
        .all()
    )
    tests_by_id = {str(t.id): t for t in tests}

    result: List[Dict[str, Any]] = []
    seen: Set[str] = set()
    for row in rows:
        tid = str(row[0])
        if tid in seen:
            continue
        seen.add(tid)
        titulo = row[1]
        legacy_subject = (row[2] or "").strip() if len(row) > 2 else ""

        disciplinas: List[str] = []
        test = tests_by_id.get(tid)
        if test:
            for subj in _get_all_subjects_from_test(test):
                name = (subj.get("name") or "").strip()
                if name and name not in disciplinas:
                    disciplinas.append(name)
        if not disciplinas and legacy_subject:
            disciplinas = [legacy_subject]

        result.append(
            {
                "id": tid,
                "titulo": titulo,
                "disciplina": disciplinas[0] if disciplinas else "",
                "disciplinas": disciplinas,
            }
        )
    return result


def obter_escolas(
    municipio_id: str,
    user: dict,
    permissao: dict,
    avaliacao_ids: List[str],
) -> List[Dict[str, Any]]:
    if not avaliacao_ids or not _can_access_municipio(user, permissao, municipio_id):
        return []

    query = (
        School.query.with_entities(School.id, School.name)
        .join(Class, School.id == cast(Class.school_id, String))
        .join(ClassTest, Class.id == ClassTest.class_id)
        .join(Test, ClassTest.test_id == Test.id)
        .join(City, School.city_id == City.id)
        .filter(City.id == municipio_id)
        .filter(Test.id.in_([str(a) for a in avaliacao_ids]))
        .filter(_filtros_avaliacao_permitida())
    )
    query = _apply_role_class_school_filters(query, user, permissao)
    rows = query.distinct().order_by(School.name.asc()).all()
    return [{"id": str(r[0]), "nome": r[1]} for r in rows]


def obter_series(
    municipio_id: str,
    user: dict,
    permissao: dict,
    avaliacao_ids: List[str],
    escola_ids: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    if not avaliacao_ids or not _can_access_municipio(user, permissao, municipio_id):
        return []

    query = (
        Grade.query.with_entities(Grade.id, Grade.name)
        .join(Class, Grade.id == Class.grade_id)
        .join(ClassTest, Class.id == ClassTest.class_id)
        .join(Test, ClassTest.test_id == Test.id)
        .join(School, School.id == cast(Class.school_id, String))
        .join(City, School.city_id == City.id)
        .filter(City.id == municipio_id)
        .filter(Test.id.in_([str(a) for a in avaliacao_ids]))
        .filter(_filtros_avaliacao_permitida())
    )
    if escola_ids:
        query = query.filter(School.id.in_([str(e) for e in escola_ids]))
    query = _apply_role_class_school_filters(query, user, permissao)
    rows = query.distinct().order_by(Grade.name.asc()).all()
    return [{"id": str(r[0]), "nome": r[1]} for r in rows]


def obter_turmas(
    municipio_id: str,
    user: dict,
    permissao: dict,
    avaliacao_ids: List[str],
    escola_ids: Optional[List[str]] = None,
    serie_ids: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    if not avaliacao_ids or not _can_access_municipio(user, permissao, municipio_id):
        return []

    query = (
        Class.query.with_entities(Class.id, Class.name, Class.shift)
        .join(ClassTest, Class.id == ClassTest.class_id)
        .join(Test, ClassTest.test_id == Test.id)
        .join(School, School.id == cast(Class.school_id, String))
        .join(City, School.city_id == City.id)
        .join(Grade, Class.grade_id == Grade.id)
        .filter(City.id == municipio_id)
        .filter(Test.id.in_([str(a) for a in avaliacao_ids]))
        .filter(_filtros_avaliacao_permitida())
    )
    if escola_ids:
        query = query.filter(School.id.in_([str(e) for e in escola_ids]))
    if serie_ids:
        serie_uuids = ensure_uuid_list(serie_ids)
        if not serie_uuids:
            return []
        query = query.filter(Grade.id.in_(serie_uuids))
    query = _apply_role_class_school_filters(query, user, permissao)
    rows = query.distinct().order_by(Class.name.asc()).all()
    return [class_filter_option(r[0], r[1], r[2] if len(r) > 2 else None) for r in rows]


def is_answer_sheet_report(args=None) -> bool:
    """True quando report_entity_type=answer_sheet (query string ou dict)."""
    if args is None:
        from flask import request

        raw = request.args.get("report_entity_type")
    else:
        raw = args.get("report_entity_type") if hasattr(args, "get") else None
    return (str(raw or "").strip().lower()) == "answer_sheet"


def build_filter_options(user: dict, args) -> Dict[str, Any]:
    """
    Monta resposta incremental de opções de filtro a partir dos query args.

    Com report_entity_type=answer_sheet, lista gabaritos na chave ``avaliacoes``.
    """
    if is_answer_sheet_report(args):
        from app.participation_report.services.answer_sheet import build_filter_options_answer_sheet

        return build_filter_options_answer_sheet(user, args)

    permissao = get_user_permission_scope(user)
    if not permissao.get("permitted"):
        raise PermissionError(permissao.get("error") or "Sem permissão")

    estado = (args.get("estado") or "").strip() or None
    municipio = (args.get("municipio") or "").strip() or None

    def _multi(*keys: str) -> List[str]:
        values = []
        for key in keys:
            values.append(args.get(key))
            getlist = getattr(args, "getlist", None)
            if callable(getlist):
                values.extend(getlist(key))
        return parse_id_list(*values)

    avaliacao_ids = _multi("avaliacoes", "avaliacao")
    escola_ids = _multi("escolas", "escola")
    serie_ids = _multi("series", "serie")

    response: Dict[str, Any] = {
        "estados": obter_estados(user, permissao),
    }

    if not estado:
        return response

    response["municipios"] = obter_municipios(estado, user, permissao)

    if not municipio:
        return response

    response["avaliacoes"] = obter_avaliacoes(
        municipio, user, permissao, escola_ids=escola_ids or None
    )

    if not avaliacao_ids:
        return response

    response["escolas"] = obter_escolas(municipio, user, permissao, avaliacao_ids)
    response["series"] = obter_series(
        municipio, user, permissao, avaliacao_ids, escola_ids=escola_ids or None
    )

    if serie_ids or escola_ids:
        response["turmas"] = obter_turmas(
            municipio,
            user,
            permissao,
            avaliacao_ids,
            escola_ids=escola_ids or None,
            serie_ids=serie_ids or None,
        )

    return response
