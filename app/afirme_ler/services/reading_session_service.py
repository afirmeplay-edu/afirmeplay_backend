# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import joinedload

from app import db
from app.models.student import Student
from app.afirme_ler.models import (
    ReadingComprehensionAnswer,
    ReadingEvaluationSession,
    ReadingTextQuestion,
)
from app.afirme_ler.services.fluency_metrics_service import (
    build_fluency_record,
    refresh_ica_in_fluency_data,
)
from app.afirme_ler.services.parsing import get_field
from app.afirme_ler.services.reading_evaluation_service import ReadingEvaluationService


class ReadingSessionService:
    @staticmethod
    def _apply_fluency_columns(session: ReadingEvaluationSession, flat: dict) -> None:
        session.calculated_plcm = flat.get("calculated_plcm")
        session.calculated_accuracy = flat.get("calculated_accuracy")
        session.precision_level = flat.get("precision_level")
        session.fluency_level = flat.get("fluency_level")
        session.ica_score = flat.get("ica_score")
        session.ica_breakdown = flat.get("ica_breakdown")
        if flat.get("prosody_level") is not None:
            session.prosody_level = flat.get("prosody_level")

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
    def create_or_get_session(
        evaluation_id: str,
        student_id: str,
        class_id: Optional[str] = None,
    ) -> ReadingEvaluationSession:
        evaluation = ReadingEvaluationService.get_evaluation(evaluation_id)
        if evaluation.status in ("concluida", "cancelada"):
            raise ValueError("Avaliação já encerrada.")

        student = Student.query.get(student_id)
        if not student:
            raise LookupError("Aluno não encontrado.")

        session = (
            ReadingEvaluationSession.query.options(joinedload(ReadingEvaluationSession.student))
            .filter_by(reading_evaluation_id=evaluation.id, student_id=str(student.id))
            .filter(ReadingEvaluationSession.status.in_(("pendente", "em_andamento")))
            .order_by(ReadingEvaluationSession.created_at.desc())
            .first()
        )
        if not session:
            session = ReadingEvaluationSession(
                reading_evaluation_id=evaluation.id,
                student_id=str(student.id),
                class_id=class_id or student.class_id,
                status="pendente",
            )
            db.session.add(session)

        if evaluation.status == "rascunho":
            evaluation.status = "agendada"

        db.session.commit()
        return ReadingSessionService.get_session(evaluation.id, session.id)

    @staticmethod
    def serialize_for_aplicador(session: ReadingEvaluationSession) -> dict:
        evaluation = session.evaluation or ReadingEvaluationService.get_evaluation(
            session.reading_evaluation_id
        )
        data = session.to_dict()
        data.update(
            {
                "evaluationId": evaluation.id,
                "readingTextId": evaluation.reading_text_id,
                "wordsWordListId": evaluation.words_word_list_id,
                "knownWordListId": evaluation.words_word_list_id,
                "uncommonWordListId": evaluation.uncommon_word_list_id,
                "schoolId": (evaluation.school_ids or [None])[0]
                if isinstance(evaluation.school_ids, list) and evaluation.school_ids
                else None,
                "caderno": "A",
            }
        )
        return data

    @staticmethod
    def start_session(
        user: Dict[str, Any],
        evaluation_id: str,
        session_id: str,
    ) -> ReadingEvaluationSession:
        evaluation = ReadingEvaluationService.get_evaluation(evaluation_id)
        if evaluation.status == "rascunho":
            evaluation.status = "agendada"
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
        if evaluation.assessment_type not in (
            "fluencia",
            "completa",
            "entrada",
            "formativa",
            "saida",
        ):
            raise ValueError("Esta avaliação não inclui fluência.")

        session = ReadingSessionService.get_session(evaluation_id, session_id)
        if session.status not in ("em_andamento", "pendente"):
            raise ValueError("Sessão não está em andamento.")

        if not isinstance(fluency_data, dict):
            raise ValueError("fluencyData deve ser um objeto JSON.")

        from sqlalchemy.orm.attributes import flag_modified

        record, flat = build_fluency_record(
            fluency_data,
            comprehension_score=session.comprehension_score,
            existing=session.fluency_data
            if isinstance(session.fluency_data, dict)
            else None,
        )
        session.fluency_data = record
        flag_modified(session, "fluency_data")
        ReadingSessionService._apply_fluency_columns(session, flat)

        if session.status == "pendente":
            session.status = "em_andamento"
            session.started_at = session.started_at or datetime.utcnow()
        db.session.commit()
        return ReadingSessionService.get_session(evaluation_id, session_id)

    @staticmethod
    def save_comprehension_answers(
        evaluation_id: str,
        session_id: str,
        answers_payload: List[dict],
    ) -> ReadingEvaluationSession:
        evaluation = ReadingEvaluationService.get_evaluation(evaluation_id)
        if evaluation.assessment_type not in (
            "compreensao",
            "completa",
            "entrada",
            "formativa",
            "saida",
        ):
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
                try:
                    selected = int(selected)
                except (TypeError, ValueError) as exc:
                    raise ValueError("selectedOption deve ser inteiro.") from exc
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
            round((correct / total_questions) * 100, 2) if total_questions else 0.0
        )

        # Recalcula ICA se já houver fluência persistida
        updated_fluency, flat = refresh_ica_in_fluency_data(
            session.fluency_data,
            comprehension_score=session.comprehension_score,
        )
        if updated_fluency is not None:
            session.fluency_data = updated_fluency
            ReadingSessionService._apply_fluency_columns(session, flat)

        db.session.commit()
        return ReadingSessionService.get_session(
            evaluation_id, session_id, include_answers=True
        )

    @staticmethod
    def build_report(evaluation_id: str, session_id: str) -> dict:
        """Relatório consolidado (Leiturômetro) da sessão."""
        evaluation = ReadingEvaluationService.get_evaluation(evaluation_id)
        session = ReadingSessionService.get_session(
            evaluation_id, session_id, include_answers=True
        )
        fluency = session.fluency_data if isinstance(session.fluency_data, dict) else {}
        metrics = fluency.get("metrics") if isinstance(fluency.get("metrics"), dict) else {}

        return {
            "evaluationId": evaluation.id,
            "evaluationTitle": evaluation.title,
            "assessmentType": evaluation.assessment_type,
            "sessionId": session.id,
            "studentId": session.student_id,
            "studentName": session.student.name if session.student else None,
            "classId": str(session.class_id) if session.class_id else None,
            "status": session.status,
            "readingTextId": evaluation.reading_text_id,
            "wordsWordListId": evaluation.words_word_list_id,
            "uncommonWordListId": evaluation.uncommon_word_list_id,
            "q1": fluency.get("q1"),
            "q2": fluency.get("q2"),
            "q3": fluency.get("q3"),
            "prosodyLevel": session.prosody_level or fluency.get("prosodyLevel"),
            "caderno": fluency.get("caderno"),
            "notReadReason": fluency.get("notReadReason"),
            "extras": fluency.get("extras") or {},
            "comprehension": {
                "correctCount": session.comprehension_correct_count,
                "total": session.comprehension_total,
                "score": session.comprehension_score,
                "answers": [a.to_dict() for a in (session.answers or [])],
            },
            "calculatedPlcm": session.calculated_plcm
            if session.calculated_plcm is not None
            else metrics.get("calculatedPlcm"),
            "calculatedAccuracy": session.calculated_accuracy
            if session.calculated_accuracy is not None
            else metrics.get("calculatedAccuracy"),
            "precisionLevel": session.precision_level or metrics.get("precisionLevel"),
            "fluencyLevel": session.fluency_level or metrics.get("fluencyLevel"),
            "icaScore": session.ica_score
            if session.ica_score is not None
            else metrics.get("icaScore"),
            "icaBreakdown": session.ica_breakdown or metrics.get("icaBreakdown"),
            "leiturimetroLevel": (
                (session.ica_breakdown or {}).get("leiturimetroLevel")
                if isinstance(session.ica_breakdown, dict)
                else None
            )
            or metrics.get("leiturimetroLevel"),
            "startedAt": session.started_at.isoformat() if session.started_at else None,
            "submittedAt": session.submitted_at.isoformat() if session.submitted_at else None,
        }

    @staticmethod
    def finalize_session(evaluation_id: str, session_id: str) -> ReadingEvaluationSession:
        session = ReadingSessionService.get_session(
            evaluation_id, session_id, include_answers=True
        )
        if session.status == "finalizada":
            return session
        if session.status not in ("em_andamento", "pendente"):
            raise ValueError("Sessão não pode ser finalizada.")

        from sqlalchemy.orm.attributes import flag_modified

        updated_fluency, flat = refresh_ica_in_fluency_data(
            session.fluency_data,
            comprehension_score=session.comprehension_score,
        )
        if updated_fluency is not None:
            session.fluency_data = updated_fluency
            flag_modified(session, "fluency_data")
            ReadingSessionService._apply_fluency_columns(session, flat)

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
