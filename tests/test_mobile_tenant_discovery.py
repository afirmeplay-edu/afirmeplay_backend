"""
Testes do discovery mobile (tenant_discovery_service + rota available-cities).
Execução: python -m unittest tests.test_mobile_tenant_discovery
"""
import os
import unittest

from app.mobile.services.tenant_discovery_service import (
    API_CONTRACT_VERSION,
    build_available_cities_response,
    serialize_city_entry,
    _normalize_api_base_url,
)


class TestTenantDiscoveryHelpers(unittest.TestCase):
    def test_normalize_api_base_url(self):
        self.assertEqual(
            _normalize_api_base_url("https://api.example.com/"),
            "https://api.example.com",
        )

    def test_serialize_city_entry(self):
        class Row:
            id = "uuid-1"
            tenant_code = "TST001"
            city_slug = "test-city"
            city_name = "Test City"
            hosting_mode = "dedicated"
            api_base_url = "https://api.test.com/"

        out = serialize_city_entry(Row())
        self.assertEqual(out["slug"], "test-city")
        self.assertEqual(out["name"], "Test City")
        self.assertEqual(out["hosting_mode"], "dedicated")
        self.assertEqual(out["api_base_url"], "https://api.test.com")
        self.assertEqual(out["tenant_code"], "TST001")


class TestAvailableCitiesRoute(unittest.TestCase):
    @unittest.skipUnless(os.getenv("DATABASE_URL"), "DATABASE_URL não definido")
    def test_get_available_cities_public(self):
        from app import create_app

        app = create_app()
        client = app.test_client()
        rv = client.get("/mobile/v1/available-cities")
        self.assertEqual(rv.status_code, 200)
        data = rv.get_json()
        self.assertEqual(data.get("api_contract_version"), API_CONTRACT_VERSION)
        self.assertIn("generated_at", data)
        self.assertIn("cities", data)
        self.assertIsInstance(data["cities"], list)
        for item in data["cities"]:
            self.assertIn("id", item)
            self.assertIn("tenant_code", item)
            self.assertIn("slug", item)
            self.assertIn("name", item)
            self.assertIn("hosting_mode", item)
            self.assertIn("api_base_url", item)

    @unittest.skipUnless(os.getenv("DATABASE_URL"), "DATABASE_URL não definido")
    def test_build_response_lists_active_visible(self):
        from app import create_app

        app = create_app()
        with app.app_context():
            payload = build_available_cities_response()
            self.assertEqual(payload["api_contract_version"], API_CONTRACT_VERSION)
            for item in payload["cities"]:
                self.assertTrue(item["api_base_url"].startswith("https://"))
