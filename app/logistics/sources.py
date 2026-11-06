# -*- coding: utf-8 -*-
"""Origens do cronograma: avaliação, cartão-resposta e personalizada."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from sqlalchemy import String, cast, func

from app import db
from app.models.answerSheetGabarito import AnswerSheetGabarito
from app.models.grades import Grade
from app.models.logisticsSchedule import (
    LOGISTICS_EVAL_MODES,
    LOGISTICS_EVAL_PHYSICAL,
    LOGISTICS_SOURCE_AVALIACAO,
    LOGISTICS_SOURCE_CARTAO,
    LOGISTICS_SOURCE_PERSONALIZADA,
    LOGISTICS_SOURCES,
    LogisticsSchedule,
)
from app.models.school import School
from app.models.student import Student
from app.models.studentClass import Class
from app.models.test import Test
from app.services.cartao_resposta.answer_sheet_gabarito_generation import (
    AnswerSheetGabaritoGeneration,
)
from app.utils.class_label_helpers import normalize_shift
from app.utils.municipality_availability import apply_municipality_availability_filter
from app.utils.uuid_helpers import ensure_uuid, ensure_uuid_list


SOURCE_LABELS = {
    LOGISTICS_SOURCE_AVALIACAO: "Avaliação do sistema",
    LOGISTICS_SOURCE_CARTAO: "Cartão-resposta",
    LOGISTICS_SOURCE_PERSONALIZADA: "Personalizada",
}


def normalize_source(raw: Any) -> str:
    value = (str(raw or "").strip().lower() or LOGISTICS_SOURCE_AVALIACAO)
    if value not in LOGISTICS_SOURCES:
        raise ValueError(f"source inválido: {raw!r}")
    return value


def schedule_source(schedule: LogisticsSchedule) -> str:
    value = (getattr(schedule, "source", None) or LOGISTICS_SOURCE_AVALIACAO)
    value = str(value).strip().lower()
    return value if value in LOGISTICS_SOURCES else LOGISTICS_SOURCE_AVALIACAO


def instrument_key(schedule: LogisticsSchedule) -> str:
    source = schedule_source(schedule)
    if source == LOGISTICS_SOURCE_AVALIACAO:
        return f"avaliacao:{schedule.test_id}"
    if source == LOGISTICS_SOURCE_CARTAO:
        if schedule.gabarito_id:
            return f"cartao:{schedule.gabarito_id}"
        return f"cartao-schedule:{schedule.id}"
    return f"personalizada:{schedule.id}"


def parse_instrument_key(raw: Optional[str]) -> Optional[Tuple[str, str]]:
    text = (raw or "").strip()
    if not text or ":" not in text:
        return None
    kind, value = text.split(":", 1)
    kind = kind.strip().lower()
    value = value.strip()
    if not value:
        return None
    if kind in ("avaliacao", "cartao", "cartao-schedule", "personalizada"):
        return kind, value
    return None


def schedule_display_label(
    schedule: LogisticsSchedule,
    *,
    test: Optional[Test] = None,
    gabarito: Optional[AnswerSheetGabarito] = None,
) -> str:
    source = schedule_source(schedule)
    if source == LOGISTICS_SOURCE_AVALIACAO:
        return (test.title if test else None) or schedule.title or "Avaliação"
    if source == LOGISTICS_SOURCE_CARTAO:
        return (
            schedule.title
            or (gabarito.title if gabarito else None)
            or "Cartão-resposta"
        )
    return (schedule.title or "").strip() or "Personalizada"


def schedule_evaluation_mode(
    schedule: LogisticsSchedule, *, test: Optional[Test] = None
) -> str:
    source = schedule_source(schedule)
    if source == LOGISTICS_SOURCE_AVALIACAO:
        return ((test.evaluation_mode if test else None) or "virtual").strip().lower()
    if source == LOGISTICS_SOURCE_CARTAO:
        return LOGISTICS_EVAL_PHYSICAL
    mode = (schedule.evaluation_mode or LOGISTICS_EVAL_PHYSICAL).strip().lower()
    return mode if mode in LOGISTICS_EVAL_MODES else LOGISTICS_EVAL_PHYSICAL


def source_badge(schedule: LogisticsSchedule) -> Optional[str]:
    source = schedule_source(schedule)
    if source == LOGISTICS_SOURCE_CARTAO:
        return "Cartão-resposta"
    if source == LOGISTICS_SOURCE_PERSONALIZADA:
        return "Personalizada"
    return None


def city_classes_info(
    city_id: str, class_ids: Iterable[Any]
) -> Dict[str, Dict[str, Any]]:
    """Turmas do município entre class_ids (sem exigir class_test)."""
    uuids = ensure_uuid_list(list(class_ids))
    if not uuids:
        return {}
    rows = (
        db.session.query(Class.id, cast(Class.school_id, String), Class.grade_id)
        .join(School, School.id == cast(Class.school_id, String))
        .filter(School.city_id == city_id, Class.id.in_(uuids))
        .distinct()
        .all()
    )
    return {
        str(r[0]): {"school_id": str(r[1]), "grade_id": r[2]}
        for r in rows
    }


def _student_count_by_class(class_ids: Iterable[Any]) -> Dict[str, int]:
    uuids = ensure_uuid_list(list(class_ids))
    if not uuids:
        return {}
    rows = (
        db.session.query(Student.class_id, func.count(Student.id))
        .filter(Student.class_id.in_(uuids))
        .group_by(Student.class_id)
        .all()
    )
    return {str(cid): int(total) for cid, total in rows if cid is not None}


def _student_count_adap(
    class_to_subturmas: Dict[str, Set[str]],
) -> Dict[str, int]:
    """Contagem por turma restrita às subturmas ADAP informadas."""
    counts: Dict[str, int] = {}
    for class_id, sub_ids in class_to_subturmas.items():
        class_uuid = ensure_uuid(class_id)
        sub_uuids = ensure_uuid_list(list(sub_ids))
        if not class_uuid or not sub_uuids:
            counts[str(class_id)] = 0
            continue
        total = (
            db.session.query(func.count(Student.id))
            .filter(
                Student.class_id == class_uuid,
                Student.subturma_id.in_(sub_uuids),
            )
            .scalar()
        )
        counts[str(class_id)] = int(total or 0)
    return counts


def _class_ids_from_snapshot(snapshot: Any) -> Tuple[List[str], Dict[str, Set[str]]]:
    """Devolve (class_ids ordenados, mapa turma→subturmas ADAP)."""
    if not isinstance(snapshot, dict):
        return [], {}
    entries = snapshot.get("class_ids") or []
    adap = bool(snapshot.get("subturma_ids"))
    class_ids: List[str] = []
    seen: Set[str] = set()
    adap_map: Dict[str, Set[str]] = {}
    for item in entries:
        if isinstance(item, dict):
            cid = str(item.get("class_id") or "").strip()
            sub = str(item.get("subturma_id") or "").strip() if adap else ""
        else:
            cid = str(item or "").strip()
            sub = ""
        if not cid:
            continue
        if cid not in seen:
            seen.add(cid)
            class_ids.append(cid)
        if sub:
            adap_map.setdefault(cid, set()).add(sub)
    # Também aceita subturma_ids no topo sem vínculo por item
    if adap and not adap_map:
        top_subs = {
            str(s).strip() for s in (snapshot.get("subturma_ids") or []) if str(s or "").strip()
        }
        if top_subs:
            for cid in class_ids:
                adap_map[cid] = set(top_subs)
    return class_ids, adap_map


def _class_ids_from_gabarito_cadastro(gabarito: AnswerSheetGabarito) -> List[str]:
    """Fallback sem geração: class_id, grades/grade_id e school_id do cadastro."""
    if gabarito.class_id:
        return [str(gabarito.class_id)]

    grade_ids: List[Any] = []
    raw_grades = gabarito.grades
    if isinstance(raw_grades, list):
        for entry in raw_grades:
            if isinstance(entry, dict) and entry.get("id"):
                grade_ids.append(entry["id"])
            elif entry:
                grade_ids.append(entry)
    if gabarito.grade_id and not grade_ids:
        grade_ids.append(gabarito.grade_id)

    query = (
        db.session.query(Class.id)
        .join(School, School.id == cast(Class.school_id, String))
    )
    if gabarito.school_id:
        query = query.filter(School.id == str(gabarito.school_id))
    grade_uuids = ensure_uuid_list(grade_ids)
    if grade_uuids:
        query = query.filter(Class.grade_id.in_(grade_uuids))
    elif not gabarito.school_id:
        return []
    return [str(row[0]) for row in query.distinct().all()]


def last_generation_for_gabarito(
    gabarito_id: str,
) -> Optional[AnswerSheetGabaritoGeneration]:
    return (
        AnswerSheetGabaritoGeneration.query.filter_by(gabarito_id=str(gabarito_id))
        .order_by(
            AnswerSheetGabaritoGeneration.created_at.desc(),
            AnswerSheetGabaritoGeneration.id.desc(),
        )
        .first()
    )


def resolve_gabarito_class_scope(
    gabarito: AnswerSheetGabarito,
) -> Tuple[List[str], Dict[str, Set[str]], Optional[datetime]]:
    """Turmas sugeridas do cartão + mapa ADAP + data da última geração."""
    generation = last_generation_for_gabarito(str(gabarito.id))
    if generation and generation.scope_snapshot:
        class_ids, adap_map = _class_ids_from_snapshot(generation.scope_snapshot)
        if class_ids:
            return class_ids, adap_map, generation.created_at
    return _class_ids_from_gabarito_cadastro(gabarito), {}, (
        generation.created_at if generation else None
    )


def get_gabarito_or_error(gabarito_id: Any) -> AnswerSheetGabarito:
    if not gabarito_id:
        raise ValueError("gabarito_id é obrigatório.")
    gabarito = AnswerSheetGabarito.query.get(str(gabarito_id))
    if not gabarito:
        raise LookupError("Gabarito não encontrado.")
    return gabarito


def list_municipality_gabaritos(user: dict) -> List[Dict[str, Any]]:
    """Mesmo recorte de GET /answer-sheets/gabaritos (admin/tecadm vê todos)."""
    query = AnswerSheetGabarito.query
    role = str((user or {}).get("role") or "").strip().lower()
    if role not in ("admin", "tecadm", "aplicador"):
        query = query.filter(AnswerSheetGabarito.created_by == str(user.get("id")))
    query = apply_municipality_availability_filter(query, AnswerSheetGabarito, user)
    gabaritos = query.order_by(AnswerSheetGabarito.created_at.desc()).all()
    if not gabaritos:
        return []

    ids = [str(g.id) for g in gabaritos]
    last_by_gabarito: Dict[str, datetime] = {}
    rows = (
        db.session.query(
            AnswerSheetGabaritoGeneration.gabarito_id,
            func.max(AnswerSheetGabaritoGeneration.created_at),
        )
        .filter(AnswerSheetGabaritoGeneration.gabarito_id.in_(ids))
        .group_by(AnswerSheetGabaritoGeneration.gabarito_id)
        .all()
    )
    for gid, when in rows:
        if when:
            last_by_gabarito[str(gid)] = when

    result = []
    for gabarito in gabaritos:
        last_at = last_by_gabarito.get(str(gabarito.id))
        result.append(
            {
                "id": str(gabarito.id),
                "titulo": (gabarito.title or "").strip() or f"Gabarito {gabarito.id}",
                "last_generation_at": last_at.isoformat() if last_at else None,
            }
        )
    return result


def _preview_rows_for_classes(
    class_ids: List[str],
    *,
    city_id: str,
    evaluation_mode: str,
    escola_ids: Optional[List[str]] = None,
    serie_ids: Optional[List[str]] = None,
    turma_ids: Optional[List[str]] = None,
    adap_counts: Optional[Dict[str, int]] = None,
) -> List[Dict[str, Any]]:
    from app.logistics.services import _suggest_supplies

    uuids = ensure_uuid_list(class_ids)
    if not uuids:
        return []
    query = (
        db.session.query(
            Class.id,
            Class.name,
            Class.shift,
            School.id,
            School.name,
            Grade.id,
            Grade.name,
        )
        .join(School, School.id == cast(Class.school_id, String))
        .outerjoin(Grade, Grade.id == Class.grade_id)
        .filter(School.city_id == city_id, Class.id.in_(uuids))
    )
    if escola_ids:
        query = query.filter(School.id.in_([str(e) for e in escola_ids]))
    if serie_ids:
        query = query.filter(Grade.id.in_(ensure_uuid_list(serie_ids)))
    if turma_ids:
        query = query.filter(Class.id.in_(ensure_uuid_list(turma_ids)))

    by_class: Dict[str, Dict[str, Any]] = {}
    for cid, cname, shift, sid, sname, gid, gname in query.all():
        key = str(cid)
        by_class[key] = {
            "class_id": key,
            "class_name": (cname or "").strip() or f"Turma {key}",
            "shift": normalize_shift(shift) or "",
            "school_id": str(sid),
            "school_name": sname,
            "grade_id": str(gid) if gid else None,
            "grade_name": gname,
            "suggested_date": None,
        }

    full_counts = _student_count_by_class(by_class.keys())
    items = []
    for row in by_class.values():
        if adap_counts and row["class_id"] in adap_counts:
            students = adap_counts[row["class_id"]]
        else:
            students = full_counts.get(row["class_id"], 0)
        suggestion = _suggest_supplies(evaluation_mode, students)
        row["students_count"] = students
        row["suggested_tablets_qty"] = suggestion["tablets_qty"]
        row["suggested_booklets_qty"] = suggestion["booklets_qty"]
        items.append(row)
    items.sort(key=lambda r: (r["school_name"] or "", r["grade_name"] or "", r["class_name"] or ""))
    return items


def build_cartao_preview(
    city_id: str,
    gabarito_id: str,
    *,
    escola_ids: Optional[List[str]] = None,
    serie_ids: Optional[List[str]] = None,
    turma_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    gabarito = get_gabarito_or_error(gabarito_id)
    class_ids, adap_map, last_at = resolve_gabarito_class_scope(gabarito)
    adap_counts = _student_count_adap(adap_map) if adap_map else None
    items = _preview_rows_for_classes(
        class_ids,
        city_id=city_id,
        evaluation_mode=LOGISTICS_EVAL_PHYSICAL,
        escola_ids=escola_ids,
        serie_ids=serie_ids,
        turma_ids=turma_ids,
        adap_counts=adap_counts,
    )
    return {
        "gabarito": {
            "id": str(gabarito.id),
            "title": (gabarito.title or "").strip() or f"Gabarito {gabarito.id}",
            "evaluation_mode": LOGISTICS_EVAL_PHYSICAL,
            "last_generation_at": last_at.isoformat() if last_at else None,
            "has_adap": bool(adap_map),
        },
        "items": items,
        "totals": {
            "classes": len(items),
            "schools": len({r["school_id"] for r in items}),
            "students": sum(r["students_count"] for r in items),
        },
    }


def build_personalizada_preview(
    city_id: str,
    evaluation_mode: str,
    *,
    escola_ids: Optional[List[str]] = None,
    serie_ids: Optional[List[str]] = None,
    turma_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    mode = (evaluation_mode or "").strip().lower()
    if mode not in LOGISTICS_EVAL_MODES:
        raise ValueError("evaluation_mode deve ser 'virtual' ou 'physical'.")

    query = (
        db.session.query(
            Class.id,
            Class.name,
            Class.shift,
            School.id,
            School.name,
            Grade.id,
            Grade.name,
        )
        .join(School, School.id == cast(Class.school_id, String))
        .outerjoin(Grade, Grade.id == Class.grade_id)
        .filter(School.city_id == city_id)
    )
    if escola_ids:
        query = query.filter(School.id.in_([str(e) for e in escola_ids]))
    if serie_ids:
        query = query.filter(Grade.id.in_(ensure_uuid_list(serie_ids)))
    if turma_ids:
        query = query.filter(Class.id.in_(ensure_uuid_list(turma_ids)))

    class_ids = [str(row[0]) for row in query.all()]
    # Dedup preservando ordem
    seen: Set[str] = set()
    ordered: List[str] = []
    for cid in class_ids:
        if cid not in seen:
            seen.add(cid)
            ordered.append(cid)

    items = _preview_rows_for_classes(
        ordered,
        city_id=city_id,
        evaluation_mode=mode,
        escola_ids=escola_ids,
        serie_ids=serie_ids,
        turma_ids=turma_ids,
    )
    return {
        "evaluation_mode": mode,
        "items": items,
        "totals": {
            "classes": len(items),
            "schools": len({r["school_id"] for r in items}),
            "students": sum(r["students_count"] for r in items),
        },
    }
