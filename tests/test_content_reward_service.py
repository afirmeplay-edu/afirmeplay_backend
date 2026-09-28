# -*- coding: utf-8 -*-
"""Testes do ContentRewardService (Jogos / Play TV)."""
import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from sqlalchemy.exc import IntegrityError

import app.models  # noqa: F401  registra models antes de CoinService/rewards

from app.rewards.config import (
    CONTENT_TYPE_GAME,
    CONTENT_TYPE_VIDEO,
    GAME_MIN_VISIBLE_SECONDS,
    GAME_REWARD_COINS,
    VIDEO_FALLBACK_SECONDS,
    VIDEO_REWARD_COINS,
    YOUTUBE_WATCHED_PERCENT,
)
from app.rewards.services import ContentRewardService, _meets_time_criteria, is_youtube_url


def _session(student_id="st1", content_type=CONTENT_TYPE_GAME, content_id="g1", started_at=None):
    return SimpleNamespace(
        id="sess-1",
        student_id=student_id,
        content_type=content_type,
        content_id=content_id,
        started_at=started_at if started_at is not None else datetime.utcnow() - timedelta(seconds=120),
    )


class _FilterQuery:
    def __init__(self, result=None):
        self._result = result

    def filter_by(self, **_kwargs):
        return self

    def first(self):
        return self._result

    def get(self, _id):
        return self._result

    def with_for_update(self):
        return self

    def all(self):
        return self._result or []


def _content_session_class(session):
    cls = MagicMock()
    cls.query = _FilterQuery(session)
    cls.return_value = MagicMock()
    return cls


def _content_reward_class(existing=None):
    cls = MagicMock()
    cls.query = _FilterQuery(existing)
    cls.return_value = MagicMock()
    return cls


class TestYoutubeUrl(unittest.TestCase):
    def test_detects_youtube(self):
        self.assertTrue(is_youtube_url("https://www.youtube.com/watch?v=abc"))
        self.assertTrue(is_youtube_url("https://youtu.be/abc"))
        self.assertFalse(is_youtube_url("https://vimeo.com/123"))
        self.assertFalse(is_youtube_url(None))


class TestTimeCriteria(unittest.TestCase):
    def test_game_too_early(self):
        session = _session(started_at=datetime.utcnow())
        self.assertFalse(
            _meets_time_criteria(session, CONTENT_TYPE_GAME, False, None, None)
        )

    def test_game_ready_after_min_seconds(self):
        session = _session(
            started_at=datetime.utcnow() - timedelta(seconds=GAME_MIN_VISIBLE_SECONDS + 1)
        )
        self.assertTrue(
            _meets_time_criteria(session, CONTENT_TYPE_GAME, False, None, None)
        )

    def test_video_fallback_too_early(self):
        session = _session(
            content_type=CONTENT_TYPE_VIDEO,
            started_at=datetime.utcnow() - timedelta(seconds=VIDEO_FALLBACK_SECONDS - 10),
        )
        self.assertFalse(
            _meets_time_criteria(session, CONTENT_TYPE_VIDEO, False, None, None)
        )

    def test_youtube_requires_percent_and_wall_clock(self):
        session = _session(
            content_type=CONTENT_TYPE_VIDEO,
            started_at=datetime.utcnow() - timedelta(seconds=40),
        )
        self.assertFalse(
            _meets_time_criteria(session, CONTENT_TYPE_VIDEO, True, 50, 100)
        )
        self.assertTrue(
            _meets_time_criteria(
                session, CONTENT_TYPE_VIDEO, True, YOUTUBE_WATCHED_PERCENT, 100
            )
        )

    def test_youtube_instant_claim_rejected(self):
        session = _session(
            content_type=CONTENT_TYPE_VIDEO,
            started_at=datetime.utcnow(),
        )
        self.assertFalse(
            _meets_time_criteria(session, CONTENT_TYPE_VIDEO, True, 100, 10)
        )


