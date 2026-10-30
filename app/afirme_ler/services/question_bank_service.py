# -*- coding: utf-8 -*-
"""Cadastro de questões do Afirme Ler sobre public.question (origin = 'afirme_ler')."""
from __future__ import annotations

import base64
import json
import logging
import math
import os
import re
import uuid
from pathlib import Path
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
QUESTION_TYPE_DICTATION = "dictation"
QUESTION_TYPE_TEXT_PRODUCTION = "text_production"
LER_QUESTION_TYPES = (
    QUESTION_TYPE_MULTIPLE_CHOICE,
    QUESTION_TYPE_DICTATION,
    QUESTION_TYPE_TEXT_PRODUCTION,
)
OBJECTIVE_DB_TYPES = ("multipleChoice", "multiple_choice")

# Chaves já passadas por normalize_question_type (minúsculas, espaço/hífen → "_").
DICTATION_ALIASES = {"dictation", "ditado"}
TEXT_PRODUCTION_ALIASES = {
    "text_production",
    "producao_textual",
    "produção_textual",
    "bilhete",
}
TYPE_LABELS = {
    QUESTION_TYPE_DICTATION: "ditado (dictation)",
    QUESTION_TYPE_TEXT_PRODUCTION: "produção escrita (text_production)",
}
MAX_DICTATED_WORD_LENGTH = 40
MAX_IMAGE_DESCRIPTION_LENGTH = 500
_DATA_IMAGE = re.compile(
    r'<img[^>]+src="(data:image/[^;]+;base64,[^"]+)"',
    re.IGNORECASE,
)
STIMULUS_WORD = "word"
STIMULUS_IMAGE = "image"
_STIMULUS_ALIASES = {
    "word": STIMULUS_WORD,
    "ditado": STIMULUS_WORD,
    "palavra": STIMULUS_WORD,
    "image": STIMULUS_IMAGE,
    "imagem": STIMULUS_IMAGE,
    "figura": STIMULUS_IMAGE,
}

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


def canonical_ler_question_type(value: Any) -> Optional[str]:
    """Nome canônico do tipo no Afirme Ler, ou None se não for um tipo do Ler."""
    key = normalize_question_type(value)
    if key in OBJECTIVE_TYPES:
        return QUESTION_TYPE_MULTIPLE_CHOICE
    if key in DICTATION_ALIASES:
        return QUESTION_TYPE_DICTATION
    if key in TEXT_PRODUCTION_ALIASES:
        return QUESTION_TYPE_TEXT_PRODUCTION
    return None


def normalize_ler_question_type(value: Any) -> str:
    if value is None or not str(value).strip():
        raise ValueError("type é obrigatório.")
    canonical = canonical_ler_question_type(value)
    if canonical is None:
        raise ValueError(
            "Tipo de questão inválido no Afirme Ler. Tipos permitidos: "
            "multipleChoice (múltipla escolha), dictation (ditado) e "
            "text_production (produção escrita)."
        )
    return canonical


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


def parse_dictated_word(value: Any) -> str:
    if value is None or (isinstance(value, str) and not value.strip()):
        raise ValueError("dictatedWord é obrigatório para questões de ditado (dictation).")
    if not isinstance(value, str):
        raise ValueError("dictatedWord deve ser um texto.")
    word = value.strip()
    if any(char.isspace() for char in word):
        raise ValueError("dictatedWord deve ser uma única palavra, sem espaços.")
    if len(word) > MAX_DICTATED_WORD_LENGTH:
        raise ValueError(
            f"dictatedWord deve ter no máximo {MAX_DICTATED_WORD_LENGTH} caracteres."
        )
    return word


def _assert_without_options(question_type: str, options: Any) -> None:
    if options is None or options == [] or options == "":
        return
    raise ValueError(
        f"Questão de {TYPE_LABELS[question_type]} não tem alternativas. Não envie options."
    )


def parse_stimulus(value: Any, question_type: str, default: Optional[str] = None) -> Optional[str]:
    """word ou image no ditado. Nos outros tipos, stimulus não é aceito."""
    if question_type != QUESTION_TYPE_DICTATION:
        if value is None or (isinstance(value, str) and not str(value).strip()):
            return None
        raise ValueError("stimulus só vale para questão de ditado (dictation).")
    if value is None or (isinstance(value, str) and not str(value).strip()):
        value = default or STIMULUS_WORD
    if not isinstance(value, str):
        raise ValueError("stimulus deve ser word ou image.")
    stimulus = _STIMULUS_ALIASES.get(value.strip().lower())
    if stimulus is None:
        raise ValueError("stimulus deve ser word ou image.")
    return stimulus


