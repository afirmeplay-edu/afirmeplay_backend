# -*- coding: utf-8 -*-
"""Listagem achatada (somente leitura) dos itens de logística.

Cada linha é um logistics_schedule_item. Não grava nada e não altera o editor.
"""
from __future__ import annotations

import unicodedata
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func, or_
from sqlalchemy.orm import Query

from app import db
from app.logistics.services import (
    LogisticsError,
    _parse_date,
    resolve_access,
)
from app.models.educationStage import EducationStage
from app.models.grades import Grade
from app.models.logisticsSchedule import (
    LOGISTICS_STATUS_PUBLISHED,
    LOGISTICS_STATUSES,
    LogisticsSchedule,
    LogisticsScheduleItem,
)
from app.models.school import School
from app.models.studentClass import Class
from app.models.test import EVALUATION_MODES, Test
from app.models.user import User

_ACCENT_FROM = "áàâãäéèêëíìîïóòôõöúùûüç"
_ACCENT_TO = "aaaaaeeeeiiiiooooouuuuc"

if len(_ACCENT_FROM) != len(_ACCENT_TO):
    raise RuntimeError("Mapa de acentos da busca da logística está inconsistente.")

_SHIFT_GROUPS = (
    ("Matutino", ("matutino", "morning", "manha")),
    ("Vespertino", ("vespertino", "afternoon", "tarde")),
    ("Noturno", ("noturno", "night", "noite", "evening")),
    ("Integral", ("integral", "full-time", "fulltime", "full")),
)
_SHIFT_ORDER = {name: index for index, (name, _) in enumerate(_SHIFT_GROUPS)}

_FORMATO_ORDER = {mode: index for index, mode in enumerate(EVALUATION_MODES)}
_DEFAULT_PER_PAGE = 20
_MAX_PER_PAGE = 100


