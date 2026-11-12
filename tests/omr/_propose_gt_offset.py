# -*- coding: utf-8 -*-
"""
Propõe GT: 1) Hough para estimar (dx,dy,row_h,spacing) por bloco;
2) aplica modelo; 3) score de escuridão no disco interno.
"""
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
    # binário: cobertura de pixels escuros também
    mean_dark = float(255.0 - np.mean(vals))
    frac = float(np.mean(vals < 128))
    return mean_dark * 0.5 + frac * 255.0 * 0.5


def main():
    outdir = os.path.join(os.path.dirname(__file__), "_baseline_debug", "gt_final")
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
            bx, by, bw, bh = block["x"], block["y"], block["w"], block["h"]
            roi = a4[by : by + bh, bx : bx + bw]
            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            cfg = topo["topology"]["blocks"][idx]
            grid = omr._map_topology_to_grid(roi, cfg)
            bubbles = omr._calculate_bubble_centers(grid)
            circles = find_circles(gray)

            # Para cada bolha nominal, círculo Hough mais próximo (até 80px)
            pairs = []
            used = set()
            for b in bubbles:
                best_i, best_d = None, 1e9
                for i, (cx, cy, r) in enumerate(circles):
                    if i in used:
                        continue
                    d = (cx - b["cx"]) ** 2 + (cy - b["cy"]) ** 2
                    if d < best_d:
                        best_d, best_i = d, i
                if best_i is not None and best_d <= 80 ** 2:
                    used.add(best_i)
                    cx, cy, r = circles[best_i]
                    pairs.append(
                        (
                            b,
                            cx,
                            cy,
                            r,
                            cx - b["cx"],
                            cy - b["cy"],
                            grid["questions"],
                        )
                    )

            # offsets robustos
            if len(pairs) >= 12:
                dx = float(np.median([p[4] for p in pairs]))
                dy = float(np.median([p[5] for p in pairs]))
            else:
                dx, dy = 0.0, 0.0

            # row height a partir de y dos círculos agrupados por row_idx
            row_of, col_of = {}, {}
            for qmap in grid["questions"]:
                for alt in qmap["alternatives"]:
                    row_of[(qmap["q_num"], alt["letter"])] = qmap["row_idx"]
                    col_of[(qmap["q_num"], alt["letter"])] = alt["col_idx"]

            by_row, by_col = {}, {}
            for b, cx, cy, r, ddx, ddy, _ in pairs:
                key = (b["q_num"], b["alternative"])
                by_row.setdefault(row_of[key], []).append(cy)
                by_col.setdefault(col_of[key], []).append(cx)

            if len(by_row) >= 3:
                ri = sorted(by_row)
                ry = [float(np.median(by_row[i])) for i in ri]
                A = np.vstack([np.ones(len(ri)), np.asarray(ri, float)]).T
                coef, *_ = np.linalg.lstsq(A, np.asarray(ry), rcond=None)
                a_y, b_y = float(coef[0]), float(coef[1])
            else:
                a_y = OMR.BLOCK_OFFSET_Y + OMR.ROW_HEIGHT_PX / 2 + dy
                b_y = OMR.ROW_HEIGHT_PX

            if len(by_col) >= 2:
                ci = sorted(by_col)
                cxv = [float(np.median(by_col[i])) for i in ci]
                A = np.vstack([np.ones(len(ci)), np.asarray(ci, float)]).T
                coef, *_ = np.linalg.lstsq(A, np.asarray(cxv), rcond=None)
                a_x, b_x = float(coef[0]), float(coef[1])
            else:
                a_x = OMR.BLOCK_OFFSET_X + OMR.BUBBLE_WIDTH_PX / 2 + dx
                b_x = float(OMR.BUBBLE_SPACING_PX)

            # se pitch absurdo, cai no offset simples
            if not (45 <= b_y <= 62) or not (45 <= b_x <= 80):
                a_y = OMR.BLOCK_OFFSET_Y + OMR.ROW_HEIGHT_PX / 2 + dy
                b_y = OMR.ROW_HEIGHT_PX
                a_x = OMR.BLOCK_OFFSET_X + OMR.BUBBLE_WIDTH_PX / 2 + dx
                b_x = float(OMR.BUBBLE_SPACING_PX)

            vis = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
            q_scores = {}
            for b in bubbles:
                key = (b["q_num"], b["alternative"])
                fx = int(round(a_x + b_x * col_of[key]))
                fy = int(round(a_y + b_y * row_of[key]))
                sc = dark_score(gray, fx, fy, b["r"], 0.55)
                q_scores.setdefault(b["q_num"], []).append(
                    {"letter": b["alternative"], "score": sc, "fx": fx, "fy": fy}
                )
                cv2.circle(vis, (fx, fy), b["r"], (255, 180, 0), 1)

            all_sc = [s["score"] for qs in q_scores.values() for s in qs]
            # top scores por questão (candidatos a marca)
            tops = []
            for scored in q_scores.values():
                tops.append(max(s["score"] for s in scored))
            tops_sorted = sorted(tops, reverse=True)
            # nível marca ≈ mediana dos top 40% ; vazio ≈ mediana dos bottom 50%
            k = max(3, int(0.4 * len(tops_sorted)))
            mark_level = float(np.median(tops_sorted[:k]))
            empty_level = float(np.median(sorted(all_sc)[: max(3, len(all_sc) // 2)]))
            thr = empty_level + 0.40 * max(mark_level - empty_level, 1.0)
            thr = max(thr, empty_level + 25)

            for q_num, scored in q_scores.items():
                ordered = sorted(scored, key=lambda z: z["score"], reverse=True)
                top, second = ordered[0], ordered[1]
                if top["score"] < thr:
                    dec = None
                elif second["score"] >= thr and (top["score"] - second["score"]) < 20:
                    dec = "INVALID"
                else:
                    dec = top["letter"]
                proposal[q_num] = dec
                for s in scored:
                    color = (160, 160, 160)
                    if dec == s["letter"]:
                        color = (0, 220, 0)
                    elif dec == "INVALID" and s["letter"] in (
                        top["letter"],
                        second["letter"],
                    ):
                        color = (0, 140, 255)
                    cv2.circle(vis, (s["fx"], s["fy"]), 22, color, 2)
                cy0 = int(np.median([s["fy"] for s in scored]))
                lab = "?" if dec is None else (dec if dec != "INVALID" else "X")
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
            print(
                fname,
                f"B{cfg['block_id']}",
                f"dx={dx:.1f}",
                f"dy={dy:.1f}",
                f"row={b_y:.2f}",
                f"sp={b_x:.2f}",
                f"thr={thr:.1f}",
                f"pairs={len(pairs)}",
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
        cv2.imwrite(os.path.join(outdir, f"{stem}_gt.jpg"), mont2)
        gt_all[fname] = {str(k): v for k, v in sorted(proposal.items())}
        n_m = sum(1 for v in proposal.values() if v and v != "INVALID")
        n_i = sum(1 for v in proposal.values() if v == "INVALID")
        print(" =>", fname, "marked", n_m, "inv", n_i)

    path = os.path.join(outdir, "gt_proposed.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(gt_all, f, indent=2, ensure_ascii=False)
    print("saved", path)


if __name__ == "__main__":
    main()
