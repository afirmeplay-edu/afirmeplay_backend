"""
Testes do pacote offline (código em texto claro, escopo, cache de bundle).
Execução: python -m unittest tests.test_offline_pack_service
"""
import base64
import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from app.services.mobile import offline_pack_service as svc
from app.services.mobile.ddl import get_mobile_tables_ddl


class TestOfflinePackDDL(unittest.TestCase):
    def test_ddl_has_activation_code(self):
        sql = get_mobile_tables_ddl("city_test123")
        self.assertIn("activation_code", sql)


class TestOfflinePackQrCode(unittest.TestCase):
    def test_build_qr_png_base64_decodes_as_png(self):
        b64 = svc.build_offline_pack_qr_png_base64("ABCD-EFGH-JKLM")
        raw = base64.b64decode(b64)
        self.assertEqual(raw[:8], b"\x89PNG\r\n\x1a\n")

    def test_qrcode_api_dict_matches_code(self):
        pack = MagicMock()
        pack.id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        pack.activation_code = "WXYZ-2345-6789"
        payload = svc.offline_pack_qrcode_api_dict(pack)
        self.assertEqual(payload["code"], "WXYZ-2345-6789")
        self.assertEqual(payload["offline_pack_id"], str(pack.id))
        self.assertTrue(payload["qr_code_data_url"].startswith("data:image/png;base64,"))
        self.assertEqual(
            payload["qr_code_data_url"],
            f"data:image/png;base64,{payload['qr_code_png_base64']}",
        )

    def test_qrcode_without_activation_code_raises(self):
        pack = MagicMock()
        pack.id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        pack.activation_code = None
        with self.assertRaises(ValueError):
            svc.offline_pack_qrcode_api_dict(pack)


class TestOfflinePackCodeHelpers(unittest.TestCase):
    def test_format_and_normalize_roundtrip(self):
        raw = "ABCD-EFGH-JKLM"
        norm = svc.normalize_mobile_input_code(raw)
        self.assertEqual(len(norm), 12)
        self.assertEqual(svc.format_code(norm), "ABCD-EFGH-JKLM")

    def test_registry_lookup_key_is_plain(self):
        norm = "ABCDEFGHJKLM"
        self.assertEqual(svc.registry_lookup_key(norm), norm)
        self.assertNotEqual(svc.registry_lookup_key(norm), svc.hash_code(norm))


class TestInvalidatePackBundleCache(unittest.TestCase):
    def test_clears_resolved_versions(self):
        pack = MagicMock()
        pack.scope_json = {
            "type": "custom",
            "school_ids": ["s1"],
            "_resolved": {
                "sync_bundle_version_by_school": {"s1": 1},
                "bundle_valid_until_min": "2026-01-01T00:00:00Z",
            },
        }
        svc.invalidate_pack_bundle_cache(pack)
        self.assertNotIn(
            "sync_bundle_version_by_school",
            pack.scope_json.get("_resolved", {}),
        )


class TestUpdateOfflinePackValidation(unittest.TestCase):
    def test_expired_without_ttl_raises(self):
        pack = MagicMock()
        pack.revoked_at = None
        pack.expires_at = datetime.utcnow() - timedelta(hours=1)
        pack.scope_json = {"type": "municipality"}
        with self.assertRaises(ValueError) as ctx:
            svc.update_offline_pack(
                pack=pack,
                city_id="city-1",
                scope={"type": "municipality"},
            )
        self.assertIn("expirado", str(ctx.exception).lower())

    @patch.object(svc, "resolve_school_ids")
    @patch.object(svc, "invalidate_pack_bundle_cache")
    @patch.object(svc, "db")
    def test_scope_update_invalidates_cache(
        self, mock_db, mock_invalidate, mock_resolve
    ):
        pack = MagicMock()
        pack.revoked_at = None
        pack.expires_at = datetime.utcnow() + timedelta(hours=24)
        pack.scope_json = {"type": "custom", "school_ids": ["a"]}
        new_scope = {"type": "custom", "school_ids": ["a", "b"]}
        svc.update_offline_pack(
            pack=pack,
            city_id="city-1",
            scope=new_scope,
        )
        mock_resolve.assert_called_once()
        mock_invalidate.assert_called_once_with(pack)
        self.assertEqual(pack.scope_json, new_scope)


class TestDeleteOfflinePacksBulk(unittest.TestCase):
    def test_empty_ids_raises(self):
        with self.assertRaises(ValueError):
            svc.delete_offline_packs_bulk([], {"id": "u1", "role": "admin"})

    def test_too_many_ids_raises(self):
        ids = [f"id-{i}" for i in range(svc._BULK_DELETE_MAX + 1)]
        with self.assertRaises(ValueError):
            svc.delete_offline_packs_bulk(ids, {"id": "u1", "role": "admin"})

    @patch.object(svc, "delete_offline_pack")
    @patch.object(svc, "get_offline_pack_by_id")
    def test_bulk_deletes_found_only(self, mock_get, mock_delete):
        user = {"id": "user-1", "role": "admin"}
        pack = MagicMock()
        pack.id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

        def lookup(pid):
            if pid == str(pack.id):
                return pack
            return None

        mock_get.side_effect = lookup
        result = svc.delete_offline_packs_bulk(
            [str(pack.id), "00000000-0000-0000-0000-000000000099", str(pack.id)],
            user,
        )
        self.assertEqual(result["deleted"], [str(pack.id)])
        self.assertEqual(
            result["not_found"], ["00000000-0000-0000-0000-000000000099"]
        )
        self.assertEqual(result["forbidden"], [])
        mock_delete.assert_called_once_with(pack)

    @patch.object(svc, "delete_offline_pack")
    @patch.object(svc, "get_offline_pack_by_id")
    def test_bulk_forbidden_for_non_creator(self, mock_get, mock_delete):
        pack = MagicMock()
        pack.id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        pack.created_by_user_id = "other-user"
        mock_get.return_value = pack
        user = {"id": "user-1", "role": "aplicador"}
        result = svc.delete_offline_packs_bulk([str(pack.id)], user)
        self.assertEqual(result["deleted"], [])
        self.assertEqual(result["forbidden"], [str(pack.id)])
        mock_delete.assert_not_called()

    def test_can_manage_admin_any_pack(self):
        pack = MagicMock()
        pack.created_by_user_id = "other"
        self.assertTrue(
            svc.can_manage_offline_pack(pack, {"id": "a", "role": "admin"})
        )

    def test_can_manage_creator_only(self):
        pack = MagicMock()
        pack.created_by_user_id = "user-1"
        self.assertTrue(
            svc.can_manage_offline_pack(pack, {"id": "user-1", "role": "coordenador"})
        )
        self.assertFalse(
            svc.can_manage_offline_pack(pack, {"id": "user-2", "role": "aplicador"})
        )


if __name__ == "__main__":
    unittest.main()
