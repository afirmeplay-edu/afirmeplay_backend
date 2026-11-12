# -*- coding: utf-8 -*-
"""Gera faixa por questão (11 linhas × 4 blocos) para anotação visual rápida."""
import os

import cv2
import numpy as np

from _load_omr import ROOT, default_topology, load_omr_class

OMR = load_omr_class()


def main():
    outdir = os.path.join(os.path.dirname(__file__), "_baseline_debug", "rows")
    os.makedirs(outdir, exist_ok=True)
    topo = default_topology()
    base = os.path.join(ROOT, "avaliacoes_marcadas")
    # uma prova por vez — todas
    for fname in sorted(os.listdir(base)):
        if not fname.lower().endswith(".jpg"):
            continue
        omr = OMR(debug=False)
        img = cv2.imread(os.path.join(base, fname))
        a4 = omr._normalize_to_a4(
            img, omr._detect_a4_anchors(img, omr._preprocess_image(img)["edges"])
        )
        blocks = omr._detect_blocks_via_fiducials(a4, 4, topo["topology"]["blocks"])
        stem = os.path.splitext(fname)[0]
        card_dir = os.path.join(outdir, stem)
        os.makedirs(card_dir, exist_ok=True)

        # montage: para cada questão, strip horizontal dos 4 alts com margem
        strips = []
        for idx, block in enumerate(blocks):
            bx, by, bw, bh = block["x"], block["y"], block["w"], block["h"]
            # ROI um pouco mais largo à esquerda para pegar número
            x0 = max(0, bx - 40)
            roi = a4[by : by + bh, x0 : bx + bw]
            cfg = topo["topology"]["blocks"][idx]
            for qi, q in enumerate(cfg["questions"]):
                # faixa Y generosa cobrindo possível drift
                y_nom = int(
                    OMR.BLOCK_OFFSET_Y
                    + OMR.ROW_HEIGHT_PX * qi
                    + OMR.ROW_HEIGHT_PX / 2
                )
                # pegar janela alta para ver bolha real mesmo com dy~40
                y_a = max(0, y_nom - 45)
                y_b = min(roi.shape[0], y_nom + 70)
                strip = roi[y_a:y_b, :].copy()
                # label
                label = np.full((28, strip.shape[1], 3), 240, np.uint8)
                cv2.putText(
                    label,
                    f"Q{q['q']} block{idx+1}",
                    (8, 20),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.55,
                    (0, 0, 200),
                    1,
                )
                # marca A B C D positions approx
                for ci, let in enumerate(["A", "B", "C", "D"]):
                    cx = int(
                        (bx - x0)
                        + OMR.BLOCK_OFFSET_X
                        + ci * OMR.BUBBLE_SPACING_PX
                        + OMR.BUBBLE_WIDTH_PX / 2
                    )
                    cy = y_nom - y_a
                    if 0 <= cx < strip.shape[1]:
                        cv2.putText(
                            strip,
                            let,
                            (cx - 5, 12),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.4,
                            (0, 128, 0),
                            1,
                        )
                combo = np.vstack([label, strip])
                out = os.path.join(card_dir, f"q{q['q']:02d}.jpg")
                cv2.imwrite(out, combo)
                strips.append((q["q"], combo))

        # big sheet: 11 rows x 4 cols of strips is heavy; make 44 stacked preview scaled
        # instead: 11 rows, each row is concat of that q's strip already per-q
        print(fname, "->", card_dir, "n=", len(strips))


if __name__ == "__main__":
    main()
