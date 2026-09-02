# -*- coding: utf-8 -*-
"""Serviço da Leitura Guiada Automática."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import joinedload

from app import db
from app.models.student import Student
from app.afirme_ler.models import (
    ReadingGuidedAutoComprehensionAnswer,
    ReadingGuidedAutoSession,
    ReadingGuidedAutoWord,
    ReadingTextQuestion,
)
from app.afirme_ler.services.auto_evaluation.metrics import (
    ALGORITHM_VERSION,
    EVALUATION_VERSION,
    calculate_comprehension,
    calculate_ica,
    evaluate_reading,
)
from app.afirme_ler.services.auto_evaluation.normalize import tokenize
from app.afirme_ler.services.guided_auto_audio_service import GuidedAutoAudioService
from app.afirme_ler.services.parsing import get_field
from app.afirme_ler.services.reading_text_service import ReadingTextService
from app.afirme_ler.services.stt import get_stt_provider
from app.afirme_ler.services.word_list_service import WordListService

logger = logging.getLogger(__name__)

FORBIDDEN_SCORE_FIELDS = frozenset(
    {
        "score",
        "accuracy",
        "plcm",
        "ica",
        "icaScore",
        "ica_score",
        "calculatedPlcm",
        "calculated_plcm",
        "calculatedAccuracy",
        "calculated_accuracy",
        "wordsRead",
        "words_read",
        "errorsCount",
        "errors_count",
        "precisionLevel",
        "precision_level",
        "fluencyLevel",
        "fluency_level",
        "comprehensionScore",
        "comprehension_score",
    }
)

ALLOWED_STATUSES = frozenset(
    {
        "awaiting_audio",
        "queued",
        "processing",
        "completed",
        "failed",
    }
)

PART_WORDS = "words"
PART_UNCOMMON = "uncommon"
PART_TEXT = "text"


class GuidedAutoSessionService:
    @staticmethod
    def _reject_client_scores(data: dict) -> None:
        present = sorted(FORBIDDEN_SCORE_FIELDS.intersection(data.keys()))
        if present:
            raise ValueError(
                "Campos de resultado não são aceitos do cliente: "
                + ", ".join(present)
                + ". O backend calcula as métricas automaticamente."
            )

    @staticmethod
    def serialize(
        session: ReadingGuidedAutoSession,
        *,
        include_answers: bool = False,
        include_words: bool = False,
        include_audio_url: bool = True,
    ) -> dict:
        audio_url = None
        if include_audio_url and (session.audio_key or session.part_audios):
            audio_url = GuidedAutoAudioService.api_playback_path(session.id)
        return session.to_dict(
            include_answers=include_answers,
            include_words=include_words,
            audio_url=audio_url,
        )

    @staticmethod
    def get_session(
        session_id: str,
        *,
        include_answers: bool = False,
        include_words: bool = False,
    ) -> ReadingGuidedAutoSession:
        options = [joinedload(ReadingGuidedAutoSession.student)]
        if include_answers:
            options.append(joinedload(ReadingGuidedAutoSession.answers))
        if include_words:
            options.append(joinedload(ReadingGuidedAutoSession.words))

        session = (
            ReadingGuidedAutoSession.query.options(*options)
            .filter_by(id=session_id)
            .first()
        )
        if not session:
            raise LookupError("Sessão de leitura guiada automática não encontrada.")
        return session

    @staticmethod
    def list_sessions(filters: dict) -> List[ReadingGuidedAutoSession]:
        query = ReadingGuidedAutoSession.query.options(
            joinedload(ReadingGuidedAutoSession.student)
        )

        student_id = filters.get("studentId") or filters.get("student_id")
        if student_id:
            query = query.filter(ReadingGuidedAutoSession.student_id == str(student_id))

        text_id = filters.get("readingTextId") or filters.get("reading_text_id")
        if text_id:
            query = query.filter(
                ReadingGuidedAutoSession.reading_text_id == str(text_id)
            )

        status = filters.get("status")
        if status:
            normalized = str(status).strip().lower()
            if normalized not in ALLOWED_STATUSES:
                raise ValueError("status inválido.")
            query = query.filter(ReadingGuidedAutoSession.status == normalized)

        limit_raw = filters.get("limit")
        limit = 100
        if limit_raw is not None:
            try:
                limit = max(1, min(500, int(limit_raw)))
            except (TypeError, ValueError) as exc:
                raise ValueError("limit deve ser um inteiro.") from exc

        return (
            query.order_by(ReadingGuidedAutoSession.created_at.desc())
            .limit(limit)
            .all()
        )

    @staticmethod
    def _build_expected_payload(
        user: Dict[str, Any],
        *,
        reading_text_id: Optional[str],
        words_word_list_id: Optional[str],
        uncommon_word_list_id: Optional[str],
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "words": None,
            "uncommon": None,
            "text": None,
            "textTokens": None,
            "configuredParts": [],
        }

        if words_word_list_id:
            word_list = WordListService.get_visible(user, str(words_word_list_id))
            items = [
                str(item).strip()
                for item in (word_list.items or [])
                if str(item).strip()
            ]
            payload["words"] = {
                "wordListId": word_list.id,
                "items": items,
                "tokens": tokenize(" ".join(items)),
            }
            payload["configuredParts"].append(PART_WORDS)

        if uncommon_word_list_id:
            uncommon = WordListService.get_visible(user, str(uncommon_word_list_id))
            items = [
                str(item).strip()
                for item in (uncommon.items or [])
                if str(item).strip()
            ]
            payload["uncommon"] = {
                "wordListId": uncommon.id,
                "items": items,
                "tokens": tokenize(" ".join(items)),
            }
            payload["configuredParts"].append(PART_UNCOMMON)

        if reading_text_id:
            text = ReadingTextService.get_visible_text(user, str(reading_text_id))
            payload["text"] = {
                "readingTextId": text.id,
                "title": text.title,
                "content": text.content,
            }
            payload["textTokens"] = tokenize(text.content or "")
            payload["configuredParts"].append(PART_TEXT)

        if not payload["configuredParts"]:
            raise ValueError(
                "Informe ao menos readingTextId, wordsWordListId ou uncommonWordListId."
            )
        return payload

    @staticmethod
    def create(user: Dict[str, Any], data: dict) -> ReadingGuidedAutoSession:
        GuidedAutoSessionService._reject_client_scores(data)

        student_id = get_field(data, "studentId", "student_id")
        if not student_id:
            raise ValueError("studentId é obrigatório.")

        student = Student.query.get(str(student_id))
        if not student:
            raise LookupError("Aluno não encontrado.")

        reading_text_id = get_field(data, "readingTextId", "reading_text_id")
        words_id = get_field(data, "wordsWordListId", "words_word_list_id")
        uncommon_id = get_field(
            data, "uncommonWordListId", "uncommon_word_list_id"
        )

        expected = GuidedAutoSessionService._build_expected_payload(
            user,
            reading_text_id=str(reading_text_id) if reading_text_id else None,
            words_word_list_id=str(words_id) if words_id else None,
            uncommon_word_list_id=str(uncommon_id) if uncommon_id else None,
        )

        user_id = user.get("id") or user.get("user_id")
        session = ReadingGuidedAutoSession(
            student_id=str(student_id),
            class_id=student.class_id,
            reading_text_id=str(reading_text_id) if reading_text_id else None,
            words_word_list_id=str(words_id) if words_id else None,
            uncommon_word_list_id=str(uncommon_id) if uncommon_id else None,
            expected_payload=expected,
            part_results={},
            status="awaiting_audio",
            algorithm_version=ALGORITHM_VERSION,
            evaluation_version=EVALUATION_VERSION,
            applied_by=user_id,
        )
        db.session.add(session)
        db.session.flush()

        answers_payload = get_field(data, "answers", default=None)
        if answers_payload is not None:
            GuidedAutoSessionService._save_answers(session, answers_payload)

        db.session.commit()
        return GuidedAutoSessionService.get_session(
            session.id, include_answers=True, include_words=False
        )

    @staticmethod
    def configured_parts(session: ReadingGuidedAutoSession) -> List[str]:
        payload = session.expected_payload or {}
        parts = payload.get("configuredParts") or []
        return [str(p) for p in parts]

    @staticmethod
    def resolve_part(
        session: ReadingGuidedAutoSession, part: Optional[str]
    ) -> str:
        configured = GuidedAutoSessionService.configured_parts(session)
        if not configured:
            raise ValueError("Sessão sem partes configuradas.")
        if part:
            normalized = str(part).strip().lower()
            if normalized not in configured:
                raise ValueError(
                    f"part inválida. Configuradas: {', '.join(configured)}"
                )
            return normalized
        if len(configured) == 1:
            return configured[0]
        # Preferência: texto > palavras > pouco comuns
        for preferred in (PART_TEXT, PART_WORDS, PART_UNCOMMON):
            if preferred in configured:
                return preferred
        return configured[0]

    @staticmethod
    def _expected_tokens_for_part(
        session: ReadingGuidedAutoSession, part: str
    ) -> List[str]:
        payload = session.expected_payload or {}
        if part == PART_TEXT:
            return list(payload.get("textTokens") or [])
        if part == PART_WORDS:
            block = payload.get("words") or {}
            return list(block.get("tokens") or [])
        if part == PART_UNCOMMON:
            block = payload.get("uncommon") or {}
            return list(block.get("tokens") or [])
        raise ValueError(f"part desconhecida: {part}")

    @staticmethod
    def enqueue_processing(
        session_id: str,
        *,
        part: str,
        city_id: str,
        duration_hint_seconds: Optional[float] = None,
    ) -> ReadingGuidedAutoSession:
        session = GuidedAutoSessionService.get_session(session_id)
        if session.status == "completed":
            # Reprocessamento de uma parte: volta para queued
            pass
        session.status = "queued"
        session.error_message = None
        db.session.commit()

        from app.afirme_ler.tasks import process_guided_auto_session

        try:
            process_guided_auto_session.delay(
                session_id=session.id,
                part=part,
                city_id=str(city_id),
                duration_hint_seconds=duration_hint_seconds,
            )
        except Exception as exc:
            logger.warning(
                "Falha ao enfileirar Celery; processando sincronamente: %s",
                exc,
            )
            from app.utils.tenant_middleware import (
                city_id_to_schema_name,
                set_search_path,
            )

            set_search_path(city_id_to_schema_name(str(city_id)))
            GuidedAutoSessionService.process_part(
                session.id,
                part=part,
                duration_hint_seconds=duration_hint_seconds,
            )
        return GuidedAutoSessionService.get_session(session.id, include_answers=True)

    @staticmethod
    def process_part(
        session_id: str,
        *,
        part: str,
        duration_hint_seconds: Optional[float] = None,
    ) -> ReadingGuidedAutoSession:
        session = GuidedAutoSessionService.get_session(
            session_id, include_answers=True, include_words=True
        )
        session.status = "processing"
        session.error_message = None
        db.session.commit()

        try:
            part_audios = session.part_audios or {}
            meta = part_audios.get(part)
            if not meta:
                raise ValueError(f"Áudio da parte '{part}' não encontrado.")

            audio_bytes, mime = GuidedAutoAudioService.download_part_audio(
                session, part=part
            )
            stt = get_stt_provider()
            stt_result = stt.transcribe(audio_bytes, mime)

            duration = stt_result.duration_seconds
            if duration is None and duration_hint_seconds is not None:
                duration = float(duration_hint_seconds)

            expected_tokens = GuidedAutoSessionService._expected_tokens_for_part(
                session, part
            )
            content_kind = "word_list" if part in (PART_WORDS, PART_UNCOMMON) else "text"
            metrics = evaluate_reading(
                expected_tokens,
                stt_result.text,
                part=part,
                duration_seconds=duration,
                content_kind=content_kind,
            )

            # Substitui alinhamento da parte
            ReadingGuidedAutoWord.query.filter_by(
                session_id=session.id, part=part
            ).delete(synchronize_session=False)

            for item in metrics.alignment:
                db.session.add(
                    ReadingGuidedAutoWord(
                        session_id=session.id,
                        part=part,
                        position=int(item["position"]),
                        expected_token=item.get("expected_token"),
                        recognized_token=item.get("recognized_token"),
                        similarity=item.get("similarity"),
                        phonetic_expected=item.get("phonetic_expected"),
                        phonetic_recognized=item.get("phonetic_recognized"),
                        match_type=item["match_type"],
                    )
                )

            part_results = dict(session.part_results or {})
            part_results[part] = {
                "wordsRead": metrics.words_read,
                "errorsCount": metrics.errors_count,
                "omittedCount": metrics.omitted_count,
                "extraCount": metrics.extra_count,
                "correctCount": metrics.correct_count,
                "accuracy": metrics.accuracy,
                "plcm": metrics.plcm,
                "precisionLevel": metrics.precision_level,
                "fluencyLevel": metrics.fluency_level,
                "durationSeconds": metrics.duration_seconds,
                "transcript": metrics.transcript,
                "sttProvider": stt_result.provider,
                "sttModel": stt_result.model,
            }
            session.part_results = part_results
            session.transcript_raw = metrics.transcript
            session.stt_provider = stt_result.provider
            session.stt_model = stt_result.model
            session.algorithm_version = ALGORITHM_VERSION
            session.evaluation_version = EVALUATION_VERSION

            GuidedAutoSessionService._refresh_aggregate_metrics(session)

            configured = set(GuidedAutoSessionService.configured_parts(session))
            processed = set(part_results.keys())
            if configured.issubset(processed):
                session.status = "completed"
                session.submitted_at = datetime.utcnow()
            else:
                session.status = "awaiting_audio"

            db.session.commit()
            return GuidedAutoSessionService.get_session(
                session.id, include_answers=True, include_words=True
            )
        except Exception as exc:
            logger.exception(
                "Falha ao processar leitura guiada automática %s part=%s",
                session_id,
                part,
            )
            session = ReadingGuidedAutoSession.query.get(session_id)
            if session:
                session.status = "failed"
                session.error_message = str(exc)
                db.session.commit()
            raise

    @staticmethod
    def _refresh_aggregate_metrics(session: ReadingGuidedAutoSession) -> None:
        part_results = session.part_results or {}
        primary_order = (PART_TEXT, PART_WORDS, PART_UNCOMMON)
        primary = None
        for key in primary_order:
            if key in part_results:
                primary = part_results[key]
                break

        if primary:
            session.words_read = primary.get("wordsRead")
            session.errors_count = primary.get("errorsCount")
            session.omitted_count = primary.get("omittedCount")
            session.extra_count = primary.get("extraCount")
            session.duration_seconds = primary.get("durationSeconds")
            session.calculated_plcm = primary.get("plcm")
            session.calculated_accuracy = primary.get("accuracy")
            session.precision_level = primary.get("precisionLevel")
            session.fluency_level = primary.get("fluencyLevel")

        words_acc = (part_results.get(PART_WORDS) or {}).get("accuracy")
        uncommon_acc = (part_results.get(PART_UNCOMMON) or {}).get("accuracy")
        text_acc = (part_results.get(PART_TEXT) or {}).get("accuracy")
        plcm_for_ica = (part_results.get(PART_TEXT) or {}).get("plcm")
        if plcm_for_ica is None:
            plcm_for_ica = session.calculated_plcm

        ica = calculate_ica(
            accuracy_lista1=words_acc,
            accuracy_lista2=uncommon_acc,
            accuracy_texto=text_acc,
            comprehension=session.comprehension_score,
            plcm=plcm_for_ica,
        )
        if ica:
            session.ica_score = ica["icaScore"]
            session.ica_breakdown = ica
        else:
            session.ica_score = None
            session.ica_breakdown = None

    @staticmethod
    def save_comprehension_answers(
        session_id: str, answers_payload: Any
    ) -> ReadingGuidedAutoSession:
        session = GuidedAutoSessionService.get_session(
            session_id, include_answers=True
        )
        if not session.reading_text_id:
            raise ValueError(
                "Compreensão só é permitida quando a sessão possui readingTextId."
            )
        GuidedAutoSessionService._save_answers(session, answers_payload)
        GuidedAutoSessionService._refresh_aggregate_metrics(session)
        db.session.commit()
        return GuidedAutoSessionService.get_session(
            session.id, include_answers=True, include_words=False
        )

    @staticmethod
    def _save_answers(
        session: ReadingGuidedAutoSession, answers_payload: Any
    ) -> None:
        if answers_payload is None:
            answers_payload = []
        if not isinstance(answers_payload, list):
            raise ValueError("answers deve ser uma lista.")
        if not session.reading_text_id:
            if answers_payload:
                raise ValueError(
                    "answers exige readingTextId na sessão."
                )
            return

        ReadingGuidedAutoComprehensionAnswer.query.filter_by(
            session_id=session.id
        ).delete(synchronize_session=False)

        questions = {
            q.id: q
            for q in ReadingTextQuestion.query.filter_by(
                reading_text_id=session.reading_text_id
            ).all()
        }

        for item in answers_payload:
            if not isinstance(item, dict):
                raise ValueError("Cada resposta deve ser um objeto.")
            question_id = get_field(
                item, "readingTextQuestionId", "reading_text_question_id"
            )
            selected = get_field(item, "selectedOption", "selected_option")
            if question_id is None or selected is None:
                raise ValueError(
                    "Cada resposta deve ter readingTextQuestionId e selectedOption."
                )
            question = questions.get(str(question_id))
            if not question:
                raise ValueError(
                    f"Questão não pertence ao texto da sessão: {question_id}"
                )
            if not isinstance(selected, int):
                try:
                    selected = int(selected)
                except (TypeError, ValueError) as exc:
                    raise ValueError("selectedOption deve ser inteiro.") from exc
            options = question.options if isinstance(question.options, list) else []
            if selected < 0 or selected >= len(options):
                raise ValueError(
                    f"selectedOption inválido para a questão {question_id}."
                )
            is_correct = (
                question.correct_option is not None
                and selected == question.correct_option
            )
            db.session.add(
                ReadingGuidedAutoComprehensionAnswer(
                    session_id=session.id,
                    reading_text_question_id=str(question_id),
                    selected_option=selected,
                    is_correct=is_correct,
                )
            )

        db.session.flush()
        all_answers = ReadingGuidedAutoComprehensionAnswer.query.filter_by(
            session_id=session.id
        ).all()
        total_questions = len(questions)
        correct = sum(1 for a in all_answers if a.is_correct)

        if not answers_payload:
            session.comprehension_correct_count = None
            session.comprehension_total = None
            session.comprehension_score = None
            return

        session.comprehension_correct_count = correct
        session.comprehension_total = (
            total_questions if total_questions else len(all_answers)
        )
        session.comprehension_score = calculate_comprehension(
            correct, session.comprehension_total or 0
        )

    @staticmethod
    def delete(session_id: str) -> None:
        session = GuidedAutoSessionService.get_session(session_id)
        GuidedAutoAudioService.delete_all_best_effort(session)
        db.session.delete(session)
        db.session.commit()
