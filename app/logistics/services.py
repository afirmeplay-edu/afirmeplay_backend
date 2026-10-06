# -*- coding: utf-8 -*-
"""
Regras do cronograma de logística de aplicação.

- admin/tecadm: criam, editam, publicam e cancelam.
- diretor/coordenador/professor: só leem cronogramas publicados, limitados às próprias escolas.
- demais perfis (inclui aplicador, que o role_required adiciona sozinho): sem acesso.

ClassTest é apenas lido (data sugerida); nada aqui altera a janela online da prova.
Rascunho não gera notificação; publicar, editar publicado e cancelar publicado geram.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, Iterable, List, Optional, Set

from sqlalchemy import String, cast, func

from app import db
from app.logistics import notifications as logistics_notifications
from app.models.classTest import ClassTest
from app.models.grades import Grade
from app.models.logisticsSchedule import (
    LOGISTICS_STATUS_CANCELLED,
    LOGISTICS_STATUS_DRAFT,
    LOGISTICS_STATUS_PUBLISHED,
    LOGISTICS_STATUSES,
    LogisticsSchedule,
    LogisticsScheduleItem,
)
from app.models.school import School
from app.models.student import Student
from app.models.studentClass import Class
from app.models.test import Test
from app.permissions import get_user_scope
from app.permissions.roles import Roles
from app.utils.class_label_helpers import normalize_shift
from app.utils.uuid_helpers import ensure_uuid, ensure_uuid_list


MANAGER_ROLES = {Roles.ADMIN, Roles.TECADM}
READER_ROLES = {Roles.DIRETOR, Roles.COORDENADOR, Roles.PROFESSOR}


class LogisticsError(Exception):
    status_code = 400


class LogisticsNotFound(LogisticsError):
    status_code = 404


class LogisticsConflict(LogisticsError):
    status_code = 409


class LogisticsForbidden(LogisticsError):
    status_code = 403


# ---------------------------------------------------------------------------
# Acesso
# ---------------------------------------------------------------------------

def resolve_access(user: dict) -> Dict[str, Any]:
    """
    {'can_manage': bool, 'school_ids': None | set[str]}
    school_ids=None significa sem restrição de escola (admin/tecadm).
    """
    role = Roles.normalize(user.get("role", ""))
    if role in MANAGER_ROLES:
        return {"can_manage": True, "school_ids": None}
    if role in READER_ROLES:
        scope = get_user_scope(user)
        school_ids = {str(s) for s in (scope.get("school_ids") or []) if s}
        return {"can_manage": False, "school_ids": school_ids}
    raise LogisticsForbidden("Perfil sem acesso ao cronograma de logística.")


def require_manager(user: dict) -> None:
    if not resolve_access(user)["can_manage"]:
        raise LogisticsForbidden("Apenas admin e tecadm podem alterar cronogramas.")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


def _parse_application_date(value: Optional[str]) -> Optional[date]:
    """ClassTest.application é texto ISO com offset; devolve o dia civil daquele offset."""
    if not value:
        return None
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text).date()
    except ValueError:
        try:
            return date.fromisoformat(text[:10])
        except ValueError:
            return None


def _parse_date(value: Any, field: str = "scheduled_date") -> Optional[date]:
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        raise LogisticsError(f"Data inválida em {field}: {value!r} (use AAAA-MM-DD).")


def _parse_qty(value: Any, field: str) -> int:
    if value in (None, ""):
        return 0
    try:
        qty = int(value)
    except (TypeError, ValueError):
        raise LogisticsError(f"Quantidade inválida em {field}: {value!r}.")
    if qty < 0:
        raise LogisticsError(f"{field} não pode ser negativo.")
    return qty


def _suggest_supplies(evaluation_mode: Optional[str], students: int) -> Dict[str, int]:
    mode = (evaluation_mode or "virtual").strip().lower()
    if mode == "virtual":
        return {"tablets_qty": students, "booklets_qty": 0}
    return {"tablets_qty": 0, "booklets_qty": students}


def _get_test_or_error(test_id: Any) -> Test:
    if not test_id:
        raise LogisticsError("test_id é obrigatório.")
    test = Test.query.get(str(test_id))
    if not test:
        raise LogisticsNotFound("Avaliação não encontrada.")
    return test


def _get_schedule_or_404(schedule_id: Any) -> LogisticsSchedule:
    sid = ensure_uuid(schedule_id)
    schedule = LogisticsSchedule.query.get(sid) if sid else None
    if not schedule:
        raise LogisticsNotFound("Cronograma não encontrado.")
    return schedule


def _test_classes_in_city(test_id: str, city_id: str, class_ids: List[Any]) -> Dict[str, Dict[str, Any]]:
    """Turmas (entre class_ids) vinculadas à avaliação via class_test e pertencentes ao município."""
    uuids = ensure_uuid_list(class_ids)
    if not uuids:
        return {}
    rows = (
        db.session.query(Class.id, cast(Class.school_id, String), Class.grade_id)
        .join(ClassTest, ClassTest.class_id == Class.id)
        .join(School, School.id == cast(Class.school_id, String))
        .filter(
            ClassTest.test_id == str(test_id),
            School.city_id == city_id,
            Class.id.in_(uuids),
        )
        .distinct()
        .all()
    )
    return {
        str(r[0]): {"school_id": str(r[1]), "grade_id": r[2]}
        for r in rows
    }


def _labels_for_items(items: List[LogisticsScheduleItem]) -> Dict[str, Dict[str, Dict[str, Any]]]:
    class_ids = {i.class_id for i in items if i.class_id}
    school_ids = {i.school_id for i in items if i.school_id}
    grade_ids = {i.grade_id for i in items if i.grade_id}

    classes = {}
    if class_ids:
        for cid, name, shift in db.session.query(Class.id, Class.name, Class.shift).filter(
            Class.id.in_(list(class_ids))
        ):
            classes[str(cid)] = {"name": name, "shift": normalize_shift(shift) or ""}
    schools = {}
    if school_ids:
        for sid, name in db.session.query(School.id, School.name).filter(
            School.id.in_([str(s) for s in school_ids])
        ):
            schools[str(sid)] = name
    grades = {}
    if grade_ids:
        for gid, name in db.session.query(Grade.id, Grade.name).filter(
            Grade.id.in_(list(grade_ids))
        ):
            grades[str(gid)] = name
    return {"classes": classes, "schools": schools, "grades": grades}


def _serialize_item(item: LogisticsScheduleItem, labels: Dict[str, Dict]) -> Dict[str, Any]:
    cls = labels["classes"].get(str(item.class_id), {})
    return {
        "id": str(item.id),
        "school_id": str(item.school_id),
        "school_name": labels["schools"].get(str(item.school_id)),
        "grade_id": str(item.grade_id) if item.grade_id else None,
        "grade_name": labels["grades"].get(str(item.grade_id)) if item.grade_id else None,
        "class_id": str(item.class_id),
        "class_name": cls.get("name"),
        "shift": cls.get("shift", ""),
        "scheduled_date": item.scheduled_date.isoformat() if item.scheduled_date else None,
        "students_count": item.students_count,
        "tablets_qty": item.tablets_qty,
        "booklets_qty": item.booklets_qty,
        "notes": item.notes,
    }


def _iso(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value else None


def _serialize_schedule(
    schedule: LogisticsSchedule,
    test: Optional[Test],
    items: List[LogisticsScheduleItem],
    *,
    include_items: bool,
    can_manage: bool,
) -> Dict[str, Any]:
    data: Dict[str, Any] = {
        "id": str(schedule.id),
        "test_id": schedule.test_id,
        "test_title": test.title if test else None,
        "evaluation_mode": (test.evaluation_mode if test else None) or "virtual",
        "education_stage_id": str(schedule.education_stage_id) if schedule.education_stage_id else None,
        "title": schedule.title,
        "status": schedule.status,
        "notes": schedule.notes,
        "created_by": schedule.created_by,
        "created_at": _iso(schedule.created_at),
        "updated_at": _iso(schedule.updated_at),
        "published_at": _iso(schedule.published_at),
        "cancelled_at": _iso(schedule.cancelled_at),
        "can_manage": can_manage,
        "totals": {
            "items": len(items),
            "schools": len({i.school_id for i in items}),
            "students": sum(i.students_count or 0 for i in items),
            "tablets": sum(i.tablets_qty or 0 for i in items),
            "booklets": sum(i.booklets_qty or 0 for i in items),
        },
        "dates": sorted({i.scheduled_date.isoformat() for i in items if i.scheduled_date}),
    }
    if include_items:
        labels = _labels_for_items(items)
        serialized = [_serialize_item(i, labels) for i in items]
        serialized.sort(
            key=lambda r: (
                r["school_name"] or "",
                r["grade_name"] or "",
                r["class_name"] or "",
                r["scheduled_date"] or "",
            )
        )
        data["items"] = serialized
    return data


def _visible_items(schedule: LogisticsSchedule, school_ids: Optional[Set[str]]) -> List[LogisticsScheduleItem]:
    items = list(schedule.items)
    if school_ids is None:
        return items
    return [i for i in items if str(i.school_id) in school_ids]


# ---------------------------------------------------------------------------
# Prévia
# ---------------------------------------------------------------------------

def build_preview(
    city_id: str,
    test_id: str,
    *,
    etapa_id: Optional[str] = None,
    escola_ids: Optional[List[str]] = None,
    serie_ids: Optional[List[str]] = None,
    turma_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    test = _get_test_or_error(test_id)

    query = (
        db.session.query(
            Class.id,
            Class.name,
            Class.shift,
            School.id,
            School.name,
            Grade.id,
            Grade.name,
            ClassTest.application,
        )
        .join(ClassTest, ClassTest.class_id == Class.id)
        .join(School, School.id == cast(Class.school_id, String))
        .outerjoin(Grade, Grade.id == Class.grade_id)
        .filter(ClassTest.test_id == str(test.id), School.city_id == city_id)
    )
    if etapa_id:
        etapa_uuid = ensure_uuid(etapa_id)
        if not etapa_uuid:
            raise LogisticsError("etapa inválida.")
        query = query.filter(Grade.education_stage_id == etapa_uuid)
    if escola_ids:
        query = query.filter(School.id.in_([str(e) for e in escola_ids]))
    if serie_ids:
        query = query.filter(Grade.id.in_(ensure_uuid_list(serie_ids)))
    if turma_ids:
        query = query.filter(Class.id.in_(ensure_uuid_list(turma_ids)))

    by_class: Dict[str, Dict[str, Any]] = {}
    for cid, cname, shift, sid, sname, gid, gname, application in query.all():
        key = str(cid)
        app_date = _parse_application_date(application)
        current = by_class.get(key)
        if current is None:
            by_class[key] = {
                "class_id": key,
                "class_name": (cname or "").strip() or f"Turma {key}",
                "shift": normalize_shift(shift) or "",
                "school_id": str(sid),
                "school_name": sname,
                "grade_id": str(gid) if gid else None,
                "grade_name": gname,
                "suggested_date": app_date,
            }
        elif app_date and (current["suggested_date"] is None or app_date < current["suggested_date"]):
            current["suggested_date"] = app_date

    counts = _student_count_by_class(by_class.keys())
    items = []
    for row in by_class.values():
        students = counts.get(row["class_id"], 0)
        suggestion = _suggest_supplies(test.evaluation_mode, students)
        row["students_count"] = students
        row["suggested_tablets_qty"] = suggestion["tablets_qty"]
        row["suggested_booklets_qty"] = suggestion["booklets_qty"]
        row["suggested_date"] = row["suggested_date"].isoformat() if row["suggested_date"] else None
        items.append(row)

    items.sort(key=lambda r: (r["school_name"] or "", r["grade_name"] or "", r["class_name"] or ""))
    return {
        "test": {
            "id": str(test.id),
            "title": test.title,
            "evaluation_mode": test.evaluation_mode or "virtual",
        },
        "items": items,
        "totals": {
            "classes": len(items),
            "schools": len({r["school_id"] for r in items}),
            "students": sum(r["students_count"] for r in items),
        },
    }


# ---------------------------------------------------------------------------
# Itens
# ---------------------------------------------------------------------------

def _empty_changes() -> Dict[str, List[Dict[str, Any]]]:
    return {"date_changes": [], "added_items": [], "removed_items": []}


def _pair_recreated_classes(
    added: List[Dict[str, Any]], removed: List[Dict[str, Any]], date_changes: List[Dict[str, Any]]
) -> None:
    """
    Turma removida e recriada no mesmo save (item novo sem 'id') conta como troca de data,
    não como cancelamento + nova marcação. Mesma data nos dois lados = nenhuma mudança.
    """
    for new in list(added):
        old = next((r for r in removed if r["class_id"] == new["class_id"]), None)
        if old is None:
            continue
        removed.remove(old)
        added.remove(new)
        if old["scheduled_date"] != new["scheduled_date"]:
            date_changes.append(
                {
                    **new,
                    "item_id": new["id"],
                    "old_date": old["scheduled_date"],
                    "new_date": new["scheduled_date"],
                }
            )


def _apply_items(
    schedule: LogisticsSchedule, items_payload: Any, city_id: str
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Substitui os itens do cronograma pelo payload (itens com 'id' são atualizados,
    sem 'id' são criados, ausentes são removidos).

    Devolve as mudanças, com os itens serializados (escola, série, turma, quantidades):
    {
      'date_changes':  [item + {'item_id', 'old_date', 'new_date'}],
      'added_items':   [item],
      'removed_items': [item como estava antes de remover],
    }
    """
    if not isinstance(items_payload, list):
        raise LogisticsError("items deve ser uma lista.")

    parsed: List[Dict[str, Any]] = []
    seen_keys: Set[tuple] = set()
    seen_ids: Set[Any] = set()
    for idx, raw in enumerate(items_payload):
        if not isinstance(raw, dict):
            raise LogisticsError(f"items[{idx}] inválido.")
        item_id = ensure_uuid(raw.get("id"))
        if item_id is not None:
            if item_id in seen_ids:
                raise LogisticsError(f"items[{idx}].id repetido.")
            seen_ids.add(item_id)
        class_uuid = ensure_uuid(raw.get("class_id"))
        if not class_uuid:
            raise LogisticsError(f"items[{idx}].class_id inválido.")
        scheduled = _parse_date(raw.get("scheduled_date"), f"items[{idx}].scheduled_date")
        key = (str(class_uuid), scheduled)
        if key in seen_keys:
            raise LogisticsError(
                f"Turma repetida na mesma data em items[{idx}] (class_id={class_uuid})."
            )
        seen_keys.add(key)
        notes = raw.get("notes")
        parsed.append(
            {
                "id": item_id,
                "class_id": class_uuid,
                "scheduled_date": scheduled,
                "tablets_qty": _parse_qty(raw.get("tablets_qty"), f"items[{idx}].tablets_qty"),
                "booklets_qty": _parse_qty(raw.get("booklets_qty"), f"items[{idx}].booklets_qty"),
                "notes": (str(notes).strip() or None) if notes is not None else None,
            }
        )

    class_info = _test_classes_in_city(
        schedule.test_id, city_id, [p["class_id"] for p in parsed]
    )
    missing = [str(p["class_id"]) for p in parsed if str(p["class_id"]) not in class_info]
    if missing:
        raise LogisticsError(
            "Turmas não vinculadas a esta avaliação no município: " + ", ".join(sorted(set(missing)))
        )

    counts = _student_count_by_class(class_info.keys())
    existing = {item.id: item for item in schedule.items}
    keep_ids = {p["id"] for p in parsed if p["id"] in existing}

    removed = [item for item_id, item in existing.items() if item_id not in keep_ids]
    removed_items: List[Dict[str, Any]] = []
    if removed:
        removed_labels = _labels_for_items(removed)
        removed_items = [_serialize_item(item, removed_labels) for item in removed]
        for item in removed:
            schedule.items.remove(item)
    db.session.flush()

    changed: List[tuple] = []
    added: List[LogisticsScheduleItem] = []
    for p in parsed:
        info = class_info[str(p["class_id"])]
        item = existing.get(p["id"]) if p["id"] in keep_ids else None
        if item is None:
            item = LogisticsScheduleItem(schedule_id=schedule.id)
            schedule.items.append(item)
            added.append(item)
        elif item.scheduled_date != p["scheduled_date"]:
            changed.append((item, item.scheduled_date))
        item.class_id = p["class_id"]
        item.school_id = info["school_id"]
        item.grade_id = info["grade_id"]
        item.scheduled_date = p["scheduled_date"]
        item.students_count = counts.get(str(p["class_id"]), 0)
        item.tablets_qty = p["tablets_qty"]
        item.booklets_qty = p["booklets_qty"]
        item.notes = p["notes"]
    db.session.flush()

    if not (removed_items or added or changed):
        return _empty_changes()
    labels = _labels_for_items(list(schedule.items))
    date_changes = [
        {
            **_serialize_item(item, labels),
            "item_id": str(item.id),
            "old_date": old_date.isoformat() if old_date else None,
            "new_date": item.scheduled_date.isoformat() if item.scheduled_date else None,
        }
        for item, old_date in changed
    ]
    added_items = [_serialize_item(item, labels) for item in added]
    _pair_recreated_classes(added_items, removed_items, date_changes)
    return {"date_changes": date_changes, "added_items": added_items, "removed_items": removed_items}


