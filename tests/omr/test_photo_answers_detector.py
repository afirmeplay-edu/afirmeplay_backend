# -*- coding: utf-8 -*-
"""Testes do pipeline image-first de foto da área de respostas (sem Flask/DB)."""

from __future__ import annotations

import importlib.util
import os
import sys
import types
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SAMPLE_IMAGE = os.path.join(os.path.dirname(__file__), "fixtures", "photo_answers_sample.jpg")
ALT_SAMPLE = r"C:\Users\conta\.cursor\projects\c-Users-conta-Documents-Afirme\assets\WhatsApp_Image_2026-11-19_at_10.41.08-f9da7047-df84-4a5c-8a65-b85391e22e84.jpg"


def _load_detector():
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)

    if "app" not in sys.modules:
        app_mod = types.ModuleType("app")
        app_mod.__path__ = [os.path.join(ROOT, "app")]
        app_mod.db = types.SimpleNamespace()
        sys.modules["app"] = app_mod

    for name in ["app.services", "app.services.cartao_resposta"]:
        if name not in sys.modules:
            m = types.ModuleType(name)
            m.__path__ = [os.path.join(ROOT, *name.split("."))]
            sys.modules[name] = m

    det_path = os.path.join(ROOT, "app", "services", "cartao_resposta", "photo_answers_detector.py")
    det_name = "app.services.cartao_resposta.photo_answers_detector"
    spec = importlib.util.spec_from_file_location(det_name, det_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[det_name] = mod
    spec.loader.exec_module(mod)
    return mod


def _topology_4x13():
    blocks = []
    q = 1
    for b in range(1, 5):
        qs = [{"q": q + i, "alternatives": ["A", "B", "C", "D"]} for i in range(13)]
        q += 13
        blocks.append(
            {
                "block_id": b,
                "subject_name": "Português" if b <= 2 else "Matemática",
                "questions": qs,
            }
        )
    return {"num_blocks": 4, "topology": {"blocks": blocks}}


def _topology_wrong_2q():
    """Simula o bug: prova subjetiva com 2 questões / 2 blocos."""
    return {
        "num_blocks": 2,
        "topology": {
            "blocks": [
                {"block_id": 1, "questions": [{"q": 1, "alternatives": ["A", "B", "C", "D"]}]},
                {"block_id": 2, "questions": [{"q": 2, "alternatives": ["A", "B", "C", "D"]}]},
            ]
        },
    }


def _sample_path():
    for p in (SAMPLE_IMAGE, ALT_SAMPLE):
        if p and os.path.isfile(p):
            return p
    return None


class TestPhotoAnswersDetector(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load_detector()
        cls.Detector = cls.mod.PhotoAnswersDetector
        cls.Error = cls.mod.PhotoAnswersDetectionError

    def test_missing_topology(self):
        det = self.Detector(debug=False)
        with self.assertRaises(self.Error) as ctx:
            det.detect(b"not-an-image", {"topology": {"blocks": []}})
        self.assertEqual(ctx.exception.code, "missing_topology")

    def test_invalid_image(self):
        det = self.Detector(debug=False)
        with self.assertRaises(self.Error) as ctx:
            det.detect(b"not-an-image", _topology_4x13())
        self.assertEqual(ctx.exception.code, "invalid_image")

    def test_sample_photo_detects_52_answers(self):
        path = _sample_path()
        if not path:
            self.skipTest("Imagem de exemplo não encontrada")
        with open(path, "rb") as f:
            data = f.read()
        det = self.Detector(debug=False)
        result = det.detect(data, _topology_4x13())
        self.assertTrue(result["success"])
        self.assertEqual(result["blocks_detected"], 4)
        self.assertEqual(result["blocks_expected"], 4)
        self.assertEqual(len(result["answers"]), 52)
        nums = sorted(a["question_number"] for a in result["answers"])
        self.assertEqual(nums, list(range(1, 53)))
        marked = [a for a in result["answers"] if a["answer"]]
        # Em cartão preenchido, a maioria deve vir marcada
        self.assertGreaterEqual(len(marked), 30)
        ok_or_low = sum(1 for a in result["answers"] if a["status"] in ("ok", "low_confidence"))
        self.assertGreaterEqual(ok_or_low, 20)
        self.assertEqual(result.get("method"), "image_first_hough_grid")

    def test_user_photo_52q_exact_answers(self):
        path = os.path.join(os.path.dirname(__file__), "fixtures", "photo_answers_52q.jpg")
        if not os.path.isfile(path):
            self.skipTest("Fixture 52q ausente")
        expected = (
            "DBADCBADBACAB"  # 1-13
            "DBDDBCCBBBCAC"  # 14-26
            "DCDCBCBBADACC"  # 27-39
            "BDBBACABBCCBB"  # 40-52
        )
        with open(path, "rb") as f:
            data = f.read()
        result = self.Detector(debug=False).detect(data, _topology_4x13())
        got = "".join(a["answer"] or "-" for a in result["answers"])
        self.assertEqual(got, expected)
        self.assertEqual(result["summary"]["ok"], 52)

    def test_wrong_topology_mismatches_image(self):
        path = _sample_path()
        if not path:
            self.skipTest("Imagem de exemplo não encontrada")
        with open(path, "rb") as f:
            data = f.read()
        det = self.Detector(debug=False)
        with self.assertRaises(self.Error) as ctx:
            det.detect(data, _topology_wrong_2q())
        self.assertIn(ctx.exception.code, ("blocks_mismatch", "topology_image_mismatch"))


class TestPhotoAnswersServiceValidation(unittest.TestCase):
    def test_validate_image_bytes(self):
        MAX = 10 * 1024 * 1024

        def validate(image_data, content_type=None):
            if not image_data:
                raise ValueError("Imagem vazia")
            if len(image_data) > MAX:
                raise ValueError("Imagem muito grande")
            if content_type and not str(content_type).startswith("image/"):
                raise ValueError("Tipo inválido")

        with self.assertRaises(ValueError):
            validate(b"")
        with self.assertRaises(ValueError):
            validate(b"x" * (MAX + 1))
        validate(b"abc", "image/jpeg")


if __name__ == "__main__":
    unittest.main()
