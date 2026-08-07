# -*- coding: utf-8 -*-
"""Serviço de sessões de Leitura Guiada (1 aluno + 1 texto)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from sqlalchemy.orm import joinedload

from app import db
from app.models.student import Student
from app.afirme_ler.models import (
    ReadingGuidedComprehensionAnswer,
    ReadingGuidedSession,
    ReadingTextQuestion,
)
from app.afirme_ler.services.guided_audio_service import GuidedAudioService
from app.afirme_ler.services.parsing import (
    calculate_guided_metrics,
    get_field,
    validate_guided_session_status,
    validate_prosody_level,
)
from app.afirme_ler.services.reading_text_service import ReadingTextService


class GuidedSessionService:
    @staticmethod
    def _parse_non_negative_int(value: Any, field_name: str) -> int:
        if value is None:
            raise ValueError(f"{field_name} é obrigatório.")
        try:
            parsed = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{field_name} deve ser um inteiro.") from exc
        if parsed < 0:
            raise ValueError(f"{field_name} não pode ser negativo.")
        return parsed

    @staticmethod
    def serialize(
        session: ReadingGuidedSession,
        *,
        include_answers: bool = False,
        include_audio_url: bool = True,
    ) -> dict:
        audio_url = None
        if include_audio_url and session.audio_key:
            audio_url = GuidedAudioService.api_playback_path(session.id)
        return session.to_dict(include_answers=include_answers, audio_url=audio_url)

    @staticmethod
    def get_session(
        session_id: str,
        *,
        include_answers: bool = False,
    ) -> ReadingGuidedSession:
        options = [joinedload(ReadingGuidedSession.student)]
        if include_answers:
            options.append(joinedload(ReadingGuidedSession.answers))

        session = (
            ReadingGuidedSession.query.options(*options)
            .filter_by(id=session_id)
            .first()
        )
        if not session:
            raise LookupError("Sessão de leitura guiada não encontrada.")
        return session

    @staticmethod
    def list_sessions(filters: dict) -> List[ReadingGuidedSession]:
        query = ReadingGuidedSession.query.options(
            joinedload(ReadingGuidedSession.student)
        )

        student_id = filters.get("studentId") or filters.get("student_id")
        if student_id:
            query = query.filter(ReadingGuidedSession.student_id == str(student_id))

        text_id = filters.get("readingTextId") or filters.get("reading_text_id")
        if text_id:
            query = query.filter(ReadingGuidedSession.reading_text_id == str(text_id))

        status = filters.get("status")
        if status:
            query = query.filter(
                ReadingGuidedSession.status == validate_guided_session_status(status)
            )

        limit_raw = filters.get("limit")
        limit = 100
        if limit_raw is not None:
            try:
                limit = max(1, min(500, int(limit_raw)))
            except (TypeError, ValueError) as exc:
                raise ValueError("limit deve ser um inteiro.") from exc

        return (
            query.order_by(ReadingGuidedSession.created_at.desc())
            .limit(limit)
            .all()
        )

    @staticmethod
    def create(user: Dict[str, Any], data: dict) -> ReadingGuidedSession:
        student_id = get_field(data, "studentId", "student_id")
        reading_text_id = get_field(data, "readingTextId", "reading_text_id")
        if not student_id:
            raise ValueError("studentId é obrigatório.")
        if not reading_text_id:
            raise ValueError("readingTextId é obrigatório.")

        student = Student.query.get(str(student_id))
        if not student:
            raise LookupError("Aluno não encontrado.")

        ReadingTextService.get_visible_text(user, str(reading_text_id))

        words_read = GuidedSessionService._parse_non_negative_int(
            get_field(data, "wordsRead", "words_read"), "wordsRead"
        )
        reading_time_seconds = GuidedSessionService._parse_non_negative_int(
            get_field(data, "readingTimeSeconds", "reading_time_seconds"),
            "readingTimeSeconds",
        )
        errors_count = GuidedSessionService._parse_non_negative_int(
            get_field(data, "errorsCount", "errors_count", default=0),
            "errorsCount",
        )
        if errors_count > words_read:
            raise ValueError("errorsCount não pode ser maior que wordsRead.")

        prosody_level = validate_prosody_level(
            get_field(data, "prosodyLevel", "prosody_level")
        )

        plcm, accuracy = calculate_guided_metrics(
            words_read, errors_count, reading_time_seconds
        )
        user_id = user.get("id") or user.get("user_id")

        session = ReadingGuidedSession(
            student_id=str(student_id),
            class_id=student.class_id,
            reading_text_id=str(reading_text_id),
            words_read=words_read,
            reading_time_seconds=reading_time_seconds,
            errors_count=errors_count,
            prosody_level=prosody_level,
            status="finalizada",
            calculated_plcm=plcm,
            calculated_accuracy=accuracy,
            applied_by=user_id,
            submitted_at=datetime.utcnow(),
        )
        db.session.add(session)
        db.session.flush()

        answers_payload = get_field(data, "answers", default=[])
        GuidedSessionService._save_answers(session, answers_payload)

        db.session.commit()
        return GuidedSessionService.get_session(session.id, include_answers=True)

    @staticmethod
    def _save_answers(session: ReadingGuidedSession, answers_payload: Any) -> None:
        if answers_payload is None:
            answers_payload = []
        if not isinstance(answers_payload, list):
            raise ValueError("answers deve ser uma lista.")

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
                raise ValueError(f"selectedOption inválido para a questão {question_id}.")

            is_correct = (
                question.correct_option is not None
                and selected == question.correct_option
            )
            db.session.add(
                ReadingGuidedComprehensionAnswer(
                    session_id=session.id,
                    reading_text_question_id=str(question_id),
                    selected_option=selected,
                    is_correct=is_correct,
                )
            )

        db.session.flush()
        all_answers = ReadingGuidedComprehensionAnswer.query.filter_by(
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
        session.comprehension_total = total_questions if total_questions else len(all_answers)
        if session.comprehension_total:
            session.comprehension_score = round(
                (correct / session.comprehension_total) * 100, 2
            )
        else:
            session.comprehension_score = 0.0

    @staticmethod
    def delete(session_id: str) -> None:
        session = GuidedSessionService.get_session(session_id)
        GuidedAudioService.delete_audio_best_effort(
            session.audio_bucket, session.audio_key
        )
        db.session.delete(session)
        db.session.commit()
