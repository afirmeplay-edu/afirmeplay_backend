# -*- coding: utf-8 -*-
# Exec: python -m unittest tests.test_results_delivery
import importlib.util
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_DELIVERY = _ROOT / "app" / "socioeconomic_forms" / "services" / "results_delivery.py"


def _load():
    spec = importlib.util.spec_from_file_location("results_delivery", _DELIVERY)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


_delivery = _load()
decide_report_delivery = _delivery.decide_report_delivery


class TestDecideReportDelivery(unittest.TestCase):
    def test_cache_ready_returns_200_path(self):
        self.assertEqual(
            decide_report_delivery(True, workers_alive=False, inflight_age=None),
            "ready",
        )

    def test_no_worker_computes_in_request(self):
        self.assertEqual(
            decide_report_delivery(False, workers_alive=False, inflight_age=None),
            "compute_sync",
        )

    def test_worker_enqueues_once_then_waits(self):
        self.assertEqual(
            decide_report_delivery(False, workers_alive=True, inflight_age=None),
            "enqueue",
        )
        self.assertEqual(
            decide_report_delivery(False, workers_alive=True, inflight_age=2.5),
            "wait",
        )

    def test_stale_job_falls_back_to_sync(self):
        self.assertEqual(
            decide_report_delivery(False, workers_alive=True, inflight_age=20.0, stale_after=20.0),
            "compute_sync",
        )
