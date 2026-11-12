# -*- coding: utf-8 -*-
"""
Propõe gabarito de marcação com geometria corrigida (só para anotação).
Gera overlays legíveis com a letra proposta em cada questão.
"""
import json
import os

import cv2
import numpy as np

from _load_omr import ROOT, default_topology, load_omr_class

OMR = load_omr_class()


def synth_ring(radius=25, thickness=2):
    s = radius * 2 + 10
    tmpl = np.zeros((s, s), np.float32)
    c = s // 2
    cv2.circle(tmpl, (c, c), radius, 255, thickness)
    return tmpl


def disk_mean_dark(gray_u8, cx, cy, r, ratio=0.55):
    """Quanto mais escuro o disco interno, maior o score (0..255)."""
    h, w = gray_u8.shape
    rr = max(2, int(round(r * ratio)))
    yy, xx = np.ogrid[:h, :w]
    m = (xx - cx) ** 2 + (yy - cy) ** 2 <= rr * rr
    vals = gray_u8[m]
    if vals.size == 0:
        return 0.0
    return float(255.0 - np.mean(vals))


def refine_block(gray, bubbles, search=45):
    tmpl = synth_ring()
    th, tw = tmpl.shape[:2]
    inv = 255.0 - gray.astype(np.float32)
    hits = []
    for b in bubbles:
        cx, cy = int(b["cx"]), int(b["cy"])
        x0 = max(0, cx - search - tw // 2)
        y0 = max(0, cy - search - th // 2)
        x1 = min(inv.shape[1], cx + search + tw // 2)
        y1 = min(inv.shape[0], cy + search + th // 2)
        win = inv[y0:y1, x0:x1]
        if win.shape[0] < th or win.shape[1] < tw:
            hits.append({**b, "fx": cx, "fy": cy, "match": 0.0})
            continue
        res = cv2.matchTemplate(win, tmpl, cv2.TM_CCOEFF_NORMED)
        _, maxv, _, maxloc = cv2.minMaxLoc(res)
        fx = x0 + maxloc[0] + tw // 2
        fy = y0 + maxloc[1] + th // 2
        hits.append({**b, "fx": int(fx), "fy": int(fy), "match": float(maxv)})
    return hits


def fit_ab(idxs, vals):
    if len(idxs) < 3:
        return None, None, 1e9
    A = np.vstack([np.ones(len(idxs)), np.asarray(idxs, float)]).T
    coef, *_ = np.linalg.lstsq(A, np.asarray(vals, float), rcond=None)
    pred = A @ coef
    resid = float(np.median(np.abs(np.asarray(vals, float) - pred)))
    return float(coef[0]), float(coef[1]), resid


def main():
    outdir = os.path.join(os.path.dirname(__file__), "_baseline_debug", "gt_propose")
    os.makedirs(outdir, exist_ok=True)
    topo = default_topology()
    base = os.path.join(ROOT, "avaliacoes_marcadas")
    gt_all = {}

    for fname in sorted(os.listdir(base)):
        if not fname.lower().endswith(".jpg"):
            continue
        omr = OMR(debug=False)
        img = cv2.imread(os.path.join(base, fname))
        a4 = omr._normalize_to_a4(
            img, omr._detect_a4_anchors(img, omr._preprocess_image(img)["edges"])
        )
        blocks = omr._detect_blocks_via_fiducials(a4, 4, topo["topology"]["blocks"])
        proposal = {}
        overlays = []

        for idx, block in enumerate(blocks):
            x, y, w, h = block["x"], block["y"], block["w"], block["h"]
            roi = a4[y : y + h, x : x + w]
            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            cfg = topo["topology"]["blocks"][idx]
            grid = omr._map_topology_to_grid(roi, cfg)
            bubbles = omr._calculate_bubble_centers(grid)
            hits = refine_block(gray, bubbles, search=45)

            row_of, col_of = {}, {}
            for qmap in grid["questions"]:
                for alt in qmap["alternatives"]:
                    row_of[(qmap["q_num"], alt["letter"])] = qmap["row_idx"]
                    col_of[(qmap["q_num"], alt["letter"])] = alt["col_idx"]

            high = [h for h in hits if h["match"] >= 0.22]
            by_row, by_col = {}, {}
            for h in high:
                key = (h["q_num"], h["alternative"])
                by_row.setdefault(row_of[key], []).append(h["fy"])
                by_col.setdefault(col_of[key], []).append(h["fx"])
            ri = sorted(by_row)
            ry = [float(np.median(by_row[i])) for i in ri]
            ci = sorted(by_col)
            cx = [float(np.median(by_col[i])) for i in ci]
            a_y, b_y, res_y = fit_ab(ri, ry)
            a_x, b_x, res_x = fit_ab(ci, cx)

            vis = roi.copy()
            q_scores = {}
            for h in hits:
                key = (h["q_num"], h["alternative"])
                if a_y is not None and res_y < 6:
                    fy = int(round(a_y + b_y * row_of[key]))
                else:
                    fy = h["fy"] if h["match"] >= 0.22 else h["cy"]
                if a_x is not None and res_x < 6:
                    fx = int(round(a_x + b_x * col_of[key]))
                else:
                    fx = h["fx"] if h["match"] >= 0.22 else h["cx"]
                sc = disk_mean_dark(gray, fx, fy, h["r"], 0.55)
                q_scores.setdefault(h["q_num"], []).append(
                    {"letter": h["alternative"], "score": sc, "fx": fx, "fy": fy, "r": h["r"]}
                )
                cv2.circle(vis, (fx, fy), h["r"], (0, 200, 255), 1)

            for q_num, scored in q_scores.items():
                ordered = sorted(scored, key=lambda z: z["score"], reverse=True)
                top, second = ordered[0], ordered[1]
                # limiares relativos no cartão binário
                if top["score"] < 40:
                    dec = None
                elif second["score"] > 70 and (top["score"] - second["score"]) < 18:
                    dec = "INVALID"
                elif (top["score"] - second["score"]) >= 15 and top["score"] >= 55:
                    dec = top["letter"]
                elif top["score"] >= 80 and (top["score"] - second["score"]) >= 10:
                    dec = top["letter"]
                else:
                    dec = None
                proposal[q_num] = dec
                # desenhar decisão
                for s in scored:
                    color = (180, 180, 180)
                    if dec == s["letter"]:
                        color = (0, 220, 0)
                    elif dec == "INVALID" and s["letter"] in (
                        top["letter"],
                        second["letter"],
                    ):
                        color = (0, 140, 255)
                    cv2.circle(vis, (s["fx"], s["fy"]), s["r"], color, 2)
                label = "?" if dec is None else dec
                cy0 = int(np.median([s["fy"] for s in scored]))
                cv2.putText(
                    vis,
                    f"{q_num}:{label}",
                    (8, cy0 + 5),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.45,
                    (0, 0, 255),
                    1,
                )

            overlays.append(vis)
            print(
                fname,
                "B",
                cfg["block_id"],
                "row",
                None if b_y is None else round(b_y, 2),
                "sp",
                None if b_x is None else round(b_x, 2),
                "res",
                None if res_y is None else round(res_y, 2),
                None if res_x is None else round(res_x, 2),
            )

        H = max(v.shape[0] for v in overlays)
        W = sum(v.shape[1] for v in overlays) + 30
        mont = np.full((H, W, 3), 255, np.uint8)
        xx = 0
        for v in overlays:
            mont[: v.shape[0], xx : xx + v.shape[1]] = v
            xx += v.shape[1] + 8
        scale = min(1.0, 1800 / mont.shape[1])
        mont2 = cv2.resize(mont, (0, 0), fx=scale, fy=scale)
        stem = os.path.splitext(fname)[0]
        cv2.imwrite(os.path.join(outdir, f"{stem}_gtprop.jpg"), mont2)
        gt_all[fname] = {str(k): v for k, v in sorted(proposal.items())}
        n_m = sum(1 for v in proposal.values() if v and v != "INVALID")
        n_i = sum(1 for v in proposal.values() if v == "INVALID")
        print(fname, "marked", n_m, "invalid", n_i)

    with open(os.path.join(outdir, "gt_proposed.json"), "w", encoding="utf-8") as f:
        json.dump(gt_all, f, indent=2, ensure_ascii=False)
    print("saved", outdir)


if __name__ == "__main__":
    main()
