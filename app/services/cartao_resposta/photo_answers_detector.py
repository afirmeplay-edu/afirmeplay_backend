# -*- coding: utf-8 -*-
"""
Detector OMR para fotos da área de respostas (sem QR / sem página A4 completa).

Abordagem image-first:
1. Pré-processa (EXIF, upscale)
2. Corrige perspectiva pelos marcadores de canto (quando visíveis)
3. Detecta bolhas com HoughCircles e agrupa em colunas/linhas
4. Pontua o núcleo interno de cada bolha (preenchimento de tinta)
5. Mapeia o grid detectado para a topologia da prova

A topologia define quantas colunas/questões/alternativas esperar e os números
das questões. Se a estrutura visual divergir demais, retorna erro claro.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class PhotoAnswersDetectionError(Exception):
    """Erro de detecção com código estável para a API."""

    def __init__(self, code: str, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        payload = {"error": self.message, "code": self.code}
        if self.details:
            payload["details"] = self.details
        return payload


class PhotoAnswersDetector:
    """Detecta respostas em foto enquadrada na área de bolhas (image-first)."""

    NORM_WIDTH = 2000
    MIN_INPUT_WIDTH = 1400

    # Preenchimento
    CORE_RADIUS_RATIO = 0.55
    MARK_SCORE_FLOOR = 35.0
    MARK_MARGIN_OK = 18.0
    MARK_MARGIN_LOW = 10.0

    def __init__(self, debug: bool = False):
        self.debug = debug
        self.logger = logging.getLogger(f"{__name__}.PhotoAnswersDetector")

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def detect(
        self,
        image_data: bytes,
        topology: Dict[str, Any],
    ) -> Dict[str, Any]:
        blocks_topology = (topology.get("topology") or {}).get("blocks") or []
        if not blocks_topology:
            raise PhotoAnswersDetectionError(
                "missing_topology",
                "Topologia da prova não encontrada. Gere o formulário físico ou configure os blocos.",
            )

        num_expected = len(blocks_topology)
        rows_per_block = [len(b.get("questions") or []) for b in blocks_topology]
        total_expected = sum(rows_per_block)
        if total_expected <= 0:
            raise PhotoAnswersDetectionError(
                "missing_topology",
                "A topologia da prova não contém questões.",
            )

        img = self._decode_image(image_data)
        img = self._apply_exif_orientation(image_data, img)
        img = self._ensure_min_resolution(img)
        warped = self._warp_answer_area(img)

        gray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)
        gray = self._normalize_illumination(gray)
        ink = (255.0 - gray.astype(np.float32))

        circles = self._detect_bubbles(
            gray, expected=sum(len(q.get("alternatives") or "ABCD") for b in blocks_topology for q in (b.get("questions") or []))
        )
        if circles is None or len(circles) < max(8, min(total_expected, 12)):
            raise PhotoAnswersDetectionError(
                "bubbles_not_found",
                (
                    "Não foi possível localizar as bolhas na foto. "
                    "Enquadre toda a área de respostas com boa iluminação e foco."
                ),
                details={"circles": 0 if circles is None else int(len(circles))},
            )

        # Image-first: estima colunas/linhas pela geometria da foto, depois valida topologia
        avg_alts = 4
        if blocks_topology:
            alt_lens = [
                len(q.get("alternatives") or ["A", "B", "C", "D"])
                for b in blocks_topology
                for q in (b.get("questions") or [])
            ]
            if alt_lens:
                avg_alts = max(2, int(round(float(np.median(alt_lens)))))
        estimated_cols = self._estimate_column_count(circles, avg_alts)

        estimated_rows = self._estimate_row_count(circles, estimated_cols)
        estimated_questions = max(1, estimated_cols * max(1, estimated_rows))
        bubble_budget = int(len(circles))

        # Topologia com poucas questões vs foto com grid grande (caso Jaru / subjetiva)
        if bubble_budget >= max(40, total_expected * avg_alts * 2) and estimated_questions >= total_expected * 2:
            raise PhotoAnswersDetectionError(
                "topology_image_mismatch",
                (
                    f"A foto mostra cerca de {estimated_questions} questões "
                    f"({estimated_cols} colunas × ~{estimated_rows} linhas), "
                    f"mas a avaliação tem apenas {total_expected}. "
                    "Confira se a prova é objetiva de múltipla escolha e se o cartão "
                    "corresponde a esta avaliação (provas subjetivas/interativas não são suportadas)."
                ),
                details={
                    "blocks_expected": num_expected,
                    "blocks_detected": estimated_cols,
                    "questions_expected": total_expected,
                    "questions_estimated": estimated_questions,
                    "rows_estimated": estimated_rows,
                    "bubbles_detected": bubble_budget,
                },
            )

        if estimated_cols != num_expected:
            # Tolerância: se a estimativa falhou mas o count de bolhas bate, usa num_expected
            expected_bubbles = total_expected * avg_alts
            bubble_ok = abs(bubble_budget - expected_bubbles) <= max(12, int(expected_bubbles * 0.35))
            if not bubble_ok:
                raise PhotoAnswersDetectionError(
                    "blocks_mismatch",
                    (
                        f"Esperava {num_expected} coluna(s) de respostas, "
                        f"mas a foto parece ter {estimated_cols}. "
                        "Confira se a foto mostra todos os blocos do cartão desta prova."
                    ),
                    details={
                        "blocks_expected": num_expected,
                        "blocks_detected": estimated_cols,
                        "questions_expected": total_expected,
                        "questions_estimated": estimated_questions,
                        "bubbles_detected": bubble_budget,
                    },
                )

        columns = self._cluster_columns(circles, num_expected)
        if len(columns) != num_expected:
            raise PhotoAnswersDetectionError(
                "blocks_mismatch",
                (
                    f"Esperava {num_expected} coluna(s) de respostas, "
                    f"mas a foto parece ter {len(columns)}. "
                    "Confira se a foto mostra todos os blocos do cartão desta prova."
                ),
                details={
                    "blocks_expected": num_expected,
                    "blocks_detected": len(columns),
                    "questions_expected": total_expected,
                },
            )

        rows: List[Dict[str, Any]] = []
        img_h, img_w = gray.shape[:2]
        for col_idx, (block_cfg, col_circles) in enumerate(zip(blocks_topology, columns)):
            questions = block_cfg.get("questions") or []
            n_rows = len(questions)
            if n_rows == 0:
                continue

            max_alts = max(len(q.get("alternatives") or ["A", "B", "C", "D"]) for q in questions)
            # Quantas linhas a coluna realmente tem (sem forçar n_rows)
            natural_rows = self._estimate_row_count_in_column(col_circles)
            if natural_rows >= max(4, n_rows * 2) and n_rows <= 2:
                raise PhotoAnswersDetectionError(
                    "topology_image_mismatch",
                    (
                        f"A coluna {col_idx + 1} na foto tem ~{natural_rows} linhas de bolhas, "
                        f"mas a topologia da prova indica apenas {n_rows} questão(ões). "
                        "A avaliação/cartão não correspondem à foto."
                    ),
                    details={
                        "block_index": col_idx + 1,
                        "rows_expected": n_rows,
                        "rows_detected": natural_rows,
                        "questions_expected": total_expected,
                    },
                )

            alt_centers = self._cluster_alt_centers(col_circles, max_alts)
            row_centers = self._cluster_row_centers(col_circles, n_rows)

            if len(row_centers) < max(1, int(n_rows * 0.6)):
                raise PhotoAnswersDetectionError(
                    "topology_image_mismatch",
                    (
                        f"A coluna {col_idx + 1} deveria ter {n_rows} questões, "
                        f"mas a foto não formou um grid compatível ({len(row_centers)} linhas detectadas). "
                        "Use uma avaliação objetiva cujo cartão corresponda à foto, "
                        "ou reenquadre a imagem."
                    ),
                    details={
                        "block_index": col_idx + 1,
                        "rows_expected": n_rows,
                        "rows_detected": len(row_centers),
                        "questions_expected": total_expected,
                    },
                )

            # Se detectou menos linhas, interpola para n_rows
            if len(row_centers) != n_rows:
                row_centers = self._resample_centers(row_centers, n_rows)

            radius = float(np.median(col_circles[:, 2]))
            subject_name = block_cfg.get("subject_name")
            block_id = block_cfg.get("block_id", col_idx + 1)

            for row_idx, question in enumerate(questions):
                q_num = int(question.get("q"))
                alts = [str(a).upper() for a in (question.get("alternatives") or ["A", "B", "C", "D"])]
                cy = row_centers[row_idx]
                # Centros de alternativa: usa os detectados até len(alts)
                if len(alt_centers) >= len(alts):
                    cxs = alt_centers[: len(alts)]
                else:
                    # interpola a partir da largura da coluna
                    x_min = float(col_circles[:, 0].min())
                    x_max = float(col_circles[:, 0].max())
                    cxs = list(np.linspace(x_min, x_max, len(alts)))

                scored = []
                for letter, cx in zip(alts, cxs):
                    score = self._core_ink_score(ink, cx, cy, radius)
                    scored.append(
                        {"letter": letter, "score": score, "cx": float(cx), "cy": float(cy), "r": radius}
                    )
                rows.append(
                    {
                        "q_num": q_num,
                        "alts": alts,
                        "scored": scored,
                        "subject_name": subject_name or question.get("subject_name"),
                        "block_id": block_id,
                    }
                )

        # Calibração global (estilo OMRChecker): separa "vazia" de "preenchida" pela própria foto
        cal = self._calibrate([s["score"] for r in rows for s in r["scored"]])

        answers: List[Dict[str, Any]] = []
        for row in rows:
            decision, status, conf, reason, top = self._decide(row["scored"], cal)
            answers.append(
                {
                    "question_number": row["q_num"],
                    "answer": decision,
                    "status": status,
                    "confidence": conf,
                    "confidence_label": (
                        "high" if status == "ok" else ("medium" if status == "low_confidence" else "low")
                    ),
                    "alternatives": row["alts"],
                    "subject_name": row["subject_name"],
                    "block_id": row["block_id"],
                    "reason": reason,
                    "suggested_answer": top,
                    "bubbles": [
                        {
                            "letter": s["letter"],
                            "x": round(s["cx"] / img_w, 5),
                            "y": round(s["cy"] / img_h, 5),
                            "r": round(s["r"] / img_w, 5),
                            "score": round(float(s["score"]), 1),
                            "marked": s["score"] >= cal["floor"],
                        }
                        for s in row["scored"]
                    ],
                }
            )

        answers.sort(key=lambda a: int(a["question_number"]))
        summary = {
            "total": len(answers),
            "ok": sum(1 for a in answers if a["status"] == "ok"),
            "blank": sum(1 for a in answers if a["status"] == "blank"),
            "multiple": sum(1 for a in answers if a["status"] == "multiple"),
            "low_confidence": sum(1 for a in answers if a["status"] == "low_confidence"),
        }

        return {
            "success": True,
            "answers": answers,
            "blocks_detected": len(columns),
            "blocks_expected": num_expected,
            "summary": summary,
            "method": "image_first_hough_grid",
            "calibration": {k: round(float(v), 2) for k, v in cal.items()},
            "overlay_image": self._encode_overlay(warped),
        }

    # ------------------------------------------------------------------
    # Pré-processamento / calibração / overlay
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_illumination(gray: np.ndarray) -> np.ndarray:
        """Divide pela estimativa do fundo (dilatação + blur) para tolerar sombras."""
        k = max(15, (min(gray.shape[:2]) // 25) | 1)
        bg = cv2.dilate(gray, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
        bg = cv2.GaussianBlur(bg, (k | 1, k | 1), 0)
        out = cv2.divide(gray, np.maximum(bg, 1), scale=255)
        return out.astype(np.uint8)

    def _calibrate(self, scores: List[float]) -> Dict[str, float]:
        """Limiar relativo: ponto de corte entre as classes vazia/preenchida (Otsu 1D)."""
        default = {
            "floor": self.MARK_SCORE_FLOOR,
            "margin_ok": self.MARK_MARGIN_OK,
            "margin_low": self.MARK_MARGIN_LOW,
            "spread": 0.0,
        }
        if len(scores) < 12:
            return default
        s = np.sort(np.asarray(scores, dtype=np.float64))
        best_t, best_var, n = None, -1.0, len(s)
        for i in range(2, n - 1):
            w0, w1 = i / n, (n - i) / n
            m0, m1 = s[:i].mean(), s[i:].mean()
            v = w0 * w1 * (m1 - m0) ** 2
            if v > best_var:
                best_var, best_t = v, i
        if best_t is None:
            return default
        lo, hi = float(s[:best_t].mean()), float(s[best_t:].mean())
        spread = hi - lo
        if spread < 40:
            # Sem bolhas preenchidas suficientes (ou foto sem contraste): usa padrão
            return default
        return {
            "floor": lo + 0.45 * spread,
            "margin_ok": 0.25 * spread,
            "margin_low": 0.12 * spread,
            "spread": spread,
        }

    @staticmethod
    def _encode_overlay(warped: np.ndarray, width: int = 1100) -> Optional[str]:
        try:
            import base64

            h, w = warped.shape[:2]
            scale = width / float(w)
            small = cv2.resize(warped, (width, int(round(h * scale))), interpolation=cv2.INTER_AREA)
            ok, buf = cv2.imencode(".jpg", small, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
            if not ok:
                return None
            return "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode("ascii")
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Imagem
    # ------------------------------------------------------------------

    def _decode_image(self, image_data: bytes) -> np.ndarray:
        arr = np.frombuffer(image_data, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            raise PhotoAnswersDetectionError(
                "invalid_image",
                "Não foi possível ler a imagem. Envie um JPEG ou PNG válido.",
            )
        return img

    def _apply_exif_orientation(self, image_data: bytes, img: np.ndarray) -> np.ndarray:
        try:
            from io import BytesIO
            from PIL import Image, ImageOps

            pil = Image.open(BytesIO(image_data))
            pil = ImageOps.exif_transpose(pil)
            rgb = np.array(pil.convert("RGB"))
            return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        except Exception:
            return img

    def _ensure_min_resolution(self, img: np.ndarray) -> np.ndarray:
        h, w = img.shape[:2]
        target = max(self.MIN_INPUT_WIDTH, self.NORM_WIDTH)
        if w >= target:
            return img
        scale = target / float(w)
        return cv2.resize(
            img,
            (int(round(w * scale)), int(round(h * scale))),
            interpolation=cv2.INTER_CUBIC,
        )

    def _warp_answer_area(self, img: np.ndarray) -> np.ndarray:
        corners = self._detect_corner_markers(img)
        h, w = img.shape[:2]
        # Mantém proporção aproximada da área de respostas
        out_w = self.NORM_WIDTH
        out_h = int(round(self.NORM_WIDTH * (h / float(w))))
        out_h = max(900, min(out_h, 2200))

        if corners is None:
            return cv2.resize(img, (out_w, out_h), interpolation=cv2.INTER_AREA)

        dst = np.array(
            [[0, 0], [out_w - 1, 0], [out_w - 1, out_h - 1], [0, out_h - 1]],
            dtype=np.float32,
        )
        matrix = cv2.getPerspectiveTransform(corners.astype(np.float32), dst)
        return cv2.warpPerspective(img, matrix, (out_w, out_h))

    def _detect_corner_markers(self, img: np.ndarray) -> Optional[np.ndarray]:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img.copy()
        h, w = gray.shape[:2]
        gray = self._normalize_illumination(gray)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        _, thr = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        thr = cv2.morphologyEx(thr, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8), iterations=2)
        contours, _ = cv2.findContours(thr, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        img_area = float(h * w)
        candidates = []
        for cnt in contours:
            area = float(cv2.contourArea(cnt))
            if area < img_area * 0.00015 or area > img_area * 0.04:
                continue
            x, y, bw, bh = cv2.boundingRect(cnt)
            aspect = bw / float(bh) if bh else 0
            if not (0.25 < aspect < 4.0):
                continue
            cx, cy = x + bw / 2.0, y + bh / 2.0
            edge = min(cx, w - cx) / w + min(cy, h - cy) / h
            if edge > 0.38:
                continue
            candidates.append((cx, cy, area))

        if len(candidates) < 4:
            m = 0.015
            return np.array(
                [
                    [w * m, h * m],
                    [w * (1 - m), h * m],
                    [w * (1 - m), h * (1 - m)],
                    [w * m, h * (1 - m)],
                ],
                dtype=np.float32,
            )

        targets = [(0, 0), (w, 0), (w, h), (0, h)]
        chosen = []
        used = set()
        for tx, ty in targets:
            best_i, best_d = None, float("inf")
            for i, (cx, cy, _) in enumerate(candidates):
                if i in used:
                    continue
                d = (cx - tx) ** 2 + (cy - ty) ** 2
                if d < best_d:
                    best_d, best_i = d, i
            if best_i is None:
                return None
            used.add(best_i)
            cx, cy, _ = candidates[best_i]
            chosen.append((cx, cy))
        return np.array(chosen, dtype=np.float32)

    # ------------------------------------------------------------------
    # Bolhas / grid
    # ------------------------------------------------------------------

    def _detect_bubbles(
        self, gray: np.ndarray, expected: Optional[int] = None
    ) -> Optional[np.ndarray]:
        """Hough com relaxamento progressivo de param2 até atingir ~`expected` bolhas."""
        best, best_gap = None, None
        for p2 in (14, 12, 10, 8):
            c = self._detect_bubbles_once(gray, p2)
            n = 0 if c is None else len(c)
            if expected is None:
                return c
            gap = abs(n - expected)
            if best_gap is None or gap < best_gap:
                best, best_gap = c, gap
            if 0.9 * expected <= n <= 1.15 * expected:
                break
        return best

    def _detect_bubbles_once(self, gray: np.ndarray, param2: int = 14) -> Optional[np.ndarray]:
        h, w = gray.shape[:2]
        radius = self._estimate_bubble_radius(gray)
        if radius is None:
            # Fallback: ~16 bolhas na horizontal
            radius = max(8.0, w / 18.0 * 0.3)
        b = cv2.medianBlur(gray, 3)
        circles = cv2.HoughCircles(
            b,
            cv2.HOUGH_GRADIENT,
            dp=1,
            minDist=max(6, int(radius * 1.7)),
            param1=60,
            param2=param2,
            minRadius=max(4, int(radius * 0.8)),
            maxRadius=max(6, int(radius * 1.25)),
        )
        if circles is None:
            return None
        c = circles[0].astype(np.float32)
        c = self._filter_isolated(c)
        return c if len(c) else None

    @staticmethod
    def _filter_isolated(c: np.ndarray) -> np.ndarray:
        """Remove círculos sem vizinhos próximos (letras, números e marcas soltas)."""
        if len(c) < 6:
            return c
        r = float(np.median(c[:, 2]))
        d = np.sqrt(((c[:, None, :2] - c[None, :, :2]) ** 2).sum(axis=2))
        neighbors = (d < r * 4.0).sum(axis=1) - 1
        keep = neighbors >= 2
        return c[keep] if keep.sum() >= 4 else c

    def _estimate_bubble_radius(self, gray: np.ndarray) -> Optional[float]:
        """Raio típico das bolhas, medido nas bolhas preenchidas (blobs escuros e redondos)."""
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        _, dark = cv2.threshold(blur, 110, 255, cv2.THRESH_BINARY_INV)
        dark = cv2.morphologyEx(dark, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
        n, _, stats, _ = cv2.connectedComponentsWithStats(dark)
        h, w = gray.shape[:2]
        min_area = (w / 120.0) ** 2 * 3.14
        radii = []
        for i in range(1, n):
            x, y, bw, bh, area = stats[i]
            if bh == 0 or not (0.7 < bw / float(bh) < 1.4):
                continue
            if area < min_area or area > (w / 18.0) ** 2:
                continue
            if area / float(bw * bh) < 0.6:
                continue
            radii.append((bw + bh) / 4.0)
        if len(radii) < 3:
            return None
        return float(np.median(radii))

    def _cluster_1d(self, values: np.ndarray, k: int, rounds: int = 25) -> np.ndarray:
        vals = np.asarray(values, dtype=np.float64)
        if len(vals) == 0:
            return np.array([])
        if k <= 1:
            return np.array([float(vals.mean())])
        centers = np.linspace(vals.min(), vals.max(), k)
        for _ in range(rounds):
            assign = np.argmin(np.abs(vals[:, None] - centers[None, :]), axis=1)
            for i in range(k):
                pts = vals[assign == i]
                if len(pts):
                    centers[i] = float(pts.mean())
        return np.sort(centers)

    def _estimate_groups_1d(self, values: np.ndarray, min_gap_ratio: float = 1.6) -> int:
        """Conta grupos naturais ao longo de um eixo (gaps grandes entre bolhas)."""
        vals = np.sort(np.asarray(values, dtype=np.float64))
        if len(vals) < 2:
            return max(1, len(vals))
        gaps = np.diff(vals)
        if len(gaps) == 0:
            return 1
        med = float(np.median(gaps))
        if med <= 1e-6:
            return 1
        # Gaps tipicamente entre alternativas são ~med; entre colunas/blocos são bem maiores
        threshold = med * min_gap_ratio
        big = gaps > threshold
        # Exige que o gap seja também um outlier razoável
        if np.any(big):
            q90 = float(np.percentile(gaps, 90))
            big = gaps > max(threshold, q90 * 0.85)
        return int(1 + np.count_nonzero(big))

    @staticmethod
    def _gap_groups(values: np.ndarray, gap: float) -> List[np.ndarray]:
        """Agrupa valores 1D ordenados quebrando onde o salto excede `gap`."""
        v = np.sort(np.asarray(values, dtype=np.float64))
        if len(v) == 0:
            return []
        cuts = np.where(np.diff(v) > gap)[0] + 1
        return [g for g in np.split(v, cuts) if len(g)]

    def _alt_column_centers(self, circles: np.ndarray) -> List[float]:
        r = float(np.median(circles[:, 2]))
        groups = self._gap_groups(circles[:, 0], r * 0.9)
        # ignora grupos com poucas bolhas (ruído)
        min_pop = max(2, int(0.25 * np.median([len(g) for g in groups]))) if groups else 2
        return [float(g.mean()) for g in groups if len(g) >= min_pop]

    def _block_split(self, centers: List[float]) -> List[List[float]]:
        """Divide centros de alternativas em blocos pelos gaps maiores que o passo típico."""
        if len(centers) < 2:
            return [centers] if centers else []
        gaps = np.diff(centers)
        pitch = float(np.median(gaps))
        # o passo entre alternativas é o menor gap típico
        small = gaps[gaps <= pitch * 1.3]
        pitch = float(np.median(small)) if len(small) else pitch
        cuts = np.where(gaps > pitch * 1.7)[0] + 1
        return [list(map(float, g)) for g in np.split(np.asarray(centers), cuts)]

    def _estimate_column_count(self, circles: np.ndarray, alts_per_block: int = 4) -> int:
        if circles is None or len(circles) == 0:
            return 0
        centers = self._alt_column_centers(circles)
        blocks = self._block_split(centers)
        if blocks:
            return len(blocks)
        return self._estimate_column_count_peaks(circles, alts_per_block)

    def _estimate_column_count_peaks(self, circles: np.ndarray, alts_per_block: int = 4) -> int:
        if circles is None or len(circles) == 0:
            return 0
        # Agrupa por X: 4 alternativas por bloco → gaps internos pequenos; entre blocos grandes
        xs = circles[:, 0]
        # Primeiro: histograma grosso
        x_min, x_max = float(xs.min()), float(xs.max())
        span = max(1.0, x_max - x_min)
        bins = max(24, min(80, int(span / max(8.0, float(np.median(circles[:, 2])) * 1.2))))
        hist, edges = np.histogram(xs, bins=bins)
        # Suaviza
        kernel = np.array([1, 2, 3, 2, 1], dtype=np.float64)
        kernel /= kernel.sum()
        smooth = np.convolve(hist.astype(np.float64), kernel, mode="same")
        # Picos de densidade (centros de alternativa/coluna)
        peaks = []
        for i in range(1, len(smooth) - 1):
            if smooth[i] >= smooth[i - 1] and smooth[i] >= smooth[i + 1] and smooth[i] >= max(2.0, smooth.max() * 0.18):
                peaks.append((edges[i] + edges[i + 1]) / 2.0)
        if len(peaks) >= max(2, alts_per_block):
            # Agrupa picos em colunas de bloco (cada bloco ~alts_per_block alternativas)
            peak_arr = np.array(peaks, dtype=np.float64)
            n_alt_peaks = len(peak_arr)
            # Tentativas comuns: 2, 3, 4, 5 blocos
            best_k, best_score = 1, -1.0
            for k in range(1, 7):
                if n_alt_peaks < k:
                    break
                centers = self._cluster_1d(peak_arr, k)
                assign = np.argmin(np.abs(peak_arr[:, None] - centers[None, :]), axis=1)
                sizes = [int(np.sum(assign == i)) for i in range(k)]
                if min(sizes) < 1:
                    continue
                # Preferência: ~alts_per_block picos/coluna e tamanhos parecidos
                mean_sz = float(np.mean(sizes))
                score = -abs(mean_sz - float(alts_per_block)) - float(np.std(sizes)) * 0.5
                if score > best_score:
                    best_score, best_k = score, k
            if best_k >= 1:
                return best_k

        # Fallback por gaps entre círculos
        return max(1, self._estimate_groups_1d(xs, min_gap_ratio=2.2))

    def _estimate_row_count(self, circles: np.ndarray, n_cols: int) -> int:
        if circles is None or len(circles) == 0:
            return 0
        cols = self._cluster_columns(circles, max(1, n_cols))
        estimates = [self._estimate_row_count_in_column(c) for c in cols if len(c) >= 4]
        if not estimates:
            return max(1, self._estimate_groups_1d(circles[:, 1], min_gap_ratio=1.35))
        return int(round(float(np.median(estimates))))

    def _estimate_row_count_in_column(self, col_circles: np.ndarray) -> int:
        if col_circles is None or len(col_circles) == 0:
            return 0
        ys = col_circles[:, 1]
        # Gaps entre linhas de questões são regulares; usa mediana dos gaps pequenos
        return max(1, self._estimate_groups_1d(ys, min_gap_ratio=1.35))

    def _cluster_columns(self, circles: np.ndarray, n_cols: int) -> List[np.ndarray]:
        # Preferência: separar blocos pelos maiores gaps entre colunas de alternativas
        alt_centers = self._alt_column_centers(circles)
        if n_cols >= 1 and len(alt_centers) > n_cols:
            gaps = np.diff(alt_centers)
            cut_idx = sorted(int(i) for i in np.argsort(gaps)[::-1][: n_cols - 1])
            bounds = [(alt_centers[i] + alt_centers[i + 1]) / 2.0 for i in cut_idx]
            edges = [-np.inf] + bounds + [np.inf]
            cols = [
                circles[(circles[:, 0] > edges[i]) & (circles[:, 0] <= edges[i + 1])]
                for i in range(n_cols)
            ]
            if all(len(c) for c in cols):
                return cols
        centers = self._cluster_1d(circles[:, 0], n_cols)
        if len(centers) != n_cols:
            # fallback: fatias iguais
            xs = circles[:, 0]
            edges = np.linspace(xs.min(), xs.max(), n_cols + 1)
            cols = []
            for i in range(n_cols):
                mask = (circles[:, 0] >= edges[i]) & (circles[:, 0] <= edges[i + 1])
                cols.append(circles[mask])
            return cols

        assign = np.argmin(np.abs(circles[:, 0][:, None] - centers[None, :]), axis=1)
        cols = [circles[assign == i] for i in range(n_cols)]
        # Ordena esquerda → direita
        order = np.argsort([c[:, 0].mean() if len(c) else 0 for c in cols])
        return [cols[i] for i in order]

    def _cluster_alt_centers(self, col_circles: np.ndarray, n_alts: int) -> List[float]:
        if len(col_circles) == 0:
            return []
        # Descarta outliers à esquerda (números das questões às vezes viram “círculos”)
        r = float(np.median(col_circles[:, 2]))
        groups = self._gap_groups(col_circles[:, 0], r * 0.9)
        if len(groups) >= n_alts:
            # mantém os n_alts grupos mais populosos, em ordem espacial
            top = sorted(sorted(range(len(groups)), key=lambda i: -len(groups[i]))[:n_alts])
            return [float(groups[i].mean()) for i in top]
        xs = col_circles[:, 0]
        centers = self._cluster_1d(xs, n_alts)
        return [float(x) for x in centers]

    def _cluster_row_centers(self, col_circles: np.ndarray, n_rows: int) -> List[float]:
        if len(col_circles) == 0:
            return []
        ys = col_circles[:, 1]
        r = float(np.median(col_circles[:, 2]))
        groups = self._gap_groups(ys, r * 0.9)
        if len(groups) == n_rows:
            return [float(g.mean()) for g in groups]
        if len(groups) > n_rows:
            top = sorted(sorted(range(len(groups)), key=lambda i: -len(groups[i]))[:n_rows])
            return [float(groups[i].mean()) for i in top]
        # menos grupos que linhas (linhas coladas): devolve o que há; o chamador reamostra
        return [float(g.mean()) for g in groups]

    @staticmethod
    def _resample_centers(centers: List[float], n: int) -> List[float]:
        if not centers:
            return [0.0] * n
        if len(centers) == n:
            return centers
        src = np.array(centers, dtype=np.float64)
        xp = np.linspace(0, 1, len(src))
        xq = np.linspace(0, 1, n)
        return [float(v) for v in np.interp(xq, xp, src)]

    def _core_ink_score(self, ink: np.ndarray, cx: float, cy: float, radius: float) -> float:
        r = max(2.0, float(radius) * self.CORE_RADIUS_RATIO)
        h, w = ink.shape[:2]
        x0 = max(0, int(cx - r))
        x1 = min(w, int(cx + r) + 1)
        y0 = max(0, int(cy - r))
        y1 = min(h, int(cy + r) + 1)
        if x1 <= x0 or y1 <= y0:
            return 0.0
        patch = ink[y0:y1, x0:x1]
        yy, xx = np.ogrid[y0:y1, x0:x1]
        mask = (xx - cx) ** 2 + (yy - cy) ** 2 <= r * r
        if not np.any(mask):
            return 0.0
        return float(np.mean(patch[mask]))

    def _decide(
        self, scored: List[Dict[str, Any]], cal: Optional[Dict[str, float]] = None
    ) -> Tuple[Optional[str], str, float, str, Optional[str]]:
        cal = cal or {
            "floor": self.MARK_SCORE_FLOOR,
            "margin_ok": self.MARK_MARGIN_OK,
            "margin_low": self.MARK_MARGIN_LOW,
            "spread": 0.0,
        }
        floor, m_ok, m_low = cal["floor"], cal["margin_ok"], cal["margin_low"]
        if not scored:
            return None, "blank", 0.0, "no_scores", None
        ordered = sorted(scored, key=lambda s: s["score"], reverse=True)
        top = ordered[0]
        second = ordered[1] if len(ordered) > 1 else {"score": 0.0, "letter": None}
        margin = float(top["score"] - second["score"])
        top_letter = str(top["letter"]).upper()
        top_score = float(top["score"])

        if top_score < floor:
            return None, "blank", 0.2, f"below_floor score={top_score:.1f}", top_letter

        # Dois marcados com margem pequena -> ambígua, mas sugere o topo
        if margin < m_low and second["score"] >= floor:
            return top_letter, "multiple", 0.4, f"double_mark margin={margin:.1f}", top_letter

        if margin < m_ok:
            return top_letter, "low_confidence", 0.55, f"low_margin margin={margin:.1f}", top_letter

        scale = cal["spread"] or 100.0
        conf = min(0.99, 0.7 + min(margin / scale, 1.0) * 0.29)
        return top_letter, "ok", round(conf, 3), f"ok margin={margin:.1f}", top_letter
