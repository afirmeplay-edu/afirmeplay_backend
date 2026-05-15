import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.models import CalendarTargetType
from app.services.calendar_event_service import CalendarEventService
import app.services.calendar_event_service as ces


class FakeQuery:
    def __init__(self, items=None, get_map=None):
        self._items = list(items or [])
        self._get_map = dict(get_map or {})

    def all(self):
        return list(self._items)

    def first(self):
        return self._items[0] if self._items else None

    def get(self, key):
        return self._get_map.get(key)

    def filter(self, *args, **kwargs):
        return self

    def filter_by(self, **kwargs):
        filtered = []
        for item in self._items:
            if all(getattr(item, k, None) == v for k, v in kwargs.items()):
                filtered.append(item)
        return FakeQuery(filtered, self._get_map)


class TestCalendarEventTecadmRecipients(unittest.TestCase):
    def test_matches_tecadm_school_filter_without_manager(self):
        tecadm_user = SimpleNamespace(id="u-tec", role="tecadm", city_id="city-1")
        school = SimpleNamespace(id="school-1", city_id="city-1")
        filters = {"school_ids": ["school-1"], "grade_ids": [], "class_ids": []}

        with patch.object(ces.User, "query", FakeQuery(get_map={"u-tec": tecadm_user})):
            with patch.object(ces.Manager, "query", FakeQuery(items=[])):
                with patch.object(ces.School, "query", FakeQuery(items=[school])):
                    ok, ctx = CalendarEventService._matches_role_group_filters_for_user(
                        "tecadm",
                        "u-tec",
                        filters,
                        tenant_city_id="city-1",
                    )

        self.assertTrue(ok)
        self.assertEqual(ctx[2], "tecadm")

    def test_materialize_role_group_tecadm_includes_user_without_manager(self):
        event = SimpleNamespace(
            id="event-1",
            created_by_user_id="creator-1",
            created_by_role="admin",
            municipality_id="city-1",
            visibility_scope=None,
            school_id=None,
        )
        target = SimpleNamespace(
            target_type=CalendarTargetType.ROLE_GROUP,
            target_id="tecadm",
            target_filters={"school_ids": ["school-1"], "grade_ids": [], "class_ids": []},
        )
        creator = SimpleNamespace(id="creator-1", role="admin", city_id="city-1")
        tecadm_user = SimpleNamespace(id="u-tec", role="tecadm", city_id="city-1")
        school = SimpleNamespace(id="school-1", city_id="city-1")

        mock_session = Mock()

        with patch.object(ces.CalendarEvent, "query", FakeQuery(get_map={"event-1": event})):
            with patch.object(ces.CalendarEventTarget, "query", FakeQuery(items=[target])):
                with patch.object(
                    ces.User,
                    "query",
                    FakeQuery(items=[creator, tecadm_user], get_map={"creator-1": creator, "u-tec": tecadm_user}),
                ):
                    with patch.object(ces.Manager, "query", FakeQuery(items=[])):
                        with patch.object(ces.School, "query", FakeQuery(items=[school])):
                            with patch.object(ces.db, "session", mock_session):
                                CalendarEventService.materialize_recipients("event-1")

        added_recipients = [call.args[0] for call in mock_session.add.call_args_list]
        recipient_ids = {recipient.user_id for recipient in added_recipients}
        self.assertIn("u-tec", recipient_ids)
        mock_session.commit.assert_called_once()


if __name__ == "__main__":
    unittest.main()
