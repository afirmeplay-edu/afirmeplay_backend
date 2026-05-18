"""Testes do serviço de usuário aplicador."""
import unittest
from unittest.mock import MagicMock, patch

from app.models.user import RoleEnum
from app.services.aplicador_user_service import (
    assert_email_prefix_unique_in_city,
    collect_aplicadores_for_city,
    email_login_prefix,
    resolve_user_by_login_ident,
)


class TestEmailLoginPrefix(unittest.TestCase):
    def test_prefix(self):
        self.assertEqual(email_login_prefix("joao@afirmeplay.com.br"), "joao")

    def test_invalid(self):
        self.assertIsNone(email_login_prefix("invalid"))


class TestCollectAplicadores(unittest.TestCase):
    @patch("app.services.aplicador_user_service.User")
    def test_serializes_aplicadores(self, mock_user):
        u = MagicMock()
        u.id = "u1"
        u.name = "Maria"
        u.email = "maria@city.gov.br"
        u.registration = None
        u.offline_password = "senha123"
        mock_user.query.filter_by.return_value.order_by.return_value.all.return_value = [
            u
        ]
        rows = collect_aplicadores_for_city("city-1")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["login"], "maria")
        self.assertEqual(rows[0]["role"], "aplicador")
        self.assertEqual(rows[0]["offline_password"], "senha123")


class TestPrefixUnique(unittest.TestCase):
    @patch("app.services.aplicador_user_service.User")
    def test_duplicate_prefix_raises(self, mock_user):
        other = MagicMock()
        other.id = "x"
        other.email = "joao@other.domain"
        mock_user.query.filter.return_value.all.return_value = [other]
        with self.assertRaises(ValueError):
            assert_email_prefix_unique_in_city("joao@afirme.com", "city-1")


if __name__ == "__main__":
    unittest.main()