def _apply_header(schedule: LogisticsSchedule, data: Dict[str, Any], test: Test) -> None:
    if "education_stage_id" in data:
        raw = data.get("education_stage_id")
        if raw in (None, ""):
            schedule.education_stage_id = None
        else:
            stage = ensure_uuid(raw)
            if not stage:
                raise LogisticsError("education_stage_id inválido.")
            schedule.education_stage_id = stage
    if "title" in data or not schedule.title:
        title = (str(data.get("title") or "").strip() or (test.title or "Cronograma"))[:200]
        schedule.title = title
    if "notes" in data:
        notes = data.get("notes")
        schedule.notes = (str(notes).strip() or None) if notes is not None else None


def _validate_publishable(schedule: LogisticsSchedule) -> None:
    if not schedule.items:
        raise LogisticsError("O cronograma precisa de ao menos uma turma para ser publicado.")
    if any(item.scheduled_date is None for item in schedule.items):
        raise LogisticsError("Todas as turmas precisam de data antes de publicar.")


# ---------------------------------------------------------------------------
# CRUD e ações
# ---------------------------------------------------------------------------

def list_schedules(user: dict, args) -> List[Dict[str, Any]]:
    access = resolve_access(user)
    school_ids = access["school_ids"]

    query = LogisticsSchedule.query
    test_id = (args.get("test_id") or "").strip()
    if test_id:
        query = query.filter(LogisticsSchedule.test_id == test_id)

    if access["can_manage"]:
        status = (args.get("status") or "").strip().lower()
        if status:
            if status not in LOGISTICS_STATUSES:
                raise LogisticsError("status inválido.")
            query = query.filter(LogisticsSchedule.status == status)
    else:
        if not school_ids:
            return []
        query = query.filter(
            LogisticsSchedule.status == LOGISTICS_STATUS_PUBLISHED,
            LogisticsSchedule.items.any(LogisticsScheduleItem.school_id.in_(list(school_ids))),
        )

    schedules = query.order_by(LogisticsSchedule.created_at.desc()).all()
    tests = {}
    test_ids = {s.test_id for s in schedules}
    if test_ids:
        tests = {str(t.id): t for t in Test.query.filter(Test.id.in_(list(test_ids))).all()}

    return [
        _serialize_schedule(
            s,
            tests.get(str(s.test_id)),
            _visible_items(s, school_ids),
            include_items=False,
            can_manage=access["can_manage"],
        )
        for s in schedules
    ]


