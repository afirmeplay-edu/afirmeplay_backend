# -*- coding: utf-8 -*-
import unittest

from app.physical_tests.tasks import _is_non_retryable_generation_error


class TestPhysicalFormsCeleryRetryPolicy(unittest.TestCase):
    def test_prova_nao_encontrada_is_not_retryable(self):
        self.assertTrue(
            _is_non_retryable_generation_error(
                "Prova 8f744297-39ae-4d7d-84c1-242d3cbc934f não encontrada"
            )
        )

    def test_transient_errors_remain_retryable(self):
        self.assertFalse(_is_non_retryable_generation_error("server closed the connection unexpectedly"))
        self.assertFalse(_is_non_retryable_generation_error("deadlock detected"))


if __name__ == "__main__":
    unittest.main()
