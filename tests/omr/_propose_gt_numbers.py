# -*- coding: utf-8 -*-
"""
GT por geometria dos números impressos + busca horizontal da marca na linha.
Mais estável que Hough/matchTemplate de anel em scan binário.
"""
import json
import os
import re

import cv2
import numpy as np

from _load_omr import ROOT, default_topology, load_omr_class

OMR = load_omr_class()

# tenta OCR leve via pytesseract se disponível; senão, projection + template digits
try:
    import pytesseract

    HAS_TESS = True
except Exception:
    HAS_TESS = False


def find_row_ys_by_projection(gray, num_rows=11):
    """
    Estima Y das linhas pela projeção horizontal na faixa dos números (esquerda).
    """
    h, w = gray.shape
    # números ficam ~ à esquerda das bolhas; pegar faixa 0..min(120, w//3)
    x1 = min(120, max(40, w // 4))
    strip = gray[:, :x1]
    # tinta = pixels escuros
    ink = (strip < 140).astype(np.float32)
    proj = ink.sum(axis=1)
    # suavizar
    k = 9
    kernel = np.ones(k) / k
    sm = np.convolve(proj, kernel, mode="same")
    # picos
    peaks = []
    for y in range(2, h - 2):
        if sm[y] >= sm[y - 1] and sm[y] >= sm[y + 1] and sm[y] > 3.0:
            peaks.append((y, sm[y]))
    peaks.sort(key=lambda t: -t[1])
    # NMS
    chosen = []
    for y, s in peaks:
        if all(abs(y - cy) > 25 for cy in chosen):
            chosen.append(y)
        if len(chosen) >= num_rows + 3:
            break
    chosen = sorted(chosen)
    # se sobrou, pegar as num_rows mais centrais / com maior score
    if len(chosen) > num_rows:
        # preferir sequência com pitch ~53
        best = None
        best_score = 1e9
        for i in range(len(chosen) - num_rows + 1):
            seq = chosen[i : i + num_rows]
            diffs = np.diff(seq)
            score = float(np.mean(np.abs(diffs - 53)))
            if score < best_score:
                best_score = score
                best = seq
        chosen = best
    return chosen


def score_row_alternatives(gray, cy, x0_bubble, spacing, r=25, n_alts=4):
    """Scores A..D na linha cy; centros em x0 + i*spacing."""
    h, w = gray.shape
    scored = []
    for i, let in enumerate(["A", "B", "C", "D"][:n_alts]):
        cx = int(round(x0_bubble + i * spacing))
        rr = max(2, int(round(r * 0.55)))
        x_a = max(0, cx - rr)
        x_b = min(w, cx + rr + 1)
        y_a = max(0, cy - rr)
        y_b = min(h, cy + rr + 1)
        patch = gray[y_a:y_b, x_a:x_b]
        if patch.size == 0:
            scored.append((let, 0.0, cx))
            continue
        yy, xx = np.ogrid[: patch.shape[0], : patch.shape[1]]
        mask = (xx - (cx - x_a)) ** 2 + (yy - (cy - y_a)) ** 2 <= rr * rr
        vals = patch[mask]
        if vals.size == 0:
            scored.append((let, 0.0, cx))
            continue
        mean_dark = float(255.0 - np.mean(vals))
        frac = float(np.mean(vals < 120))
        sc = 0.45 * mean_dark + 0.55 * frac * 255.0
        scored.append((let, sc, cx))
    return scored


def estimate_x0_and_spacing(gray, row_ys, r=25):
    """
    Na mediana das linhas, procura 4 círculos/picos de anel na região das bolhas.
    """
    h, w = gray.shape
    # faixa das bolhas: depois dos números
    x_left = min(130, w // 4)
    # soma vertical de bordas numa faixa em torno das linhas
    acc = np.zeros(w, np.float32)
    edges = cv2.Canny(gray, 40, 120)
    for cy in row_ys:
        y0 = max(0, cy - 20)
        y1 = min(h, cy + 21)
        acc += edges[y0:y1, :].sum(axis=0)
    # suavizar
    acc_s = np.convolve(acc, np.ones(7) / 7, mode="same")
    # picos na região de bolhas
    peaks = []
    for x in range(x_left + 5, w - 5):
        if acc_s[x] >= acc_s[x - 1] and acc_s[x] >= acc_s[x + 1] and acc_s[x] > 20:
            peaks.append(x)
    # NMS spacing ~30
    kept = []
    for x in peaks:
        if not kept or abs(x - kept[-1]) > 28:
            kept.append(x)
    # agrupar em ~4 colunas: escolher sequência com spacing ~61
    best = None
    best_err = 1e9
    for i in range(len(kept)):
        for j in range(i + 3, min(i + 8, len(kept))):
            # tentar pegar 4 pontos
            pts = kept[i : i + 4]
            if len(pts) < 4:
                continue
            sp = np.diff(pts)
            err = float(np.mean(np.abs(sp - 61)))
            if err < best_err and np.all(sp > 40) and np.all(sp < 85):
                best_err = err
                best = pts
    if best is None and len(kept) >= 4:
        # fallback: primeiros 4 após x_left
        best = kept[:4]
        best_err = 99
    if best is None:
        return OMR.BLOCK_OFFSET_X + OMR.BUBBLE_WIDTH_PX / 2, float(OMR.BUBBLE_SPACING_PX)
    spacing = float(np.mean(np.diff(best)))
    x0 = float(best[0])
    return x0, spacing


def main():
    outdir = os.path.join(os.path.dirname(__file__), "_baseline_debug", "gt_num")
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
            questions = cfg["questions"]
            n_rows = len(questions)
            row_ys = find_row_ys_by_projection(gray, num_rows=n_rows)
            if len(row_ys) != n_rows:
                # fallback: modelo nominal + dy estimado
                print(fname, f"B{idx+1}", "row_ys", len(row_ys), "fallback")
                row_ys = [
                    int(
                        round(
                            OMR.BLOCK_OFFSET_Y
                            + OMR.ROW_HEIGHT_PX * i
                            + OMR.ROW_HEIGHT_PX / 2
                        )
                    )
                    for i in range(n_rows)
                ]

            x0, spacing = estimate_x0_and_spacing(gray, row_ys)
            # se spacing absurdo
            if not (45 <= spacing <= 80):
                x0 = OMR.BLOCK_OFFSET_X + OMR.BUBBLE_WIDTH_PX / 2
                spacing = float(OMR.BUBBLE_SPACING_PX)

            vis = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
            all_top = []
            row_decisions = []
            for i, q in enumerate(questions):
                cy = int(row_ys[i]) if i < len(row_ys) else row_ys[-1]
                scored = score_row_alternatives(gray, cy, x0, spacing, r=25, n_alts=4)
                ordered = sorted(scored, key=lambda t: -t[1])
                all_top.append(ordered[0][1])
                row_decisions.append((q["q"], scored, ordered, cy))
                cv2.line(vis, (0, cy), (vis.shape[1] - 1, cy), (255, 200, 0), 1)
                for let, sc, cx in scored:
                    cv2.circle(vis, (cx, cy), 18, (200, 200, 200), 1)

            tops = sorted(all_top, reverse=True)
            mark_lvl = float(np.median(tops[: max(3, len(tops) // 2)]))
            # vazios: usar 2º/3º/4º de cada linha
            empties = []
            for _, scored, ordered, _ in row_decisions:
                for t in ordered[1:]:
                    empties.append(t[1])
            empty_lvl = float(np.median(empties)) if empties else 20.0
            thr = empty_lvl + 0.35 * max(mark_lvl - empty_lvl, 1.0)
            thr = max(thr, empty_lvl + 18)

            for q_num, scored, ordered, cy in row_decisions:
                top, second = ordered[0], ordered[1]
                if top[1] < thr:
                    dec = None
                elif second[1] >= thr and (top[1] - second[1]) < 15:
                    dec = "INVALID"
                else:
                    dec = top[0]
                proposal[q_num] = dec
                for let, sc, cx in scored:
                    color = (160, 160, 160)
                    if dec == let:
                        color = (0, 220, 0)
                    elif dec == "INVALID" and let in (top[0], second[0]):
                        color = (0, 140, 255)
                    cv2.circle(vis, (cx, cy), 20, color, 2)
                lab = "?" if dec is None else (dec if dec != "INVALID" else "X")
                cv2.putText(
                    vis,
                    f"{q_num}:{lab}",
                    (4, cy + 4),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.4,
                    (0, 0, 255),
                    1,
                )

            overlays.append(vis)
            pitch = float(np.median(np.diff(row_ys))) if len(row_ys) > 1 else None
            print(
                fname,
                f"B{idx+1}",
                f"x0={x0:.1f}",
                f"sp={spacing:.1f}",
                f"pitch={pitch}",
                f"thr={thr:.1f}",
                f"rows={len(row_ys)}",
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
        print(" =>", fname, "marked", n_m)

    with open(os.path.join(outdir, "gt_proposed.json"), "w", encoding="utf-8") as f:
        json.dump(gt_all, f, indent=2, ensure_ascii=False)
    print("tesseract", HAS_TESS, "saved", outdir)


if __name__ == "__main__":
    main()
