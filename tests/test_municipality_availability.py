import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.utils.municipality_availability import (
    UNAVAILABLE_CODE,
    apply_availability_fields,
    apply_municipality_availability_filter,
    is_available_to_municipality,
    municipality_availability_payload,
    parse_available_from,
    parse_available_to_municipality,
    resolve_availability_for_create,
    role_bypasses_municipality_availability,
    user_can_access_municipality_content,
)


def _record(**kwargs):
    defaults = {
        "available_to_municipality": True,
        "available_from": None,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


class TestMunicipalityAvailability(unittest.TestCase):
    def test_parse_flag(self):
        self.assertTrue(parse_available_to_municipality(None))
        self.assertFalse(parse_available_to_municipality("false"))
        self.assertFalse(parse_available_to_municipality("não"))
        self.assertTrue(parse_available_to_municipality("sim"))

    def test_parse_available_from_iso(self):
        parsed, err = parse_available_from("2026-09-10T08:00:00-03:00")
        self.assertIsNone(err)
        self.assertEqual(parsed.tzinfo, timezone.utc)
        self.assertEqual(parsed.hour, 11)

        empty, err = parse_available_from("")
        self.assertIsNone(err)
        self.assertIsNone(empty)

        _, err = parse_available_from("nao-e-data")
        self.assertIsNotNone(err)

    def test_hidden_by_flag(self):
        rec = _record(available_to_municipality=False)
        self.assertFalse(is_available_to_municipality(rec))

    def test_hidden_until_date(self):
        future = datetime.now(timezone.utc) + timedelta(days=2)
        rec = _record(available_to_municipality=True, available_from=future)
        self.assertFalse(is_available_to_municipality(rec))
        self.assertTrue(
            is_available_to_municipality(rec, now=future + timedelta(minutes=1))
        )

    def test_visible_when_default(self):
        rec = _record()
        self.assertTrue(is_available_to_municipality(rec))

    def test_admin_and_tecadm_always_access(self):
        rec = _record(available_to_municipality=False)
        self.assertTrue(user_can_access_municipality_content({"role": "admin"}, rec))
        self.assertTrue(user_can_access_municipality_content({"role": "tecadm"}, rec))
        self.assertFalse(user_can_access_municipality_content({"role": "aplicador"}, rec))
        self.assertFalse(user_can_access_municipality_content({"role": "diretor"}, rec))
        self.assertTrue(user_can_access_municipality_content({"role": "aluno"}, rec))

    def test_role_bypass(self):
        self.assertTrue(role_bypasses_municipality_availability("admin"))
        self.assertTrue(role_bypasses_municipality_availability("tecadm"))
        self.assertFalse(role_bypasses_municipality_availability("aplicador"))

    def test_professor_create_ignores_hide_fields(self):
        flag, start, err = resolve_availability_for_create(
            {"available_to_municipality": False, "available_from": "2026-09-10T08:00:00Z"},
            {"role": "professor"},
        )
        self.assertIsNone(err)
        self.assertTrue(flag)
        self.assertIsNone(start)

    def test_admin_create_can_hide(self):
        flag, start, err = resolve_availability_for_create(
            {
                "available_to_municipality": False,
                "available_from": "2026-09-10T08:00:00Z",
            },
            {"role": "admin"},
        )
        self.assertIsNone(err)
        self.assertFalse(flag)
        self.assertIsNotNone(start)

    def test_apply_fields_only_admin(self):
        rec = _record()
        changed, err = apply_availability_fields(
            rec, {"available_to_municipality": False}, {"role": "diretor"}
        )
        self.assertIsNone(err)
        self.assertFalse(changed)
        self.assertTrue(rec.available_to_municipality)

        changed, err = apply_availability_fields(
            rec, {"available_to_municipality": False}, {"role": "tecadm"}
        )
        self.assertIsNone(err)
        self.assertTrue(changed)
        self.assertFalse(rec.available_to_municipality)

    def test_payload(self):
        rec = _record(available_to_municipality=True, available_from=None)
        payload = municipality_availability_payload(rec)
        self.assertTrue(payload["available_to_municipality"])
        self.assertIsNone(payload["available_from"])
        self.assertTrue(payload["is_available_to_municipality_now"])
        self.assertEqual(UNAVAILABLE_CODE, "NOT_AVAILABLE_TO_MUNICIPALITY")

    def test_query_filter_skips_admin(self):
        class FakeQuery:
            def __init__(self):
                self.filtered = False

            def filter(self, *args, **kwargs):
                self.filtered = True
                return self

        q = FakeQuery()
        out = apply_municipality_availability_filter(
            q, SimpleNamespace(), {"role": "admin"}
        )
        self.assertIs(out, q)
        self.assertFalse(q.filtered)


if __name__ == "__main__":
    unittest.main()
