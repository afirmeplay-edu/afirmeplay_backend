"""
O onboarding não pode recriar o engine do município que já está em uso.
Execução: python -m unittest tests.test_physical_schema_override
"""
import unittest
from unittest.mock import patch

from flask import Flask, g

from app.multitenant.physical_schema_binding import (
    _G_BIND_CACHE,
    get_effective_tenant_physical_schema,
    set_physical_schema_override,
)
from app.utils.tenant_middleware import ensure_tenant_schema_for_user


class _RequestCtx:
    def __init__(self, schema):
        self.tenant_schema = schema


class _TenantCtx:
    def __init__(self, schema):
        self.has_tenant_context = True
        self.schema = schema


class TestPhysicalSchemaOverride(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.ctx = self.app.app_context()
        self.ctx.push()

    def tearDown(self):
        self.ctx.pop()

    def test_mesmo_schema_preserva_o_engine(self):
        g.request_context = _RequestCtx("city_abc")
        setattr(g, _G_BIND_CACHE, {"engine": object()})

        set_physical_schema_override("city_abc")

        self.assertEqual(get_effective_tenant_physical_schema(), "city_abc")
        self.assertTrue(hasattr(g, _G_BIND_CACHE))

    def test_troca_de_schema_descarta_o_engine(self):
        g.request_context = _RequestCtx("city_abc")
        setattr(g, _G_BIND_CACHE, {"engine": object()})

        set_physical_schema_override("city_other")

        self.assertEqual(get_effective_tenant_physical_schema(), "city_other")
        self.assertFalse(hasattr(g, _G_BIND_CACHE))

    def test_ensure_nao_reaplica_schema_ja_ativo(self):
        g.request_context = _RequestCtx("city_abc")
        g.tenant_context = _TenantCtx("city_abc")

        with patch("app.utils.tenant_middleware.set_search_path") as set_search_path:
            self.assertTrue(ensure_tenant_schema_for_user("user-1"))
            set_search_path.assert_not_called()

    def test_ensure_restaura_schema_quando_o_bind_foi_trocado(self):
        g.request_context = _RequestCtx("city_abc")
        set_physical_schema_override("city_other")
        g.tenant_context = _TenantCtx("city_abc")

        with patch("app.utils.tenant_middleware.set_search_path") as set_search_path:
            self.assertTrue(ensure_tenant_schema_for_user("user-1"))
            set_search_path.assert_called_once_with("city_abc")


if __name__ == "__main__":
    unittest.main()
