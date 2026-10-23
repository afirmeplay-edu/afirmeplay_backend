# -*- coding: utf-8 -*-
"""Cadastro de questões do Afirme Ler sobre public.question (origin = 'afirme_ler')."""
from __future__ import annotations

import math
import uuid
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import or_
from sqlalchemy.orm import joinedload

from app import db
from app.mapa_questoes.helpers import LETTERS, OBJECTIVE_TYPES, normalize_question_type
from app.models.question import QUESTION_ORIGIN_LER, QUESTION_ORIGINS, Question
from app.permissions.roles import Roles
from app.utils.response_formatters import format_question_response
from app.afirme_ler.services.scope_service import (
    apply_visibility_filter,
    resolve_scope_on_create,
    user_can_modify,
)

QUESTION_TYPE_MULTIPLE_CHOICE = "multipleChoice"
OBJECTIVE_DB_TYPES = ("multipleChoice", "multiple_choice")

WRITE_ROLES = (
    Roles.ADMIN,
    Roles.TECADM,
    Roles.PROFESSOR,
    Roles.COORDENADOR,
    Roles.DIRETOR,
)

MIN_ALTERNATIVES = 2
MAX_ALTERNATIVES = len(LETTERS)
DEFAULT_PER_PAGE = 10
MAX_PER_PAGE = 100

# Campos opcionais do corpo (camelCase do Play) → coluna.
_OPTIONAL_FIELDS = {
    "number": "number",
    "formattedText": "formatted_text",
    "secondStatement": "secondstatement",
    "title": "title",
    "description": "description",
    "command": "command",
    "subtitle": "subtitle",
    "difficulty": "difficulty_level",
    "formattedSolution": "formatted_solution",
    "topics": "topics",
    "educationStageId": "education_stage_id",
}


def _user_id(user: Dict[str, Any]) -> Optional[str]:
    uid = user.get("id") or user.get("user_id")
    return str(uid) if uid else None


def assert_can_write(user: Dict[str, Any]) -> None:
    role = Roles.normalize(user.get("role", ""))
    if role not in WRITE_ROLES:
        raise PermissionError("Seu perfil não pode cadastrar ou editar questões.")


def normalize_ler_question_type(value: Any) -> str:
    if value is None or not str(value).strip():
        raise ValueError("type é obrigatório.")
    if normalize_question_type(value) not in OBJECTIVE_TYPES:
        raise ValueError(
            "No Afirme Ler só é permitido o tipo multipleChoice (múltipla escolha)."
        )
    return QUESTION_TYPE_MULTIPLE_CHOICE


def _alternative_has_content(alt: Dict[str, Any]) -> bool:
    text = str(alt.get("text") or alt.get("answer") or "").strip()
    if text:
        return True
    formatted = str(alt.get("formattedText") or alt.get("formatted_text") or "").strip()
    if formatted:
        return True
    image = alt.get("image")
    if isinstance(image, str):
        return bool(image.strip())
    if isinstance(image, dict):
        return bool(
            image.get("data") or image.get("base64") or image.get("id")
            or image.get("minio_object_name")
        )
    return False


def validate_ler_alternatives(options: Any) -> Tuple[List[Dict[str, Any]], str]:
    """
    Valida as alternativas e devolve (alternativas, letra do gabarito).

    Exige de 2 a 8 alternativas (A–H), cada uma com texto ou imagem,
    e exatamente uma marcada com isCorrect.
    """
    if not isinstance(options, list) or not options:
        raise ValueError("options é obrigatório e deve ser uma lista de alternativas.")
    if len(options) < MIN_ALTERNATIVES:
        raise ValueError(f"Informe pelo menos {MIN_ALTERNATIVES} alternativas.")
    if len(options) > MAX_ALTERNATIVES:
        raise ValueError(
            f"Informe no máximo {MAX_ALTERNATIVES} alternativas (letras A a {LETTERS[-1]})."
        )

    normalized: List[Dict[str, Any]] = []
    correct_indexes: List[int] = []
    for index, alt in enumerate(options):
        if not isinstance(alt, dict):
            raise ValueError(f"A alternativa {LETTERS[index]} deve ser um objeto.")
        if not _alternative_has_content(alt):
            raise ValueError(f"A alternativa {LETTERS[index]} precisa de texto ou imagem.")
        is_correct = alt.get("isCorrect", alt.get("is_correct", False))
        if not isinstance(is_correct, bool):
            raise ValueError(
                f"isCorrect da alternativa {LETTERS[index]} deve ser true ou false."
            )
        item = {k: v for k, v in alt.items() if k != "is_correct"}
        item["isCorrect"] = is_correct
        if is_correct:
            correct_indexes.append(index)
        normalized.append(item)

    if len(correct_indexes) != 1:
        raise ValueError("Marque exatamente uma alternativa correta (isCorrect: true).")
    return normalized, LETTERS[correct_indexes[0]]


