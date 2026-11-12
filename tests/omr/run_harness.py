# -*- coding: utf-8 -*-
"""
Harness de regressão OMR — Fase A.

Roda o corretor SEM banco, chamando métodos internos:
  _detect_a4_anchors → _normalize_to_a4 → _detect_blocks_via_fiducials
  → _map_topology_to_grid → _calculate_bubble_centers → _detect_marked_bubbles

Uso:
  python tests/omr/run_harness.py
  python tests/omr/run_harness.py --images avaliacoes_marcadas --gt tests/omr/fixtures/ground_truth.json
  python tests/omr/run_harness.py --tag baseline
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from _load_omr import ROOT, default_topology, load_omr_class  # noqa: E402

OMR = load_omr_class()


def _norm_ans(v: Any) -> Optional[str]:
    if v is None:
        return None
    if isinstance(v, float) and np.isnan(v):
        return None
    s = str(v).strip().upper()
    if s in ("", "NONE", "NULL", "BLANK", "NONE"):
        return None
    if s in ("INVALID", "INV", "X", "DUP"):
        return "INVALID"
    if s in ("A", "B", "C", "D", "E"):
        return s
    return s


def load_ground_truth(path: str) -> Dict[str, Dict[int, Optional[str]]]:
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    out: Dict[str, Dict[int, Optional[str]]] = {}
    for fname, answers in raw.items():
        out[fname] = {int(k): _norm_ans(v) for k, v in answers.items()}
    return out


def classify_pair(
    expected: Optional[str], predicted: Optional[str]
) -> str:
    """
    Categorias:
      ok_mark, ok_blank, ok_invalid,
      false_blank (marca real → None),
      false_mark (None → letra),
      letter_swap (letra → outra letra),
      false_invalid (não-INVALID → INVALID),
      missed_invalid (INVALID → outra coisa)
    """
    e, p = expected, predicted
    if e == p:
        if e is None:
            return "ok_blank"
        if e == "INVALID":
            return "ok_invalid"
        return "ok_mark"
    if e is not None and e != "INVALID" and p is None:
        return "false_blank"
    if e is None and p is not None and p != "INVALID":
        return "false_mark"
    if e is None and p == "INVALID":
        return "false_invalid"
    if e == "INVALID" and p != "INVALID":
        return "missed_invalid"
    if e is not None and e != "INVALID" and p == "INVALID":
        return "false_invalid"
    if (
        e is not None
        and e != "INVALID"
        and p is not None
        and p != "INVALID"
        and e != p
    ):
        return "letter_swap"
    return "other_error"


def run_one_card(
    omr: Any,
    image_path: str,
    topology: Dict,
    save_overlay_dir: Optional[str] = None,
) -> Dict[str, Any]:
    t0 = time.perf_counter()
    img = cv2.imread(image_path)
    if img is None:
        return {"success": False, "error": f"falha ao ler {image_path}"}

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    hist = cv2.calcHist([gray], [0], None, [256], [0, 256]).flatten()
    hist = hist / max(float(hist.sum()), 1.0)
    binaryish = float(hist[:16].sum() + hist[240:].sum())

    processed = omr._preprocess_image(img)
    anchors = omr._detect_a4_anchors(img, processed["edges"])
    if anchors is None:
        return {"success": False, "error": "âncoras A4 não detectadas"}

    img_a4 = omr._normalize_to_a4(img, anchors)
    blocks_topo = topology["topology"]["blocks"]
    blocks = omr._detect_blocks_via_fiducials(
        img_a4, topology["num_blocks"], blocks_topo
    )
    if blocks is None:
        return {"success": False, "error": "fiduciais de bloco não detectados"}

    answers: Dict[int, Optional[str]] = {}
    omr.last_bubble_diagnostics = {}
    all_scores: List[float] = []
    overlay = img_a4.copy()

    for idx, block in enumerate(blocks):
        x, y, w, h = block["x"], block["y"], block["w"], block["h"]
        roi = img_a4[y : y + h, x : x + w]
        cfg = blocks_topo[idx]
        grid = omr._map_topology_to_grid(roi, cfg)
        if not grid:
            continue
        bubbles = omr._calculate_bubble_centers(grid)
        block_id = cfg.get("block_id", idx + 1)
        block_ans = omr._detect_marked_bubbles(roi, bubbles, block_id)
        answers.update(block_ans)

        for b in bubbles:
            q = int(b["q_num"])
            let = b["alternative"]
            cx, cy, r = int(b["cx"]), int(b["cy"]), int(b["r"])
            diag = omr.last_bubble_diagnostics.get(q, {})
            sc = float(
                (diag.get("alternatives") or {}).get(let, {}).get("score", 0.0)
            )
            all_scores.append(sc)
            dec = answers.get(q)
            if dec == let:
                color = (0, 220, 0)
            elif dec == "INVALID" and let in (
                diag.get("top_letter"),
                diag.get("second_letter"),
            ):
                color = (0, 140, 255)
            else:
                color = (255, 80, 80)
            cv2.circle(overlay, (x + cx, y + cy), r, color, 2)

    elapsed = time.perf_counter() - t0

    if save_overlay_dir:
        os.makedirs(save_overlay_dir, exist_ok=True)
        stem = os.path.splitext(os.path.basename(image_path))[0]
        ys = [b["y"] for b in blocks]
        xs = [b["x"] for b in blocks]
        ye = [b["y"] + b["h"] for b in blocks]
        xe = [b["x"] + b["w"] for b in blocks]
        crop = overlay[
            max(0, min(ys) - 20) : max(ye) + 20,
            max(0, min(xs) - 20) : max(xe) + 20,
        ]
        cv2.imwrite(os.path.join(save_overlay_dir, f"{stem}_overlay.jpg"), crop)

    score_arr = np.array(all_scores, dtype=np.float64) if all_scores else np.array([0.0])
    conf_counts = Counter(
        (omr.last_bubble_diagnostics.get(q) or {}).get("confidence", "?")
        for q in answers
    )

    return {
        "success": True,
        "answers": {int(k): v for k, v in answers.items()},
        "diagnostics": dict(omr.last_bubble_diagnostics),
        "binaryish": binaryish,
        "elapsed_s": elapsed,
        "score_stats": {
            "min": float(score_arr.min()),
            "max": float(score_arr.max()),
            "mean": float(score_arr.mean()),
            "median": float(np.median(score_arr)),
            "p90": float(np.percentile(score_arr, 90)),
            "p10": float(np.percentile(score_arr, 10)),
        },
        "confidence_counts": dict(conf_counts),
        "n_marked": sum(1 for v in answers.values() if v and v != "INVALID"),
        "n_blank": sum(1 for v in answers.values() if v is None),
        "n_invalid": sum(1 for v in answers.values() if v == "INVALID"),
    }


def evaluate_card(
    predicted: Dict[int, Optional[str]],
    expected: Dict[int, Optional[str]],
) -> Dict[str, Any]:
    cats = Counter()
    details = []
    for q in sorted(expected.keys()):
        e = expected[q]
        p = predicted.get(q)
        cat = classify_pair(e, p)
        cats[cat] += 1
        if cat not in ("ok_mark", "ok_blank", "ok_invalid"):
            details.append({"q": q, "expected": e, "predicted": p, "cat": cat})
    return {"confusion": dict(cats), "errors": details}


def print_report(report: Dict[str, Any]) -> None:
    print("\n===== RELATÓRIO HARNESS OMR =====")
    print(f"tag={report.get('tag')}  n_cards={report.get('n_cards')}")
    totals = report.get("totals", {})
    print("\nTotais (questões):")
    for k in (
        "ok_mark",
        "ok_blank",
        "ok_invalid",
        "false_blank",
        "false_mark",
        "letter_swap",
        "false_invalid",
        "missed_invalid",
        "other_error",
    ):
        print(f"  {k:16s} {totals.get(k, 0)}")
    print(
        f"\nTempo médio/cartão: {report.get('mean_elapsed_s', 0):.3f}s "
        f"(max {report.get('max_elapsed_s', 0):.3f}s)"
    )
    print("\nPor cartão:")
    for fname, card in report.get("cards", {}).items():
        if not card.get("success"):
            print(f"  {fname}: ERRO {card.get('error')}")
            continue
        c = card.get("confusion", {})
        print(
            f"  {fname}: marked={card.get('n_marked')} blank={card.get('n_blank')} "
            f"inv={card.get('n_invalid')} | "
            f"FB={c.get('false_blank', 0)} FM={c.get('false_mark', 0)} "
            f"SW={c.get('letter_swap', 0)} FI={c.get('false_invalid', 0)} "
            f"bin={card.get('binaryish', 0):.3f} t={card.get('elapsed_s', 0):.2f}s"
        )
        for err in card.get("errors", [])[:8]:
            print(
                f"      Q{err['q']}: exp={err['expected']!r} pred={err['predicted']!r} ({err['cat']})"
            )
        if len(card.get("errors", [])) > 8:
            print(f"      ... +{len(card['errors']) - 8} erros")


def main():
    ap = argparse.ArgumentParser(description="Harness OMR AfirmePlay")
    ap.add_argument(
        "--images",
        default=os.path.join(ROOT, "avaliacoes_marcadas"),
        help="Pasta com JPGs dos cartões",
    )
    ap.add_argument(
        "--gt",
        default=os.path.join(HERE, "fixtures", "ground_truth.json"),
        help="JSON de gabarito de marcação",
    )
    ap.add_argument(
        "--tag",
        default="baseline",
        help="Nome da rodada (baseline, after_b, ...)",
    )
    ap.add_argument(
        "--out",
        default=os.path.join(HERE, "reports"),
        help="Pasta de saída de relatórios/overlays",
    )
    ap.add_argument("--debug", action="store_true")
    args = ap.parse_args()

    topology = default_topology(4, 11)
    gt = {}
    if os.path.exists(args.gt):
        gt = load_ground_truth(args.gt)
    else:
        print(f"AVISO: gabarito não encontrado em {args.gt} — só roda detecção")

    out_tag = os.path.join(args.out, args.tag)
    overlay_dir = os.path.join(out_tag, "overlays")
    os.makedirs(out_tag, exist_ok=True)

    images = sorted(
        f
        for f in os.listdir(args.images)
        if f.lower().endswith((".jpg", ".jpeg", ".png"))
    )
    omr = OMR(debug=bool(args.debug))
    if args.debug:
        omr.debug_dir = os.path.join(out_tag, "debug_omr")
        os.makedirs(omr.debug_dir, exist_ok=True)

    report: Dict[str, Any] = {
        "tag": args.tag,
        "n_cards": 0,
        "cards": {},
        "totals": Counter(),
        "score_hist_all": [],
    }
    elapsed_list = []

    for fname in images:
        path = os.path.join(args.images, fname)
        print(f"→ {fname}")
        result = run_one_card(omr, path, topology, save_overlay_dir=overlay_dir)
        card_rep: Dict[str, Any] = dict(result)
        if result.get("success") and fname in gt:
            ev = evaluate_card(result["answers"], gt[fname])
            card_rep.update(ev)
            report["totals"].update(ev["confusion"])
        elif result.get("success"):
            card_rep["confusion"] = {}
            card_rep["errors"] = []
            card_rep["note"] = "sem gabarito"
        # serializar answers
        if "answers" in card_rep:
            card_rep["answers"] = {
                str(k): v for k, v in sorted(card_rep["answers"].items())
            }
        # diagnostics muito grandes — só resumo de scores top
        if "diagnostics" in card_rep:
            diag_slim = {}
            for q, d in card_rep["diagnostics"].items():
                diag_slim[str(q)] = {
                    "decision": d.get("decision"),
                    "confidence": d.get("confidence"),
                    "reason": d.get("reason"),
                    "top_letter": d.get("top_letter"),
                    "top_score": d.get("top_score"),
                    "second_score": d.get("second_score"),
                    "margin": d.get("margin"),
                }
            card_rep["diagnostics"] = diag_slim
        report["cards"][fname] = card_rep
        report["n_cards"] += 1
        if result.get("success"):
            elapsed_list.append(result["elapsed_s"])
            report["score_hist_all"].extend(
                [
                    float(d.get("top_score") or 0)
                    for d in (result.get("diagnostics") or {}).values()
                ]
            )

    report["totals"] = dict(report["totals"])
    report["mean_elapsed_s"] = float(np.mean(elapsed_list)) if elapsed_list else 0.0
    report["max_elapsed_s"] = float(np.max(elapsed_list)) if elapsed_list else 0.0
    if report["score_hist_all"]:
        arr = np.array(report["score_hist_all"], dtype=np.float64)
        report["score_distribution"] = {
            "min": float(arr.min()),
            "max": float(arr.max()),
            "mean": float(arr.mean()),
            "median": float(np.median(arr)),
            "p10": float(np.percentile(arr, 10)),
            "p90": float(np.percentile(arr, 90)),
            "hist_bins": [float(x) for x in np.histogram(arr, bins=12, range=(0, 120))[0]],
            "hist_edges": [float(x) for x in np.linspace(0, 120, 13)],
        }

    out_json = os.path.join(out_tag, "report.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    # tabela markdown
    md_path = os.path.join(out_tag, "report.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(f"# Relatório OMR — `{args.tag}`\n\n")
        f.write("| cartão | marked | blank | inv | falso_branco | falso_marcado | troca | INVALID_indevido | bin | t(s) |\n")
        f.write("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|\n")
        for fname, card in report["cards"].items():
            c = card.get("confusion") or {}
            f.write(
                f"| {fname} | {card.get('n_marked', '-')} | {card.get('n_blank', '-')} | "
                f"{card.get('n_invalid', '-')} | {c.get('false_blank', 0)} | "
                f"{c.get('false_mark', 0)} | {c.get('letter_swap', 0)} | "
                f"{c.get('false_invalid', 0)} | {card.get('binaryish', 0):.3f} | "
                f"{card.get('elapsed_s', 0):.2f} |\n"
            )
        tot = report["totals"]
        f.write(
            f"| **TOTAL** |  |  |  | **{tot.get('false_blank', 0)}** | "
            f"**{tot.get('false_mark', 0)}** | **{tot.get('letter_swap', 0)}** | "
            f"**{tot.get('false_invalid', 0)}** |  | {report['mean_elapsed_s']:.2f} |\n"
        )
        if "score_distribution" in report:
            sd = report["score_distribution"]
            f.write(
                f"\nScores (top por questão): median={sd['median']:.1f} "
                f"p10={sd['p10']:.1f} p90={sd['p90']:.1f}\n"
            )

    print_report(report)
    print(f"\nSalvo: {out_json}")
    print(f"Salvo: {md_path}")
    print(f"Overlays: {overlay_dir}")


if __name__ == "__main__":
    main()