def fold_text(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").strip().lower())
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def canonical_turno(value: Any) -> Optional[str]:
    folded = fold_text(value)
    if not folded:
        return None
    for name, aliases in _SHIFT_GROUPS:
        if folded == fold_text(name) or folded in aliases:
            return name
    raw = str(value).strip()
    return raw or None


def _folded_column(column):
    return func.translate(
        func.lower(func.trim(func.coalesce(column, ""))),
        _ACCENT_FROM,
        _ACCENT_TO,
    )


def _like_pattern(term: str) -> str:
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _opt(args, key: str) -> Optional[str]:
    value = (args.get(key) or "").strip()
    return value or None


def _positive_int(raw: Optional[str], default: int, field: str, maximum: Optional[int] = None) -> int:
    if raw is None:
        return default
    try:
        number = int(raw)
    except (TypeError, ValueError):
        raise LogisticsError(f"{field} inválido.")
    if number < 1:
        raise LogisticsError(f"{field} inválido.")
    if maximum is not None and number > maximum:
        number = maximum
    return number


def _base_query() -> Query:
    return (
        db.session.query(LogisticsScheduleItem, LogisticsSchedule, Test, School, Grade, Class)
        .join(LogisticsSchedule, LogisticsSchedule.id == LogisticsScheduleItem.schedule_id)
        .outerjoin(Test, Test.id == LogisticsSchedule.test_id)
        .outerjoin(School, School.id == LogisticsScheduleItem.school_id)
        .outerjoin(Grade, Grade.id == LogisticsScheduleItem.grade_id)
        .outerjoin(Class, Class.id == LogisticsScheduleItem.class_id)
        .outerjoin(User, User.id == LogisticsScheduleItem.applicator_user_id)
    )


def _apply_access(query: Query, user: dict) -> Tuple[Query, Dict[str, Any]]:
    access = resolve_access(user)
    if access["can_manage"]:
        return query, access
    school_ids = access["school_ids"] or set()
    if not school_ids:
        return query.filter(False), access
    return (
        query.filter(
            LogisticsSchedule.status == LOGISTICS_STATUS_PUBLISHED,
            LogisticsScheduleItem.school_id.in_(list(school_ids)),
        ),
        access,
    )


def _apply_filters(query: Query, args, *, can_manage: bool) -> Query:
    ano = _opt(args, "ano")
    if ano is not None:
        if not ano.isdigit() or len(ano) != 4:
            raise LogisticsError("ano inválido.")
        query = query.filter(func.extract("year", LogisticsScheduleItem.scheduled_date) == int(ano))

    etapa = _opt(args, "etapa")
    if etapa:
        from app.utils.uuid_helpers import ensure_uuid

        etapa_uuid = ensure_uuid(etapa)
        if not etapa_uuid:
            raise LogisticsError("etapa inválida.")
        query = query.filter(Grade.education_stage_id == etapa_uuid)

    avaliacao = _opt(args, "avaliacao")
    if avaliacao:
        query = query.filter(LogisticsSchedule.test_id == avaliacao)

    escola = _opt(args, "escola")
    if escola:
        query = query.filter(LogisticsScheduleItem.school_id == escola)

    serie = _opt(args, "serie")
    if serie:
        from app.utils.uuid_helpers import ensure_uuid

        serie_uuid = ensure_uuid(serie)
        if not serie_uuid:
            raise LogisticsError("serie inválida.")
        query = query.filter(LogisticsScheduleItem.grade_id == serie_uuid)

    turno = _opt(args, "turno")
    if turno:
        canon = canonical_turno(turno)
        keys = {fold_text(turno)}
        for name, aliases in _SHIFT_GROUPS:
            if canon == name:
                keys.update(aliases)
                keys.add(fold_text(name))
        query = query.filter(_folded_column(Class.shift).in_(list(keys)))

    formato = _opt(args, "formato")
    if formato:
        formato = formato.lower()
        if formato not in EVALUATION_MODES:
            raise LogisticsError("formato inválido.")
        if formato == "virtual":
            query = query.filter(
                or_(
                    func.lower(func.coalesce(Test.evaluation_mode, "virtual")) == "virtual",
                    Test.evaluation_mode.is_(None),
                )
            )
        else:
            query = query.filter(func.lower(Test.evaluation_mode) == formato)

    data_inicio = _parse_date(_opt(args, "data_inicio"), "data_inicio") if _opt(args, "data_inicio") else None
    data_fim = _parse_date(_opt(args, "data_fim"), "data_fim") if _opt(args, "data_fim") else None
    if data_inicio:
        query = query.filter(LogisticsScheduleItem.scheduled_date >= data_inicio)
    if data_fim:
        query = query.filter(LogisticsScheduleItem.scheduled_date <= data_fim)

    aplicador = _opt(args, "aplicador")
    sem_aplicador = (_opt(args, "sem_aplicador") or "").lower()
    if sem_aplicador in ("1", "true", "sim") or aplicador == "sem_aplicador":
        query = query.filter(LogisticsScheduleItem.applicator_user_id.is_(None))
    elif aplicador:
        query = query.filter(LogisticsScheduleItem.applicator_user_id == aplicador)

    status = _opt(args, "status")
    if status:
        status = status.lower()
        if status not in LOGISTICS_STATUSES:
            raise LogisticsError("status inválido.")
        if not can_manage and status != LOGISTICS_STATUS_PUBLISHED:
            return query.filter(False)
        query = query.filter(LogisticsSchedule.status == status)

    term = fold_text(_opt(args, "q") or "")
    if term:
        pattern = _like_pattern(term)
        folded_school = _folded_column(School.name)
        folded_class = _folded_column(Class.name)
        folded_grade = _folded_column(Grade.name)
        folded_applicator = _folded_column(User.name)
        query = query.filter(
            or_(
                folded_school.like(pattern, escape="\\"),
                folded_class.like(pattern, escape="\\"),
                folded_grade.like(pattern, escape="\\"),
                folded_applicator.like(pattern, escape="\\"),
            )
        )
    return query


def _cards(query: Query) -> Dict[str, int]:
    row = query.order_by(None).with_entities(
        func.count(func.distinct(LogisticsScheduleItem.id)),
        func.coalesce(func.sum(LogisticsScheduleItem.students_count), 0),
        func.count(func.distinct(LogisticsScheduleItem.school_id)),
        func.count(func.distinct(LogisticsScheduleItem.class_id)),
    ).one()
    return {
        "total_agendamentos": int(row[0] or 0),
        "total_alunos_previstos": int(row[1] or 0),
        "escolas_atendidas": int(row[2] or 0),
        "turmas_agendadas": int(row[3] or 0),
    }


def _serialize_row(item, schedule, test, school, grade, class_, applicator=None) -> Dict[str, Any]:
    mode = (test.evaluation_mode if test and test.evaluation_mode else None) or "virtual"
    scheduled = item.scheduled_date.isoformat() if isinstance(item.scheduled_date, date) else (
        item.scheduled_date.isoformat() if item.scheduled_date else None
    )
    return {
        "id": str(item.id),
        "schedule_id": str(item.schedule_id),
        "status": schedule.status,
        "test_id": schedule.test_id,
        "test_title": test.title if test else None,
        "evaluation_mode": mode,
        "scheduled_date": scheduled,
        "school_id": str(item.school_id) if item.school_id else None,
        "school_name": school.name if school else None,
        "grade_id": str(item.grade_id) if item.grade_id else None,
        "grade_name": grade.name if grade else None,
        "class_id": str(item.class_id) if item.class_id else None,
        "class_name": class_.name if class_ else None,
        "turno": canonical_turno(class_.shift) if class_ else None,
        "students_count": int(item.students_count or 0),
        "tablets_qty": int(item.tablets_qty or 0),
        "booklets_qty": int(item.booklets_qty or 0),
        "applicator_user_id": str(item.applicator_user_id) if item.applicator_user_id else None,
        "applicator_name": (applicator.name if applicator and applicator.name else None),
        "origem": item.origem or "manual",
        "editado_manualmente": bool(item.editado_manualmente),
    }


def list_items(user: dict, args) -> Dict[str, Any]:
    query, access = _apply_access(_base_query(), user)
    query = _apply_filters(query, args, can_manage=access["can_manage"])
    cards = _cards(query)
    page = _positive_int(_opt(args, "page"), 1, "page")
    per_page = _positive_int(_opt(args, "per_page"), _DEFAULT_PER_PAGE, "per_page", _MAX_PER_PAGE)

    rows = (
        query.order_by(
            LogisticsScheduleItem.scheduled_date.asc().nulls_last(),
            func.lower(func.coalesce(School.name, "")).asc(),
            func.lower(func.coalesce(Grade.name, "")).asc(),
            func.lower(func.coalesce(Class.name, "")).asc(),
            LogisticsScheduleItem.id.asc(),
        )
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return {
        "items": [_serialize_row(*row) for row in rows],
        "total": cards["total_agendamentos"],
        "page": page,
        "per_page": per_page,
        "cards": cards,
        "can_manage": access["can_manage"],
    }


def _empty_options(can_manage: bool) -> Dict[str, Any]:
    return {
        "anos": [],
        "etapas": [],
        "avaliacoes": [],
        "escolas": [],
        "series": [],
        "turnos": [],
        "formatos": [],
        "aplicadores": [],
        "status": list(LOGISTICS_STATUSES) if can_manage else [LOGISTICS_STATUS_PUBLISHED],
        "can_manage": can_manage,
    }


def grade_filter_options(user: dict) -> Dict[str, Any]:
    """Opções da grade, no recorte de quem consulta. Não altera /opcoes-filtros."""
    query, access = _apply_access(_base_query(), user)
    query = query.outerjoin(EducationStage, EducationStage.id == Grade.education_stage_id)
    if not access["can_manage"] and not access["school_ids"]:
        return _empty_options(False)

    rows = query.with_entities(
        LogisticsScheduleItem.scheduled_date,
        LogisticsSchedule.test_id,
        Test.title,
        Test.evaluation_mode,
        LogisticsScheduleItem.school_id,
        School.name,
        LogisticsScheduleItem.grade_id,
        Grade.name,
        Grade.education_stage_id,
        EducationStage.name,
        Class.shift,
        User.id,
        User.name,
    ).all()

    anos = set()
    etapas: Dict[str, str] = {}
    avaliacoes: Dict[str, Dict[str, Any]] = {}
    escolas: Dict[str, str] = {}
    series: Dict[str, Dict[str, Any]] = {}
    turnos = set()
    formatos = set()
    aplicadores: Dict[str, str] = {}

    for (
        scheduled,
        test_id,
        title,
        mode,
        school_id,
        school_name,
        grade_id,
        grade_name,
        stage_id,
        stage_name,
        shift,
        applicator_id,
        applicator_name,
    ) in rows:
        if isinstance(scheduled, date):
            anos.add(scheduled.year)
        stage_key = str(stage_id) if stage_id else None
        if stage_key and stage_name:
            etapas[stage_key] = stage_name
        if test_id:
            entry = avaliacoes.setdefault(
                str(test_id),
                {
                    "id": str(test_id),
                    "titulo": title or str(test_id),
                    "evaluation_mode": (mode or "virtual"),
                    "etapa_ids": set(),
                },
            )
            if stage_key:
                entry["etapa_ids"].add(stage_key)
        if school_id and school_name:
            escolas[str(school_id)] = school_name
        if grade_id and grade_name:
            serie = series.setdefault(
                str(grade_id),
                {
                    "id": str(grade_id),
                    "nome": grade_name,
                    "etapa_id": stage_key,
                    "escola_ids": set(),
                },
            )
            if school_id:
                serie["escola_ids"].add(str(school_id))
        turno = canonical_turno(shift)
        if turno:
            turnos.add(turno)
        formatos.add((mode or "virtual").strip().lower() or "virtual")
        if applicator_id:
            aplicadores[str(applicator_id)] = applicator_name or "Sem nome"

    def _by_name(pairs: List[Tuple[str, str]]) -> List[Dict[str, str]]:
        return [{"id": key, "nome": name} for key, name in sorted(pairs, key=lambda pair: (pair[1] or "").lower())]

    return {
        "anos": sorted(anos, reverse=True),
        "etapas": _by_name(list(etapas.items())),
        "avaliacoes": sorted(
            (
                {
                    "id": item["id"],
                    "titulo": item["titulo"],
                    "evaluation_mode": item["evaluation_mode"],
                    "etapa_ids": sorted(item["etapa_ids"]),
                }
                for item in avaliacoes.values()
            ),
            key=lambda item: (item["titulo"] or "").lower(),
        ),
        "escolas": _by_name(list(escolas.items())),
        "series": sorted(
            (
                {
                    "id": item["id"],
                    "nome": item["nome"],
                    "etapa_id": item["etapa_id"],
                    "escola_ids": sorted(item["escola_ids"]),
                }
                for item in series.values()
            ),
            key=lambda item: (item["nome"] or "").lower(),
        ),
        "turnos": sorted(turnos, key=lambda name: (_SHIFT_ORDER.get(name, 99), name.lower())),
        "formatos": sorted(formatos, key=lambda mode: (_FORMATO_ORDER.get(mode, 99), mode)),
        "aplicadores": _by_name(list(aplicadores.items())),
        "status": list(LOGISTICS_STATUSES) if access["can_manage"] else [LOGISTICS_STATUS_PUBLISHED],
        "can_manage": access["can_manage"],
    }
