# -*- coding: utf-8 -*-
"""Filtros do Relatório de Tempo de Prova (avaliações virtuais: web + mobile)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy import String, cast

from app.models.city import City
from app.models.classTest import ClassTest
from app.models.school import School
from app.models.student import Student
from app.models.studentClass import Class
from app.models.test import Test
from app.models.testSession import TestSession
from app.participation_report.filters import (
    _apply_role_class_school_filters,
    _can_access_municipio,
    _filtros_avaliacao_permitida,
    obter_avaliacoes,
    obter_escolas,
    obter_estados,
    obter_municipios,
    obter_series,
    obter_turmas,
    parse_id_list,
)
from app.permissions import get_user_permission_scope
from app.utils.uuid_helpers import ensure_uuid_list


def obter_alunos(
    municipio_id: str,
    user: dict,
    permissao: dict,
    avaliacao_ids: List[str],
    escola_ids: Optional[List[str]] = None,
    serie_ids: Optional[List[str]] = None,
    turma_ids: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    if not avaliacao_ids or not _can_access_municipio(user, permissao, municipio_id):
        return []

    query = (
        Student.query.with_entities(Student.id, Student.name)
        .join(TestSession, TestSession.student_id == Student.id)
        .join(Test, TestSession.test_id == Test.id)
        .join(ClassTest, ClassTest.test_id == Test.id)
        .join(Class, Class.id == ClassTest.class_id)
        .join(School, School.id == cast(Class.school_id, String))
        .join(City, School.city_id == City.id)
        .filter(City.id == municipio_id)
        .filter(Test.id.in_([str(a) for a in avaliacao_ids]))
        .filter(_filtros_avaliacao_permitida())
        .filter(Student.class_id == Class.id)
    )
    if escola_ids:
        query = query.filter(School.id.in_([str(e) for e in escola_ids]))
    if serie_ids:
        serie_uuids = ensure_uuid_list(serie_ids)
        if not serie_uuids:
            return []
        query = query.filter(Class.grade_id.in_(serie_uuids))
    if turma_ids:
        turma_uuids = ensure_uuid_list(turma_ids)
        if not turma_uuids:
            return []
        query = query.filter(Class.id.in_(turma_uuids))

    query = _apply_role_class_school_filters(query, user, permissao)
    rows = query.distinct().order_by(Student.name.asc()).limit(800).all()
    return [{"id": str(r[0]), "nome": r[1] or ""} for r in rows]


def build_filter_options(user: dict, args) -> Dict[str, Any]:
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
    turma_ids = _multi("turmas", "turma")

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

    if turma_ids or escola_ids or serie_ids:
        response["alunos"] = obter_alunos(
            municipio,
            user,
            permissao,
            avaliacao_ids,
            escola_ids=escola_ids or None,
            serie_ids=serie_ids or None,
            turma_ids=turma_ids or None,
        )

    return response