class TestClaimReward(unittest.TestCase):
    def _common_patches(self, session, existing=None, remaining=50, balance=0):
        return (
            patch("app.rewards.services.ContentSession", _content_session_class(session)),
            patch("app.rewards.services.ContentReward", _content_reward_class(existing)),
            patch.object(ContentRewardService, "daily_remaining", return_value=remaining),
            patch.object(ContentRewardService, "daily_used", return_value=0),
            patch("app.rewards.services.CoinService.get_balance", return_value=balance),
            patch.object(ContentRewardService, "_lock_student_coins"),
            patch("app.rewards.services.db.session"),
        )

    def test_not_eligible(self):
        session = _session()
        patches = self._common_patches(session)
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6]:
            result = ContentRewardService.claim_reward(
                "st1", CONTENT_TYPE_GAME, "g1", "sess-1", eligible=False
            )
        self.assertFalse(result["granted"])
        self.assertEqual(result["status"], "not_eligible")

    def test_non_student_or_no_access_is_not_eligible(self):
        session = _session()
        patches = self._common_patches(session)
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6]:
            result = ContentRewardService.claim_reward(
                "st1", CONTENT_TYPE_GAME, "g1", "sess-1", eligible=False
            )
        self.assertEqual(result["status"], "not_eligible")
        self.assertEqual(result["coins"], 0)

    def test_session_for_other_content(self):
        session = _session(content_id="other-game")
        patches = self._common_patches(session)
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6]:
            result = ContentRewardService.claim_reward(
                "st1", CONTENT_TYPE_GAME, "g1", "sess-1", eligible=True
            )
        self.assertEqual(result["status"], "not_eligible")

    def test_session_of_another_student(self):
        session = _session(student_id="other")
        patches = self._common_patches(session)
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6]:
            result = ContentRewardService.claim_reward(
                "st1", CONTENT_TYPE_GAME, "g1", "sess-1", eligible=True
            )
        self.assertFalse(result["granted"])
        self.assertEqual(result["status"], "not_eligible")

    def test_already_claimed(self):
        session = _session()
        existing = SimpleNamespace(id="r1")
        patches = self._common_patches(session, existing=existing)
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6]:
            result = ContentRewardService.claim_reward(
                "st1", CONTENT_TYPE_GAME, "g1", "sess-1", eligible=True
            )
        self.assertFalse(result["granted"])
        self.assertEqual(result["status"], "already_claimed")

    def test_too_early(self):
        session = _session(started_at=datetime.utcnow())
        patches = self._common_patches(session)
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6]:
            result = ContentRewardService.claim_reward(
                "st1", CONTENT_TYPE_GAME, "g1", "sess-1", eligible=True
            )
        self.assertFalse(result["granted"])
        self.assertEqual(result["status"], "too_early")

    def test_daily_cap_reached(self):
        session = _session()
        patches = self._common_patches(session, remaining=0)
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6]:
            result = ContentRewardService.claim_reward(
                "st1", CONTENT_TYPE_GAME, "g1", "sess-1", eligible=True
            )
        self.assertFalse(result["granted"])
        self.assertEqual(result["status"], "daily_cap_reached")
        self.assertEqual(result["coins"], 0)

    def test_granted_game(self):
        session = _session()
        tx = SimpleNamespace(id="tx-1")
        patches = self._common_patches(session, remaining=50, balance=10)
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6]:
            with patch(
                "app.rewards.services.CoinService.credit_coins", return_value=tx
            ) as credit:
                with patch(
                    "app.rewards.services._achievement_progress_for",
                    return_value={"id": "explorador_jogos", "level": None, "progress": 0, "next_threshold": 3},
                ):
                    result = ContentRewardService.claim_reward(
                        "st1", CONTENT_TYPE_GAME, "g1", "sess-1", eligible=True
                    )
        self.assertTrue(result["granted"])
        self.assertEqual(result["status"], "granted")
        self.assertEqual(result["coins"], GAME_REWARD_COINS)
        credit.assert_called_once()
        self.assertEqual(credit.call_args.kwargs.get("commit"), False)
        self.assertEqual(credit.call_args.kwargs.get("reason"), "game_play")

    def test_double_claim_unique_violation(self):
        session = _session()
        session_mock = MagicMock()
        session_mock.flush.side_effect = IntegrityError("unique", {}, None)
        patches = list(self._common_patches(session))
        patches[6] = patch("app.rewards.services.db.session", session_mock)
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6]:
            result = ContentRewardService.claim_reward(
                "st1", CONTENT_TYPE_GAME, "g1", "sess-1", eligible=True
            )
        self.assertFalse(result["granted"])
        self.assertEqual(result["status"], "already_claimed")

    def test_video_youtube_too_early_without_percent(self):
        session = _session(
            content_type=CONTENT_TYPE_VIDEO,
            content_id="v1",
            started_at=datetime.utcnow() - timedelta(seconds=120),
        )
        patches = self._common_patches(session)
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6]:
            result = ContentRewardService.claim_reward(
                "st1",
                CONTENT_TYPE_VIDEO,
                "v1",
                "sess-1",
                eligible=True,
                is_youtube=True,
                watched_percent=10,
                duration_seconds=200,
            )
        self.assertEqual(result["status"], "too_early")

    def test_video_fallback_granted(self):
        session = _session(
            content_type=CONTENT_TYPE_VIDEO,
            content_id="v1",
            started_at=datetime.utcnow() - timedelta(seconds=VIDEO_FALLBACK_SECONDS + 1),
        )
        tx = SimpleNamespace(id="tx-2")
        patches = self._common_patches(session, remaining=50, balance=0)
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6]:
            with patch("app.rewards.services.CoinService.credit_coins", return_value=tx):
                with patch("app.rewards.services._achievement_progress_for", return_value=None):
                    result = ContentRewardService.claim_reward(
                        "st1",
                        CONTENT_TYPE_VIDEO,
                        "v1",
                        "sess-1",
                        eligible=True,
                        is_youtube=False,
                    )
        self.assertTrue(result["granted"])
        self.assertEqual(result["coins"], VIDEO_REWARD_COINS)


if __name__ == "__main__":
    unittest.main()
