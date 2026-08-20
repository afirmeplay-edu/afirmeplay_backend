# -*- coding: utf-8 -*-
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import joinedload

from app import db
from app.models.grades import Grade
from app.models.student import Student
from app.afirme_ler.models import ReadingEvaluation, ReadingEvaluationSession
from app.afirme_ler.services.parsing import (
    get_field,
    validate_assessment_type,
    validate_evaluation_status,
)
from app.afirme_ler.services.word_list_service import WordListService


class ReadingEvaluationService:
    @staticmethod
    def _parse_uuid_list(values: Any, field_name: str) -> List[str]:
        if values is None:
            return []
        if not isinstance(values, list):
            raise ValueError(f"{field_name} deve ser uma lista.")
        parsed: List[str] = []
        for item in values:
            try:
                parsed.append(str(uuid.UUID(str(item))))
            except (ValueError, TypeError) as exc:
                raise ValueError(f"{field_name} contém ID inválido: {item}") from exc
        return parsed

    @staticmethod
    def _validate_catalog_refs(user: Dict[str, Any], data: dict) -> dict:
        from app.afirme_ler.services.reading_text_service import ReadingTextService

        reading_text_id = get_field(data, "readingTextId", "reading_text_id")
        if not reading_text_id:
            raise ValueError("readingTextId é obrigatório.")
        ReadingTextService.get_visible_text(user, str(reading_text_id))

        words_id = get_field(data, "wordsWordListId", "words_word_list_id")
        uncommon_id = get_field(data, "uncommonWordListId", "uncommon_word_list_id")
        if words_id:
            WordListService.get_visible(user, str(words_id))
        if uncommon_id:
            WordListService.get_visible(user, str(uncommon_id))
        return {
            "reading_text_id": str(reading_text_id),
            "words_word_list_id": str(words_id) if words_id else None,
            "uncommon_word_list_id": str(uncommon_id) if uncommon_id else None,
        }

    @staticmethod
    def create(user: Dict[str, Any], data: dict) -> ReadingEvaluation:
        title = get_field(data, "title")
        if not title or not str(title).strip():
            raise ValueError("title é obrigatório.")

        refs = ReadingEvaluationService._validate_catalog_refs(user, data)
        assessment_type = validate_assessment_type(
            get_field(data, "assessmentType", "assessment_type", default="completa")
        )
        if assessment_type in ("fluencia", "completa", "entrada", "formativa", "saida") and not (
            refs["words_word_list_id"] or refs["uncommon_word_list_id"]
        ):
            raise ValueError("Selecione uma lista de palavras para a avaliação.")

        grade_id = get_field(data, "gradeId", "grade_id")
        if grade_id:
            if not Grade.query.get(grade_id):
                raise ValueError("Série (gradeId) não encontrada.")

        class_ids = ReadingEvaluationService._parse_uuid_list(
            get_field(data, "classIds", "class_ids", default=[]),
            "classIds",
        )
        school_ids = ReadingEvaluationService._parse_uuid_list(
            get_field(data, "schoolIds", "school_ids", default=[]),
            "schoolIds",
        ) if get_field(data, "schoolIds", "school_ids") else None

        user_id = user.get("id") or user.get("user_id")
        evaluation = ReadingEvaluation(
            title=str(title).strip(),
            description=get_field(data, "description"),
            reading_text_id=refs["reading_text_id"],
            words_word_list_id=refs["words_word_list_id"],
            uncommon_word_list_id=refs["uncommon_word_list_id"],
            grade_id=grade_id,
            class_ids=class_ids,
            school_ids=school_ids,
            assessment_type=assessment_type,
            status="rascunho",
            timezone=get_field(data, "timezone", default="America/Sao_Paulo"),
            created_by=user_id,
        )
        db.session.add(evaluation)
        db.session.commit()
        return ReadingEvaluation.query.options(
            joinedload(ReadingEvaluation.grade),
            joinedload(ReadingEvaluation.creator),
        ).get(evaluation.id)

    @staticmethod
    def list_evaluations(user: Dict[str, Any], filters: dict) -> List[ReadingEvaluation]:
        query = ReadingEvaluation.query.options(
            joinedload(ReadingEvaluation.grade),
            joinedload(ReadingEvaluation.creator),
        )

        status = filters.get("status")
        if status:
            query = query.filter(
                ReadingEvaluation.status == validate_evaluation_status(status)
            )

        assessment_type = filters.get("assessmentType") or filters.get("assessment_type")
        if assessment_type:
            query = query.filter(
                ReadingEvaluation.assessment_type == validate_assessment_type(assessment_type)
            )

        return query.order_by(ReadingEvaluation.created_at.desc()).all()

    @staticmethod
    def get_evaluation(evaluation_id: str, *, include_sessions=False) -> ReadingEvaluation:
        options = [
            joinedload(ReadingEvaluation.grade),
            joinedload(ReadingEvaluation.creator),
        ]
        if include_sessions:
            options.append(joinedload(ReadingEvaluation.sessions))

        evaluation = ReadingEvaluation.query.options(*options).get(evaluation_id)
        if not evaluation:
            raise LookupError("Avaliação de leitura não encontrada.")
        return evaluation

    @staticmethod
    def update(user: Dict[str, Any], evaluation_id: str, data: dict) -> ReadingEvaluation:
        evaluation = ReadingEvaluationService.get_evaluation(evaluation_id)
        if evaluation.status in ("concluida", "cancelada"):
            raise ValueError("Não é possível editar avaliação concluída ou cancelada.")

        if "title" in data:
            title = get_field(data, "title")
            if not title or not str(title).strip():
                raise ValueError("title não pode ser vazio.")
            evaluation.title = str(title).strip()

        if "description" in data:
            evaluation.description = data.get("description")

        if any(
            key in data
            for key in (
                "readingTextId",
                "reading_text_id",
                "wordsWordListId",
                "words_word_list_id",
                "uncommonWordListId",
                "uncommon_word_list_id",
            )
        ):
            refs = ReadingEvaluationService._validate_catalog_refs(user, data)
            evaluation.reading_text_id = refs["reading_text_id"]
            if refs["words_word_list_id"] is not None:
                evaluation.words_word_list_id = refs["words_word_list_id"]
            if refs["uncommon_word_list_id"] is not None:
                evaluation.uncommon_word_list_id = refs["uncommon_word_list_id"]

        if get_field(data, "assessmentType", "assessment_type") is not None:
            evaluation.assessment_type = validate_assessment_type(
                get_field(data, "assessmentType", "assessment_type")
            )

        if get_field(data, "gradeId", "grade_id") is not None:
            grade_id = get_field(data, "gradeId", "grade_id")
            if grade_id and not Grade.query.get(grade_id):
                raise ValueError("Série (gradeId) não encontrada.")
            evaluation.grade_id = grade_id

        if get_field(data, "classIds", "class_ids") is not None:
            evaluation.class_ids = ReadingEvaluationService._parse_uuid_list(
                get_field(data, "classIds", "class_ids"),
                "classIds",
            )

        if get_field(data, "schoolIds", "school_ids") is not None:
            evaluation.school_ids = ReadingEvaluationService._parse_uuid_list(
                get_field(data, "schoolIds", "school_ids"),
                "schoolIds",
            )

        if get_field(data, "applicationStart", "application_start") is not None:
            evaluation.application_start = ReadingEvaluationService._parse_datetime(
                get_field(data, "applicationStart", "application_start")
            )

        if get_field(data, "applicationEnd", "application_end") is not None:
            evaluation.application_end = ReadingEvaluationService._parse_datetime(
                get_field(data, "applicationEnd", "application_end")
            )

        if "timezone" in data:
            evaluation.timezone = data.get("timezone")

        if get_field(data, "status") is not None:
            evaluation.status = validate_evaluation_status(get_field(data, "status"))

        db.session.commit()
        return ReadingEvaluation.query.options(
            joinedload(ReadingEvaluation.grade),
            joinedload(ReadingEvaluation.creator),
        ).get(evaluation.id)

    @staticmethod
    def _parse_datetime(value: Any) -> Optional[datetime]:
        if value is None or value == "":
            return None
        if isinstance(value, datetime):
            return value
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("Data/hora inválida.") from exc

    @staticmethod
    def delete(evaluation_id: str) -> None:
        evaluation = ReadingEvaluationService.get_evaluation(evaluation_id)
        if evaluation.status == "em_andamento":
            raise ValueError("Não é possível excluir avaliação em andamento.")
        db.session.delete(evaluation)
        db.session.commit()

    @staticmethod
    def apply_to_classes(user: Dict[str, Any], evaluation_id: str, data: dict) -> dict:
        evaluation = ReadingEvaluationService.get_evaluation(evaluation_id)
        if evaluation.status in ("concluida", "cancelada"):
            raise ValueError("Avaliação já encerrada.")

        class_ids = ReadingEvaluationService._parse_uuid_list(
            get_field(data, "classIds", "class_ids", default=evaluation.class_ids or []),
            "classIds",
        )
        if not class_ids:
            raise ValueError("Informe ao menos uma turma em classIds.")

        application_start = ReadingEvaluationService._parse_datetime(
            get_field(data, "applicationStart", "application_start", default=evaluation.application_start)
        )
        application_end = ReadingEvaluationService._parse_datetime(
            get_field(data, "applicationEnd", "application_end", default=evaluation.application_end)
        )

        evaluation.class_ids = class_ids
        evaluation.application_start = application_start
        evaluation.application_end = application_end
        evaluation.status = "agendada"

        students = Student.query.filter(Student.class_id.in_(class_ids)).all()
        created = 0
        skipped = 0
        for student in students:
            exists = ReadingEvaluationSession.query.filter_by(
                reading_evaluation_id=evaluation.id,
                student_id=student.id,
            ).first()
            if exists:
                skipped += 1
                continue
            session = ReadingEvaluationSession(
                reading_evaluation_id=evaluation.id,
                student_id=student.id,
                class_id=student.class_id,
                status="pendente",
            )
            db.session.add(session)
            created += 1

        db.session.commit()
        return {
            "evaluationId": evaluation.id,
            "status": evaluation.status,
            "sessionsCreated": created,
            "sessionsSkipped": skipped,
            "totalStudents": len(students),
        }
