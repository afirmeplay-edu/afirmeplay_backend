# -*- coding: utf-8 -*-
"""Testes sintéticos (A–D e A–E) do detector de foto, com medição de acurácia."""

from __future__ import annotations

import os
import random
import sys
import unittest

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from test_photo_answers_detector import _load_detector  # noqa: E402

LETTERS = "ABCDE"


def build_topology(n_blocks, rows, n_alts):
    blocks, q = [], 1
    for b in range(1, n_blocks + 1):
        qs = [{"q": q + i, "alternatives": list(LETTERS[:n_alts])} for i in range(rows)]
        q += rows
        blocks.append({"block_id": b, "subject_name": f"Disc {b}", "questions": qs})
    return {"num_blocks": n_blocks, "topology": {"blocks": blocks}}


def render_card(n_blocks, rows, n_alts, seed=0, double_every=0, blank_every=0):
    """Gera cartão sintético; retorna (imagem BGR, string de respostas esperadas)."""
    rnd = random.Random(seed)
    W, H = 1500, 140 + rows * 62
    img = np.full((H, W, 3), 245, np.uint8)
    for (x, y) in [(30, 30), (W - 70, 30), (W - 70, H - 70), (30, H - 70)]:
        cv2.rectangle(img, (x, y), (x + 40, y + 40), (0, 0, 0), -1)

    r, pitch_x, pitch_y = 16, 50, 62
    block_w = (n_alts - 1) * pitch_x
    gap = (W - 200 - n_blocks * block_w) / max(1, n_blocks - 1) if n_blocks > 1 else 0
    expected = []
    for b in range(n_blocks):
        x0 = 100 + b * (block_w + gap)
        for i in range(rows):
            y = 100 + i * pitch_y
            n_q = b * rows + i
            cv2.putText(img, str(n_q + 1), (int(x0 - 60), y + 6), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1)
            choice = rnd.randrange(n_alts)
            blank = blank_every and n_q % blank_every == 0
            for a in range(n_alts):
                cx = int(x0 + a * pitch_x)
                cv2.circle(img, (cx, y), r, (0, 0, 0), 2)
                cv2.putText(img, LETTERS[a], (cx - 6, y + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (90, 90, 90), 1)
                if a == choice and not blank:
                    cv2.circle(img, (cx, y), r - 1, (20, 20, 20), -1)
            expected.append("-" if blank else LETTERS[choice])
    return img, "".join(expected)


def degrade(img, kind, seed=0):
    rnd = np.random.RandomState(seed)
    h, w = img.shape[:2]
    out = img.copy()
    if kind == "shadow":
        grad = np.tile(np.linspace(0.55, 1.0, w, dtype=np.float32), (h, 1))
        out = (out.astype(np.float32) * grad[..., None]).astype(np.uint8)
    elif kind == "noise_blur":
        out = cv2.GaussianBlur(out, (5, 5), 0)
        out = np.clip(out.astype(np.int16) + rnd.normal(0, 8, out.shape), 0, 255).astype(np.uint8)
    elif kind == "perspective":
        src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
        dst = np.float32([[25, 15], [w - 10, 40], [w - 30, h - 20], [10, h - 35]])
        m = cv2.getPerspectiveTransform(src, dst)
        out = cv2.warpPerspective(out, m, (w, h), borderValue=(235, 235, 235))
    return out


def _encode(img):
    ok, buf = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
    assert ok
    return buf.tobytes()


class TestSynthetic(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _load_detector()
        cls.det = cls.mod.PhotoAnswersDetector(debug=False)

    def _run(self, n_blocks, rows, n_alts, kind=None, seed=1, **kw):
        img, expected = render_card(n_blocks, rows, n_alts, seed=seed, **kw)
        if kind:
            img = degrade(img, kind, seed)
        res = self.det.detect(_encode(img), build_topology(n_blocks, rows, n_alts))
        got = "".join(a["answer"] or "-" for a in res["answers"])
        acc = sum(1 for g, e in zip(got, expected) if g == e) / float(len(expected))
        return acc, got, expected, res

    def test_accuracy_matrix(self):
        configs = [(4, 13, 4), (4, 13, 5), (3, 10, 4), (2, 20, 5), (4, 8, 4)]
        kinds = [None, "shadow", "noise_blur", "perspective"]
        worst = 1.0
        report = []
        for cfg in configs:
            for kind in kinds:
                try:
                    acc, _got, _exp, _res = self._run(*cfg, kind=kind)
                except self.mod.PhotoAnswersDetectionError as exc:
                    print(f"  {cfg} {kind}: ERRO {exc.code}")
                    acc = 0.0
                report.append((cfg, kind, acc))
                worst = min(worst, acc)
        for cfg, kind, acc in report:
            print(f"  {cfg} {kind or 'clean':<12} acc={acc:.3f}")
        mean = sum(a for _, _, a in report) / len(report)
        print(f"  média={mean:.3f} pior={worst:.3f}")
        self.assertGreaterEqual(mean, 0.97)
        self.assertGreaterEqual(worst, 0.90)

    def test_blank_rows_are_blank(self):
        acc, got, exp, _ = self._run(4, 13, 4, blank_every=7)
        self.assertGreaterEqual(acc, 0.95, f"{got}\n{exp}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
