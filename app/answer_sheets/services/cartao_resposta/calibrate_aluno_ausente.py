# -*- coding: utf-8 -*-
"""
Calibrador interativo da bolinha "Aluno ausente".

Usa o overlay de debug (04_aluno_ausente.jpg) para achar a faixa/círculo
atuais e desenha o ajuste sobre o A4 limpo (03_normalized_a4.jpg).

Uso (na raiz do repo, venv ativo):

    python -m app.answer_sheets.services.cartao_resposta.calibrate_aluno_ausente

    python -m app.answer_sheets.services.cartao_resposta.calibrate_aluno_ausente ^
        --image debug_corrections_new/20260824_105522_647599_04_aluno_ausente.jpg

Controles:
    Clique esquerdo     coloca o centro da bolinha 1 (Aluno ausente)
    Scroll              raio +/-
    Setas / W A D X     move 1 px
    I J K L             move 10 px
    + / -               raio +/- 1
    TAB                 alterna editar CIRCULO <-> FAIXA
    Q / E               sobe / desce a borda superior da faixa
    Z / C               sobe / desce a borda inferior da faixa
    U / O               estreita / alarga a faixa (X)
    R                   reset para o overlay original
    P                   imprime valores no terminal
    Enter / S           salva JSON + snapshot
    ESC                 sai
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

import cv2
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[3]
CALIBRATION_JSON = Path(__file__).resolve().parent / "aluno_ausente_calibration.json"
DEFAULT_DEBUG = (
    REPO_ROOT
    / "debug_corrections_new"
    / "20260824_105522_647599_04_aluno_ausente.jpg"
)
PX_PER_CM = 118.11
CSS_PX_TO_A4 = 300.0 / 96.0
FILL_THRESHOLD = 0.45
BUBBLE_GAP_PX = int((18 + 3) * CSS_PX_TO_A4)
ARROW = {
    2490368: "up",
    2621440: "down",
    2424832: "left",
    2555904: "right",
    0x260000: "up",
    0x280000: "down",
    0x250000: "left",
    0x270000: "right",
}


def circle_fill_ratio(img: np.ndarray, cx: int, cy: int, r: int) -> float:
    if img is None or r <= 0:
        return 0.0
    h, w = img.shape[:2]
    cx, cy, r = int(cx), int(cy), int(r)
    if not (0 <= cx < w and 0 <= cy < h):
        return 0.0
    pad = max(r * 3, 20)
    x0, y0 = max(0, cx - pad), max(0, cy - pad)
    x1, y1 = min(w, cx + pad), min(h, cy + pad)
    patch = img[y0:y1, x0:x1]
    if patch.size == 0:
        return 0.0
    gray = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY) if patch.ndim == 3 else patch
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    _, thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    mask = np.zeros_like(thresh)
    cv2.circle(mask, (cx - x0, cy - y0), r, 255, -1)
    total = cv2.countNonZero(mask)
    if total <= 0:
        return 0.0
    return float(cv2.countNonZero(cv2.bitwise_and(thresh, mask))) / float(total)


def extract_overlay(
    debug_bgr: np.ndarray,
) -> Tuple[Tuple[int, int, int, int], Tuple[int, int, int]]:
    """Lê retângulo magenta + círculo vermelho do overlay 04_aluno_ausente."""
    b, g, r = cv2.split(debug_bgr)
    magenta = (r > 180) & (b > 180) & (g < 120)
    ys, xs = np.where(magenta)
    if len(xs) < 20:
        raise RuntimeError(
            "Não achei o retângulo magenta no overlay. Gere de novo com OMR_DEBUG=1."
        )
    x1, x2 = int(xs.min()), int(xs.max())
    y1, y2 = int(ys.min()), int(ys.max())

    inset = 8
    roi_r = r[y1 + inset : y2 - inset, x1 + inset : x2 - inset]
    roi_g = g[y1 + inset : y2 - inset, x1 + inset : x2 - inset]
    roi_b = b[y1 + inset : y2 - inset, x1 + inset : x2 - inset]
    red = (roi_r > 180) & (roi_g < 90) & (roi_b < 90)
    rys, rxs = np.where(red)
    if len(rxs) < 8:
        cx = (x1 + x2) // 2
        cy = y1 + int(0.55 * PX_PER_CM)
        radius = max(8, int((18 / 2.0) * CSS_PX_TO_A4))
    else:
        cx = x1 + inset + int(rxs.mean())
        cy = y1 + inset + int(rys.mean())
        radius = max(
            8, int(max(int(rxs.max() - rxs.min()), int(rys.max() - rys.min())) / 2)
        )
    return (x1, y1, x2, y2), (cx, cy, radius)


def sibling_normalized(debug_path: Path) -> Optional[Path]:
    name = debug_path.name
    token = "_04_aluno_ausente"
    if token not in name:
        return None
    cand = debug_path.with_name(name.replace(token, "_03_normalized_a4"))
    return cand if cand.exists() else None


class AusenteCalibrator:
    def __init__(
        self,
        canvas: np.ndarray,
        band,
        circle,
        source_debug: Path,
        source_a4: Path,
    ):
        self.canvas = canvas
        self.initial_band = tuple(int(v) for v in band)
        self.initial_circle = tuple(int(v) for v in circle)
        self.x1, self.y1, self.x2, self.y2 = self.initial_band
        self.cx, self.cy, self.r = self.initial_circle
        self.mode = "circle"
        self.scale = 2.0
        self.source_debug = source_debug
        self.source_a4 = source_a4
        self.win = "Calibrar aluno ausente"
        self.zoom_win = "Zoom bolinha"
        self._drag_band = False
        self._drag_off = (0, 0)

    def crop_box(self):
        h, w = self.canvas.shape[:2]
        pad_x, pad_y = 80, 120
        x0 = max(0, min(self.x1, self.cx) - pad_x)
        y0 = max(0, min(self.y1, self.cy) - pad_y)
        x1 = min(w, max(self.x2, self.cx) + pad_x + 280)
        y1 = min(h, max(self.y2, self.cy + 2 * BUBBLE_GAP_PX) + pad_y)
        return x0, y0, x1, y1

    def fill(self) -> float:
        return circle_fill_ratio(self.canvas, self.cx, self.cy, self.r)

    def draw(self) -> np.ndarray:
        vis = self.canvas.copy()
        cv2.rectangle(vis, (self.x1, self.y1), (self.x2, self.y2), (255, 0, 255), 3)
        fill = self.fill()
        marked = fill > FILL_THRESHOLD
        color = (0, 0, 255) if marked else (0, 255, 0)
        for i in range(3):
            yy = self.cy + i * BUBBLE_GAP_PX
            thick = 3 if i == 0 else 1
            col = color if i == 0 else (180, 180, 0)
            cv2.circle(vis, (self.cx, yy), self.r, col, thick)
        cv2.circle(vis, (self.cx, self.cy), 2, color, -1)

        x0, y0, x1, y1 = self.crop_box()
        crop = vis[y0:y1, x0:x1]
        view = cv2.resize(
            crop, None, fx=self.scale, fy=self.scale, interpolation=cv2.INTER_NEAREST
        )

        dy_px = self.cy - self.y1
        lines = [
            f"modo={'CIRCULO' if self.mode == 'circle' else 'FAIXA'}  fill={fill:.3f}  "
            f"{'AUSENTE' if marked else 'vazio'}  thr={FILL_THRESHOLD}",
            f"cx={self.cx}  cy={self.cy}  r={self.r}   dx={self.cx - self.initial_circle[0]:+d}  "
            f"dy={self.cy - self.initial_circle[1]:+d}",
            f"faixa x1={self.x1} y1={self.y1} x2={self.x2} y2={self.y2}",
            f"cy-y1={dy_px}px ({dy_px / PX_PER_CM:.3f} cm)   clique=centro  WADX=1px  IJKL=10px",
            "TAB=modo  Q/E=topo faixa  Z/C=base  U/O=largura  S=salvar  ESC=sair",
        ]
        y_txt = 28
        for line in lines:
            cv2.putText(
                view, line, (12, y_txt), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 3, cv2.LINE_AA
            )
            cv2.putText(
                view, line, (12, y_txt), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA
            )
            y_txt += 24
        return view

    def draw_zoom(self) -> np.ndarray:
        pad = max(self.r * 4, 40)
        h, w = self.canvas.shape[:2]
        x0, y0 = max(0, self.cx - pad), max(0, self.cy - pad)
        x1, y1 = min(w, self.cx + pad), min(h, self.cy + pad)
        patch = self.canvas[y0:y1, x0:x1].copy()
        local = (self.cx - x0, self.cy - y0)
        fill = self.fill()
        color = (0, 0, 255) if fill > FILL_THRESHOLD else (0, 255, 0)
        cv2.circle(patch, local, self.r, color, 1)
        cv2.circle(patch, local, 1, color, -1)
        zoom = cv2.resize(patch, None, fx=6, fy=6, interpolation=cv2.INTER_NEAREST)
        label = f"fill={fill:.3f} r={self.r}"
        cv2.putText(zoom, label, (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 3, cv2.LINE_AA)
        cv2.putText(zoom, label, (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 1, cv2.LINE_AA)
        return zoom

    def view_to_a4(self, vx: int, vy: int) -> Tuple[int, int]:
        x0, y0, _, _ = self.crop_box()
        return int(x0 + vx / self.scale), int(y0 + vy / self.scale)

    def on_mouse(self, event, x, y, flags, _userdata):
        ax, ay = self.view_to_a4(x, y)
        if event == cv2.EVENT_LBUTTONDOWN:
            if self.mode == "circle":
                self.cx, self.cy = ax, ay
            else:
                self._drag_band = True
                self._drag_off = (ax - self.x1, ay - self.y1)
        elif event == cv2.EVENT_MOUSEMOVE and self._drag_band:
            bw = self.x2 - self.x1
            bh = self.y2 - self.y1
            self.x1 = ax - self._drag_off[0]
            self.y1 = ay - self._drag_off[1]
            self.x2 = self.x1 + bw
            self.y2 = self.y1 + bh
        elif event == cv2.EVENT_LBUTTONUP:
            self._drag_band = False
        elif event == cv2.EVENT_MOUSEWHEEL:
            delta = 1 if flags > 0 else -1
            if self.mode == "circle":
                self.r = max(6, self.r + delta)
            else:
                self.x1 -= delta
                self.x2 += delta
                self.y1 -= delta
                self.y2 += delta

    def nudge(self, dx: int, dy: int, step: int):
        dx, dy = dx * step, dy * step
        if self.mode == "circle":
            self.cx += dx
            self.cy += dy
        else:
            self.x1 += dx
            self.x2 += dx
            self.y1 += dy
            self.y2 += dy

    def snapshot_dict(self) -> dict:
        fill = round(self.fill(), 4)
        dy = self.cy - self.y1
        dx_init = self.cx - self.initial_circle[0]
        dy_init = self.cy - self.initial_circle[1]
        return {
            "source_debug": str(self.source_debug),
            "source_a4": str(self.source_a4),
            "saved_at": datetime.now().isoformat(timespec="seconds"),
            "cx": int(self.cx),
            "cy": int(self.cy),
            "r": int(self.r),
            "band": {
                "x1": int(self.x1),
                "y1": int(self.y1),
                "x2": int(self.x2),
                "y2": int(self.y2),
            },
            "fill_ratio": fill,
            "marked_with_current_threshold": fill > FILL_THRESHOLD,
            "offset_from_overlay_px": {"dx": int(dx_init), "dy": int(dy_init)},
            "cy_minus_band_top_px": int(dy),
            "cy_minus_band_top_cm": round(dy / PX_PER_CM, 4),
            "suggested_fallback": {
                "comment": "Em _fallback_ausente_center, trocar o 0.55 cm pelo valor abaixo.",
                "cy_offset_cm": round(dy / PX_PER_CM, 4),
                "cx": int(self.cx),
                "r": int(self.r),
            },
        }

    def print_values(self):
        data = self.snapshot_dict()
        print("\n" + "=" * 72)
        print("CALIBRACAO aluno ausente")
        print("=" * 72)
        print(json.dumps(data, indent=2, ensure_ascii=False))
        print("-" * 72)
        print(
            "Sugestao _fallback_ausente_center:\n"
            f"    cy = y1 + int({data['cy_minus_band_top_cm']} * self.PX_PER_CM_A4)\n"
            f"    # overlay original: {data['offset_from_overlay_px']['dy']:+d} px em Y, "
            f"{data['offset_from_overlay_px']['dx']:+d} px em X"
        )
        print("=" * 72 + "\n")

    def save(self):
        json_path = CALIBRATION_JSON
        img_path = (
            self.source_debug.parent
            / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_aluno_ausente_calibrated.jpg"
        )
        data = self.snapshot_dict()
        json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        cv2.imwrite(str(img_path), self.draw())
        self.print_values()
        print(f"Salvo: {json_path}")
        print(f"Snapshot: {img_path}")

    def reset(self):
        self.x1, self.y1, self.x2, self.y2 = self.initial_band
        self.cx, self.cy, self.r = self.initial_circle

    def handle_key(self, key: int) -> bool:
        """True = continuar, False = sair."""
        raw = key
        ch = key & 0xFF
        letter = chr(ch) if 32 <= ch < 127 else ""
        low = letter.lower()

        if ch == 27:
            return False
        if ch in (13,) or low == "s":
            self.save()
            return True
        if low == "p":
            self.print_values()
            return True
        if low == "r":
            self.reset()
            return True
        if ch == 9:
            self.mode = "band" if self.mode == "circle" else "circle"
            print(f"modo -> {self.mode}")
            return True

        arrow = ARROW.get(raw)
        if arrow == "up" or low == "w":
            self.nudge(0, -1, 1)
        elif arrow == "down" or low == "x":
            self.nudge(0, 1, 1)
        elif arrow == "left" or low == "a":
            self.nudge(-1, 0, 1)
        elif arrow == "right" or low == "d":
            self.nudge(1, 0, 1)
        elif low == "i":
            self.nudge(0, -1, 10)
        elif low == "k":
            self.nudge(0, 1, 10)
        elif low == "j":
            self.nudge(-1, 0, 10)
        elif low == "l":
            self.nudge(1, 0, 10)
        elif ch in (ord("+"), ord("=")):
            self.r += 1
        elif ch in (ord("-"), ord("_")):
            self.r = max(6, self.r - 1)
        elif low == "q":
            self.y1 -= 1
        elif low == "e":
            self.y1 += 1
        elif low == "z":
            self.y2 -= 1
        elif low == "c":
            self.y2 += 1
        elif low == "u":
            self.x1 += 1
            self.x2 -= 1
        elif low == "o":
            self.x1 -= 1
            self.x2 += 1
        return True

    def run(self):
        cv2.namedWindow(self.win, cv2.WINDOW_NORMAL)
        cv2.namedWindow(self.zoom_win, cv2.WINDOW_NORMAL)
        cv2.setMouseCallback(self.win, self.on_mouse)
        print(__doc__)
        self.print_values()
        while True:
            cv2.imshow(self.win, self.draw())
            cv2.imshow(self.zoom_win, self.draw_zoom())
            key = cv2.waitKeyEx(30)
            if key < 0:
                continue
            if not self.handle_key(key):
                break
        cv2.destroyAllWindows()


def parse_args():
    parser = argparse.ArgumentParser(description="Calibrar coordenadas da bolinha Aluno ausente")
    parser.add_argument(
        "--image",
        type=Path,
        default=DEFAULT_DEBUG,
        help="Caminho para *_04_aluno_ausente.jpg",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    debug_path = args.image if args.image.is_absolute() else (REPO_ROOT / args.image)
    if not debug_path.exists():
        print(f"Imagem nao encontrada: {debug_path}", file=sys.stderr)
        sys.exit(1)

    debug_img = cv2.imread(str(debug_path))
    if debug_img is None:
        print(f"Falha ao ler: {debug_path}", file=sys.stderr)
        sys.exit(1)

    band, circle = extract_overlay(debug_img)
    a4_path = sibling_normalized(debug_path)
    if a4_path is not None:
        canvas = cv2.imread(str(a4_path))
        if canvas is None:
            print(f"Falha ao ler A4 limpo, usando o overlay: {a4_path}")
            canvas = debug_img
            a4_path = debug_path
        else:
            print(f"Canvas limpo: {a4_path.name}")
    else:
        canvas = debug_img
        a4_path = debug_path
        print("03_normalized_a4 nao encontrado — usando o proprio overlay.")

    print(f"Overlay: {debug_path.name}")
    print(f"Faixa inicial: {band}  circulo inicial: {circle}")

    AusenteCalibrator(canvas, band, circle, debug_path, a4_path).run()


if __name__ == "__main__":
    main()
