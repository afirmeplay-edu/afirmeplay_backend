# -*- coding: utf-8 -*-
"""Propõe GT via HoughCircles + escuridão no disco (anotação, não produção)."""
import json
import os

import cv2
import numpy as np

from _load_omr import ROOT, default_topology, load_omr_class

OMR = load_omr_class()


def find_circles(gray):
    blur = cv2.GaussianBlur(gray, (5, 5), 1.2)
    circles = cv2.HoughCircles(
        blur,
        cv2.HOUGH_GRADIENT,
        dp=1.2,
        minDist=28,
        param1=80,
        param2=22,
        minRadius=18,
        maxRadius=34,
    )
    if circles is None:
        return []
    return [(int(round(c[0])), int(round(c[1])), int(round(c[2]))) for c in circles[0]]


def dark_score(gray, cx, cy, r, ratio=0.55):
    h, w = gray.shape
    rr = max(2, int(round(r * ratio)))
    yy, xx = np.ogrid[:h, :w]
    m = (xx - cx) ** 2 + (yy - cy) ** 2 <= rr * rr
    vals = gray[m]
    if vals.size == 0:
        return 0.0
    return float(255.0 - np.mean(vals))


def assign_circles_to_grid(circles, bubbles, max_dist=55):
    """Associa cada bolha nominal ao círculo Hough mais próximo."""
    assigned = []
    used = set()
    for b in bubbles:
        best_i, best_d = None, 1e9
        for i, (cx, cy, r) in enumerate(circles):
            if i in used:
                continue
            d = (cx - b["cx"]) ** 2 + (cy - b["cy"]) ** 2
            if d < best_d:
                best_d = d
                best_i = i
        if best_i is not None and best_d <= max_dist ** 2:
            used.add(best_i)
            cx, cy, r = circles[best_i]
            assigned.append({**b, "fx": cx, "fy": cy, "fr": r, "dist": best_d ** 0.5})
        else:
            assigned.append(
                {**b, "fx": b["cx"], "fy": b["cy"], "fr": b["r"], "dist": None}
            )
    return assigned


def fit_ab(idxs, vals):
    if len(idxs) < 3:
        return None, None, 1e9
    A = np.vstack([np.ones(len(idxs)), np.asarray(idxs, float)]).T
    coef, *_ = np.linalg.lstsq(A, np.asarray(vals, float), rcond=None)
    pred = A @ coef
    resid = float(np.median(np.abs(np.asarray(vals, float) - pred)))
    return float(coef[0]), float(coef[1]), resid


