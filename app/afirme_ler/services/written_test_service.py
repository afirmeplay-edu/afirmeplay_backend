# -*- coding: utf-8 -*-
"""
Avaliação escrita do Afirme Ler: criação, escopo (séries/escolas/turmas), questões e publicação.

Tabelas próprias no schema do município (reading_written_test*). Não usa test/test_questions/
class_test do Afirme Play nem reading_evaluation da fluência.
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import Text, cast
from sqlalchemy.orm import joinedload
from sqlalchemy.orm.attributes import flag_modified

from app import db
from app.models.grades import Grade
from app.models.question import Question
from app.models.school import School
from app.models.studentClass import Class
from app.permissions.roles import Roles
from app.afirme_ler.models.reading_written_test import (
    WRITTEN_TEST_STATUS_DRAFT,
    WRITTEN_TEST_STATUS_PUBLISHED,
    WRITTEN_TEST_STATUSES,
    ReadingWrittenTest,
    ReadingWrittenTestQuestion,
)
from app.afirme_ler.services.question_bank_service import (
    DEFAULT_PER_PAGE,
    MAX_PER_PAGE,
    OBJECTIVE_DB_TYPES,
    QUESTION_TYPE_DICTATION,
    QUESTION_TYPE_MULTIPLE_CHOICE,
    QUESTION_TYPE_TEXT_PRODUCTION,
    WRITE_ROLES,
    _escape_like,
    _parse_positive_int,
    _with_relations,
    to_response,
)
from app.afirme_ler.services.scope_service import apply_visibility_filter

REQUIRED_QUESTIONS = 20
ALLOWED_QUESTION_DB_TYPES = OBJECTIVE_DB_TYPES + (
    QUESTION_TYPE_DICTATION,
    QUESTION_TYPE_TEXT_PRODUCTION,
)
SCOPE_FIELDS = {"gradeIds": "grade_ids", "schoolIds": "school_ids", "classIds": "class_ids"}

MSG_PUBLISHED_LOCKED = "Avaliação publicada não pode ser alterada."
MSG_PUBLISHED_DELETE = "Avaliação publicada não pode ser excluída."
MSG_MAX_QUESTIONS = f"A avaliação aceita no máximo {REQUIRED_QUESTIONS} questões."


def _user_id(user: Dict[str, Any]) -> Optional[str]:
    uid = user.get("id") or user.get("user_id")
    return str(uid) if uid else None


def _role(user: Dict[str, Any]) -> str:
    return Roles.normalize(user.get("role", ""))


def assert_can_write(user: Dict[str, Any]) -> None:
    if _role(user) not in WRITE_ROLES:
        raise PermissionError("Seu perfil não pode criar ou alterar avaliações escritas.")


def assert_can_manage(user: Dict[str, Any], written_test: ReadingWrittenTest) -> None:
    """Quem criou, admin e tecadm (o schema já é o do município do contexto)."""
    assert_can_write(user)
    if _role(user) in (Roles.ADMIN, Roles.TECADM):
        return
    uid = _user_id(user)
    if uid and str(written_test.created_by) == uid:
        return
    raise PermissionError("Você não tem permissão para alterar esta avaliação.")


def _assert_draft(written_test: ReadingWrittenTest, message: str = MSG_PUBLISHED_LOCKED) -> None:
    if written_test.status != WRITTEN_TEST_STATUS_DRAFT:
        raise ValueError(message)


def _required_title(value: Any) -> str:
    if value is None or not str(value).strip():
        raise ValueError("title é obrigatório.")
    title = str(value).strip()
    if len(title) > 255:
        raise ValueError("title deve ter no máximo 255 caracteres.")
    return title


def _optional_description(value: Any) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("description deve ser um texto.")
    return value.strip() or None


def _uuid_list(values: Any, field_name: str) -> List[str]:
    if values is None:
        return []
    if not isinstance(values, list):
        raise ValueError(f"{field_name} deve ser uma lista.")
    parsed: List[str] = []
    for item in values:
        try:
            value = str(uuid.UUID(str(item).strip()))
        except (TypeError, ValueError, AttributeError) as exc:
            raise ValueError(f"{field_name} contém ID inválido: {item}") from exc
        if value not in parsed:
            parsed.append(value)
    return parsed


def validate_scope(data: Dict[str, Any]) -> Dict[str, List[str]]:
    """
    Mesma lógica de ReadingEvaluationService._validate_scope: ao menos uma série, uma escola e
    uma turma; ids precisam existir; toda turma é de uma das escolas e de uma das séries.
    """
    grade_ids = _uuid_list(data.get("gradeIds"), "gradeIds")
    if not grade_ids:
        raise ValueError("Informe ao menos uma série em gradeIds.")
    found_grades = {str(row.id) for row in Grade.query.filter(Grade.id.in_(
        [uuid.UUID(item) for item in grade_ids]
    )).all()}
    missing = [item for item in grade_ids if item not in found_grades]
    if missing:
        raise ValueError(f"Série não encontrada: {missing[0]}.")

    school_ids = _uuid_list(data.get("schoolIds"), "schoolIds")
    if not school_ids:
        raise ValueError("Informe ao menos uma escola em schoolIds.")
    found_schools = {str(row.id) for row in School.query.filter(School.id.in_(school_ids)).all()}
    missing = [item for item in school_ids if item not in found_schools]
    if missing:
        raise ValueError(f"Escola não encontrada: {missing[0]}.")

    class_ids = _uuid_list(data.get("classIds"), "classIds")
    if not class_ids:
        raise ValueError("Informe ao menos uma turma em classIds.")
    classes = Class.query.filter(Class.id.in_([uuid.UUID(item) for item in class_ids])).all()
    by_id = {str(klass.id): klass for klass in classes}
    for class_id in class_ids:
        klass = by_id.get(class_id)
        if not klass:
            raise ValueError(f"Turma não encontrada: {class_id}.")
        label = klass.name or class_id
        if str(klass.school_id) not in school_ids:
            raise ValueError(f"A turma {label} não pertence às escolas escolhidas.")
        if not klass.grade_id or str(klass.grade_id) not in grade_ids:
            raise ValueError(f"A turma {label} não pertence às séries escolhidas.")

    return {"grade_ids": grade_ids, "school_ids": school_ids, "class_ids": class_ids}


def parse_question_items(raw: Any) -> List[Tuple[str, int]]:
    """Lista [{id, order}] → [(question_id, order)] ordenada por order (1..N, sem repetição)."""
    if not isinstance(raw, list):
        raise ValueError("questions deve ser uma lista de {id, order}.")
    if len(raw) > REQUIRED_QUESTIONS:
        raise ValueError(MSG_MAX_QUESTIONS)

    items: List[Tuple[str, int]] = []
    seen_ids = set()
    for position, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            raise ValueError("Cada questão deve ser um objeto {id, order}.")
        question_id = item.get("id")
        if question_id is None or not str(question_id).strip():
            raise ValueError("Cada questão precisa de id.")
        question_id = str(question_id).strip()
        if question_id in seen_ids:
            raise ValueError("Questão repetida na avaliação.")
        seen_ids.add(question_id)

        order = item.get("order")
        if order is None:
            order = position
        elif isinstance(order, bool) or not isinstance(order, int):
            raise ValueError("order deve ser um número inteiro.")
        items.append((question_id, order))

    orders = sorted(order for _, order in items)
    if orders != list(range(1, len(items) + 1)):
        raise ValueError(f"Os valores de order devem ser únicos e de 1 a {len(items)}.")
    return sorted(items, key=lambda pair: pair[1])


def _assert_allowed_type(question: Question) -> None:
    if question.question_type not in ALLOWED_QUESTION_DB_TYPES:
        raise ValueError(
            f"A questão {question.id} é do tipo {question.question_type or 'sem tipo'}, "
            "que não é aceito na avaliação escrita. Tipos permitidos: "
            "multipleChoice, dictation e text_production."
        )


def load_visible_questions(user: Dict[str, Any], question_ids: List[str]) -> Dict[str, Question]:
    if not question_ids:
        return {}
    query = Question.query.filter(Question.id.in_(question_ids))
    found = {q.id: q for q in apply_visibility_filter(query, Question, user).all()}
    for question_id in question_ids:
        question = found.get(question_id)
        if not question:
            raise ValueError(f"Questão não encontrada ou sem acesso: {question_id}.")
        _assert_allowed_type(question)
    return found


def _replace_questions(written_test: ReadingWrittenTest, items: List[Tuple[str, int]]) -> None:
    # Apaga antes de inserir: as UNIQUE (teste, questão) e (teste, order) não toleram a troca no mesmo flush.
    written_test.questions.clear()
    db.session.flush()
    for question_id, order in items:
        written_test.questions.append(
            ReadingWrittenTestQuestion(question_id=question_id, order=order)
        )


def _question_value(question: Optional[Question]) -> float:
    if question is None or question.value is None:
        return 1.0
    return float(question.value)


def _type_key(question_type: Optional[str]) -> Optional[str]:
    if question_type in OBJECTIVE_DB_TYPES:
        return QUESTION_TYPE_MULTIPLE_CHOICE
    if question_type in (QUESTION_TYPE_DICTATION, QUESTION_TYPE_TEXT_PRODUCTION):
        return question_type
    return None


def _summary_counts(links: List[ReadingWrittenTestQuestion], questions: Dict[str, Question]) -> Dict[str, Any]:
    by_type = {
        QUESTION_TYPE_MULTIPLE_CHOICE: 0,
        QUESTION_TYPE_DICTATION: 0,
        QUESTION_TYPE_TEXT_PRODUCTION: 0,
    }
    total_score = 0.0
    for link in links:
        question = questions.get(link.question_id)
        if question is None:
            continue
        key = _type_key(question.question_type)
        if key:
            by_type[key] += 1
        total_score += _question_value(question)
    return {
        "totalQuestions": len(links),
        "totalScore": total_score,
        "questionsByType": by_type,
    }


def _named(rows, ids: List[str], extra=None) -> List[Dict[str, Any]]:
    by_id = {str(row.id): row for row in rows}
    out = []
    for item_id in ids:
        row = by_id.get(item_id)
        entry = {"id": item_id, "name": row.name if row else None}
        if extra:
            entry.update(extra(row))
        out.append(entry)
    return out


def _base_dict(written_test: ReadingWrittenTest) -> Dict[str, Any]:
    creator = written_test.creator
    return {
        "id": written_test.id,
        "title": written_test.title,
        "description": written_test.description,
        "status": written_test.status,
        "gradeIds": list(written_test.grade_ids or []),
        "schoolIds": list(written_test.school_ids or []),
        "classIds": list(written_test.class_ids or []),
        "createdBy": {
            "id": written_test.created_by,
            "name": creator.name if creator else None,
        },
        "createdAt": written_test.created_at.isoformat() if written_test.created_at else None,
        "updatedAt": written_test.updated_at.isoformat() if written_test.updated_at else None,
        "publishedAt": written_test.published_at.isoformat() if written_test.published_at else None,
    }


def to_detail(written_test: ReadingWrittenTest) -> Dict[str, Any]:
    data = _base_dict(written_test)
    links = list(written_test.questions or [])
    ids = [link.question_id for link in links]
    questions = (
        {q.id: q for q in _with_relations(Question.query.filter(Question.id.in_(ids))).all()}
        if ids else {}
    )
    data.update(_summary_counts(links, questions))

    grade_ids = data["gradeIds"]
    grade_rows = Grade.query.filter(Grade.id.in_([uuid.UUID(g) for g in grade_ids])).all() if grade_ids else []
    data["grades"] = _named(grade_rows, grade_ids)

    school_ids = data["schoolIds"]
    school_rows = School.query.filter(School.id.in_(school_ids)).all() if school_ids else []
    data["schools"] = _named(school_rows, school_ids)

    class_ids = data["classIds"]
    class_rows = (
        Class.query.filter(Class.id.in_([uuid.UUID(c) for c in class_ids])).all() if class_ids else []
    )
    data["classes"] = _named(
        class_rows,
        class_ids,
        extra=lambda row: {
            "schoolId": str(row.school_id) if row and row.school_id else None,
            "gradeId": str(row.grade_id) if row and row.grade_id else None,
        },
    )

    items = []
    for link in links:
        question = questions.get(link.question_id)
        if question is None:
            items.append({"id": link.question_id, "order": link.order, "missing": True})
            continue
        item = to_response(question)
        item["order"] = link.order
        items.append(item)
    data["questions"] = items
    return data


class WrittenTestService:
    @staticmethod
    def get(written_test_id: str) -> ReadingWrittenTest:
        written_test = ReadingWrittenTest.query.options(
            joinedload(ReadingWrittenTest.creator),
            joinedload(ReadingWrittenTest.questions),
        ).filter(ReadingWrittenTest.id == str(written_test_id)).first()
        if not written_test:
            raise LookupError("Avaliação escrita não encontrada.")
        return written_test

    @staticmethod
    def create(user: Dict[str, Any], data: Dict[str, Any]) -> ReadingWrittenTest:
        assert_can_write(user)
        title = _required_title(data.get("title"))
        description = _optional_description(data.get("description"))
        scope = validate_scope(data)
        items = parse_question_items(data["questions"]) if data.get("questions") is not None else []
        load_visible_questions(user, [question_id for question_id, _ in items])

        written_test = ReadingWrittenTest(
            title=title,
            description=description,
            status=WRITTEN_TEST_STATUS_DRAFT,
            created_by=_user_id(user),
            **scope,
        )
        db.session.add(written_test)
        db.session.flush()
        _replace_questions(written_test, items)
        db.session.commit()
        return WrittenTestService.get(written_test.id)

    @staticmethod
    def update(user: Dict[str, Any], written_test_id: str, data: Dict[str, Any]) -> ReadingWrittenTest:
        written_test = WrittenTestService.get(written_test_id)
        assert_can_manage(user, written_test)
        _assert_draft(written_test)

        if "title" in data:
            written_test.title = _required_title(data.get("title"))
        if "description" in data:
            written_test.description = _optional_description(data.get("description"))
        if any(key in data for key in SCOPE_FIELDS):
            merged = {
                key: data[key] if key in data else getattr(written_test, column)
                for key, column in SCOPE_FIELDS.items()
            }
            scope = validate_scope(merged)
            for column, values in scope.items():
                setattr(written_test, column, values)
                flag_modified(written_test, column)

        written_test.updated_at = db.func.now()
        db.session.commit()
        return WrittenTestService.get(written_test.id)

    @staticmethod
    def set_questions(user: Dict[str, Any], written_test_id: str, data: Dict[str, Any]) -> ReadingWrittenTest:
        written_test = WrittenTestService.get(written_test_id)
        assert_can_manage(user, written_test)
        _assert_draft(written_test)
        if "questions" not in data:
            raise ValueError("questions é obrigatório.")
        items = parse_question_items(data.get("questions"))
        load_visible_questions(user, [question_id for question_id, _ in items])

        _replace_questions(written_test, items)
        written_test.updated_at = db.func.now()
        db.session.commit()
        return WrittenTestService.get(written_test.id)

    @staticmethod
    def publish(user: Dict[str, Any], written_test_id: str) -> ReadingWrittenTest:
        written_test = WrittenTestService.get(written_test_id)
        assert_can_manage(user, written_test)
        if written_test.status == WRITTEN_TEST_STATUS_PUBLISHED:
            raise ValueError("A avaliação já está publicada.")

        links = list(written_test.questions or [])
        if len(links) != REQUIRED_QUESTIONS:
            raise ValueError(
                f"A avaliação precisa ter exatamente {REQUIRED_QUESTIONS} questões para ser "
                f"publicada (hoje tem {len(links)})."
            )
        ids = [link.question_id for link in links]
        found = {q.id: q for q in Question.query.filter(Question.id.in_(ids)).all()}
        for question_id in ids:
            question = found.get(question_id)
            if not question:
                raise ValueError(
                    f"A questão {question_id} não existe mais no banco de questões. "
                    "Troque-a antes de publicar."
                )
            _assert_allowed_type(question)

        written_test.status = WRITTEN_TEST_STATUS_PUBLISHED
        written_test.published_at = db.func.now()
        written_test.updated_at = db.func.now()
        db.session.commit()
        return WrittenTestService.get(written_test.id)

    @staticmethod
    def delete(user: Dict[str, Any], written_test_id: str) -> None:
        written_test = WrittenTestService.get(written_test_id)
        assert_can_manage(user, written_test)
        _assert_draft(written_test, MSG_PUBLISHED_DELETE)
        db.session.delete(written_test)
        db.session.commit()

    @staticmethod
    def list_tests(filters: Dict[str, Any]) -> Dict[str, Any]:
        page = _parse_positive_int(filters.get("page"), "page", 1)
        per_page = min(
            _parse_positive_int(filters.get("per_page"), "per_page", DEFAULT_PER_PAGE),
            MAX_PER_PAGE,
        )
        query = ReadingWrittenTest.query.options(joinedload(ReadingWrittenTest.creator))

        status = (filters.get("status") or "").strip()
        if status:
            if status not in WRITTEN_TEST_STATUSES:
                raise ValueError("status inválido. Valores permitidos: rascunho, publicada.")
            query = query.filter(ReadingWrittenTest.status == status)

        for param, column in (("grade_id", ReadingWrittenTest.grade_ids),
                              ("school_id", ReadingWrittenTest.school_ids)):
            raw = (filters.get(param) or "").strip()
            if raw:
                try:
                    value = str(uuid.UUID(raw))
                except ValueError as exc:
                    raise ValueError(f"{param} deve ser um UUID.") from exc
                query = query.filter(cast(column, Text).like(f'%"{value}"%'))

        term = (filters.get("q") or "").strip()
        if term:
            query = query.filter(
                ReadingWrittenTest.title.ilike(f"%{_escape_like(term)}%", escape="\\")
            )

        query = query.order_by(ReadingWrittenTest.created_at.desc(), ReadingWrittenTest.id.asc())
        paginated = query.paginate(page=page, per_page=per_page, error_out=False)

        test_ids = [item.id for item in paginated.items]
        links = (
            ReadingWrittenTestQuestion.query
            .filter(ReadingWrittenTestQuestion.written_test_id.in_(test_ids)).all()
            if test_ids else []
        )
        question_ids = list({link.question_id for link in links})
        questions = (
            {q.id: q for q in Question.query.filter(Question.id.in_(question_ids)).all()}
            if question_ids else {}
        )
        links_by_test: Dict[str, List[ReadingWrittenTestQuestion]] = {}
        for link in links:
            links_by_test.setdefault(link.written_test_id, []).append(link)

        data = []
        for item in paginated.items:
            entry = _base_dict(item)
            entry.update(_summary_counts(links_by_test.get(item.id, []), questions))
            data.append(entry)

        return {
            "data": data,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": paginated.total,
                "pages": paginated.pages,
                "has_next": paginated.has_next,
                "has_prev": paginated.has_prev,
                "next_num": paginated.next_num,
                "prev_num": paginated.prev_num,
            },
        }
