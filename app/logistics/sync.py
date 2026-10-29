# -*- coding: utf-8 -*-
"""Sincroniza o cronograma de logística com as turmas aplicadas em class_test.

Não notifica. Não altera cronograma publicado ou cancelado. Uma falha aqui
não pode desfazer a aplicação da prova: o trabalho roda num savepoint.
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

from app import db
from app.logistics.services import _student_count_by_class, _suggest_supplies
from app.models.classTest import ClassTest
from app.models.logisticsSchedule import (
    LOGISTICS_ORIGEM_AUTO,
    LOGISTICS_STATUS_CANCELLED,
    LOGISTICS_STATUS_DRAFT,
    LogisticsSchedule,
    LogisticsScheduleItem,
)
from app.models.studentClass import Class
from app.models.test import Test
from app.models.user import User
from app.utils.uuid_helpers import ensure_uuid_list

logger = logging.getLogger(__name__)

_SYNC_MODES = ("virtual", "physical", "subjective")


def schedule_sync_decision(statuses: List[str]) -> str:
    """O que fazer com os cronogramas não cancelados da avaliação.

    create: nenhum não cancelado.
    update: um rascunho.
    skip: publicado, ou mais de um não cancelado.
    """
    if len(statuses) > 1:
        return "skip"
    if len(statuses) == 1 and statuses[0] != LOGISTICS_STATUS_DRAFT:
        return "skip"
    if len(statuses) == 1:
        return "update"
    return "create"


def civil_application_date(application: Optional[str], timezone_name: Optional[str]) -> Optional[date]:
    """Dia civil de class_test.application no fuso da aplicação."""
    if not application:
        return None
    text = str(application).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        try:
            return date.fromisoformat(text[:10])
        except ValueError:
            return None
    if timezone_name:
        try:
            zone = ZoneInfo(str(timezone_name))
            if moment.tzinfo is None:
                moment = moment.replace(tzinfo=zone)
            else:
                moment = moment.astimezone(zone)
        except Exception:
            logger.warning("Fuso inválido na aplicação da logística: %s", timezone_name)
    return moment.date()


def _actor_id_from_request() -> Optional[str]:
    try:
        from app.permissions import get_current_user_from_token

        user = get_current_user_from_token()
    except Exception:
        logger.exception("Logística: não foi possível ler o usuário do token.")
        return None
    if not user or not user.get("id"):
        return None
    return str(user["id"])


def _is_auto_untouched(item: LogisticsScheduleItem) -> bool:
    return (item.origem or "manual") == LOGISTICS_ORIGEM_AUTO and not bool(item.editado_manualmente)


def _date_taken(items: List[LogisticsScheduleItem], class_id: str, when: Optional[date], ignore_id) -> bool:
    for other in items:
        if str(other.class_id) != class_id or other.id == ignore_id:
            continue
        if other.scheduled_date == when:
            return True
    return False


def sync_application_safe(test_id: Optional[str], actor_user_id: Optional[str] = None) -> None:
    """Grava a logística da aplicação. Erro de logística é logado e não propaga.

    O flush anterior ao savepoint garante que os class_test já escritos fiquem
    na transação de fora. Se a logística falhar, só o savepoint é desfeito.
    """
    if not test_id:
        return
    if not actor_user_id:
        actor_user_id = _actor_id_from_request()
    try:
        db.session.flush()
    except Exception:
        logger.exception(
            "Logística: flush anterior à sincronização falhou para a avaliação %s.",
            test_id,
        )
        raise
    try:
        with db.session.begin_nested():
            _sync_schedule_from_class_tests(str(test_id), actor_user_id)
    except Exception:
        logger.exception(
            "Logística: falha ao sincronizar a avaliação %s. A aplicação da prova segue normalmente.",
            test_id,
        )


def _sync_schedule_from_class_tests(test_id: str, actor_user_id: Optional[str]) -> None:
    test = Test.query.get(str(test_id))
    if not test:
        logger.info("Logística: avaliação %s não encontrada; sincronização ignorada.", test_id)
        return
    if (test.type or "").strip().upper() == "OLIMPIADA":
        logger.info("Logística: avaliação %s é olimpíada; sincronização ignorada.", test_id)
        return
    mode = (test.evaluation_mode or "virtual").strip().lower()
    if mode not in _SYNC_MODES:
        logger.info(
            "Logística: avaliação %s com formato %s fora da sincronização.",
            test_id,
            mode,
        )
        return

    schedules = (
        LogisticsSchedule.query.filter(
            LogisticsSchedule.test_id == str(test.id),
            LogisticsSchedule.status != LOGISTICS_STATUS_CANCELLED,
        )
        .order_by(LogisticsSchedule.created_at.asc())
        .all()
    )
    decision = schedule_sync_decision([schedule.status for schedule in schedules])
    if decision == "skip":
        if len(schedules) > 1:
            logger.warning(
                "Logística: avaliação %s tem %s cronogramas não cancelados; sincronização ignorada.",
                test_id,
                len(schedules),
            )
        else:
            logger.info(
                "Logística: cronograma %s da avaliação %s está %s; sincronização não altera.",
                schedules[0].id,
                test_id,
                schedules[0].status,
            )
        return

    class_tests = ClassTest.query.filter_by(test_id=str(test.id)).all()
    if decision == "create" and not class_tests:
        return

    actor_id = (actor_user_id or "").strip() or None
    if actor_id and db.session.query(User.id).filter(User.id == actor_id).first() is None:
        actor_id = None

    if decision == "create":
        schedule = LogisticsSchedule(
            test_id=str(test.id),
            status=LOGISTICS_STATUS_DRAFT,
            title=(test.title or "Cronograma")[:200],
            created_by=actor_id,
        )
        db.session.add(schedule)
        db.session.flush()
    else:
        schedule = schedules[0]

    applied: Dict[str, Optional[date]] = {}
    for class_test in class_tests:
        key = str(class_test.class_id)
        if key in applied:
            logger.warning(
                "Logística: class_test duplicado para a turma %s na avaliação %s.",
                key,
                test_id,
            )
        applied[key] = civil_application_date(
            class_test.application, getattr(class_test, "timezone", None)
        )

    class_uuids = ensure_uuid_list(list(applied.keys()))
    uuid_by_class = {str(class_uuid): class_uuid for class_uuid in class_uuids}
    class_rows = (
        db.session.query(Class.id, Class.school_id, Class.grade_id)
        .filter(Class.id.in_(class_uuids))
        .all()
        if class_uuids
        else []
    )
    class_info = {
        str(row[0]): {"school_id": str(row[1]) if row[1] is not None else None, "grade_id": row[2]}
        for row in class_rows
    }
    counts = _student_count_by_class(class_info.keys())
    supplies_by_count = {
        total: _suggest_supplies(mode, total) for total in set(counts.values()) | {0}
    }

    items = list(schedule.items)
    by_class: Dict[str, List[LogisticsScheduleItem]] = {}
    for item in items:
        by_class.setdefault(str(item.class_id), []).append(item)

    created = 0
    updated = 0
    removed = 0

    for class_id, when in applied.items():
        info = class_info.get(class_id)
        class_uuid = uuid_by_class.get(class_id)
        if not info or not info["school_id"] or class_uuid is None:
            logger.warning(
                "Logística: turma %s da avaliação %s sem escola; item não criado.",
                class_id,
                test_id,
            )
            continue
        current = by_class.get(class_id, [])
        if not current:
            total = counts.get(class_id, 0)
            supplies = supplies_by_count.get(total) or _suggest_supplies(mode, total)
            item = LogisticsScheduleItem(
                schedule_id=schedule.id,
                school_id=info["school_id"],
                grade_id=info["grade_id"],
                class_id=class_uuid,
                scheduled_date=when,
                students_count=total,
                tablets_qty=supplies["tablets_qty"],
                booklets_qty=supplies["booklets_qty"],
                notes=None,
                origem=LOGISTICS_ORIGEM_AUTO,
                editado_manualmente=False,
                applicator_user_id=actor_id,
            )
            schedule.items.append(item)
            items.append(item)
            by_class.setdefault(class_id, []).append(item)
            created += 1
            continue
        for item in current:
            if not _is_auto_untouched(item) or item.scheduled_date == when:
                continue
            if _date_taken(items, class_id, when, item.id):
                logger.warning(
                    "Logística: data %s da turma %s colidiria com outro item do cronograma %s.",
                    when,
                    class_id,
                    schedule.id,
                )
                continue
            item.scheduled_date = when
            updated += 1

    for class_id, current in list(by_class.items()):
        if class_id in applied:
            continue
        for item in list(current):
            if not _is_auto_untouched(item):
                continue
            if item in schedule.items:
                schedule.items.remove(item)
            else:
                db.session.delete(item)
            removed += 1

    if created or updated or removed:
        logger.info(
            "Logística: avaliação %s sincronizada no cronograma %s "
            "(%s itens criados, %s datas atualizadas, %s itens removidos).",
            test_id,
            schedule.id,
            created,
            updated,
            removed,
        )
