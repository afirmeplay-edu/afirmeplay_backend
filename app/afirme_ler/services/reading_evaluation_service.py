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
    ReadingFluencySession,
    ReadingText,
    ReadingWordList,
)
from app.afirme_ler.services.parsing import (
    EVALUATION_KIND_LABELS,
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
        text = ReadingTextService.get_visible_text(user, str(reading_text_id))

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
            "text": text,
            "known_list": known_list,
            "uncommon_list": uncommon_list,
        }

    @staticmethod
    def _assert_materials_match_grades(
        text: ReadingText,
        known_list: ReadingWordList,
        uncommon_list: ReadingWordList,
        grade_ids: List[str],
    ) -> None:
        allowed = {str(item) for item in grade_ids}
        text_grade = str(text.grade_id) if text and text.grade_id else None
        if not text_grade or text_grade not in allowed:
            raise ValueError("O texto não pertence às séries selecionadas.")
        known_grade = str(known_list.grade_id) if known_list and known_list.grade_id else None
        if not known_grade or known_grade not in allowed:
            raise ValueError(
                "knownWordListId não pertence às séries selecionadas."
            )
        uncommon_grade = (
            str(uncommon_list.grade_id)
            if uncommon_list and uncommon_list.grade_id
            else None
        )
        if not uncommon_grade or uncommon_grade not in allowed:
            raise ValueError(
                "uncommonWordListId não pertence às séries selecionadas."
            )

    @staticmethod
    def _class_uuids(class_ids: List[str]) -> List[UUID]:
        parsed: List[UUID] = []
        for class_id in class_ids:
            try:
                parsed.append(UUID(str(class_id)))
            except (TypeError, ValueError):
                continue
        return parsed

    @staticmethod
    def _stored_grade_ids(evaluation: ReadingEvaluation) -> List[str]:
        return evaluation.grade_id_list()

    @staticmethod
    def _resolve_grade_ids(data: dict, *, default: Optional[List[str]] = None) -> List[str]:
        raw = get_field(data, "gradeIds", "grade_ids")
        if raw is None:
            single = get_field(data, "gradeId", "grade_id")
            if single is None:
                raw = default if default is not None else []
            elif isinstance(single, list):
                raw = single
            else:
                raw = [single]
        return ReadingEvaluationService._parse_uuid_list(raw, "gradeIds")

    @staticmethod
    def _grades_payload(grade_ids: List[str]) -> List[dict]:
        if not grade_ids:
            return []
        rows = Grade.query.filter(Grade.id.in_(grade_ids)).all()
        by_id = {str(row.id): row for row in rows}
        return [
            {"id": gid, "name": by_id[gid].name if gid in by_id else None}
            for gid in grade_ids
        ]

    @staticmethod
    def _validate_scope(data: dict) -> dict:
        grade_ids = ReadingEvaluationService._resolve_grade_ids(data)
        if not grade_ids:
            raise ValueError("Informe ao menos uma série em gradeIds.")
        found_grades = {
            str(row.id)
            for row in Grade.query.filter(Grade.id.in_(grade_ids)).all()
        }
        missing_grades = [item for item in grade_ids if item not in found_grades]
        if missing_grades:
            raise ValueError(f"Série (gradeId) não encontrada: {missing_grades[0]}.")
        grade_id_set = set(grade_ids)

        school_ids = ReadingEvaluationService._parse_uuid_list(
            get_field(data, "schoolIds", "school_ids", default=[]),
            "schoolIds",
        )
        if not school_ids:
            raise ValueError("Informe ao menos uma escola em schoolIds.")
        found_schools = {
            str(row.id)
            for row in School.query.filter(School.id.in_(school_ids)).all()
        }
        missing_schools = [item for item in school_ids if item not in found_schools]
        if missing_schools:
            raise ValueError(f"Escola não encontrada: {missing_schools[0]}.")

        class_ids = ReadingEvaluationService._parse_uuid_list(
            get_field(data, "classIds", "class_ids", default=[]),
            "classIds",
        )
        if not class_ids:
            raise ValueError("Informe ao menos uma turma em classIds.")

        class_uuids = ReadingEvaluationService._class_uuids(class_ids)
        klasses = Class.query.filter(Class.id.in_(class_uuids)).all() if class_uuids else []
        by_id = {str(klass.id): klass for klass in klasses}
        for class_id in class_ids:
            klass = by_id.get(class_id)
            if not klass:
                raise ValueError(f"Turma não encontrada: {class_id}.")
            if str(klass.school_id) not in school_ids:
                raise ValueError("Turma não pertence às escolas selecionadas.")
            if klass.grade_id and str(klass.grade_id) not in grade_id_set:
                raise ValueError("Turma não pertence às séries selecionadas.")

        student_ids = ReadingEvaluationService._parse_uuid_list(
            get_field(data, "studentIds", "student_ids", default=[]),
            "studentIds",
        )
        return {
            "grade_ids": grade_ids,
            "grade_id": grade_ids[0],
            "school_ids": school_ids,
            "class_ids": class_ids,
            "student_ids": student_ids,
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
        scope = ReadingEvaluationService._validate_scope(data)
        ReadingEvaluationService._assert_materials_match_grades(
            refs["text"],
            refs["known_list"],
            refs["uncommon_list"],
            scope["grade_ids"],
        )

        user_id = _user_id(user)
        evaluation = ReadingEvaluation(
            title=str(title).strip(),
            description=get_field(data, "description"),
            reading_text_id=refs["reading_text_id"],
            words_word_list_id=refs["words_word_list_id"],
            uncommon_word_list_id=refs["uncommon_word_list_id"],
            grade_id=scope["grade_id"],
            grade_ids=scope["grade_ids"],
            class_ids=scope["class_ids"],
            school_ids=scope["school_ids"],
            student_ids=scope["student_ids"],
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
            "grades": data.get("grades") or [],
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

        scope_keys = (
            "gradeId",
            "grade_id",
            "gradeIds",
            "grade_ids",
            "classIds",
            "class_ids",
            "schoolIds",
            "school_ids",
            "studentIds",
            "student_ids",
        )
        if any(key in data for key in scope_keys):
            merged_scope = {
                "gradeIds": get_field(
                    data,
                    "gradeIds",
                    "grade_ids",
                    default=ReadingEvaluationService._stored_grade_ids(evaluation),
                ),
                "schoolIds": get_field(
                    data,
                    "schoolIds",
                    "school_ids",
                    default=evaluation.school_ids or [],
                ),
                "classIds": get_field(
                    data,
                    "classIds",
                    "class_ids",
                    default=evaluation.class_ids or [],
                ),
                "studentIds": get_field(
                    data,
                    "studentIds",
                    "student_ids",
                    default=evaluation.student_ids or [],
                ),
            }
            if "gradeId" in data or "grade_id" in data:
                if "gradeIds" not in data and "grade_ids" not in data:
                    merged_scope["gradeIds"] = None
                    merged_scope["gradeId"] = get_field(data, "gradeId", "grade_id")
            scope = ReadingEvaluationService._validate_scope(merged_scope)
            evaluation.grade_id = scope["grade_id"]
            evaluation.grade_ids = scope["grade_ids"]
            evaluation.school_ids = scope["school_ids"]
            evaluation.class_ids = scope["class_ids"]
            evaluation.student_ids = scope["student_ids"]

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

        catalog_changed = any(key in data for key in catalog_keys)
        scope_changed = any(key in data for key in scope_keys)
        if catalog_changed or scope_changed:
            text = ReadingText.query.get(evaluation.reading_text_id)
            known_list = (
                ReadingWordList.query.get(evaluation.words_word_list_id)
                if evaluation.words_word_list_id
                else None
            )
            uncommon_list = (
                ReadingWordList.query.get(evaluation.uncommon_word_list_id)
                if evaluation.uncommon_word_list_id
                else None
            )
            if not text or not known_list or not uncommon_list:
                raise ValueError("Texto ou listas da avaliação não encontrados.")
            ReadingEvaluationService._assert_materials_match_grades(
                text,
                known_list,
                uncommon_list,
                ReadingEvaluationService._stored_grade_ids(evaluation),
            )

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
    def _session_sort_key(session: ReadingFluencySession):
        return (
            session.updated_at
            or session.submitted_at
            or session.created_at
            or datetime.min
        )

    @staticmethod
    def _pick_application(sessions: List[ReadingFluencySession]):
        if not sessions:
            return None
        in_progress = [item for item in sessions if item.status == "em_andamento"]
        if in_progress:
            return max(in_progress, key=ReadingEvaluationService._session_sort_key)
        finalized = [item for item in sessions if item.status == "finalizada"]
        if finalized:
            return max(finalized, key=ReadingEvaluationService._session_sort_key)
        return max(sessions, key=ReadingEvaluationService._session_sort_key)

    @staticmethod
    def list_applicants(user: Dict[str, Any], evaluation_id: str) -> dict:
        evaluation = ReadingEvaluationService.get_evaluation(evaluation_id)
        ReadingEvaluationService.assert_can_apply(user, evaluation)

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
        student_allow = (
            [str(item) for item in evaluation.student_ids]
            if isinstance(evaluation.student_ids, list)
            else []
        )

        class_uuids = ReadingEvaluationService._class_uuids(class_ids)
        klasses = (
            Class.query.filter(Class.id.in_(class_uuids)).all() if class_uuids else []
        )
        klass_by_id = {str(klass.id): klass for klass in klasses}

        school_id_set = {str(klass.school_id) for klass in klasses if klass.school_id}
        school_id_set.update(school_ids)
        schools_by_id = {}
        if school_id_set:
            schools_by_id = {
                str(row.id): row
                for row in School.query.filter(School.id.in_(list(school_id_set))).all()
            }

        students_query = Student.query
        if class_uuids:
            students_query = students_query.filter(Student.class_id.in_(class_uuids))
        else:
            students_query = students_query.filter(Student.id.in_([]))
        if school_ids:
            students_query = students_query.filter(Student.school_id.in_(school_ids))
        grade_ids = ReadingEvaluationService._stored_grade_ids(evaluation)
        if grade_ids:
            students_query = students_query.filter(Student.grade_id.in_(grade_ids))
        if student_allow:
            students_query = students_query.filter(Student.id.in_(student_allow))

        students = students_query.order_by(Student.name.asc()).all()
        student_ids = [student.id for student in students]
        sessions: List[ReadingFluencySession] = []
        if student_ids:
            sessions = ReadingFluencySession.query.filter(
                ReadingFluencySession.reading_evaluation_id == evaluation.id,
                ReadingFluencySession.student_id.in_(student_ids),
            ).all()

        sessions_by_student: Dict[str, List[ReadingFluencySession]] = {}
        for session in sessions:
            sessions_by_student.setdefault(session.student_id, []).append(session)

        students_by_class: Dict[str, List[Student]] = {}
        for student in students:
            class_key = str(student.class_id) if student.class_id else ""
            students_by_class.setdefault(class_key, []).append(student)

        classes_payload = []
        for class_id in class_ids:
            klass = klass_by_id.get(class_id)
            school_id = str(klass.school_id) if klass and klass.school_id else None
            school = schools_by_id.get(school_id) if school_id else None
            class_students = []
            for student in students_by_class.get(class_id, []):
                picked = ReadingEvaluationService._pick_application(
                    sessions_by_student.get(student.id) or []
                )
                application = None
                if picked:
                    application = {
                        "sessionId": picked.id,
                        "status": picked.status,
                        "startedAt": (
                            picked.started_at.isoformat() if picked.started_at else None
                        ),
                        "submittedAt": (
                            picked.submitted_at.isoformat()
                            if picked.submitted_at
                            else None
                        ),
                    }
                status = application["status"] if application else None
                class_students.append(
                    {
                        "id": student.id,
                        "name": student.name,
                        "classId": class_id,
                        "schoolId": (
                            str(student.school_id) if student.school_id else school_id
                        ),
                        "application": application,
                        "canStart": status is None or status == "ausente",
                        "canContinue": status == "em_andamento",
                        "canView": status == "finalizada",
                    }
                )
            classes_payload.append(
                {
                    "id": class_id,
                    "name": klass.name if klass else None,
                    "schoolId": school_id,
                    "schoolName": school.name if school else None,
                    "gradeId": str(klass.grade_id) if klass and klass.grade_id else None,
                    "students": class_students,
                }
            )

        grades = ReadingEvaluationService._grades_payload(grade_ids)
        return {
            "evaluationId": evaluation.id,
            "evaluationTitle": evaluation.title,
            "evaluationKind": evaluation.evaluation_kind,
            "evaluationKindLabel": EVALUATION_KIND_LABELS.get(
                evaluation.evaluation_kind
            ),
            "gradeIds": grade_ids,
            "grades": grades,
            "grade": grades[0] if grades else None,
            "classes": classes_payload,
        }

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

        grade_ids = ReadingEvaluationService._stored_grade_ids(evaluation)
        if grade_ids and student.grade_id:
            if str(student.grade_id) not in grade_ids:
                raise ValueError("Aluno não pertence às séries desta avaliação.")

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
