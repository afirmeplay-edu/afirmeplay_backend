# -*- coding: utf-8 -*-
"""Persistência do cache de relatórios para cartão-resposta (gabarito)."""

from __future__ import annotations

import os
import socket
from datetime import datetime
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import logging
from sqlalchemy.exc import SQLAlchemyError

from app import db
from app.models.answerSheetReportAggregate import AnswerSheetReportAggregate
from app.models.school import School
from app.models.student import Student
from app.models.studentClass import Class

logger = logging.getLogger(__name__)


def any_configured_redis_tcp_unreachable(timeout_sec: float = 0.45) -> bool:
    """
    True se **algum** host:port vindo de URLs redis nas envs não aceitar TCP.

    Importante: broker (ex. localhost) e result backend (ex. IP remoto) podem ser
    hosts diferentes; testar só o primeiro fazia o apply_async do rebuild travar
    ~20s quando o segundo estava fora.
    """
    seen: set[tuple[str, int]] = set()
    endpoints: list[tuple[str, int]] = []
    for key in ("CELERY_RESULT_BACKEND", "CELERY_BROKER_URL", "REDIS_URL"):
        raw = (os.getenv(key) or "").strip()
        if not raw or not raw.startswith(("redis://", "rediss://")):
            continue
        try:
            u = urlparse(raw)
            if not u.hostname:
                continue
            port = int(u.port or 6379)
            ep = (u.hostname.lower(), port)
            if ep not in seen:
                seen.add(ep)
                endpoints.append(ep)
        except (ValueError, TypeError):
            continue
    if not endpoints:
        return False
    for host, port in endpoints:
        try:
            with socket.create_connection((host, port), timeout=timeout_sec):
                pass
        except OSError:
            logger.debug(
                "Redis TCP unreachable (%s:%s) — skip Celery enqueue deste host",
                host,
                port,
            )
            return True
    return False


