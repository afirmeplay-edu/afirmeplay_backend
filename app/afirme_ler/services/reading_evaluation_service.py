# -*- coding: utf-8 -*-
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import joinedload

from app import db
from app.models.grades import Grade
from app.models.school import School
from app.models.student import Student
from app.models.studentClass import Class
from app.permissions.roles import Roles
from app.afirme_ler.models import (
    ReadingEvaluation,
    ReadingEvaluationSession,
    ReadingText,
    ReadingWordList,
)
from app.afirme_ler.services.parsing import (
    KIND_PALAVRAS_CONHECIDAS,
    KIND_POUCO_COMUNS,
    get_field,
    validate_evaluation_kind,
    validate_evaluation_status,
)
from app.afirme_ler.services.word_list_service import WordListService


def _user_id(user: Dict[str, Any]) -> Optional[str]:
    return user.get("id") or user.get("user_id")


def _user_role(user: Dict[str, Any]) -> str:
    return Roles.normalize(user.get("role", ""))


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
    def _is_admin_viewer(user: Dict[str, Any]) -> bool:
        return _user_role(user) in (Roles.ADMIN, Roles.TECADM)

    @staticmethod
    def _is_creator(user: Dict[str, Any], evaluation: ReadingEvaluation) -> bool:
        uid = _user_id(user)
        return bool(uid) and str(evaluation.created_by) == str(uid)

    @staticmethod
    def assert_can_view(user: Dict[str, Any], evaluation: ReadingEvaluation) -> None:
        if ReadingEvaluationService._is_admin_viewer(user):
            return
        if ReadingEvaluationService._is_creator(user, evaluation):
            return
        raise PermissionError("Você não tem permissão para visualizar esta avaliação.")

    @staticmethod
    def assert_can_edit(user: Dict[str, Any], evaluation: ReadingEvaluation) -> None:
        if ReadingEvaluationService._is_creator(user, evaluation):
            return
        raise PermissionError("Somente quem criou a avaliação pode editá-la.")

    @staticmethod
    def assert_can_delete(user: Dict[str, Any], evaluation: ReadingEvaluation) -> None:
        if ReadingEvaluationService._is_admin_viewer(user):
            return
        if ReadingEvaluationService._is_creator(user, evaluation):
            return
        raise PermissionError("Você não tem permissão para excluir esta avaliação.")

    @staticmethod
    def assert_can_apply(user: Dict[str, Any], evaluation: ReadingEvaluation) -> None:
        if ReadingEvaluationService._is_creator(user, evaluation):
            return
        raise PermissionError("Você só pode aplicar avaliações que você mesmo criou.")

    @staticmethod
    def _known_list_id_from_data(data: dict):
        return get_field(
            data,
            "knownWordListId",
            "known_word_list_id",
            "wordsWordListId",
            "words_word_list_id",
        )

    @staticmethod
    def _validate_catalog_refs(user: Dict[str, Any], data: dict) -> dict:
        from app.afirme_ler.services.reading_text_service import ReadingTextService

        reading_text_id = get_field(data, "readingTextId", "reading_text_id")
        if not reading_text_id:
            raise ValueError("readingTextId é obrigatório.")
        ReadingTextService.get_visible_text(user, str(reading_text_id))

        words_id = ReadingEvaluationService._known_list_id_from_data(data)
        uncommon_id = get_field(data, "uncommonWordListId", "uncommon_word_list_id")
        if not words_id:
            raise ValueError("knownWordListId é obrigatório.")
        if not uncommon_id:
            raise ValueError("uncommonWordListId é obrigatório.")

        known_list = WordListService.get_visible(user, str(words_id))
        if known_list.kind != KIND_PALAVRAS_CONHECIDAS:
            raise ValueError(
                "knownWordListId deve ser uma lista do tipo PALAVRAS_CONHECIDAS."
            )
        uncommon_list = WordListService.get_visible(user, str(uncommon_id))
        if uncommon_list.kind != KIND_POUCO_COMUNS:
            raise ValueError(
                "uncommonWordListId deve ser uma lista do tipo POUCO_COMUNS."
            )
        return {
            "reading_text_id": str(reading_text_id),
            "words_word_list_id": str(words_id),
            "uncommon_word_list_id": str(uncommon_id),
        }

    @staticmethod
    def create(user: Dict[str, Any], data: dict) -> ReadingEvaluation:
        title = get_field(data, "title")
        if not title or not str(title).strip():
            raise ValueError("title é obrigatório.")

        evaluation_kind = validate_evaluation_kind(
            get_field(data, "evaluationKind", "evaluation_kind")
        )
        refs = ReadingEvaluationService._validate_catalog_refs(user, data)

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
        ) if get_field(data, "schoolIds", "school_ids") else []
        student_ids = ReadingEvaluationService._parse_uuid_list(
            get_field(data, "studentIds", "student_ids", default=[]),
            "studentIds",
        )

        user_id = _user_id(user)
        evaluation = ReadingEvaluation(
            title=str(title).strip(),
            description=get_field(data, "description"),
            reading_text_id=refs["reading_text_id"],
            words_word_list_id=refs["words_word_list_id"],
            uncommon_word_list_id=refs["uncommon_word_list_id"],
            grade_id=grade_id,
            class_ids=class_ids,
            school_ids=school_ids or None,
            student_ids=student_ids,
            evaluation_kind=evaluation_kind,
            assessment_type="completa",
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

        if not ReadingEvaluationService._is_admin_viewer(user):
            uid = _user_id(user)
            if not uid:
                return []
            query = query.filter(ReadingEvaluation.created_by == str(uid))

        status = filters.get("status")
        if status:
            query = query.filter(
                ReadingEvaluation.status == validate_evaluation_status(status)
            )

        evaluation_kind = filters.get("evaluationKind") or filters.get("evaluation_kind")
        if evaluation_kind:
            query = query.filter(
                ReadingEvaluation.evaluation_kind
                == validate_evaluation_kind(evaluation_kind)
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
    def to_detail_dict(evaluation: ReadingEvaluation) -> dict:
        data = evaluation.to_dict()
        text = ReadingText.query.options(
            joinedload(ReadingText.grade),
            joinedload(ReadingText.questions),
        ).get(evaluation.reading_text_id)
        data["readingText"] = (
            text.to_dict(include_questions=True) if text else None
        )

        known = (
            ReadingWordList.query.get(evaluation.words_word_list_id)
            if evaluation.words_word_list_id
            else None
        )
        uncommon = (
            ReadingWordList.query.get(evaluation.uncommon_word_list_id)
            if evaluation.uncommon_word_list_id
            else None
        )
        data["knownWordList"] = known.to_dict() if known else None
        data["uncommonWordList"] = uncommon.to_dict() if uncommon else None

        school_ids = data["schoolIds"] or []
        class_ids = data["classIds"] or []
        student_ids = data["studentIds"] or []

        schools = []
        if school_ids:
            rows = School.query.filter(School.id.in_(school_ids)).all()
            by_id = {str(row.id): row for row in rows}
            schools = [
                {"id": sid, "name": by_id[sid].name if sid in by_id else None}
                for sid in school_ids
            ]

        classes = []
        if class_ids:
            class_uuids = []
            for cid in class_ids:
                try:
                    class_uuids.append(UUID(str(cid)))
                except (TypeError, ValueError):
                    continue
            rows = Class.query.filter(Class.id.in_(class_uuids)).all() if class_uuids else []
            by_id = {str(row.id): row for row in rows}
            for cid in class_ids:
                klass = by_id.get(cid)
                classes.append(
                    {
                        "id": cid,
                        "name": klass.name if klass else None,
                        "schoolId": str(klass.school_id) if klass and klass.school_id else None,
                        "gradeId": str(klass.grade_id) if klass and klass.grade_id else None,
                    }
                )

        students = []
        if student_ids:
            rows = Student.query.filter(Student.id.in_(student_ids)).all()
            by_id = {str(row.id): row for row in rows}
            for sid in student_ids:
                student = by_id.get(sid)
                students.append(
                    {
                        "id": sid,
                        "name": student.name if student else None,
                        "classId": str(student.class_id) if student and student.class_id else None,
                        "schoolId": str(student.school_id) if student and student.school_id else None,
                    }
                )

        data["scope"] = {
            "grade": data.get("grade"),
            "schools": schools,
            "classes": classes,
            "students": students,
        }
        return data

    @staticmethod
    def update(user: Dict[str, Any], evaluation_id: str, data: dict) -> ReadingEvaluation:
        evaluation = ReadingEvaluationService.get_evaluation(evaluation_id)
        ReadingEvaluationService.assert_can_edit(user, evaluation)
        if evaluation.status in ("concluida", "cancelada"):
            raise ValueError("Não é possível editar avaliação concluída ou cancelada.")

        if "title" in data:
            title = get_field(data, "title")
            if not title or not str(title).strip():
                raise ValueError("title não pode ser vazio.")
            evaluation.title = str(title).strip()

        if "description" in data:
            evaluation.description = data.get("description")

        catalog_keys = (
            "readingTextId",
            "reading_text_id",
            "knownWordListId",
            "known_word_list_id",
            "wordsWordListId",
            "words_word_list_id",
            "uncommonWordListId",
            "uncommon_word_list_id",
        )
        if any(key in data for key in catalog_keys):
            merged = {
                "readingTextId": get_field(
                    data, "readingTextId", "reading_text_id",
                    default=evaluation.reading_text_id,
                ),
                "knownWordListId": ReadingEvaluationService._known_list_id_from_data(data)
                or evaluation.words_word_list_id,
                "uncommonWordListId": get_field(
                    data, "uncommonWordListId", "uncommon_word_list_id",
                    default=evaluation.uncommon_word_list_id,
                ),
            }
            refs = ReadingEvaluationService._validate_catalog_refs(user, merged)
            evaluation.reading_text_id = refs["reading_text_id"]
            evaluation.words_word_list_id = refs["words_word_list_id"]
            evaluation.uncommon_word_list_id = refs["uncommon_word_list_id"]

        if get_field(data, "evaluationKind", "evaluation_kind") is not None:
            evaluation.evaluation_kind = validate_evaluation_kind(
                get_field(data, "evaluationKind", "evaluation_kind")
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

        if get_field(data, "studentIds", "student_ids") is not None:
            evaluation.student_ids = ReadingEvaluationService._parse_uuid_list(
                get_field(data, "studentIds", "student_ids"),
                "studentIds",
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
    def delete(user: Dict[str, Any], evaluation_id: str) -> None:
        from app.afirme_ler.models import ReadingFluencySession

        evaluation = ReadingEvaluationService.get_evaluation(evaluation_id)
        ReadingEvaluationService.assert_can_delete(user, evaluation)
        if evaluation.status == "em_andamento":
            raise ValueError("Não é possível excluir avaliação em andamento.")
        has_fluency = ReadingFluencySession.query.filter_by(
            reading_evaluation_id=evaluation.id
        ).first()
        if has_fluency:
            raise ValueError("Não é possível excluir avaliação com aplicações registradas.")
        db.session.delete(evaluation)
        db.session.commit()

    @staticmethod
    def assert_student_in_scope(evaluation: ReadingEvaluation, student: Student) -> None:
        student_ids = (
            [str(item) for item in evaluation.student_ids]
            if isinstance(evaluation.student_ids, list)
            else []
        )
        class_ids = (
            [str(item) for item in evaluation.class_ids]
            if isinstance(evaluation.class_ids, list)
            else []
        )
        school_ids = (
            [str(item) for item in evaluation.school_ids]
            if isinstance(evaluation.school_ids, list)
            else []
        )

        if student_ids and str(student.id) not in student_ids:
            raise ValueError("Aluno não pertence ao escopo desta avaliação.")

        if class_ids:
            if not student.class_id or str(student.class_id) not in class_ids:
                raise ValueError("Aluno não pertence às turmas desta avaliação.")

        if school_ids:
            if not student.school_id or str(student.school_id) not in school_ids:
                raise ValueError("Aluno não pertence às escolas desta avaliação.")

        if evaluation.grade_id and student.grade_id:
            if str(student.grade_id) != str(evaluation.grade_id):
                raise ValueError("Aluno não pertence à série desta avaliação.")

    @staticmethod
    def apply_to_classes(user: Dict[str, Any], evaluation_id: str, data: dict) -> dict:
        evaluation = ReadingEvaluationService.get_evaluation(evaluation_id)
        ReadingEvaluationService.assert_can_apply(user, evaluation)
        if evaluation.status in ("concluida", "cancelada"):
            raise ValueError("Avaliação já encerrada.")

        class_ids = ReadingEvaluationService._parse_uuid_list(
            get_field(data, "classIds", "class_ids", default=evaluation.class_ids or []),
            "classIds",
        )
        student_ids = ReadingEvaluationService._parse_uuid_list(
            get_field(
                data,
                "studentIds",
                "student_ids",
                default=evaluation.student_ids or [],
            ),
            "studentIds",
        )
        if not class_ids and not student_ids:
            raise ValueError("Informe ao menos uma turma em classIds ou alunos em studentIds.")

        application_start = ReadingEvaluationService._parse_datetime(
            get_field(data, "applicationStart", "application_start", default=evaluation.application_start)
        )
        application_end = ReadingEvaluationService._parse_datetime(
            get_field(data, "applicationEnd", "application_end", default=evaluation.application_end)
        )

        if class_ids:
            evaluation.class_ids = class_ids
        if student_ids:
            evaluation.student_ids = student_ids
        evaluation.application_start = application_start
        evaluation.application_end = application_end
        evaluation.status = "agendada"

        query = Student.query
        if class_ids:
            query = query.filter(Student.class_id.in_(class_ids))
        if student_ids:
            query = query.filter(Student.id.in_(student_ids))
        students = query.all()
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