def parse_value(value: Any) -> float:
    if value is None or value == "":
        return 1.0
    if isinstance(value, bool):
        raise ValueError("value deve ser um número maior que zero.")
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("value deve ser um número maior que zero.") from exc
    if not math.isfinite(parsed) or parsed <= 0:
        raise ValueError("value deve ser um número maior que zero.")
    return parsed


def parse_skill(value: Any) -> Optional[str]:
    """Mesma regra do Play: só uma habilidade; se vier lista, usa a primeira."""
    if isinstance(value, list):
        value = value[0] if value else None
    if value is None or not str(value).strip():
        return None
    return str(value).strip()


def _optional_value(key: str, value: Any) -> Any:
    if key != "educationStageId":
        return value
    if value is None or not str(value).strip():
        return None
    try:
        return uuid.UUID(str(value).strip())
    except ValueError as exc:
        raise ValueError("educationStageId deve ser um UUID.") from exc


def _required_text(data: dict, key: str) -> str:
    value = data.get(key)
    if value is None or not str(value).strip():
        raise ValueError(f"{key} é obrigatório.")
    return str(value).strip()


def _grade_id(value: Any) -> uuid.UUID:
    if isinstance(value, dict):
        value = value.get("id")
    if value is None or not str(value).strip():
        raise ValueError("grade é obrigatório.")
    try:
        return uuid.UUID(str(value).strip())
    except ValueError as exc:
        raise ValueError("grade deve ser o UUID de uma série.") from exc


def parse_create_payload(data: Any) -> Dict[str, Any]:
    """Valida o corpo de criação e devolve as colunas de Question (sem escopo/autor)."""
    if not isinstance(data, dict):
        raise ValueError("Corpo da requisição inválido.")

    fields: Dict[str, Any] = {
        "text": _required_text(data, "text"),
        "question_type": normalize_ler_question_type(data.get("type")),
        "subject_id": _required_text(data, "subjectId"),
        "grade_level": _grade_id(data.get("grade")),
        "skill": parse_skill(data.get("skills")),
        "value": parse_value(data.get("value")),
    }
    alternatives, letter = validate_ler_alternatives(data.get("options"))
    fields["alternatives"] = alternatives
    fields["correct_answer"] = letter

    for key, column in _OPTIONAL_FIELDS.items():
        if key in data:
            fields[column] = _optional_value(key, data.get(key))
    return fields


def apply_update_payload(question: Any, data: Any) -> None:
    """Aplica PUT parcial e revalida tipo e gabarito sobre o estado final."""
    if not isinstance(data, dict) or not data:
        raise ValueError("Corpo da requisição inválido.")

    if "text" in data:
        question.text = _required_text(data, "text")
    if "subjectId" in data:
        question.subject_id = _required_text(data, "subjectId")
    if "grade" in data:
        question.grade_level = _grade_id(data.get("grade"))
    if "skills" in data:
        question.skill = parse_skill(data.get("skills"))
    if "value" in data:
        question.value = parse_value(data.get("value"))
    for key, column in _OPTIONAL_FIELDS.items():
        if key in data:
            setattr(question, column, _optional_value(key, data.get(key)))

    question.question_type = normalize_ler_question_type(
        data["type"] if "type" in data else question.question_type
    )
    options = data["options"] if "options" in data else question.alternatives
    alternatives, letter = validate_ler_alternatives(options)
    question.alternatives = alternatives
    question.correct_answer = letter


def _assert_references_exist(subject_id: Optional[str], grade_id: Optional[uuid.UUID],
                             education_stage_id: Optional[uuid.UUID]) -> None:
    from app.models.educationStage import EducationStage
    from app.models.grades import Grade
    from app.models.subject import Subject

    if subject_id and not db.session.get(Subject, subject_id):
        raise ValueError("Disciplina (subjectId) não encontrada.")
    if grade_id and not db.session.get(Grade, grade_id):
        raise ValueError("Série (grade) não encontrada.")
    if education_stage_id and not db.session.get(EducationStage, education_stage_id):
        raise ValueError("Etapa de ensino (educationStageId) não encontrada.")


def _apply_images(question: Question) -> None:
    from app.routes.question_routes import _apply_question_images_pipeline

    _apply_question_images_pipeline(question)


def _with_relations(query):
    return query.options(
        joinedload(Question.subject),
        joinedload(Question.grade),
        joinedload(Question.education_stage),
        joinedload(Question.creator),
        joinedload(Question.last_modifier),
    )


