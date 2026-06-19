# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from sqlalchemy.orm import joinedload

from app import db
from app.afirme_ler.models import (
    ReadingComprehensionAnswer,
    ReadingEvaluationSession,
    ReadingTextQuestion,
)
from app.afirme_ler.services.parsing import get_field
from app.afirme_ler.services.reading_evaluation_service import ReadingEvaluationService


class ReadingSessionService:
    @staticmethod
    def list_sessions(evaluation_id: str) -> List[ReadingEvaluationSession]:
        ReadingEvaluationService.get_evaluation(evaluation_id)
        return (
            ReadingEvaluationSession.query.options(joinedload(ReadingEvaluationSession.student))
            .filter_by(reading_evaluation_id=evaluation_id)
            .order_by(ReadingEvaluationSession.created_at.asc())
            .all()
        )

    @staticmethod
    def get_session(evaluation_id: str, session_id: str, *, include_answers=False):
        options = [joinedload(ReadingEvaluationSession.student)]
        if include_answers:
            options.append(joinedload(ReadingEvaluationSession.answers))

        session = (
            ReadingEvaluationSession.query.options(*options)
            .filter_by(id=session_id, reading_evaluation_id=evaluation_id)
            .first()
        )
        if not session:
            raise LookupError("Sessão de avaliação não encontrada.")
        return session

    @staticmethod
    def start_session(
        user: Dict[str, Any],
        evaluation_id: str,
        session_id: str,
    ) -> ReadingEvaluationSession:
        evaluation = ReadingEvaluationService.get_evaluation(evaluation_id)
        if evaluation.status not in ("agendada", "em_andamento"):
            raise ValueError("Avaliação não está disponível para aplicação.")

        session = ReadingSessionService.get_session(evaluation_id, session_id)
        if session.status == "finalizada":
            raise ValueError("Sessão já finalizada.")
        if session.status == "ausente":
            raise ValueError("Sessão marcada como ausente.")

        session.status = "em_andamento"
        session.started_at = session.started_at or datetime.utcnow()
        session.applied_by = user.get("id") or user.get("user_id")
        if evaluation.status == "agendada":
            evaluation.status = "em_andamento"
        db.session.commit()
        return ReadingSessionService.get_session(evaluation_id, session_id)

    @staticmethod
    def save_fluency(
        evaluation_id: str,
        session_id: str,
        fluency_data: Any,
    ) -> ReadingEvaluationSession:
        evaluation = ReadingEvaluationService.get_evaluation(evaluation_id)
        if evaluation.assessment_type not in ("fluencia", "completa"):
            raise ValueError("Esta avaliação não inclui fluência.")

        session = ReadingSessionService.get_session(evaluation_id, session_id)
        if session.status not in ("em_andamento", "pendente"):
            raise ValueError("Sessão não está em andamento.")

        if not isinstance(fluency_data, dict):
            raise ValueError("fluencyData deve ser um objeto JSON.")

        session.fluency_data = fluency_data
        if session.status == "pendente":
            session.status = "em_andamento"
            session.started_at = session.started_at or datetime.utcnow()
        db.session.commit()
        return session

    @staticmethod
    def save_comprehension_answers(
        evaluation_id: str,
        session_id: str,
        answers_payload: List[dict],
    ) -> ReadingEvaluationSession:
        evaluation = ReadingEvaluationService.get_evaluation(evaluation_id)
        if evaluation.assessment_type not in ("compreensao", "completa"):
            raise ValueError("Esta avaliação não inclui compreensão.")

        session = ReadingSessionService.get_session(
            evaluation_id, session_id, include_answers=True
        )
        if not isinstance(answers_payload, list) or not answers_payload:
            raise ValueError("Informe ao menos uma resposta.")

        questions = {
            q.id: q
            for q in ReadingTextQuestion.query.filter_by(
                reading_text_id=evaluation.reading_text_id
            ).all()
        }

        for item in answers_payload:
            question_id = get_field(item, "readingTextQuestionId", "reading_text_question_id")
            selected = get_field(item, "selectedOption", "selected_option")
            if question_id is None or selected is None:
                raise ValueError("Cada resposta deve ter readingTextQuestionId e selectedOption.")
            question = questions.get(str(question_id))
            if not question:
                raise ValueError(f"Questão não pertence ao texto da avaliação: {question_id}")
            if not isinstance(selected, int):
                raise ValueError("selectedOption deve ser inteiro.")
            options = question.options if isinstance(question.options, list) else []
            if selected < 0 or selected >= len(options):
                raise ValueError(f"selectedOption inválido para a questão {question_id}.")

            is_correct = (
                question.correct_option is not None and selected == question.correct_option
            )
            existing = ReadingComprehensionAnswer.query.filter_by(
                session_id=session.id,
                reading_text_question_id=str(question_id),
            ).first()
            if existing:
                existing.selected_option = selected
                existing.is_correct = is_correct
            else:
                db.session.add(
                    ReadingComprehensionAnswer(
                        session_id=session.id,
                        reading_text_question_id=str(question_id),
                        selected_option=selected,
                        is_correct=is_correct,
                    )
                )

        db.session.flush()
        all_answers = ReadingComprehensionAnswer.query.filter_by(session_id=session.id).all()
        total_questions = len(questions)
        correct = sum(1 for a in all_answers if a.is_correct)
        session.comprehension_correct_count = correct
        session.comprehension_total = total_questions
        session.comprehension_score = (
            (correct / total_questions) * 100 if total_questions else 0.0
        )
        db.session.commit()
        return ReadingSessionService.get_session(
            evaluation_id, session_id, include_answers=True
        )

    @staticmethod
    def finalize_session(evaluation_id: str, session_id: str) -> ReadingEvaluationSession:
        session = ReadingSessionService.get_session(
            evaluation_id, session_id, include_answers=True
        )
        if session.status == "finalizada":
            return session
        if session.status not in ("em_andamento", "pendente"):
            raise ValueError("Sessão não pode ser finalizada.")

        session.status = "finalizada"
        session.submitted_at = datetime.utcnow()
        db.session.commit()

        pending = ReadingEvaluationSession.query.filter(
            ReadingEvaluationSession.reading_evaluation_id == evaluation_id,
            ReadingEvaluationSession.status.in_(("pendente", "em_andamento")),
        ).count()
        if pending == 0:
            evaluation = ReadingEvaluationService.get_evaluation(evaluation_id)
            evaluation.status = "concluida"
            db.session.commit()

        return session

    @staticmethod
    def mark_absent(evaluation_id: str, session_id: str) -> ReadingEvaluationSession:
        session = ReadingSessionService.get_session(evaluation_id, session_id)
        if session.status == "finalizada":
            raise ValueError("Sessão já finalizada.")
        session.status = "ausente"
        session.submitted_at = datetime.utcnow()
        db.session.commit()
        return session