def resolve_answer_fields(
    question_type: str,
    data: Dict[str, Any],
    current_alternatives: Any = None,
    current_dictated_word: Optional[str] = None,
    stimulus: str = STIMULUS_WORD,
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """
    Alternativas e gabarito do estado final, pelas regras do tipo.

    multipleChoice: alternativas validadas e letra. dictation em word: sem
    alternativas, gabarito = palavra ditada. dictation em image: sem gabarito
    (a descrição da figura é gerada depois). text_production: sem gabarito.
    """
    if question_type == QUESTION_TYPE_MULTIPLE_CHOICE:
        options = data["options"] if "options" in data else current_alternatives
        return validate_ler_alternatives(options)

    if "options" in data:
        _assert_without_options(question_type, data.get("options"))
    if question_type == QUESTION_TYPE_DICTATION:
        if stimulus == STIMULUS_IMAGE:
            word = data.get("dictatedWord")
            if isinstance(word, str) and word.strip():
                raise ValueError(
                    "Questão com imagem não recebe dictatedWord. "
                    "Gere a descrição da figura."
                )
            return [], None
        word = data["dictatedWord"] if "dictatedWord" in data else current_dictated_word
        return [], parse_dictated_word(word)
    return [], None


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
    stimulus = parse_stimulus(data.get("stimulus"), fields["question_type"])
    alternatives, answer = resolve_answer_fields(
        fields["question_type"], data, stimulus=stimulus or STIMULUS_WORD,
    )
    fields["alternatives"] = alternatives
    fields["correct_answer"] = answer
    fields["writing_stimulus"] = stimulus
    fields["writing_reference"] = _accepted_image_description(data, stimulus)

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

    previous_type = question.question_type
    final_type = normalize_ler_question_type(
        data["type"] if "type" in data else previous_type
    )
    previous_stimulus = (
        question.writing_stimulus if previous_type == QUESTION_TYPE_DICTATION else None
    )
    if final_type == QUESTION_TYPE_DICTATION:
        stimulus = parse_stimulus(
            data.get("stimulus") if "stimulus" in data else previous_stimulus,
            final_type,
            default=previous_stimulus or STIMULUS_WORD,
        )
    elif "stimulus" in data and str(data.get("stimulus") or "").strip():
        raise ValueError("stimulus só vale para questão de ditado (dictation).")
    else:
        stimulus = None
    alternatives, answer = resolve_answer_fields(
        final_type,
        data,
        current_alternatives=question.alternatives,
        current_dictated_word=(
            question.correct_answer if previous_type == QUESTION_TYPE_DICTATION else None
        ),
        stimulus=stimulus or STIMULUS_WORD,
    )
    question.question_type = final_type
    question.alternatives = alternatives
    question.correct_answer = answer
    question.writing_stimulus = stimulus
    if stimulus != STIMULUS_IMAGE or (
        "formattedText" in data and not _description_in(data)
    ):
        question.writing_reference = None
    if _description_in(data):
        question.writing_reference = _accepted_image_description(data, stimulus)


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
    stimulus = (
        question.writing_stimulus
        if question.question_type == QUESTION_TYPE_DICTATION
        else None
    )
    if stimulus not in (STIMULUS_WORD, STIMULUS_IMAGE):
        stimulus = STIMULUS_WORD if question.question_type == QUESTION_TYPE_DICTATION else None
    image_description = (
        question.writing_reference
        if stimulus == STIMULUS_IMAGE and question.writing_reference
        else None
    )
    data["stimulus"] = stimulus
    data["imageDescription"] = image_description
    data["dictatedWord"] = (
        question.correct_answer
        if stimulus == STIMULUS_WORD
        else None
    )
    if stimulus == STIMULUS_IMAGE:
        data["correct_answer"] = ""
        data["solution"] = ""
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
            canonical = canonical_ler_question_type(question_type)
            if canonical == QUESTION_TYPE_MULTIPLE_CHOICE:
                query = query.filter(Question.question_type.in_(OBJECTIVE_DB_TYPES))
            elif canonical:
                query = query.filter(Question.question_type == canonical)
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
        if any(key in data for key in ("type", "formattedText", "formattedSolution", "options")):
            _apply_images(question)

        question.last_modified_by = _user_id(user)
        question.version = (question.version or 0) + 1
        db.session.commit()
        return QuestionBankService._get_visible_question(user, question.id)

    @staticmethod
    def describe_image(user: Dict[str, Any], question_id: str) -> Question:
        """Gera a descrição da figura do ditado e grava na questão."""
        assert_can_write(user)
        question = QuestionBankService._get_visible_question(user, question_id)
        if question.origin != QUESTION_ORIGIN_LER:
            raise PermissionError(
                "Questões do Afirme Play são somente leitura no Afirme Ler."
            )
        if not user_can_modify(user, question):
            raise PermissionError("Você não tem permissão para editar esta questão.")
        if question.question_type != QUESTION_TYPE_DICTATION or question.writing_stimulus != STIMULUS_IMAGE:
            raise ValueError(
                "Só questão de ditado com stimulus image gera descrição da figura."
            )
        image = _stimulus_image(question)
        if image is None:
            raise ValueError("Anexe a imagem do objeto antes de gerar a descrição.")
        description = _describe_stimulus_image(image)
        question.writing_reference = description
        question.last_modified_by = _user_id(user)
        question.version = (question.version or 0) + 1
        db.session.commit()
        return QuestionBankService._get_visible_question(user, question.id)

    @staticmethod
    def preview_image_description(user: Dict[str, Any], data: Any) -> str:
        """Descreve a foto do formulário e devolve só o texto. Não grava questão."""
        assert_can_write(user)
        if not isinstance(data, dict) or not data:
            raise ValueError("Corpo da requisição inválido.")
        html = data.get("formattedText", data.get("formatted_text"))
        raw, mime = _first_embedded_image(html)
        return _describe_image_bytes(raw, mime)


def _description_in(data: Dict[str, Any]) -> bool:
    return "imageDescription" in data or "image_description" in data


def _raw_description(data: Dict[str, Any]) -> Any:
    if "imageDescription" in data:
        return data.get("imageDescription")
    return data.get("image_description")


def _clean_image_description(raw: Any) -> Optional[str]:
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise ValueError("imageDescription deve ser um texto.")
    text = raw.strip()
    if not text:
        return None
    if len(text) > MAX_IMAGE_DESCRIPTION_LENGTH:
        raise ValueError(
            f"imageDescription deve ter no máximo {MAX_IMAGE_DESCRIPTION_LENGTH} caracteres."
        )
    return text


def _accepted_image_description(data: Dict[str, Any], stimulus: Optional[str]) -> Optional[str]:
    if not _description_in(data):
        return None
    text = _clean_image_description(_raw_description(data))
    if text and stimulus != STIMULUS_IMAGE:
        raise ValueError("imageDescription só vale para ditado com stimulus image.")
    return text


def _first_embedded_image(html: Any) -> Tuple[bytes, str]:
    if not isinstance(html, str) or "data:image/" not in html:
        raise ValueError("Anexe a imagem do objeto antes de gerar a descrição.")
    match = _DATA_IMAGE.search(html)
    if match is None:
        raise ValueError("Anexe a imagem do objeto antes de gerar a descrição.")
    src = match.group(1)
    mime = src.split(";", 1)[0].split(":", 1)[-1].strip() or "image/png"
    if not mime.startswith("image/"):
        mime = "image/png"
    encoded = src.split(",", 1)[1]
    try:
        raw = base64.b64decode(encoded, validate=True)
    except Exception as exc:
        raise ValueError("A imagem anexada é inválida.") from exc
    if not raw:
        raise ValueError("Anexe a imagem do objeto antes de gerar a descrição.")
    return raw, mime


def _stimulus_image(question: Question) -> Optional[Dict[str, Any]]:
    images = question.images if isinstance(question.images, list) else []
    for image in images:
        if isinstance(image, dict) and image.get("minio_object_name") and image.get("minio_bucket"):
            return image
    return None


def _describe_stimulus_image(image: Dict[str, Any]) -> str:
    from app.services.storage.minio_service import MinIOService

    raw = MinIOService().download_file(image["minio_bucket"], image["minio_object_name"])
    if not raw:
        raise ValueError("Não foi possível ler a imagem do objeto.")
    mime = str(image.get("type") or "image/png")
    if not mime.startswith("image/"):
        mime = "image/png"
    return _describe_image_bytes(raw, mime)


def _describe_image_bytes(raw: bytes, mime: str) -> str:
    encoded = base64.b64encode(raw).decode("ascii")
    prompt_path = Path(__file__).resolve().parents[1] / "prompts" / "descricao_imagem.txt"
    system = f"TAREFA: DESCRICAO_IMAGEM\n\n{prompt_path.read_text(encoding='utf-8')}"
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY não configurada.")
    from openai import OpenAI

    client = OpenAI(api_key=api_key, timeout=90)
    response = client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL") or "gpt-4o",
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": [
                {"type": "text", "text": "Descreva o objeto desta figura."},
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{encoded}"}},
            ]},
        ],
    )
    content = response.choices[0].message.content or ""
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError("A IA não devolveu a descrição da imagem.") from exc
    description = str((payload or {}).get("descricao") or "").strip()
    if not description:
        raise ValueError("A IA não descreveu a imagem.")
    if len(description) > MAX_IMAGE_DESCRIPTION_LENGTH:
        description = description[:MAX_IMAGE_DESCRIPTION_LENGTH].rstrip()
    logging.getLogger(__name__).info("Descrição de figura gerada (%s caracteres).", len(description))
    return description