def _parse_positive_int(value: Any, name: str, default: int) -> int:
    if value is None or value == "":
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} deve ser um número inteiro.") from exc
    if parsed < 1:
        raise ValueError(f"{name} deve ser maior que zero.")
    return parsed


def _escape_like(term: str) -> str:
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def to_response(question: Question) -> Dict[str, Any]:
    data = format_question_response(question)
    data["origin"] = question.origin
    data["scopeType"] = question.scope_type
    return data


class QuestionBankService:
    @staticmethod
    def _get_visible_question(user: Dict[str, Any], question_id: str) -> Question:
        query = _with_relations(Question.query.filter(Question.id == str(question_id)))
        question = apply_visibility_filter(query, Question, user).first()
        if not question:
            raise LookupError("Questão não encontrada.")
        return question

    @staticmethod
    def get_question(user: Dict[str, Any], question_id: str) -> Question:
        return QuestionBankService._get_visible_question(user, question_id)

    @staticmethod
    def list_questions(user: Dict[str, Any], filters: dict) -> Dict[str, Any]:
        page = _parse_positive_int(filters.get("page"), "page", 1)
        per_page = min(
            _parse_positive_int(filters.get("per_page"), "per_page", DEFAULT_PER_PAGE),
            MAX_PER_PAGE,
        )

        query = apply_visibility_filter(_with_relations(Question.query), Question, user)

        question_type = (filters.get("type") or "").strip()
        if question_type:
            if normalize_question_type(question_type) in OBJECTIVE_TYPES:
                query = query.filter(Question.question_type.in_(OBJECTIVE_DB_TYPES))
            else:
                query = query.filter(Question.question_type == question_type)

        subject_id = (filters.get("subject_id") or "").strip()
        if subject_id:
            query = query.filter(Question.subject_id == subject_id)

        grade_id = (filters.get("grade_id") or "").strip()
        if grade_id:
            try:
                query = query.filter(Question.grade_level == uuid.UUID(grade_id))
            except ValueError as exc:
                raise ValueError("grade_id deve ser um UUID.") from exc

        difficulty = (filters.get("difficulty") or "").strip()
        if difficulty:
            query = query.filter(Question.difficulty_level == difficulty)

        origin = (filters.get("origin") or "").strip()
        if origin:
            if origin not in QUESTION_ORIGINS:
                raise ValueError("origin inválido. Valores permitidos: afirme_play, afirme_ler.")
            query = query.filter(Question.origin == origin)

        term = (filters.get("q") or "").strip()
        if term:
            pattern = f"%{_escape_like(term)}%"
            query = query.filter(
                or_(
                    Question.text.ilike(pattern, escape="\\"),
                    Question.formatted_text.ilike(pattern, escape="\\"),
                )
            )

        query = query.order_by(Question.created_at.desc(), Question.id.asc())
        paginated = query.paginate(page=page, per_page=per_page, error_out=False)
        return {
            "data": [to_response(q) for q in paginated.items],
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

    @staticmethod
    def create(user: Dict[str, Any], data: Any) -> Question:
        assert_can_write(user)
        fields = parse_create_payload(data)
        _assert_references_exist(
            fields["subject_id"], fields["grade_level"], fields.get("education_stage_id")
        )
        scope_type, owner_city_id, owner_user_id = resolve_scope_on_create(user)

        question = Question(
            **fields,
            images=[],
            version=1,
            origin=QUESTION_ORIGIN_LER,
            created_by=_user_id(user),
            scope_type=scope_type,
            owner_city_id=owner_city_id,
            owner_user_id=owner_user_id,
        )
        db.session.add(question)
        db.session.flush()
        _apply_images(question)
        db.session.commit()
        return QuestionBankService._get_visible_question(user, question.id)

    @staticmethod
    def update(user: Dict[str, Any], question_id: str, data: Any) -> Question:
        assert_can_write(user)
        question = QuestionBankService._get_visible_question(user, question_id)
        if question.origin != QUESTION_ORIGIN_LER:
            raise PermissionError(
                "Questões do Afirme Play são somente leitura no Afirme Ler."
            )
        if not user_can_modify(user, question):
            raise PermissionError("Você não tem permissão para editar esta questão.")

        apply_update_payload(question, data)
        _assert_references_exist(
            question.subject_id if "subjectId" in data else None,
            question.grade_level if "grade" in data else None,
            question.education_stage_id if "educationStageId" in data else None,
        )
        if any(key in data for key in ("formattedText", "formattedSolution", "options")):
            _apply_images(question)

        question.last_modified_by = _user_id(user)
        question.version = (question.version or 0) + 1
        db.session.commit()
        return QuestionBankService._get_visible_question(user, question.id)