def main():
    outdir = os.path.join(os.path.dirname(__file__), "_baseline_debug", "gt_hough")
    os.makedirs(outdir, exist_ok=True)
    topo = default_topology()
    base = os.path.join(ROOT, "avaliacoes_marcadas")
    gt_all = {}
    geom = {}

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
        card_geom = []

        for idx, block in enumerate(blocks):
            x, y, w, h = block["x"], block["y"], block["w"], block["h"]
            roi = a4[y : y + h, x : x + w]
            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            cfg = topo["topology"]["blocks"][idx]
            grid = omr._map_topology_to_grid(roi, cfg)
            bubbles = omr._calculate_bubble_centers(grid)
            circles = find_circles(gray)
            hits = assign_circles_to_grid(circles, bubbles, max_dist=70)

            row_of, col_of = {}, {}
            for qmap in grid["questions"]:
                for alt in qmap["alternatives"]:
                    row_of[(qmap["q_num"], alt["letter"])] = qmap["row_idx"]
                    col_of[(qmap["q_num"], alt["letter"])] = alt["col_idx"]

            good = [h for h in hits if h["dist"] is not None and h["dist"] < 45]
            by_row, by_col = {}, {}
            dxs, dys = [], []
            for h in good:
                key = (h["q_num"], h["alternative"])
                by_row.setdefault(row_of[key], []).append(h["fy"])
                by_col.setdefault(col_of[key], []).append(h["fx"])
                dxs.append(h["fx"] - h["cx"])
                dys.append(h["fy"] - h["cy"])
            ri = sorted(by_row)
            ry = [float(np.median(by_row[i])) for i in ri]
            ci = sorted(by_col)
            cxv = [float(np.median(by_col[i])) for i in ci]
            a_y, b_y, res_y = fit_ab(ri, ry)
            a_x, b_x, res_x = fit_ab(ci, cxv)

            # centros do modelo se resíduo baixo; senão Hough/nominal
            use_model = (
                a_y is not None
                and a_x is not None
                and res_y < 4.0
                and res_x < 4.0
                and len(good) >= 20
            )

            vis = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
            for cx, cy, r in circles:
                cv2.circle(vis, (cx, cy), r, (255, 128, 0), 1)

            q_scores = {}
            for h in hits:
                key = (h["q_num"], h["alternative"])
                if use_model:
                    fx = int(round(a_x + b_x * col_of[key]))
                    fy = int(round(a_y + b_y * row_of[key]))
                    fr = int(np.median([g["fr"] for g in good]))
                else:
                    fx, fy, fr = h["fx"], h["fy"], h["fr"]
                sc = dark_score(gray, fx, fy, fr, 0.55)
                q_scores.setdefault(h["q_num"], []).append(
                    {"letter": h["alternative"], "score": sc, "fx": fx, "fy": fy, "r": fr}
                )

            # limiar adaptativo do bloco: mediana dos scores
            all_sc = [s["score"] for qs in q_scores.values() for s in qs]
            med = float(np.median(all_sc)) if all_sc else 0
            # marcas: tipicamente bem acima da mediana do anel
            for q_num, scored in q_scores.items():
                ordered = sorted(scored, key=lambda z: z["score"], reverse=True)
                top, second = ordered[0], ordered[1]
                # em cartão binário, vazio ~ anel (~30-50), marcado ~100+
                if top["score"] < max(55.0, med + 25):
                    dec = None
                elif second["score"] >= max(70.0, med + 35) and (
                    top["score"] - second["score"]
                ) < 20:
                    dec = "INVALID"
                elif top["score"] - second["score"] >= 18:
                    dec = top["letter"]
                else:
                    dec = None
                proposal[q_num] = dec
                for s in scored:
                    color = (160, 160, 160)
                    if dec == s["letter"]:
                        color = (0, 220, 0)
                    elif dec == "INVALID" and s["score"] >= second["score"] - 1:
                        color = (0, 140, 255)
                    cv2.circle(vis, (s["fx"], s["fy"]), s["r"], color, 2)
                    cv2.putText(
                        vis,
                        f"{s['score']:.0f}",
                        (s["fx"] - 10, s["fy"] + 4),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.3,
                        color,
                        1,
                    )
                cy0 = int(np.median([s["fy"] for s in scored]))
                lab = "?" if dec is None else str(dec)[0]
                cv2.putText(
                    vis,
                    f"{q_num}:{lab}",
                    (4, cy0 + 4),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.4,
                    (0, 0, 255),
                    1,
                )

            overlays.append(vis)
            card_geom.append(
                {
                    "block_id": cfg["block_id"],
                    "n_circles": len(circles),
                    "n_assigned": len(good),
                    "median_dx": float(np.median(dxs)) if dxs else None,
                    "median_dy": float(np.median(dys)) if dys else None,
                    "row_h": b_y,
                    "spacing": b_x,
                    "res_y": res_y if a_y is not None else None,
                    "res_x": res_x if a_x is not None else None,
                    "use_model": use_model,
                    "score_median": med,
                }
            )
            print(
                fname,
                "B",
                cfg["block_id"],
                "circ",
                len(circles),
                "ok",
                len(good),
                "dx",
                None if not dxs else round(float(np.median(dxs)), 1),
                "dy",
                None if not dys else round(float(np.median(dys)), 1),
                "row",
                None if b_y is None else round(b_y, 2),
                "model",
                use_model,
            )

        H = max(v.shape[0] for v in overlays)
        W = sum(v.shape[1] for v in overlays) + 30
        mont = np.full((H, W, 3), 255, np.uint8)
        xx = 0
        for v in overlays:
            mont[: v.shape[0], xx : xx + v.shape[1]] = v
            xx += v.shape[1] + 8
        scale = min(1.0, 2000 / mont.shape[1])
        mont2 = cv2.resize(mont, (0, 0), fx=scale, fy=scale)
        stem = os.path.splitext(fname)[0]
        cv2.imwrite(os.path.join(outdir, f"{stem}_hough.jpg"), mont2)
        gt_all[fname] = {str(k): v for k, v in sorted(proposal.items())}
        geom[fname] = card_geom
        n_m = sum(1 for v in proposal.values() if v and v != "INVALID")
        print(" =>", fname, "marked", n_m)

    with open(os.path.join(outdir, "gt_proposed.json"), "w", encoding="utf-8") as f:
        json.dump(gt_all, f, indent=2, ensure_ascii=False)
    with open(os.path.join(outdir, "geom.json"), "w", encoding="utf-8") as f:
        json.dump(geom, f, indent=2)
    print("saved", outdir)


if __name__ == "__main__":
    main()
