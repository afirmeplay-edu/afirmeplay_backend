# -*- coding: utf-8 -*-
"""Concessão de moedas por uso de Jogos e Play TV."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from app import db
from app.balance.models import StudentCoins
from app.balance.services.coin_service import CoinService
from app.rewards.config import (
    ACHIEVEMENT_EXPLORADOR_JOGOS,
    ACHIEVEMENT_MARATONISTA_PLAY_TV,
    CONTENT_TYPE_GAME,
    CONTENT_TYPE_VIDEO,
    DAILY_CAP_COINS,
    DAILY_CAP_TIMEZONE,
    GAME_MIN_VISIBLE_SECONDS,
    GAME_REWARD_COINS,
    REASON_GAME_PLAY,
    REASON_PLAYTV_WATCH,
    VIDEO_FALLBACK_SECONDS,
    VIDEO_REWARD_COINS,
    YOUTUBE_DURATION_FACTOR,
    YOUTUBE_MIN_WALL_SECONDS,
    YOUTUBE_WATCHED_PERCENT,
)
from app.rewards.models import ContentReward, ContentSession


def is_youtube_url(url: Optional[str]) -> bool:
    if not url:
        return False
    lowered = url.lower()
    return "youtube.com" in lowered or "youtu.be" in lowered


def _utcnow() -> datetime:
    return datetime.utcnow()


def _as_naive_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _today_utc_bounds() -> tuple:
    tz = ZoneInfo(DAILY_CAP_TIMEZONE)
    now_local = datetime.now(tz)
    start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    end_local = start_local + timedelta(days=1)
    start_utc = start_local.astimezone(timezone.utc).replace(tzinfo=None)
    end_utc = end_local.astimezone(timezone.utc).replace(tzinfo=None)
    return start_utc, end_utc


class ContentRewardService:
    @staticmethod
    def coins_for_type(content_type: str) -> int:
        if content_type == CONTENT_TYPE_GAME:
            return GAME_REWARD_COINS
        if content_type == CONTENT_TYPE_VIDEO:
            return VIDEO_REWARD_COINS
        return 0

    @staticmethod
    def daily_used(student_id: str) -> int:
        start_utc, end_utc = _today_utc_bounds()
        used = (
            db.session.query(func.coalesce(func.sum(ContentReward.coins), 0))
            .filter(
                ContentReward.student_id == student_id,
                ContentReward.paid_at >= start_utc,
                ContentReward.paid_at < end_utc,
            )
            .scalar()
        )
        return int(used or 0)

    @staticmethod
    def daily_remaining(student_id: str) -> int:
        remaining = DAILY_CAP_COINS - ContentRewardService.daily_used(student_id)
        return max(0, remaining)

    @staticmethod
    def list_claimed_ids(student_id: str, content_type: Optional[str] = None) -> list:
        query = ContentReward.query.filter_by(student_id=student_id)
        if content_type:
            query = query.filter_by(content_type=content_type)
        return [row.content_id for row in query.all()]

    @staticmethod
    def start_session(student_id: str, content_type: str, content_id: str) -> Dict[str, Any]:
        session = ContentSession(
            student_id=student_id,
            content_type=content_type,
            content_id=content_id,
            started_at=_utcnow(),
        )
        db.session.add(session)
        db.session.commit()
        return {
            "session_id": session.id,
            "started_at": session.started_at.isoformat() if session.started_at else None,
        }

    @staticmethod
    def claim_reward(
        student_id: str,
        content_type: str,
        content_id: str,
        session_id: str,
        eligible: bool = True,
        is_youtube: bool = False,
        watched_percent: Optional[float] = None,
        duration_seconds: Optional[float] = None,
    ) -> Dict[str, Any]:
        remaining = ContentRewardService.daily_remaining(student_id)
        balance = CoinService.get_balance(student_id)

        if not eligible:
            return _claim_payload(False, 0, "not_eligible", remaining, balance)

        session = ContentSession.query.get(session_id)
        if (
            session is None
            or session.student_id != student_id
            or session.content_type != content_type
            or session.content_id != content_id
        ):
            return _claim_payload(False, 0, "not_eligible", remaining, balance)

        existing = ContentReward.query.filter_by(
            student_id=student_id,
            content_type=content_type,
            content_id=content_id,
        ).first()
        if existing is not None:
            return _claim_payload(False, 0, "already_claimed", remaining, balance)

        amount = ContentRewardService.coins_for_type(content_type)
        if amount <= 0:
            return _claim_payload(False, 0, "not_eligible", remaining, balance)

        if not _meets_time_criteria(
            session=session,
            content_type=content_type,
            is_youtube=is_youtube,
            watched_percent=watched_percent,
            duration_seconds=duration_seconds,
        ):
            return _claim_payload(False, 0, "too_early", remaining, balance)

        try:
            ContentRewardService._lock_student_coins(student_id)
            remaining = ContentRewardService.daily_remaining(student_id)
            if remaining < amount:
                db.session.rollback()
                return _claim_payload(
                    False,
                    0,
                    "daily_cap_reached",
                    ContentRewardService.daily_remaining(student_id),
                    CoinService.get_balance(student_id),
                )

            now = _utcnow()
            reward = ContentReward(
                student_id=student_id,
                content_type=content_type,
                content_id=content_id,
                coins=amount,
                paid_at=now,
            )
            db.session.add(reward)
            db.session.flush()
        except IntegrityError:
            db.session.rollback()
            remaining = ContentRewardService.daily_remaining(student_id)
            return _claim_payload(
                False,
                0,
                "already_claimed",
                remaining,
                CoinService.get_balance(student_id),
            )

        reason = REASON_GAME_PLAY if content_type == CONTENT_TYPE_GAME else REASON_PLAYTV_WATCH
        description = (
            f"Jogou o jogo {content_id}"
            if content_type == CONTENT_TYPE_GAME
            else f"Assistiu o vídeo {content_id}"
        )
        try:
            transaction = CoinService.credit_coins(
                student_id=student_id,
                amount=amount,
                reason=reason,
                commit=False,
                description=description,
            )
            reward.coin_transaction_id = transaction.id
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise

        remaining = ContentRewardService.daily_remaining(student_id)
        new_balance = CoinService.get_balance(student_id)
        progress = _achievement_progress_for(student_id, content_type)
        return _claim_payload(True, amount, "granted", remaining, new_balance, progress)

    @staticmethod
    def _lock_student_coins(student_id: str) -> None:
        row = (
            StudentCoins.query.filter_by(student_id=student_id)
            .with_for_update()
            .first()
        )
        if row is None:
            db.session.add(StudentCoins(student_id=student_id, balance=0))
            db.session.flush()
            StudentCoins.query.filter_by(student_id=student_id).with_for_update().first()


def _meets_time_criteria(
    session: ContentSession,
    content_type: str,
    is_youtube: bool,
    watched_percent: Optional[float],
    duration_seconds: Optional[float],
) -> bool:
    started = _as_naive_utc(session.started_at)
    if started is None:
        return False
    elapsed = (_utcnow() - started).total_seconds()

    if content_type == CONTENT_TYPE_GAME:
        return elapsed >= GAME_MIN_VISIBLE_SECONDS

    if content_type == CONTENT_TYPE_VIDEO and is_youtube:
        try:
            percent = float(watched_percent) if watched_percent is not None else -1
        except (TypeError, ValueError):
            percent = -1
        try:
            duration = float(duration_seconds) if duration_seconds is not None else 0
        except (TypeError, ValueError):
            duration = 0
        if percent < YOUTUBE_WATCHED_PERCENT:
            return False
        min_wall = max(YOUTUBE_MIN_WALL_SECONDS, YOUTUBE_DURATION_FACTOR * max(duration, 0))
        return elapsed >= min_wall

    if content_type == CONTENT_TYPE_VIDEO:
        return elapsed >= VIDEO_FALLBACK_SECONDS

    return False


def _claim_payload(
    granted: bool,
    coins: int,
    status: str,
    daily_remaining: int,
    new_balance: Optional[int],
    achievement_progress: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "granted": granted,
        "coins": coins,
        "status": status,
        "daily_remaining": daily_remaining,
        "new_balance": new_balance,
        "achievement_progress": achievement_progress,
    }


def _achievement_progress_for(student_id: str, content_type: str) -> Optional[Dict[str, Any]]:
    achievement_id = (
        ACHIEVEMENT_EXPLORADOR_JOGOS
        if content_type == CONTENT_TYPE_GAME
        else ACHIEVEMENT_MARATONISTA_PLAY_TV
    )
    try:
        from app.services.achievement_service import get_conquistas

        result = get_conquistas(student_id, redeemed_keys=[])
        for item in result.get("conquistas") or []:
            if item.get("id") == achievement_id:
                return {
                    "id": item.get("id"),
                    "level": item.get("medalha_atual"),
                    "progress": item.get("progresso_percent"),
                    "next_threshold": item.get("limiar_proximo"),
                }
    except Exception:
        return None
    return None
