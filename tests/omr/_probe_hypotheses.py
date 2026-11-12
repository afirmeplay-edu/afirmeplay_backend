# -*- coding: utf-8 -*-
"""
Confirma hipóteses OMR com evidência numérica + propõe GT por anéis refinados.
Não altera o corretor de produção.
"""
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
    s = radius * 2 + 8
    tmpl = np.zeros((s, s), np.uint8)
    c = s // 2
    cv2.circle(tmpl, (c, c), radius, 255, thickness)
    return tmpl


def refine_centers(gray, bubbles, search=12, tmpl=None):
    if tmpl is None:
        tmpl = synth_ring()
    th, tw = tmpl.shape
    hits = []
    for b in bubbles:
        cx, cy, r = int(b["cx"]), int(b["cy"]), int(b["r"])
        x0 = max(0, cx - search - tw // 2)
        y0 = max(0, cy - search - th // 2)
        x1 = min(gray.shape[1], cx + search + tw // 2)
        y1 = min(gray.shape[0], cy + search + th // 2)
        win = gray[y0:y1, x0:x1]
        if win.shape[0] < th or win.shape[1] < tw:
            hits.append({**b, "fx": cx, "fy": cy, "match": 0.0, "dx": 0, "dy": 0})
            continue
        # anéis impressos são escuros → inverter para correlacionar com tmpl branco
        inv = 255 - win
        res = cv2.matchTemplate(inv, tmpl, cv2.TM_CCOEFF_NORMED)
        _, maxv, _, maxloc = cv2.minMaxLoc(res)
        fx = x0 + maxloc[0] + tw // 2
        fy = y0 + maxloc[1] + th // 2
        hits.append(
            {
                **b,
                "fx": int(fx),
                "fy": int(fy),
                "match": float(maxv),
                "dx": int(fx - cx),
                "dy": int(fy - cy),
            }
        )
    return hits


def fit_linear(idxs, vals):
    """y = a + b*idx via least squares."""
    if len(idxs) < 3:
        return None, None, 1e9
    A = np.vstack([np.ones(len(idxs)), idxs]).T
    coef, *_ = np.linalg.lstsq(A, np.asarray(vals, float), rcond=None)
    pred = A @ coef
    resid = float(np.median(np.abs(vals - pred)))
    return float(coef[0]), float(coef[1]), resid


def paper_dilate_ink(roi, radius=25):
    """Hipótese c: papel via dilatação elíptica + blur vs blur simples."""
    channel = np.min(roi, axis=2).astype(np.float32)
    sigma = 14.0
    paper_blur = cv2.GaussianBlur(channel, (0, 0), sigmaX=sigma)
    ink_blur = np.clip(paper_blur - channel, 0, 255)
    k = int(round(2.6 * radius))
    if k % 2 == 0:
        k += 1
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
    paper_dil = cv2.dilate(channel.astype(np.uint8), kernel)
    paper_dil = cv2.GaussianBlur(paper_dil.astype(np.float32), (0, 0), sigmaX=10)
    ink_dil = np.clip(paper_dil - channel, 0, 255)
    return ink_blur, ink_dil


def disk_score(ink, cx, cy, r, ratio=0.6):
    h, w = ink.shape
    rr = max(2, int(round(r * ratio)))
    yy, xx = np.ogrid[:h, :w]
    m = (xx - cx) ** 2 + (yy - cy) ** 2 <= rr * rr
    vals = ink[m]
    if vals.size == 0:
        return 0.0
    return float(np.mean(vals))


def main():
    outdir = os.path.join(os.path.dirname(__file__), "_baseline_debug")
    os.makedirs(outdir, exist_ok=True)
    topo = default_topology()
    base = os.path.join(ROOT, "avaliacoes_marcadas")
    tmpl = synth_ring(25, 2)
    report = {}
    gt_proposed = {}

    for fname in sorted(os.listdir(base)):
        if not fname.lower().endswith(".jpg"):
            continue
        omr = OMR(debug=False)
        img = cv2.imread(os.path.join(base, fname))
        gray0 = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        hist = cv2.calcHist([gray0], [0], None, [256], [0, 256]).flatten()
        hist /= hist.sum()
        binaryish = float(hist[:16].sum() + hist[240:].sum())

        anchors = omr._detect_a4_anchors(img, omr._preprocess_image(img)["edges"])
        a4 = omr._normalize_to_a4(img, anchors)
        blocks = omr._detect_blocks_via_fiducials(a4, 4, topo["topology"]["blocks"])

        # escala do warp: distância horizontal entre âncoras vs nominal
        # âncoras inset 0.2cm → distância nominal = 2480 - 2*0.2*118.11
        if anchors is not None and len(anchors) >= 4:
            # anchors dict/list? inspecionar
            pass

        card = {
            "binaryish_scan": binaryish,
            "blocks": [],
            "baseline_answers": {},
            "refined_proposal": {},
            "ink_attenuation": {},
        }
        answers = {}
        omr.last_bubble_diagnostics = {}
        proposal = {}
        overlay = a4.copy()

        for idx, block in enumerate(blocks):
            x, y, w, h = block["x"], block["y"], block["w"], block["h"]
            roi = a4[y : y + h, x : x + w]
            cfg = topo["topology"]["blocks"][idx]
            grid = omr._map_topology_to_grid(roi, cfg)
            bubbles = omr._calculate_bubble_centers(grid)
            ans = omr._detect_marked_bubbles(roi, bubbles, cfg["block_id"])
            answers.update(ans)

            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            hits = refine_centers(gray, bubbles, search=12, tmpl=tmpl)
            high = [h for h in hits if h["match"] >= 0.45]
            # regressão por row/col
            # row_idx from grid
            row_of = {}
            col_of = {}
            for qmap in grid["questions"]:
                for alt in qmap["alternatives"]:
                    row_of[(qmap["q_num"], alt["letter"])] = qmap["row_idx"]
                    col_of[(qmap["q_num"], alt["letter"])] = alt["col_idx"]

            rows_idx, rows_y = [], []
            cols_idx, cols_x = [], []
            for hhit in high:
                key = (hhit["q_num"], hhit["alternative"])
                rows_idx.append(row_of[key])
                rows_y.append(hhit["fy"])
                cols_idx.append(col_of[key])
                cols_x.append(hhit["fx"])

            # dedupe rows: median y per row
            by_row = {}
            for ri, ry in zip(rows_idx, rows_y):
                by_row.setdefault(ri, []).append(ry)
            ri_u = sorted(by_row)
            ry_u = [float(np.median(by_row[i])) for i in ri_u]
            a_y, b_y, res_y = fit_linear(ri_u, ry_u)

            by_col = {}
            for ci, cx in zip(cols_idx, cols_x):
                by_col.setdefault(ci, []).append(cx)
            ci_u = sorted(by_col)
            cx_u = [float(np.median(by_col[i])) for i in ci_u]
            a_x, b_x, res_x = fit_linear(ci_u, cx_u)

            dxs = [hhit["dx"] for hhit in high]
            dys = [hhit["dy"] for hhit in high]

            # ink attenuation: compare scores at baseline vs refined for dense marks
            ink_blur, ink_dil = paper_dilate_ink(roi, radius=25)
            atten = []
            for hhit in high:
                sb = disk_score(ink_blur, hhit["cx"], hhit["cy"], hhit["r"], 0.78)
                sd = disk_score(ink_dil, hhit["fx"], hhit["fy"], hhit["r"], 0.78)
                atten.append((sb, sd))

            # proposta de marcação no centro refinado + ink_dil
            # agrupar por questão
            q_groups = {}
            for hhit in hits:
                # usar centro ajustado se match ok, senão nominal
                use_x = hhit["fx"] if hhit["match"] >= 0.40 else hhit["cx"]
                use_y = hhit["fy"] if hhit["match"] >= 0.40 else hhit["cy"]
                # se regressão ok, preferir modelo
                if a_y is not None and b_y is not None and res_y < 4:
                    key = (hhit["q_num"], hhit["alternative"])
                    use_y = int(round(a_y + b_y * row_of[key]))
                if a_x is not None and b_x is not None and res_x < 4:
                    key = (hhit["q_num"], hhit["alternative"])
                    use_x = int(round(a_x + b_x * col_of[key]))
                sc = disk_score(ink_dil, use_x, use_y, hhit["r"], 0.60)
                # também cobertura binária no disco
                patch = gray[
                    max(0, use_y - 20) : use_y + 21, max(0, use_x - 20) : use_x + 21
                ]
                q_groups.setdefault(hhit["q_num"], []).append(
                    {
                        "letter": hhit["alternative"],
                        "score": sc,
                        "match": hhit["match"],
                        "cx": use_x,
                        "cy": use_y,
                    }
                )
                color = (0, 255, 0) if sc > 35 else (255, 0, 0)
                cv2.circle(overlay, (x + use_x, y + use_y), 8, color, 1)

            for q_num, scored in q_groups.items():
                ordered = sorted(scored, key=lambda z: z["score"], reverse=True)
                top, second = ordered[0], ordered[1]
                if top["score"] < 22:
                    proposal[q_num] = None
                elif second["score"] >= 40 and (top["score"] - second["score"]) < 12:
                    proposal[q_num] = "INVALID"
                elif top["score"] - second["score"] >= 8 and top["score"] >= 28:
                    proposal[q_num] = top["letter"]
                elif top["score"] >= 35 and (top["score"] - second["score"]) >= 6:
                    proposal[q_num] = top["letter"]
                else:
                    proposal[q_num] = None

            card["blocks"].append(
                {
                    "block_id": cfg["block_id"],
                    "n_high_matches": len(high),
                    "n_bubbles": len(hits),
                    "median_dx": float(np.median(dxs)) if dxs else None,
                    "median_dy": float(np.median(dys)) if dys else None,
                    "fit_a_y": a_y,
                    "fit_b_y_row_height": b_y,
                    "fit_res_y": res_y if a_y is not None else None,
                    "fit_a_x": a_x,
                    "fit_b_x_spacing": b_x,
                    "fit_res_x": res_x if a_x is not None else None,
                    "nominal_row": OMR.ROW_HEIGHT_PX,
                    "nominal_spacing": OMR.BUBBLE_SPACING_PX,
                }
            )
            if atten:
                sb = np.array([a[0] for a in atten])
                sd = np.array([a[1] for a in atten])
                card["ink_attenuation"][str(cfg["block_id"])] = {
                    "mean_score_blur_at_nominal": float(sb.mean()),
                    "mean_score_dilate_at_refined": float(sd.mean()),
                    "ratio_dilate_over_blur": float(sd.mean() / max(sb.mean(), 1e-6)),
                }

        card["baseline_answers"] = {str(k): v for k, v in sorted(answers.items())}
        card["refined_proposal"] = {str(k): v for k, v in sorted(proposal.items())}
        card["baseline_n_marked"] = sum(
            1 for v in answers.values() if v and v != "INVALID"
        )
        card["proposal_n_marked"] = sum(
            1 for v in proposal.values() if v and v != "INVALID"
        )
        report[fname] = card
        gt_proposed[fname] = {
            str(k): v for k, v in sorted(proposal.items())
        }

        ys = [b["y"] for b in blocks]
        xs = [b["x"] for b in blocks]
        ye = [b["y"] + b["h"] for b in blocks]
        xe = [b["x"] + b["w"] for b in blocks]
        crop = overlay[min(ys) - 20 : max(ye) + 20, min(xs) - 20 : max(xe) + 20]
        cv2.imwrite(
            os.path.join(outdir, f"{os.path.splitext(fname)[0]}_refined.jpg"), crop
        )
        print(
            fname,
            "bin",
            f"{binaryish:.4f}",
            "base",
            card["baseline_n_marked"],
            "prop",
            card["proposal_n_marked"],
            "row_h",
            [
                round(b["fit_b_y_row_height"], 2) if b["fit_b_y_row_height"] else None
                for b in card["blocks"]
            ],
            "dx",
            [b["median_dx"] for b in card["blocks"]],
        )

    with open(os.path.join(outdir, "hypotheses_report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    with open(os.path.join(outdir, "gt_proposed.json"), "w", encoding="utf-8") as f:
        json.dump(gt_proposed, f, indent=2, ensure_ascii=False)
    print("wrote hypotheses_report.json")


if __name__ == "__main__":
    main()
