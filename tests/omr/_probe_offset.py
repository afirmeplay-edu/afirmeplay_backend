# -*- coding: utf-8 -*-
"""Diagnóstico: offset real bolha impressa vs centro nominal (busca ampla)."""
import importlib.util
import json
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


def synth_ring(radius=25, thickness=2):
    s = radius * 2 + 10
    tmpl = np.zeros((s, s), np.uint8)
    c = s // 2
    cv2.circle(tmpl, (c, c), radius, 255, thickness)
    return tmpl.astype(np.float32)


def main():
    outdir = os.path.join(os.path.dirname(__file__), "_baseline_debug")
    topo = default_topology()
    base = os.path.join(ROOT, "avaliacoes_marcadas")
    tmpl = synth_ring(25, 2)
    th, tw = tmpl.shape
    report = {}

    for fname in sorted(os.listdir(base))[:4]:
        omr = OMR(debug=False)
        img = cv2.imread(os.path.join(base, fname))
        a4 = omr._normalize_to_a4(
            img, omr._detect_a4_anchors(img, omr._preprocess_image(img)["edges"])
        )
        blocks = omr._detect_blocks_via_fiducials(a4, 4, topo["topology"]["blocks"])
        card = {"blocks": []}
        overlay = a4.copy()
        for idx, block in enumerate(blocks):
            x, y, w, h = block["x"], block["y"], block["w"], block["h"]
            roi = a4[y : y + h, x : x + w]
            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY).astype(np.float32)
            inv = 255.0 - gray
            cfg = topo["topology"]["blocks"][idx]
            grid = omr._map_topology_to_grid(roi, cfg)
            bubbles = omr._calculate_bubble_centers(grid)

            # busca ampla ±40 para diagnóstico
            search = 40
            dxs, dys, scores = [], [], []
            row_ys = {}
            for b in bubbles:
                cx, cy = int(b["cx"]), int(b["cy"])
                x0 = max(0, cx - search - tw // 2)
                y0 = max(0, cy - search - th // 2)
                x1 = min(inv.shape[1], cx + search + tw // 2)
                y1 = min(inv.shape[0], cy + search + th // 2)
                win = inv[y0:y1, x0:x1]
                if win.shape[0] < th or win.shape[1] < tw:
                    continue
                res = cv2.matchTemplate(win, tmpl, cv2.TM_CCOEFF_NORMED)
                _, maxv, _, maxloc = cv2.minMaxLoc(res)
                fx = x0 + maxloc[0] + tw // 2
                fy = y0 + maxloc[1] + th // 2
                dx, dy = fx - cx, fy - cy
                if maxv >= 0.25:
                    dxs.append(dx)
                    dys.append(dy)
                    scores.append(maxv)
                    row_ys.setdefault(b["q_num"], []).append(fy)
                    cv2.circle(overlay, (x + cx, y + cy), 4, (255, 0, 0), 1)
                    cv2.circle(overlay, (x + fx, y + fy), 4, (0, 255, 0), 1)
                    cv2.line(
                        overlay, (x + cx, y + cy), (x + fx, y + fy), (0, 255, 255), 1
                    )

            # estimar row height a partir de y mediano por questão
            qnums = sorted(row_ys)
            ys = [float(np.median(row_ys[q])) for q in qnums]
            row_diffs = np.diff(ys) if len(ys) > 1 else []
            card["blocks"].append(
                {
                    "block_id": cfg["block_id"],
                    "n_hits": len(dxs),
                    "median_dx": float(np.median(dxs)) if dxs else None,
                    "median_dy": float(np.median(dys)) if dys else None,
                    "p90_abs_dx": float(np.percentile(np.abs(dxs), 90)) if dxs else None,
                    "p90_abs_dy": float(np.percentile(np.abs(dys), 90)) if dys else None,
                    "mean_match": float(np.mean(scores)) if scores else None,
                    "median_row_pitch": float(np.median(row_diffs))
                    if len(row_diffs)
                    else None,
                    "nominal_row": OMR.ROW_HEIGHT_PX,
                    "anchor": (block.get("anchor_x"), block.get("anchor_y")),
                    "origin": (x, y),
                    "roi": (w, h),
                }
            )
        card_path = os.path.join(
            outdir, f"{os.path.splitext(fname)[0]}_offset_diag.jpg"
        )
        ys = [b["y"] for b in blocks]
        xs = [b["x"] for b in blocks]
        ye = [b["y"] + b["h"] for b in blocks]
        xe = [b["x"] + b["w"] for b in blocks]
        crop = overlay[min(ys) - 20 : max(ye) + 20, min(xs) - 20 : max(xe) + 20]
        cv2.imwrite(card_path, crop)
        report[fname] = card
        print(fname)
        for b in card["blocks"]:
            print(
                " ",
                b["block_id"],
                "hits",
                b["n_hits"],
                "dx",
                b["median_dx"],
                "dy",
                b["median_dy"],
                "row",
                b["median_row_pitch"],
                "match",
                None if b["mean_match"] is None else round(b["mean_match"], 3),
            )

    with open(os.path.join(outdir, "offset_report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print("done")


if __name__ == "__main__":
    main()
