# -*- coding: utf-8 -*-
"""Gera crops hi-res por bloco para anotação manual de gabarito."""
import importlib.util
import os
import sys
import types

import cv2
import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

app_mod = types.ModuleType("app")
app_mod.__path__ = [os.path.join(ROOT, "app")]
app_mod.db = types.SimpleNamespace()
sys.modules["app"] = app_mod
for name in ["app.services", "app.services.cartao_resposta"]:
    m = types.ModuleType(name)
    m.__path__ = [os.path.join(ROOT, *name.split("."))]
    sys.modules[name] = m

path = os.path.join(ROOT, "app", "services", "cartao_resposta", "correction_new_grid.py")
spec = importlib.util.spec_from_file_location(
    "app.services.cartao_resposta.correction_new_grid", path
)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)
OMR = mod.AnswerSheetCorrectionNewGrid


def default_topology():
    blocks = []
    q = 1
    for b in range(1, 5):
        qs = [{"q": q + i, "alternatives": ["A", "B", "C", "D"]} for i in range(11)]
        q += 11
        blocks.append({"block_id": b, "questions": qs})
    return {"topology": {"blocks": blocks}}


def main():
    outdir = os.path.join(os.path.dirname(__file__), "_baseline_debug", "clean_hi")
    os.makedirs(outdir, exist_ok=True)
    topo = default_topology()
    base = os.path.join(ROOT, "avaliacoes_marcadas")
    for fname in sorted(os.listdir(base)):
        if not fname.lower().endswith(".jpg"):
            continue
        omr = OMR(debug=False)
        img = cv2.imread(os.path.join(base, fname))
        anchors = omr._detect_a4_anchors(img, omr._preprocess_image(img)["edges"])
        a4 = omr._normalize_to_a4(img, anchors)
        blocks = omr._detect_blocks_via_fiducials(a4, 4, topo["topology"]["blocks"])
        stem = os.path.splitext(fname)[0]
        for idx, b in enumerate(blocks):
            roi = a4[b["y"] : b["y"] + b["h"], b["x"] : b["x"] + b["w"]].copy()
            cv2.imwrite(os.path.join(outdir, f"{stem}_b{idx + 1}.jpg"), roi)
        rois = [
            a4[b["y"] : b["y"] + b["h"], b["x"] : b["x"] + b["w"]].copy()
            for b in blocks
        ]
        H = max(r.shape[0] for r in rois)
        W = sum(r.shape[1] for r in rois) + 40
        mont = np.full((H, W, 3), 255, np.uint8)
        x = 0
        for r in rois:
            mont[: r.shape[0], x : x + r.shape[1]] = r
            x += r.shape[1] + 10
        scale = 1600.0 / mont.shape[1]
        mont2 = cv2.resize(mont, (0, 0), fx=scale, fy=scale)
        cv2.imwrite(os.path.join(outdir, f"{stem}_mont.jpg"), mont2)
        print(fname, "ok")


if __name__ == "__main__":
    main()