def get_schedule(user: dict, schedule_id: Any) -> Dict[str, Any]:
    access = resolve_access(user)
    schedule = _get_schedule_or_404(schedule_id)
    items = _visible_items(schedule, access["school_ids"])
    if not access["can_manage"] and (
        schedule.status != LOGISTICS_STATUS_PUBLISHED or not items
    ):
        raise LogisticsNotFound("Cronograma não encontrado.")
    test = Test.query.get(schedule.test_id)
    return _serialize_schedule(
        schedule, test, items, include_items=True, can_manage=access["can_manage"]
    )


def create_schedule(user: dict, city_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    require_manager(user)
    test = _get_test_or_error(data.get("test_id"))
    try:
        schedule = LogisticsSchedule(
            test_id=str(test.id),
            status=LOGISTICS_STATUS_DRAFT,
            created_by=str(user["id"]),
        )
        _apply_header(schedule, data, test)
        db.session.add(schedule)
        db.session.flush()
        _apply_items(schedule, data.get("items") or [], city_id)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return _serialize_schedule(schedule, test, list(schedule.items), include_items=True, can_manage=True)


def update_schedule(
    user: dict, city_id: str, schedule_id: Any, data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Atualiza cabeçalho e (se 'items' vier no payload) substitui os itens.
    Em cronograma publicado, result traz date_changes, added_items e removed_items
    e as escolas afetadas são notificadas na mesma transação.
    """
    require_manager(user)
    schedule = _get_schedule_or_404(schedule_id)
    if schedule.status == LOGISTICS_STATUS_CANCELLED:
        raise LogisticsConflict("Cronograma cancelado não pode ser editado.")
    test = Test.query.get(schedule.test_id)
    is_published = schedule.status == LOGISTICS_STATUS_PUBLISHED
    changes = _empty_changes()
    try:
        _apply_header(schedule, data, test)
        if "items" in data:
            changes = _apply_items(schedule, data.get("items"), city_id)
        if is_published:
            _validate_publishable(schedule)
        schedule.updated_at = datetime.utcnow()
        if is_published and any(changes.values()):
            logistics_notifications.notify_changes(
                schedule,
                test.title if test else None,
                changes,
                [{"school_id": str(i.school_id)} for i in schedule.items],
                city_id,
                user.get("id"),
            )
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    result = _serialize_schedule(schedule, test, list(schedule.items), include_items=True, can_manage=True)
    result.update(changes if is_published else _empty_changes())
    return result


def delete_schedule(user: dict, schedule_id: Any) -> None:
    require_manager(user)
    schedule = _get_schedule_or_404(schedule_id)
    if schedule.status != LOGISTICS_STATUS_DRAFT:
        raise LogisticsConflict("Só rascunhos podem ser excluídos. Use cancelar para cronogramas publicados.")
    try:
        db.session.delete(schedule)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise


def _serialized_items(schedule: LogisticsSchedule) -> List[Dict[str, Any]]:
    items = list(schedule.items)
    labels = _labels_for_items(items)
    return [_serialize_item(item, labels) for item in items]


def publish_schedule(user: dict, city_id: str, schedule_id: Any) -> Dict[str, Any]:
    """Publica e notifica cada escola + resumo aos tecadm, na mesma transação."""
    require_manager(user)
    schedule = _get_schedule_or_404(schedule_id)
    if schedule.status != LOGISTICS_STATUS_DRAFT:
        raise LogisticsConflict("Só rascunhos podem ser publicados.")
    _validate_publishable(schedule)
    test = Test.query.get(schedule.test_id)
    try:
        now = datetime.utcnow()
        schedule.status = LOGISTICS_STATUS_PUBLISHED
        schedule.published_at = now
        schedule.updated_at = now
        logistics_notifications.notify_published(
            schedule, test.title if test else None, _serialized_items(schedule), city_id, user.get("id")
        )
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return _serialize_schedule(schedule, test, list(schedule.items), include_items=True, can_manage=True)


def cancel_schedule(user: dict, city_id: str, schedule_id: Any) -> Dict[str, Any]:
    """Cancela; se estava publicado, notifica as escolas e os tecadm na mesma transação."""
    require_manager(user)
    schedule = _get_schedule_or_404(schedule_id)
    if schedule.status == LOGISTICS_STATUS_CANCELLED:
        raise LogisticsConflict("Cronograma já está cancelado.")
    was_published = schedule.status == LOGISTICS_STATUS_PUBLISHED
    test = Test.query.get(schedule.test_id)
    try:
        now = datetime.utcnow()
        schedule.status = LOGISTICS_STATUS_CANCELLED
        schedule.cancelled_at = now
        schedule.updated_at = now
        if was_published:
            logistics_notifications.notify_cancelled(
                schedule, test.title if test else None, _serialized_items(schedule), city_id, user.get("id")
            )
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return _serialize_schedule(schedule, test, list(schedule.items), include_items=True, can_manage=True)