class AnswerSheetReportAggregateService:
    @staticmethod
    def _normalize_scope(scope_type: str, scope_id: Optional[str]) -> tuple[str, Optional[str]]:
        scope_type = (scope_type or "overall").lower()
        if scope_type == "all":
            scope_type = "overall"
        if scope_type not in {"overall", "city", "school", "teacher"}:
            logger.warning("Scope type inválido (answer_sheet): %s. Usando 'overall'.", scope_type)
            scope_type = "overall"
        return scope_type, scope_id if scope_type != "overall" else None

    @classmethod
    def get(
        cls, gabarito_id: str, scope_type: str = "overall", scope_id: Optional[str] = None
    ) -> Optional[AnswerSheetReportAggregate]:
        scope_type, scope_id = cls._normalize_scope(scope_type, scope_id)
        return AnswerSheetReportAggregate.query.filter_by(
            gabarito_id=gabarito_id,
            scope_type=scope_type,
            scope_id=scope_id,
        ).first()

    @classmethod
    def get_payload(
        cls, gabarito_id: str, scope_type: str = "overall", scope_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        aggregate = cls.get(gabarito_id, scope_type, scope_id)
        if not aggregate or aggregate.is_dirty:
            return None
        return aggregate.payload or {}

    @classmethod
    def get_ai_analysis(
        cls, gabarito_id: str, scope_type: str = "overall", scope_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        aggregate = cls.get(gabarito_id, scope_type, scope_id)
        if not aggregate or aggregate.ai_analysis_is_dirty or not aggregate.ai_analysis:
            return None
        return aggregate.ai_analysis or {}

    @classmethod
    def get_status(
        cls, gabarito_id: str, scope_type: str = "overall", scope_id: Optional[str] = None
    ) -> Dict[str, Any]:
        aggregate = cls.get(gabarito_id, scope_type, scope_id)
        if not aggregate:
            return {
                "status": "not_found",
                "has_payload": False,
                "has_ai_analysis": False,
                "is_dirty": True,
                "ai_analysis_is_dirty": True,
                "last_update": None,
            }
        is_ready = (
            not aggregate.is_dirty
            and aggregate.payload
            and not aggregate.ai_analysis_is_dirty
            and aggregate.ai_analysis
        )
        return {
            "status": "ready" if is_ready else "processing",
            "has_payload": bool(aggregate.payload) and not aggregate.is_dirty,
            "has_ai_analysis": bool(aggregate.ai_analysis) and not aggregate.ai_analysis_is_dirty,
            "is_dirty": aggregate.is_dirty,
            "ai_analysis_is_dirty": aggregate.ai_analysis_is_dirty,
            "last_update": aggregate.updated_at,
        }

    @classmethod
    def save_payload(
        cls,
        gabarito_id: str,
        scope_type: str,
        scope_id: Optional[str],
        payload: Dict[str, Any],
        student_count: int = 0,
        commit: bool = True,
    ) -> AnswerSheetReportAggregate:
        scope_type, scope_id = cls._normalize_scope(scope_type, scope_id)
        aggregate = cls.get(gabarito_id, scope_type, scope_id)
        if not aggregate:
            aggregate = AnswerSheetReportAggregate(
                gabarito_id=gabarito_id,
                scope_type=scope_type,
                scope_id=scope_id,
            )
            db.session.add(aggregate)
        aggregate.update_payload(payload or {}, student_count or 0)
        if commit:
            cls._safe_commit()
        return aggregate

    @classmethod
    def save_ai_analysis(
        cls,
        gabarito_id: str,
        scope_type: str,
        scope_id: Optional[str],
        ai_analysis: Dict[str, Any],
        commit: bool = True,
    ) -> AnswerSheetReportAggregate:
        scope_type, scope_id = cls._normalize_scope(scope_type, scope_id)
        aggregate = cls.get(gabarito_id, scope_type, scope_id)
        if not aggregate:
            aggregate = AnswerSheetReportAggregate(
                gabarito_id=gabarito_id,
                scope_type=scope_type,
                scope_id=scope_id,
            )
            db.session.add(aggregate)
        aggregate.update_ai_analysis(ai_analysis or {})
        if commit:
            cls._safe_commit()
        return aggregate

    @classmethod
    def mark_dirty(
        cls,
        gabarito_id: str,
        scope_type: str,
        scope_id: Optional[str],
        commit: bool = True,
    ) -> None:
        scope_type, scope_id = cls._normalize_scope(scope_type, scope_id)
        aggregate = cls.get(gabarito_id, scope_type, scope_id)
        if not aggregate:
            return
        aggregate.mark_dirty()
        if commit:
            cls._safe_commit()

    @classmethod
    def mark_ai_dirty(
        cls,
        gabarito_id: str,
        scope_type: str,
        scope_id: Optional[str],
        commit: bool = True,
    ) -> None:
        scope_type, scope_id = cls._normalize_scope(scope_type, scope_id)
        aggregate = cls.get(gabarito_id, scope_type, scope_id)
        if not aggregate:
            return
        aggregate.mark_ai_dirty()
        if commit:
            cls._safe_commit()

    @classmethod
    def mark_all_dirty_for_gabarito(cls, gabarito_id: str, commit: bool = True) -> None:
        rows = AnswerSheetReportAggregate.query.filter_by(gabarito_id=gabarito_id).all()
        for row in rows:
            row.mark_dirty()
            row.mark_ai_dirty()
        if commit and rows:
            cls._safe_commit()

    @staticmethod
    def _safe_commit() -> None:
        try:
            db.session.commit()
            db.session.expire_all()
        except SQLAlchemyError:
            logger.exception("Falha ao salvar answer_sheet_report_aggregates")
            db.session.rollback()
            raise


def invalidate_answer_sheet_report_cache_after_result(
    gabarito_id: str, student_id: str, commit: bool = True
) -> None:
    """
    Marca caches do gabarito como sujos e agenda rebuild assíncrono (Celery), se city_id conhecido.
    """
    AnswerSheetReportAggregateService.mark_all_dirty_for_gabarito(gabarito_id, commit=False)

    scope_city_id = None
    st = Student.query.get(student_id)
    if st:
        scope_school_id = getattr(st, "school_id", None)
        if not scope_school_id and st.class_id:
            co = Class.query.get(st.class_id)
            if co:
                scope_school_id = co.school_id
        if scope_school_id:
            sch = School.query.get(scope_school_id)
            if sch and sch.city_id:
                scope_city_id = sch.city_id

    if commit:
        AnswerSheetReportAggregateService._safe_commit()

    if scope_city_id:
        if any_configured_redis_tcp_unreachable():
            logger.warning(
                "Rebuild answer_sheet report não agendado: Redis inacessível (TCP)."
            )
        else:
            try:
                from app.report_analysis.tasks import rebuild_answer_sheet_reports_for_gabarito

                rebuild_answer_sheet_reports_for_gabarito.apply_async(
                    args=[gabarito_id, str(scope_city_id)],
                    ignore_result=True,
                )
            except Exception as exc:
                logger.warning("Rebuild answer_sheet report não agendado: %s", exc)


def invalidate_answer_sheet_reports_after_gabarito_bulk_update(
    gabarito_id: str,
    city_id_for_rebuild: Optional[str],
    *,
    commit: bool = True,
) -> None:
    """
    Após alterar/recalcular vários resultados do mesmo gabarito: marca caches agregados
    sujos **uma vez** e tenta agendar **no máximo um** rebuild.

    Evita chamar `invalidate_answer_sheet_report_cache_after_result` por aluno, o que
    repetia mark_dirty + commit + `.delay()` do rebuild e degradava muito com Redis/Celery.
    """
    AnswerSheetReportAggregateService.mark_all_dirty_for_gabarito(
        gabarito_id, commit=commit
    )
    if not city_id_for_rebuild:
        return
    if any_configured_redis_tcp_unreachable():
        logger.warning(
            "Rebuild answer_sheet report não agendado: Redis inacessível (TCP). "
            "Agregados marcados sujos; rebuild pode rodar depois."
        )
        return
    try:
        from app.report_analysis.tasks import rebuild_answer_sheet_reports_for_gabarito

        rebuild_answer_sheet_reports_for_gabarito.apply_async(
            args=[gabarito_id, str(city_id_for_rebuild)],
            ignore_result=True,
        )
    except Exception as exc:
        logger.warning("Rebuild answer_sheet report não agendado: %s", exc)
