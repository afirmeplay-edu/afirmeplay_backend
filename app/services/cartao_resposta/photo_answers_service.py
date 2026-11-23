# -*- coding: utf-8 -*-
"""
Serviço de suporte ao escaneamento de respostas por foto:
- resolve topologia / questões da prova
- lista respostas já existentes
- grava respostas revisadas + recalcula EvaluationResult
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app import db
from app.models.answerSheetGabarito import AnswerSheetGabarito
from app.models.physicalTestForm import PhysicalTestForm
from app.models.question import Question
from app.models.student import Student
from app.models.studentAnswer import StudentAnswer
from app.models.test import Test
from app.models.testQuestion import TestQuestion
from app.models.testSession import TestSession

logger = logging.getLogger(__name__)

ALLOWED_LETTERS = set("ABCDEFGHIJ")
PHOTO_SCAN_USER_AGENT = "Photo Answers Scan"
NON_OMR_TYPE_HINTS = (
    "ligar",
    "arrastar",
    "drag",
    "drop",
    "essay",
    "discurs",
    "dissert",
    "aberta",
    "open",
    "interactive",
    "interativ",
    "subjet",
    "audio",
    "video",
    "upload",
)


class PhotoAnswersIncompatibleError(ValueError):
    """Avaliação incompatível com escaneamento de cartão-resposta."""

    def __init__(self, code: str, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


class PhotoAnswersService:
    """Operações de negócio para detect/save de respostas por foto."""

    MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB
    ALLOWED_MIME_PREFIXES = ("image/jpeg", "image/jpg", "image/png", "image/webp")

    # ------------------------------------------------------------------
    # Validação de upload
    # ------------------------------------------------------------------

    @classmethod
    def validate_image_bytes(
        cls,
        image_data: bytes,
        content_type: Optional[str] = None,
    ) -> None:
        if not image_data:
            raise ValueError("Imagem vazia")
        if len(image_data) > cls.MAX_IMAGE_BYTES:
            raise ValueError(
                f"Imagem muito grande (máx. {cls.MAX_IMAGE_BYTES // (1024 * 1024)} MB)"
            )
        if content_type:
            ct = content_type.split(";")[0].strip().lower()
            if ct and not any(ct.startswith(p) for p in ("image/jpeg", "image/jpg", "image/png", "image/webp", "image/")):
                # Aceita image/* genérico; rejeita non-image
                if not ct.startswith("image/"):
                    raise ValueError(f"Tipo de arquivo não suportado: {content_type}")

    # ------------------------------------------------------------------
    # Compatibilidade OMR
    # ------------------------------------------------------------------

    @classmethod
    def assert_scan_compatible(cls, test_id: str) -> List[Dict[str, Any]]:
        """
        Garante que a avaliação é objetiva (bolhas A–D) e adequada ao scan por foto.
        Retorna a lista de questões objetivas (meta).
        """
        from app.mapa_questoes.helpers import (
            is_discursive_question,
            is_objective_question,
            normalize_question_type,
        )
        from app.services.evaluation_result_service import EvaluationResultService

        questions_meta = cls.get_questions_meta(test_id)
        if not questions_meta:
            raise PhotoAnswersIncompatibleError(
                "no_questions",
                "Esta avaliação não possui questões para escanear.",
            )

        omr_questions = []
        rejected = []
        for m in questions_meta:
            qtype = m.get("question_type")
            qt_norm = normalize_question_type(qtype)
            raw_alts = m.get("raw_alternatives")
            if is_discursive_question(qtype):
                rejected.append({"order": m["order"], "reason": "discursive", "type": qtype})
                continue
            if any(h in qt_norm for h in NON_OMR_TYPE_HINTS):
                rejected.append({"order": m["order"], "reason": "interactive", "type": qtype})
                continue
            if cls._looks_interactive_payload(raw_alts, qtype):
                rejected.append({"order": m["order"], "reason": "interactive_payload", "type": qtype})
                continue
            # Alternativas inventadas (A–D default) não contam como prova objetiva
            real_letters = cls._real_alternative_letters(raw_alts)
            is_mcq = (
                EvaluationResultService.is_multiple_choice_question(qtype)
                or is_objective_question(qtype, raw_alts)
            )
            if not is_mcq and len(real_letters) < 2:
                rejected.append({"order": m["order"], "reason": "not_objective", "type": qtype})
                continue
            if len(real_letters) >= 2:
                m = {**m, "alternatives": real_letters}
            elif not m.get("alternatives") or len(m.get("alternatives") or []) < 2:
                rejected.append({"order": m["order"], "reason": "not_objective", "type": qtype})
                continue
            omr_questions.append(m)

        if not omr_questions:
            raise PhotoAnswersIncompatibleError(
                "not_objective_test",
                (
                    "Esta avaliação não é de múltipla escolha com bolhas (A, B, C…). "
                    "O escaneamento por foto serve apenas para cartões-resposta objetivos. "
                    "A prova selecionada parece subjetiva/interativa (ex.: ligar colunas, arrastar e soltar)."
                ),
                details={
                    "total_questions": len(questions_meta),
                    "rejected": rejected[:20],
                },
            )

        if len(omr_questions) < len(questions_meta):
            # Mistura: por enquanto exigimos 100% objetiva para o cartão físico
            raise PhotoAnswersIncompatibleError(
                "mixed_question_types",
                (
                    f"Apenas {len(omr_questions)} de {len(questions_meta)} questões são objetivas de bolha. "
                    "O escaneamento por foto requer uma avaliação só com múltipla escolha."
                ),
                details={
                    "omr_count": len(omr_questions),
                    "total_questions": len(questions_meta),
                    "rejected": rejected[:20],
                },
            )

        return omr_questions

    # ------------------------------------------------------------------
    # Topologia / questões
    # ------------------------------------------------------------------

    @classmethod
    def resolve_topology(cls, test_id: str) -> Dict[str, Any]:
        """
        Obtém topologia dos blocos na ordem:
        1) AnswerSheetGabarito.blocks_config (se cobrir as questões objetivas)
        2) PhysicalTestForm.blocks_config (idem)
        3) Montagem a partir das questões do Test
        """
        omr_questions = cls.assert_scan_compatible(test_id)
        expected_n = len(omr_questions)

        gabarito = AnswerSheetGabarito.query.filter_by(test_id=test_id).first()
        if gabarito and gabarito.blocks_config:
            topo = cls._normalize_topology(gabarito.blocks_config, test_id)
            if topo and cls._topology_question_count(topo) == expected_n:
                return topo
            logger.warning(
                "blocks_config do gabarito ignorado (questões=%s, esperadas=%s)",
                cls._topology_question_count(topo) if topo else 0,
                expected_n,
            )

        form = PhysicalTestForm.query.filter_by(test_id=test_id).first()
        if form and form.blocks_config:
            topo = cls._normalize_topology(form.blocks_config, test_id)
            if topo and cls._topology_question_count(topo) == expected_n:
                return topo
            logger.warning(
                "blocks_config do PhysicalTestForm ignorado (questões=%s, esperadas=%s)",
                cls._topology_question_count(topo) if topo else 0,
                expected_n,
            )

        return cls._build_topology_from_test(test_id)

    @staticmethod
    def _topology_question_count(topology: Optional[Dict[str, Any]]) -> int:
        if not topology:
            return 0
        blocks = (topology.get("topology") or {}).get("blocks") or []
        return sum(len(b.get("questions") or []) for b in blocks)

    @classmethod
    def _normalize_topology(
        cls, blocks_config: Dict[str, Any], test_id: str
    ) -> Optional[Dict[str, Any]]:
        if not isinstance(blocks_config, dict):
            return None
        topology = blocks_config.get("topology") or {}
        blocks = topology.get("blocks") if isinstance(topology, dict) else None
        if not blocks:
            # Às vezes topology está direto em blocks_config
            blocks = blocks_config.get("blocks")
        if not blocks:
            return None

        # Enriquecer alternativas a partir das questões reais se faltarem
        questions_meta = cls.get_questions_meta(test_id)
        meta_by_order = {m["order"]: m for m in questions_meta}

        normalized_blocks = []
        for b in blocks:
            qs = []
            for q in b.get("questions") or []:
                q_num = int(q.get("q"))
                alts = q.get("alternatives")
                if not alts and q_num in meta_by_order:
                    alts = meta_by_order[q_num]["alternatives"]
                if not alts:
                    alts = ["A", "B", "C", "D"]
                entry = {
                    "q": q_num,
                    "alternatives": [str(a).upper() for a in alts],
                }
                subject = q.get("subject_name") or b.get("subject_name")
                if subject:
                    entry["subject_name"] = subject
                if q_num in meta_by_order and meta_by_order[q_num].get("subject_name"):
                    entry["subject_name"] = meta_by_order[q_num]["subject_name"]
                qs.append(entry)

            block_entry = {
                "block_id": b.get("block_id"),
                "questions": qs,
            }
            if b.get("subject_name"):
                block_entry["subject_name"] = b.get("subject_name")
            elif qs and qs[0].get("subject_name"):
                block_entry["subject_name"] = qs[0]["subject_name"]
            if b.get("subject_id"):
                block_entry["subject_id"] = b.get("subject_id")
            normalized_blocks.append(block_entry)

        return {
            "num_blocks": blocks_config.get("num_blocks") or len(normalized_blocks),
            "use_blocks": blocks_config.get("use_blocks", True),
            "questions_per_block": blocks_config.get("questions_per_block"),
            "topology": {"blocks": normalized_blocks},
            "source": "stored_blocks_config",
        }

    @classmethod
    def _build_topology_from_test(cls, test_id: str) -> Dict[str, Any]:
        questions_meta = cls.get_questions_meta(test_id)
        n = len(questions_meta)
        if n == 0:
            return {
                "num_blocks": 0,
                "use_blocks": True,
                "topology": {"blocks": []},
                "source": "empty",
            }

        # Distribuir em até 4 blocos, preferindo divisão por disciplina
        by_subject: Dict[str, List[Dict[str, Any]]] = {}
        subject_order: List[str] = []
        for m in questions_meta:
            key = m.get("subject_name") or "Geral"
            if key not in by_subject:
                by_subject[key] = []
                subject_order.append(key)
            by_subject[key].append(m)

        # Se poucas disciplinas, ainda pode precisar fatiar em colunas de no máx. 22
        MAX_PER_BLOCK = 22
        MAX_BLOCKS = 4
        raw_blocks: List[Tuple[str, List[Dict[str, Any]]]] = []

        for subj in subject_order:
            items = by_subject[subj]
            for i in range(0, len(items), MAX_PER_BLOCK):
                raw_blocks.append((subj, items[i : i + MAX_PER_BLOCK]))

        if len(raw_blocks) > MAX_BLOCKS:
            # Redistribuir igualmente em 4 blocos
            raw_blocks = []
            per = (n + MAX_BLOCKS - 1) // MAX_BLOCKS
            for i in range(0, n, per):
                chunk = questions_meta[i : i + per]
                subj = chunk[0].get("subject_name") or "Geral"
                raw_blocks.append((subj, chunk))
            raw_blocks = raw_blocks[:MAX_BLOCKS]

        blocks = []
        for idx, (subj, items) in enumerate(raw_blocks, start=1):
            blocks.append(
                {
                    "block_id": idx,
                    "subject_name": subj,
                    "questions": [
                        {
                            "q": m["order"],
                            "alternatives": m["alternatives"],
                            "subject_name": m.get("subject_name") or subj,
                        }
                        for m in items
                    ],
                }
            )

        return {
            "num_blocks": len(blocks),
            "use_blocks": True,
            "questions_per_block": max((len(b["questions"]) for b in blocks), default=0),
            "topology": {"blocks": blocks},
            "source": "built_from_test",
        }

    @classmethod
    def get_questions_meta(cls, test_id: str) -> List[Dict[str, Any]]:
        test_questions = (
            TestQuestion.query.filter_by(test_id=test_id)
            .order_by(TestQuestion.order)
            .all()
        )
        result = []
        for idx, tq in enumerate(test_questions, start=1):
            order = tq.order if tq.order is not None else idx
            q = Question.query.get(tq.question_id)
            alts = cls._extract_alternative_letters(q)
            subject_name = None
            subject_id = None
            if q is not None:
                subject_id = q.subject_id
                try:
                    if getattr(q, "subject", None) is not None:
                        subject_name = q.subject.name
                    elif subject_id:
                        from app.models.subject import Subject

                        subj = Subject.query.get(subject_id)
                        if subj:
                            subject_name = subj.name
                except Exception:
                    subject_name = None

            result.append(
                {
                    "order": int(order) if order else idx,
                    "question_id": tq.question_id,
                    "alternatives": alts,
                    "raw_alternatives": getattr(q, "alternatives", None) if q else None,
                    "question_type": getattr(q, "question_type", None) if q else None,
                    "correct_answer": (q.correct_answer.upper() if q and q.correct_answer else None),
                    "subject_id": subject_id,
                    "subject_name": subject_name,
                }
            )
        # Garantir order sequencial 1..N se orders no banco forem 0-based ou esparsos
        orders = [r["order"] for r in result]
        if not orders or min(orders) == 0 or len(set(orders)) != len(orders):
            for i, r in enumerate(result, start=1):
                r["order"] = i
        return result

    # ------------------------------------------------------------------
    # Cartão-resposta (AnswerSheetGabarito sem Test)
    # ------------------------------------------------------------------

    @staticmethod
    def _gabarito_blocks_config(gabarito: AnswerSheetGabarito) -> Dict[str, Any]:
        import json

        bc = gabarito.blocks_config or {}
        if isinstance(bc, str):
            try:
                bc = json.loads(bc)
            except (ValueError, TypeError):
                bc = {}
        return bc if isinstance(bc, dict) else {}

    @staticmethod
    def _gabarito_correct_answers(gabarito: AnswerSheetGabarito) -> Dict[int, str]:
        import json

        raw = gabarito.correct_answers
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except (ValueError, TypeError):
                raw = {}
        out: Dict[int, str] = {}
        for key, value in (raw or {}).items():
            try:
                out[int(key)] = str(value).strip().upper() if value else ""
            except (ValueError, TypeError):
                continue
        return out

    @staticmethod
    def _gabarito_legacy_alternatives(correct_answers: Dict[int, str]) -> List[str]:
        letters = {str(v).strip().upper() for v in (correct_answers or {}).values() if v}
        return ["A", "B", "C", "D", "E"] if "E" in letters else ["A", "B", "C", "D"]

    @classmethod
    def resolve_gabarito_topology(cls, gabarito: AnswerSheetGabarito) -> Dict[str, Any]:
        """Topologia (blocos/questões/alternativas) a partir de blocks_config do cartão."""
        bc = cls._gabarito_blocks_config(gabarito)
        correct_answers = cls._gabarito_correct_answers(gabarito)
        topo = bc.get("topology") or {}
        raw_blocks = topo.get("blocks") if isinstance(topo, dict) else None

        blocks: List[Dict[str, Any]] = []
        for idx, b in enumerate(raw_blocks or [], start=1):
            qs = []
            for q in b.get("questions") or []:
                try:
                    q_num = int(q.get("q"))
                except (TypeError, ValueError):
                    continue
                alts = q.get("alternatives")
                if not isinstance(alts, list) or len(alts) < 2:
                    alts = ["A", "B", "C", "D"]
                entry = {"q": q_num, "alternatives": [str(a).upper() for a in alts]}
                subj = q.get("subject_name") or b.get("subject_name")
                if subj:
                    entry["subject_name"] = subj
                qs.append(entry)
            if not qs:
                continue
            block = {"block_id": b.get("block_id") or idx, "questions": qs}
            if b.get("subject_name"):
                block["subject_name"] = b["subject_name"]
            if b.get("subject_id"):
                block["subject_id"] = b["subject_id"]
            blocks.append(block)

        source = "gabarito_blocks_config"
        if not blocks:
            # Cartões legados sem `topology`: usa `blocks` (start_question/end_question + disciplina)
            # O gerador atual imprime A-D por padrão; cartões com resposta correta E usam A-E.
            legacy_alternatives = cls._gabarito_legacy_alternatives(correct_answers)
            for idx, b in enumerate(bc.get("blocks") or [], start=1):
                if not isinstance(b, dict) or len(blocks) >= 4:
                    continue
                try:
                    start_q = int(b.get("start_question"))
                    end_q = int(b.get("end_question"))
                except (TypeError, ValueError):
                    continue
                if end_q < start_q:
                    continue
                subj = b.get("subject_name")
                block = {
                    "block_id": b.get("block_id") or idx,
                    "questions": [
                        {
                            "q": q,
                            "alternatives": legacy_alternatives,
                            **({"subject_name": subj} if subj else {}),
                        }
                        for q in range(start_q, end_q + 1)
                    ],
                }
                if subj:
                    block["subject_name"] = subj
                if b.get("subject_id"):
                    block["subject_id"] = b["subject_id"]
                blocks.append(block)
            if blocks:
                source = "gabarito_legacy_blocks"
        if not blocks:
            n = int(gabarito.num_questions or 0)
            per = int(bc.get("questions_per_block") or 0) or 22
            per = max(1, min(per, 22))
            source = "gabarito_num_questions"
            for i in range(0, n, per):
                if len(blocks) >= 4:
                    break
                blocks.append(
                    {
                        "block_id": len(blocks) + 1,
                        "questions": [
                            {"q": q, "alternatives": ["A", "B", "C", "D"]}
                            for q in range(i + 1, min(i + per, n) + 1)
                        ],
                    }
                )

        return {
            "num_blocks": len(blocks),
            "use_blocks": True,
            "topology": {"blocks": blocks},
            "source": source,
        }

    @classmethod
    def is_gabarito_scan_compatible(cls, gabarito: AnswerSheetGabarito) -> bool:
        if not cls._gabarito_correct_answers(gabarito):
            return False
        topo = cls.resolve_gabarito_topology(gabarito)
        if topo.get("source") == "gabarito_num_questions":
            return False
        return cls._topology_question_count(topo) > 0

    @classmethod
    def get_gabarito_questions_meta(cls, gabarito: AnswerSheetGabarito) -> List[Dict[str, Any]]:
        correct = cls._gabarito_correct_answers(gabarito)
        topo = cls.resolve_gabarito_topology(gabarito)
        out: List[Dict[str, Any]] = []
        for b in (topo.get("topology") or {}).get("blocks") or []:
            for q in b.get("questions") or []:
                out.append(
                    {
                        "order": q["q"],
                        "question_id": None,
                        "alternatives": q["alternatives"],
                        "correct_answer": correct.get(q["q"]) or None,
                        "subject_id": b.get("subject_id"),
                        "subject_name": q.get("subject_name") or b.get("subject_name"),
                    }
                )
        out.sort(key=lambda m: m["order"])
        return out

    @classmethod
    def get_gabarito_existing_answers(
        cls, gabarito_id: str, student_id: str
    ) -> Dict[str, Optional[str]]:
        from app.models.answerSheetResult import AnswerSheetResult

        row = AnswerSheetResult.query.filter_by(
            gabarito_id=gabarito_id, student_id=student_id
        ).first()
        if not row or not row.detected_answers:
            return {}
        out: Dict[str, Optional[str]] = {}
        for key, value in dict(row.detected_answers).items():
            letter = (str(value).strip().upper() if value else "") or None
            if letter == "INVALID":
                letter = None
            out[str(key)] = letter
        return out

    @classmethod
    def _looks_interactive_payload(cls, raw_alts: Any, qtype: Any = None) -> bool:
        """Detecta ligar colunas / arrastar-soltar / payloads não-OMR no JSON da questão."""
        blob_parts = [str(qtype or "")]
        if isinstance(raw_alts, (dict, list)):
            try:
                import json

                blob_parts.append(json.dumps(raw_alts, ensure_ascii=False).lower())
            except Exception:
                blob_parts.append(str(raw_alts).lower())
        elif raw_alts is not None:
            blob_parts.append(str(raw_alts).lower())
        blob = " ".join(blob_parts).lower()
        markers = (
            "ligar_colunas",
            "ligar-colunas",
            "arrastar_soltar",
            "arrastar-soltar",
            "slotvalues",
            "\"mapping\"",
            "drag_drop",
            "drag-and-drop",
            "match_columns",
        )
        return any(m in blob for m in markers) or any(h in blob for h in NON_OMR_TYPE_HINTS)

    @classmethod
    def _real_alternative_letters(cls, raw_alts: Any) -> List[str]:
        """Letras reais das alternativas; vazio se não houver estrutura MCQ utilizável."""
        if not raw_alts:
            return []
        letters: List[str] = []
        if isinstance(raw_alts, list):
            for i, item in enumerate(raw_alts):
                if isinstance(item, dict):
                    # Payload interativo tipicamente não tem letter A–D simples
                    if any(k in item for k in ("TYPE", "type", "MAPPING", "mapping", "SLOTVALUES", "slotValues")):
                        return []
                    letter = item.get("letter") or item.get("id") or item.get("key")
                    if letter and str(letter).upper()[:1] in ALLOWED_LETTERS:
                        letters.append(str(letter).upper()[:1])
                    elif letter and str(letter).startswith("option"):
                        letters.append(chr(ord("A") + i))
                    elif "text" in item or "label" in item:
                        letters.append(chr(ord("A") + i))
                elif isinstance(item, str) and len(item) == 1 and item.upper() in ALLOWED_LETTERS:
                    letters.append(item.upper())
                elif isinstance(item, str) and item.strip():
                    letters.append(chr(ord("A") + i))
        elif isinstance(raw_alts, dict):
            if any(k in raw_alts for k in ("TYPE", "type", "MAPPING", "SLOTVALUES")):
                return []
        # Dedup preservando ordem
        seen = set()
        out = []
        for L in letters:
            if L not in seen and L in ALLOWED_LETTERS:
                seen.add(L)
                out.append(L)
        return out

    @staticmethod
    def _extract_alternative_letters(question: Optional[Question]) -> List[str]:
        if question is None:
            return ["A", "B", "C", "D"]
        real = PhotoAnswersService._real_alternative_letters(question.alternatives)
        if len(real) >= 2:
            return real
        # Fallback para exibição/topologia quando o tipo já foi validado como MCQ
        return ["A", "B", "C", "D"]

    # ------------------------------------------------------------------
    # Respostas existentes
    # ------------------------------------------------------------------

    @classmethod
    def assert_existing_answers_omr_compatible(
        cls,
        existing: Dict[str, Optional[str]],
    ) -> None:
        """Se já há respostas no formato interativo/subjetivo, a prova não é OMR."""
        if not existing:
            return
        interactive = []
        for order, value in existing.items():
            if value is None:
                continue
            text = str(value)
            low = text.lower()
            if any(
                m in low
                for m in (
                    "ligar_colunas",
                    "arrastar_soltar",
                    "slotvalues",
                    '"type"',
                    "mapping",
                    "data:image/",
                )
            ) or (text.startswith("{") and "TYPE" in text):
                interactive.append(str(order))
        if interactive and len(interactive) >= max(1, len(existing) // 2):
            raise PhotoAnswersIncompatibleError(
                "not_objective_test",
                (
                    "As respostas já registradas nesta avaliação são de questões "
                    "subjetivas/interativas (ex.: ligar colunas, arrastar e soltar), "
                    "não de cartão-resposta com bolhas. "
                    "O escaneamento por foto não se aplica a este tipo de prova."
                ),
                details={"interactive_orders": interactive[:20]},
            )

    @classmethod
    def get_existing_answers(cls, test_id: str, student_id: str) -> Dict[str, Optional[str]]:
        rows = StudentAnswer.query.filter_by(test_id=test_id, student_id=student_id).all()
        if not rows:
            return {}

        tqs = (
            TestQuestion.query.filter_by(test_id=test_id)
            .order_by(TestQuestion.order)
            .all()
        )
        qid_to_order = {}
        for idx, tq in enumerate(tqs, start=1):
            order = tq.order if tq.order is not None else idx
            qid_to_order[tq.question_id] = int(order) if order else idx

        # Deduplicar pela mais recente
        best: Dict[str, StudentAnswer] = {}
        for a in rows:
            prev = best.get(a.question_id)
            if not prev:
                best[a.question_id] = a
                continue
            if (a.answered_at or datetime.min) >= (prev.answered_at or datetime.min):
                best[a.question_id] = a

        out: Dict[str, Optional[str]] = {}
        for qid, ans in best.items():
            order = qid_to_order.get(qid)
            if order is None:
                continue
            val = (ans.answer or "").strip().upper() or None
            out[str(order)] = val
        return out

    # ------------------------------------------------------------------
    # Persistência
    # ------------------------------------------------------------------

    @classmethod
    def save_answers(
        cls,
        test_id: str,
        student_id: str,
        answers: Dict[str, Any],
        overwrite: bool,
        corrected_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        test = Test.query.get(test_id)
        if not test:
            raise LookupError("Prova não encontrada")

        student = Student.query.get(student_id)
        if not student:
            raise LookupError("Aluno não encontrado")

        questions_meta = cls.get_questions_meta(test_id)
        if not questions_meta:
            raise ValueError("A prova não possui questões")

        meta_by_order = {m["order"]: m for m in questions_meta}
        existing = cls.get_existing_answers(test_id, student_id)
        if existing and not overwrite:
            raise FileExistsError("Já existem respostas para este aluno nesta avaliação")

        # Validar payload
        normalized: Dict[int, Optional[str]] = {}
        for key, value in (answers or {}).items():
            try:
                q_num = int(key)
            except (TypeError, ValueError):
                raise ValueError(f"Número de questão inválido: {key}")
            if q_num not in meta_by_order:
                raise ValueError(f"Questão {q_num} não pertence a esta avaliação")
            if value is None or value == "" or str(value).upper() in ("NULL", "NONE", "BLANK", "-"):
                normalized[q_num] = None
                continue
            letter = str(value).strip().upper()
            allowed = set(meta_by_order[q_num]["alternatives"])
            if letter not in allowed:
                raise ValueError(
                    f"Alternativa '{letter}' inválida para a questão {q_num}. "
                    f"Permitidas: {sorted(allowed)}"
                )
            normalized[q_num] = letter

        # Garantir todas as questões (em branco se omitidas)
        for m in questions_meta:
            if m["order"] not in normalized:
                normalized[m["order"]] = None

        try:
            now = datetime.utcnow()
            saved = []
            for q_num, letter in normalized.items():
                meta = meta_by_order[q_num]
                question_id = meta["question_id"]
                correct = meta.get("correct_answer")
                is_correct = None
                if letter and correct:
                    is_correct = letter.upper() == str(correct).upper()

                existing_row = StudentAnswer.query.filter_by(
                    student_id=student_id,
                    test_id=test_id,
                    question_id=question_id,
                ).first()

                answer_text = letter if letter else ""
                if existing_row:
                    existing_row.answer = answer_text
                    existing_row.is_correct = is_correct
                    existing_row.answered_at = now
                    if corrected_by:
                        existing_row.corrected_by = corrected_by
                        existing_row.corrected_at = now
                    # Marca origem via feedback curto (sem migration)
                    tag = "[origem:foto]"
                    fb = existing_row.feedback or ""
                    if tag not in fb:
                        existing_row.feedback = f"{tag} {fb}".strip()
                    row = existing_row
                else:
                    row = StudentAnswer(
                        student_id=student_id,
                        test_id=test_id,
                        question_id=question_id,
                        answer=answer_text,
                        is_correct=is_correct,
                        corrected_by=corrected_by,
                        corrected_at=now if corrected_by else None,
                        feedback="[origem:foto]",
                    )
                    db.session.add(row)

                saved.append(
                    {
                        "question_number": q_num,
                        "question_id": question_id,
                        "answer": letter,
                        "is_correct": is_correct,
                    }
                )

            session_id = cls._ensure_session(test_id, student_id)
            db.session.flush()

            from app.services.evaluation_result_service import EvaluationResultService

            evaluation_result = EvaluationResultService.calculate_and_save_result(
                test_id=test_id,
                student_id=student_id,
                session_id=session_id,
            )

            cls._mark_physical_form_corrected(test_id, student_id)
            db.session.commit()

            logger.info(
                "PhotoAnswers save: test=%s student=%s by=%s answers=%s overwrite=%s",
                test_id,
                student_id,
                corrected_by,
                len(saved),
                overwrite,
            )

            return {
                "saved": True,
                "overwritten": bool(existing),
                "answers_count": len(saved),
                "session_id": session_id,
                "evaluation_result": evaluation_result,
                "saved_answers": saved,
            }
        except Exception:
            db.session.rollback()
            raise

    @classmethod
    def _ensure_session(cls, test_id: str, student_id: str) -> str:
        existing = TestSession.query.filter_by(
            test_id=test_id,
            student_id=student_id,
            status="corrigida",
            user_agent=PHOTO_SCAN_USER_AGENT,
        ).first()
        if existing:
            return existing.id

        # Reutilizar sessão de correção física se existir
        legacy = TestSession.query.filter_by(
            test_id=test_id,
            student_id=student_id,
            status="corrigida",
        ).first()
        if legacy:
            return legacy.id

        session = TestSession(
            id=str(uuid.uuid4()),
            student_id=student_id,
            test_id=test_id,
            time_limit_minutes=None,
            ip_address=None,
            user_agent=PHOTO_SCAN_USER_AGENT,
            status="corrigida",
            started_at=datetime.utcnow(),
            submitted_at=datetime.utcnow(),
        )
        db.session.add(session)
        db.session.flush()
        return session.id

    @classmethod
    def _mark_physical_form_corrected(cls, test_id: str, student_id: str) -> None:
        form = PhysicalTestForm.query.filter_by(
            test_id=test_id, student_id=student_id
        ).first()
        if not form:
            return
        if not form.answer_sheet_sent_at:
            form.answer_sheet_sent_at = datetime.utcnow()
        form.is_corrected = True
        form.corrected_at = datetime.utcnow()
        form.status = "corrigido"
