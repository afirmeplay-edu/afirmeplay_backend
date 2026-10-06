# -*- coding: utf-8 -*-
"""
Disparo de notificações do cronograma de logística.

Uma notificação por escola e por tipo de evento (nunca uma por turma), mais um resumo
para os tecadm do município. Tudo roda dentro da transação de publicar/editar/cancelar:
nada aqui faz commit. Quem executou a ação não recebe a própria notificação.

Os itens recebidos já vêm serializados (_serialize_item), com nomes de escola/série/turma.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, Iterable, List, Optional

from app.models.logisticsSchedule import LogisticsSchedule
from app.notifications.recipients import city_tecadms, school_staff_by_school
from app.notifications.services import create_notification

NOTIFICATION_TYPE = "logistics_schedule"
REFERENCE_TYPE = "logistics_schedule"

EVENT_PUBLISHED = "published"
EVENT_ADDED = "added"
EVENT_DATE_CHANGED = "date_changed"
EVENT_REMOVED = "removed"
EVENT_CANCELLED = "cancelled"

_MAX_LISTED = 5


# ---------------------------------------------------------------------------
# Formatação
# ---------------------------------------------------------------------------

def _fmt_date(iso: Optional[str]) -> str:
    if not iso:
        return "sem data"
    try:
        return date.fromisoformat(str(iso)[:10]).strftime("%d/%m/%Y")
    except ValueError:
        return str(iso)


def _fmt_dates(isos: Iterable[Optional[str]]) -> str:
    unique = sorted({d for d in isos if d})
    if not unique:
        return "data a definir"
    shown = [_fmt_date(d) for d in unique[:_MAX_LISTED]]
    extra = len(unique) - len(shown)
    return ", ".join(shown) + (f" e mais {extra}" if extra > 0 else "")


def _plural(n: int, singular: str, plural: str) -> str:
    return f"{n} {singular if n == 1 else plural}"


def _class_label(item: Dict[str, Any]) -> str:
    return " ".join(p for p in (item.get("grade_name"), item.get("class_name")) if p) or "Turma"


def _classes_label(items: List[Dict[str, Any]]) -> str:
    if len(items) <= 3:
        return ", ".join(_class_label(i) for i in items)
    return _plural(len(items), "turma", "turmas")


def _payload_item(item: Dict[str, Any]) -> Dict[str, Any]:
    data = {
        "item_id": item.get("item_id") or item.get("id"),
        "class_id": item.get("class_id"),
        "serie": item.get("grade_name"),
        "turma": item.get("class_name"),
        "turno": item.get("shift"),
        "data": item.get("new_date", item.get("scheduled_date")),
        "alunos": item.get("students_count") or 0,
        "tablets": item.get("tablets_qty") or 0,
        "cadernos": item.get("booklets_qty") or 0,
        "observacao": item.get("notes"),
    }
    if "old_date" in item:
        data["data_anterior"] = item.get("old_date")
    return data


def _totals(items: List[Dict[str, Any]]) -> Dict[str, int]:
    return {
        "turmas": len(items),
        "alunos": sum(i.get("students_count") or 0 for i in items),
        "tablets": sum(i.get("tablets_qty") or 0 for i in items),
        "cadernos": sum(i.get("booklets_qty") or 0 for i in items),
    }


def _group_by_school(items: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    groups: Dict[str, Dict[str, Any]] = {}
    for item in items:
        sid = str(item.get("school_id"))
        group = groups.setdefault(sid, {"school_name": item.get("school_name"), "items": []})
        group["items"].append(item)
    return groups


def _action_url(schedule: LogisticsSchedule) -> str:
    return f"/app/relatorios/logistica?id={schedule.id}"


# ---------------------------------------------------------------------------
# Envio
# ---------------------------------------------------------------------------

class _Dispatcher:
    def __init__(self, schedule: LogisticsSchedule, test_title: Optional[str], city_id: str, actor_id: Optional[str]):
        self.schedule = schedule
        self.test_title = test_title or schedule.title or "Avaliação"
        self.city_id = city_id
        self.actor_id = str(actor_id) if actor_id else None
        self._staff: Dict[str, List[Dict[str, str]]] = {}

    def load_staff(self, school_ids: Iterable[str]) -> None:
        self._staff = school_staff_by_school(school_ids)

    def _without_actor(self, recipients: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [r for r in recipients if r["user_id"] != self.actor_id]

    def _base_payload(self, event: str) -> Dict[str, Any]:
        return {
            "event": event,
            "schedule_id": str(self.schedule.id),
            "schedule_title": self.schedule.title,
            "test_id": self.schedule.test_id,
            "test_title": self.test_title,
        }

    def _send(self, title: str, message: str, payload: Dict[str, Any], recipients: List[Dict[str, Any]]):
        return create_notification(
            NOTIFICATION_TYPE,
            title,
            message,
            payload,
            (REFERENCE_TYPE, str(self.schedule.id)),
            self._without_actor(recipients),
            action_url=_action_url(self.schedule),
            created_by=self.actor_id,
        )

    def school(self, event: str, school_id: str, school_name: Optional[str], items: List[Dict[str, Any]],
               title: str, message: str, **extra: Any) -> None:
        payload = self._base_payload(event)
        payload.update(
            {
                "school_id": school_id,
                "school_name": school_name,
                "items": [_payload_item(i) for i in items],
                "totals": _totals(items),
            }
        )
        payload.update(extra)
        self._send(title, message, payload, self._staff.get(school_id, []))

    def summary(self, event: str, title: str, message: str, schools: List[Dict[str, Any]]) -> None:
        payload = self._base_payload(event)
        payload.update({"summary": True, "schools": schools})
        self._send(title, message, payload, city_tecadms(self.city_id))


def notify_published(
    schedule: LogisticsSchedule,
    test_title: Optional[str],
    items: List[Dict[str, Any]],
    city_id: str,
    actor_id: Optional[str],
) -> None:
    groups = _group_by_school(items)
    if not groups:
        return
    d = _Dispatcher(schedule, test_title, city_id, actor_id)
    d.load_staff(groups.keys())

    for sid, group in groups.items():
        school_items = group["items"]
        totals = _totals(school_items)
        d.school(
            EVENT_PUBLISHED,
            sid,
            group["school_name"],
            school_items,
            "Prova marcada para a sua escola",
            f"{d.test_title}: aplicação em {_fmt_dates(i.get('scheduled_date') for i in school_items)} "
            f"({_plural(totals['turmas'], 'turma', 'turmas')}, {_plural(totals['alunos'], 'aluno', 'alunos')}).",
        )

    d.summary(
        EVENT_PUBLISHED,
        "Cronograma de logística publicado",
        f"{d.test_title}: {_plural(len(groups), 'escola', 'escolas')}, "
        f"{_plural(len(items), 'turma', 'turmas')}, aplicação em "
        f"{_fmt_dates(i.get('scheduled_date') for i in items)}.",
        [
            {
                "school_id": sid,
                "school_name": g["school_name"],
                "datas": sorted({i.get("scheduled_date") for i in g["items"] if i.get("scheduled_date")}),
                **_totals(g["items"]),
            }
            for sid, g in groups.items()
        ],
    )


def notify_changes(
    schedule: LogisticsSchedule,
    test_title: Optional[str],
    changes: Dict[str, List[Dict[str, Any]]],
    remaining_items: List[Dict[str, Any]],
    city_id: str,
    actor_id: Optional[str],
) -> None:
    """
    changes: {'date_changes', 'added_items', 'removed_items'} devolvidos por _apply_items.
    Escola sem nenhuma turma restante recebe 'aplicação cancelada' como escola removida.
    """
    by_event = {
        EVENT_ADDED: _group_by_school(changes.get("added_items") or []),
        EVENT_DATE_CHANGED: _group_by_school(changes.get("date_changes") or []),
        EVENT_REMOVED: _group_by_school(changes.get("removed_items") or []),
    }
    school_ids = set().union(*(g.keys() for g in by_event.values()))
    if not school_ids:
        return
    remaining_schools = {str(i.get("school_id")) for i in remaining_items}

    d = _Dispatcher(schedule, test_title, city_id, actor_id)
    d.load_staff(school_ids)
    summary: Dict[str, Dict[str, Any]] = {}

    def track(sid: str, name: Optional[str], event: str, n: int) -> None:
        entry = summary.setdefault(sid, {"school_id": sid, "school_name": name, "events": {}})
        entry["events"][event] = n

    for sid, group in by_event[EVENT_ADDED].items():
        items = group["items"]
        d.school(
            EVENT_ADDED,
            sid,
            group["school_name"],
            items,
            "Prova marcada para a sua escola",
            f"{d.test_title}: aplicação em {_fmt_dates(i.get('scheduled_date') for i in items)} "
            f"para {_classes_label(items)}.",
        )
        track(sid, group["school_name"], EVENT_ADDED, len(items))

    for sid, group in by_event[EVENT_DATE_CHANGED].items():
        items = group["items"]
        if len(items) <= _MAX_LISTED:
            detail = "; ".join(
                f"{_class_label(i)}: {_fmt_date(i.get('old_date'))} → {_fmt_date(i.get('new_date'))}"
                for i in items
            )
        else:
            detail = (
                f"{_plural(len(items), 'turma', 'turmas')} com nova data "
                f"({_fmt_dates(i.get('new_date') for i in items)})"
            )
        d.school(
            EVENT_DATE_CHANGED,
            sid,
            group["school_name"],
            items,
            "Data de aplicação alterada",
            f"{d.test_title}: {detail}.",
        )
        track(sid, group["school_name"], EVENT_DATE_CHANGED, len(items))

    for sid, group in by_event[EVENT_REMOVED].items():
        items = group["items"]
        school_removed = sid not in remaining_schools
        message = (
            f"{d.test_title}: a aplicação na sua escola foi cancelada."
            if school_removed
            else f"{d.test_title}: aplicação cancelada para {_classes_label(items)}."
        )
        d.school(
            EVENT_REMOVED,
            sid,
            group["school_name"],
            items,
            "Aplicação cancelada",
            message,
            school_removed=school_removed,
        )
        track(sid, group["school_name"], EVENT_REMOVED, len(items))

    parts = []
    labels = {
        EVENT_DATE_CHANGED: "data alterada em",
        EVENT_ADDED: "turmas incluídas em",
        EVENT_REMOVED: "aplicação cancelada em",
    }
    for event in (EVENT_DATE_CHANGED, EVENT_ADDED, EVENT_REMOVED):
        n = len(by_event[event])
        if n:
            parts.append(f"{labels[event]} {_plural(n, 'escola', 'escolas')}")
    d.summary(
        "changed",
        "Cronograma de logística alterado",
        f"{d.test_title}: " + ", ".join(parts) + ".",
        list(summary.values()),
    )


def notify_cancelled(
    schedule: LogisticsSchedule,
    test_title: Optional[str],
    items: List[Dict[str, Any]],
    city_id: str,
    actor_id: Optional[str],
) -> None:
    groups = _group_by_school(items)
    if not groups:
        return
    d = _Dispatcher(schedule, test_title, city_id, actor_id)
    d.load_staff(groups.keys())

    for sid, group in groups.items():
        school_items = group["items"]
        d.school(
            EVENT_CANCELLED,
            sid,
            group["school_name"],
            school_items,
            "Aplicação cancelada",
            f"{d.test_title}: a aplicação prevista para "
            f"{_fmt_dates(i.get('scheduled_date') for i in school_items)} foi cancelada.",
            school_removed=True,
        )

    d.summary(
        EVENT_CANCELLED,
        "Cronograma de logística cancelado",
        f"{d.test_title}: aplicação cancelada em {_plural(len(groups), 'escola', 'escolas')} "
        f"({_plural(len(items), 'turma', 'turmas')}).",
        [
            {"school_id": sid, "school_name": g["school_name"], **_totals(g["items"])}
            for sid, g in groups.items()
        ],
    )
