# -*- coding: utf-8 -*-
"""Aplicação de Fluência Leitora amarrada a uma avaliação já criada."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import joinedload
from sqlalchemy.orm.attributes import flag_modified

from app import db
from app.models.student import Student
from app.models.studentClass import Class
from app.afirme_ler.models import (
    ReadingFluencyComprehensionAnswer,
    ReadingFluencySession,
    ReadingTextQuestion,
)
from app.afirme_ler.services.fluency_audio_service import FluencyAudioService
from app.afirme_ler.services.fluency_metrics_service import (
    build_fluency_record,
    refresh_ica_in_fluency_data,
)
from app.afirme_ler.services.parsing import get_field
from app.afirme_ler.services.reading_evaluation_service import ReadingEvaluationService


class FluencyApplicationConflict(Exception):
    """Aluno já possui aplicação finalizada nesta avaliação."""

    def __init__(self, message: str, *, session_id: str, status: str):
        super().__init__(message)
        self.session_id = session_id
        self.status = status


class FluencySessionService:
    @staticmethod
    def _apply_fluency_columns(session: ReadingFluencySession, flat: dict) -> None:
        session.calculated_plcm = flat.get("calculated_plcm")
        session.calculated_accuracy = flat.get("calculated_accuracy")
        session.precision_level = flat.get("precision_level")
        session.fluency_level = flat.get("fluency_level")
        session.ica_score = flat.get("ica_score")
        session.ica_breakdown = flat.get("ica_breakdown")
        if flat.get("prosody_level") is not None:
            session.prosody_level = flat.get("prosody_level")

    @staticmethod
    def _parse_uuid(value: Any, field_name: str) -> Optional[UUID]:
        if value is None or value == "":
            return None
        try:
            return UUID(str(value))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{field_name} deve ser um UUID válido.") from exc

    @staticmethod
    def serialize(
        session: ReadingFluencySession,
        *,
        include_answers: bool = False,
        include_audio_urls: bool = True,
    ) -> dict:
        audio_urls = {}
        if include_audio_urls:
            summary = FluencyAudioService.part_audio_summary(session)
            audio_urls = {
                part: meta.get("audioUrl")
                for part, meta in summary.items()
                if meta.get("hasAudio")
            }
        return session.to_dict(
            include_answers=include_answers, audio_urls=audio_urls
        )

    @staticmethod
    def get_session(
        session_id: str,
        *,
        include_answers: bool = False,
    ) -> ReadingFluencySession:
        options = [
            joinedload(ReadingFluencySession.student),
            joinedload(ReadingFluencySession.evaluation),
        ]
        if include_answers:
            options.append(joinedload(ReadingFluencySession.answers))

        session = (
            ReadingFluencySession.query.options(*options)
            .filter_by(id=session_id)
            .first()
        )
        if not session:
            raise LookupError("Sessão de fluência não encontrada.")
        return session

    @staticmethod
    def assert_can_access(
        user: Dict[str, Any],
        session: ReadingFluencySession,
        *,
        mutate: bool = False,
    ) -> None:
        if session.reading_evaluation_id:
            evaluation = session.evaluation
            if evaluation is None:
                evaluation = ReadingEvaluationService.get_evaluation(
                    session.reading_evaluation_id
                )
            if mutate:
                ReadingEvaluationService.assert_can_apply(user, evaluation)
            else:
                ReadingEvaluationService.assert_can_view(user, evaluation)
            return
        uid = user.get("id") or user.get("user_id")
        if uid and str(session.applied_by) == str(uid):
            return
        raise PermissionError("Você não tem permissão para acessar esta sessão.")

    @staticmethod
    def create(user: Dict[str, Any], data: dict) -> ReadingFluencySession:
        evaluation_id = get_field(data, "evaluationId", "evaluation_id")
        if not evaluation_id:
            raise ValueError("evaluationId é obrigatório.")

        evaluation = ReadingEvaluationService.get_evaluation(str(evaluation_id))
        ReadingEvaluationService.assert_can_apply(user, evaluation)
        if evaluation.status in ("concluida", "cancelada"):
            raise ValueError("Avaliação já encerrada.")

        student_id = get_field(data, "studentId", "student_id")
        if not student_id:
            raise ValueError("studentId é obrigatório.")

        student = Student.query.get(str(student_id))
        if not student:
            raise LookupError("Aluno não encontrado.")
        ReadingEvaluationService.assert_student_in_scope(evaluation, student)

        existing_sessions = (
            ReadingFluencySession.query.options(
                joinedload(ReadingFluencySession.student),
                joinedload(ReadingFluencySession.evaluation),
            )
            .filter_by(
                reading_evaluation_id=evaluation.id,
                student_id=str(student_id),
            )
            .all()
        )
        in_progress = [
            session
            for session in existing_sessions
            if session.status == "em_andamento"
        ]
        if in_progress:
            return in_progress[0]
        finalized = [
            session
            for session in existing_sessions
            if session.status == "finalizada"
        ]
        if finalized:
            latest = max(
                finalized,
                key=lambda session: session.submitted_at
                or session.updated_at
                or session.created_at
                or datetime.min,
            )
            raise FluencyApplicationConflict(
                "Este aluno já possui aplicação finalizada nesta avaliação.",
                session_id=latest.id,
                status=latest.status,
            )

        class_id_raw = get_field(data, "classId", "class_id")
        class_id = FluencySessionService._parse_uuid(class_id_raw, "classId")
        if class_id is None and student.class_id:
            class_id = student.class_id

        school_id = get_field(data, "schoolId", "school_id")
        if school_id is not None:
            school_id = str(school_id)
        elif class_id:
            klass = Class.query.get(class_id)
            if klass:
                school_id = klass.school_id
        if school_id is None and student.school_id:
            school_id = str(student.school_id)

        caderno = get_field(data, "caderno", default="A") or "A"
        caderno = str(caderno).strip().upper() or "A"

        user_id = user.get("id") or user.get("user_id")
        now = datetime.utcnow()
        session = ReadingFluencySession(
            reading_evaluation_id=evaluation.id,
            student_id=str(student_id),
            class_id=class_id,
            school_id=school_id,
            reading_text_id=str(evaluation.reading_text_id),
            words_word_list_id=evaluation.words_word_list_id,
            uncommon_word_list_id=evaluation.uncommon_word_list_id,
            caderno=caderno,
            status="em_andamento",
            fluency_data={
                "kind": "FLUENCY",
                "caderno": caderno,
                "q1": None,
                "q2": None,
                "q3": None,
                "extras": {},
            },
            part_audios={},
            started_at=now,
            applied_by=user_id,
        )
        db.session.add(session)
        if evaluation.status in ("rascunho", "agendada"):
            evaluation.status = "em_andamento"
        db.session.commit()
        return FluencySessionService.get_session(session.id, include_answers=True)

    @staticmethod
    def save_fluency(
        session_id: str,
        fluency_data: Any,
    ) -> ReadingFluencySession:
        session = FluencySessionService.get_session(session_id)
        if session.status not in ("em_andamento",):
            raise ValueError("Sessão não está em andamento.")

        if not isinstance(fluency_data, dict):
            raise ValueError("fluencyData deve ser um objeto JSON.")

        # Garante caderno da sessão no payload se omitido
        if "caderno" not in fluency_data and session.caderno:
            fluency_data = {**fluency_data, "caderno": session.caderno}

        record, flat = build_fluency_record(
            fluency_data,
            comprehension_score=session.comprehension_score,
            existing=session.fluency_data
            if isinstance(session.fluency_data, dict)
            else None,
        )
        session.fluency_data = record
        flag_modified(session, "fluency_data")
        FluencySessionService._apply_fluency_columns(session, flat)

        if record.get("caderno"):
            session.caderno = str(record["caderno"])

        db.session.commit()
        return FluencySessionService.get_session(session_id, include_answers=True)

    @staticmethod
    def save_comprehension_answers(
        session_id: str,
        answers_payload: List[dict],
    ) -> ReadingFluencySession:
        session = FluencySessionService.get_session(
            session_id, include_answers=True
        )
        if session.status not in ("em_andamento",):
            raise ValueError("Sessão não está em andamento.")
        if not isinstance(answers_payload, list) or not answers_payload:
            raise ValueError("Informe ao menos uma resposta.")

        questions = {
            q.id: q
            for q in ReadingTextQuestion.query.filter_by(
                reading_text_id=session.reading_text_id
            ).all()
        }

        for item in answers_payload:
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
            existing = ReadingFluencyComprehensionAnswer.query.filter_by(
                session_id=session.id,
                reading_text_question_id=str(question_id),
            ).first()
            if existing:
                existing.selected_option = selected
                existing.is_correct = is_correct
            else:
                db.session.add(
                    ReadingFluencyComprehensionAnswer(
                        session_id=session.id,
                        reading_text_question_id=str(question_id),
                        selected_option=selected,
                        is_correct=is_correct,
                    )
                )

        db.session.flush()
        all_answers = ReadingFluencyComprehensionAnswer.query.filter_by(
            session_id=session.id
        ).all()
        total_questions = len(questions)
        correct = sum(1 for a in all_answers if a.is_correct)
        session.comprehension_correct_count = correct
        session.comprehension_total = total_questions
        session.comprehension_score = (
            round((correct / total_questions) * 100, 2) if total_questions else 0.0
        )

        updated_fluency, flat = refresh_ica_in_fluency_data(
            session.fluency_data,
            comprehension_score=session.comprehension_score,
        )
        if updated_fluency is not None:
            session.fluency_data = updated_fluency
            flag_modified(session, "fluency_data")
            FluencySessionService._apply_fluency_columns(session, flat)

        db.session.commit()
        return FluencySessionService.get_session(
            session_id, include_answers=True
        )

    @staticmethod
    def build_report(session_id: str) -> dict:
        session = FluencySessionService.get_session(
            session_id, include_answers=True
        )
        fluency = (
            session.fluency_data if isinstance(session.fluency_data, dict) else {}
        )
        metrics = (
            fluency.get("metrics")
            if isinstance(fluency.get("metrics"), dict)
            else {}
        )
        audio = FluencyAudioService.part_audio_summary(session)

        def _with_audio(part_key: str, part_data: Any) -> Any:
            base = dict(part_data) if isinstance(part_data, dict) else {}
            audio_meta = audio.get(part_key) or {"hasAudio": False}
            base["hasAudio"] = audio_meta.get("hasAudio", False)
            if audio_meta.get("audioUrl"):
                base["audioUrl"] = audio_meta["audioUrl"]
            return base if part_data is not None or audio_meta.get("hasAudio") else None

        ica_breakdown = session.ica_breakdown or metrics.get("icaBreakdown")
        leiturimetro = None
        if isinstance(ica_breakdown, dict):
            leiturimetro = ica_breakdown.get("leiturimetroLevel")
        if leiturimetro is None:
            leiturimetro = metrics.get("leiturimetroLevel")

        return {
            "sessionId": session.id,
            "evaluationId": session.reading_evaluation_id,
            "evaluationKind": (
                session.evaluation.evaluation_kind if session.evaluation else None
            ),
            "studentId": session.student_id,
            "studentName": session.student.name if session.student else None,
            "classId": str(session.class_id) if session.class_id else None,
            "schoolId": str(session.school_id) if session.school_id else None,
            "status": session.status,
            "readingTextId": session.reading_text_id,
            "knownWordListId": session.words_word_list_id,
            "wordsWordListId": session.words_word_list_id,
            "uncommonWordListId": session.uncommon_word_list_id,
            "caderno": session.caderno or fluency.get("caderno"),
            "q1": _with_audio("q1", fluency.get("q1")),
            "q2": _with_audio("q2", fluency.get("q2")),
            "q3": _with_audio("q3", fluency.get("q3")),
            "micTest": audio.get("mic_test"),
            "prosodyLevel": session.prosody_level or fluency.get("prosodyLevel"),
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
            "precisionLevel": session.precision_level
            or metrics.get("precisionLevel"),
            "fluencyLevel": session.fluency_level or metrics.get("fluencyLevel"),
            "icaScore": session.ica_score
            if session.ica_score is not None
            else metrics.get("icaScore"),
            "icaBreakdown": ica_breakdown,
            "leiturimetroLevel": leiturimetro,
            "startedAt": session.started_at.isoformat() if session.started_at else None,
            "submittedAt": (
                session.submitted_at.isoformat() if session.submitted_at else None
            ),
        }

    @staticmethod
    def finalize_session(session_id: str) -> ReadingFluencySession:
        session = FluencySessionService.get_session(
            session_id, include_answers=True
        )
        if session.status == "finalizada":
            return session
        if session.status != "em_andamento":
            raise ValueError("Sessão não pode ser finalizada.")

        # Recalcula ICA no submit com os campos atuais
        updated_fluency, flat = refresh_ica_in_fluency_data(
            session.fluency_data,
            comprehension_score=session.comprehension_score,
        )
        if updated_fluency is not None:
            session.fluency_data = updated_fluency
            flag_modified(session, "fluency_data")
            FluencySessionService._apply_fluency_columns(session, flat)

        session.status = "finalizada"
        session.submitted_at = datetime.utcnow()
        db.session.commit()
        return FluencySessionService.get_session(
            session_id, include_answers=True
        )

    @staticmethod
    def mark_absent(session_id: str) -> ReadingFluencySession:
        session = FluencySessionService.get_session(session_id)
        if session.status == "finalizada":
            raise ValueError("Sessão já finalizada.")
        session.status = "ausente"
        session.submitted_at = datetime.utcnow()
        db.session.commit()
        return session
