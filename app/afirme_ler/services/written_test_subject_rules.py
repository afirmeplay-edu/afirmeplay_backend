# -*- coding: utf-8 -*-
"""
Regras da avaliação escrita por disciplina (Português / Matemática).

A disciplina da prova vem de reading_written_test.subject_id → public.subject.name.
IDs de subject não são fixos: produção pode diferir do dev.
"""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from typing import Any, Dict, Optional, Sequence, Tuple

from app import db
from app.afirme_ler.services.question_bank_service import (
    OBJECTIVE_DB_TYPES,
    QUESTION_TYPE_DICTATION,
    QUESTION_TYPE_MULTIPLE_CHOICE,
    QUESTION_TYPE_TEXT_PRODUCTION,
)
from app.models.subject import Subject

SUBJECT_KEY_PORTUGUES = "portugues"
SUBJECT_KEY_MATEMATICA = "matematica"
ALLOWED_SUBJECT_KEYS = (SUBJECT_KEY_PORTUGUES, SUBJECT_KEY_MATEMATICA)

MSG_MATH_NOT_APPLICABLE = "Não se aplica a avaliações de Matemática"
MSG_SUBJECT_UNSUPPORTED = (
    "Disciplina não suportada na avaliação escrita. Use Português ou Matemática."
)
MSG_SUBJECT_REQUIRED = "subjectId é obrigatório."
MSG_SUBJECT_NOT_FOUND = "Disciplina (subjectId) não encontrada."
MSG_SUBJECT_CHANGE_LOCKED = (
    "Não é possível trocar a disciplina enquanto houver questões vinculadas. "
    "Remova as questões antes de alterar subjectId."
)
MSG_MATH_COUNT = (
    "A prova de Matemática precisa ter entre 16 e 19 questões de múltipla escolha"
)
MSG_PORTUGUES_COUNT = (
    "A avaliação precisa ter exatamente 19 questões para ser publicada"
)
MSG_QUESTION_SUBJECT_MISMATCH = (
    "A questão {question_id} é de outra disciplina. "
    "Todas as questões devem ser da mesma disciplina da avaliação."
)
MSG_MATH_FORBIDDEN_TYPE = (
    "A prova de Matemática aceita apenas questões de múltipla escolha. "
    "Ditado e produção escrita não são permitidos."
)


@dataclass(frozen=True)
class SubjectRules:
    key: str
    min_questions: int
    max_questions: int
    # Para Português: faixas por tipo na publicação. Para Matemática: None (todas MC).
    publish_pattern: Optional[Tuple[Tuple[range, str, str], ...]]
    allowed_types: Tuple[str, ...]
    forbid_types: Tuple[str, ...]


PORTUGUES_RULES = SubjectRules(
    key=SUBJECT_KEY_PORTUGUES,
    min_questions=19,
    max_questions=19,
    publish_pattern=(
        (range(1, 17), QUESTION_TYPE_MULTIPLE_CHOICE, "múltipla escolha"),
        (range(17, 19), QUESTION_TYPE_DICTATION, "ditado"),
        (range(19, 20), QUESTION_TYPE_TEXT_PRODUCTION, "bilhete"),
    ),
    allowed_types=(
        QUESTION_TYPE_MULTIPLE_CHOICE,
        QUESTION_TYPE_DICTATION,
        QUESTION_TYPE_TEXT_PRODUCTION,
    ),
    forbid_types=(),
)

MATEMATICA_RULES = SubjectRules(
    key=SUBJECT_KEY_MATEMATICA,
    min_questions=16,
    max_questions=19,
    publish_pattern=None,
    allowed_types=(QUESTION_TYPE_MULTIPLE_CHOICE,),
    forbid_types=(QUESTION_TYPE_DICTATION, QUESTION_TYPE_TEXT_PRODUCTION),
)

SUBJECT_RULES: Dict[str, SubjectRules] = {
    SUBJECT_KEY_PORTUGUES: PORTUGUES_RULES,
    SUBJECT_KEY_MATEMATICA: MATEMATICA_RULES,
}


def _strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def normalize_subject_name(name: Optional[str]) -> str:
    if not name:
        return ""
    return " ".join(_strip_accents(str(name)).casefold().split())


def subject_key_from_name(name: Optional[str]) -> Optional[str]:
    """Resolve 'portugues' | 'matematica' pelo nome do subject; None se não reconhecer."""
    text = normalize_subject_name(name)
    if not text:
        return None
    if "portugu" in text or text in {"lp", "lingua portuguesa", "lingua portuguesa"}:
        return SUBJECT_KEY_PORTUGUES
    if "matem" in text:
        return SUBJECT_KEY_MATEMATICA
    return None


def find_subject_id_by_key(key: str) -> str:
    """
    Busca public.subject pelo nome. Falha com ValueError se não achar exatamente um
    candidato claro (útil em migration/backfill).
    """
    if key not in SUBJECT_RULES:
        raise ValueError(f"Chave de disciplina inválida: {key}.")
    rows = Subject.query.all()
    matches = [row for row in rows if subject_key_from_name(row.name) == key]
    if not matches:
        label = "Português" if key == SUBJECT_KEY_PORTUGUES else "Matemática"
        raise ValueError(
            f"Não foi possível encontrar a disciplina '{label}' em public.subject pelo nome. "
            "Cadastre-a (ou ajuste o nome) antes de rodar a migration."
        )
    if len(matches) > 1:
        # Preferência: nome mais curto / mais “canônico” (ex.: Matemática vs Matemática - …)
        matches.sort(key=lambda row: (len(str(row.name or "")), str(row.name or ""), str(row.id)))
    return str(matches[0].id)


def resolve_subject_key(subject_id: Optional[str]) -> str:
    if not subject_id or not str(subject_id).strip():
        raise ValueError(MSG_SUBJECT_REQUIRED)
    subject = db.session.get(Subject, str(subject_id).strip())
    if subject is None:
        raise ValueError(MSG_SUBJECT_NOT_FOUND)
    key = subject_key_from_name(subject.name)
    if key is None:
        raise ValueError(MSG_SUBJECT_UNSUPPORTED)
    return key


def rules_for_subject_id(subject_id: Optional[str]) -> SubjectRules:
    return SUBJECT_RULES[resolve_subject_key(subject_id)]


def rules_for_written_test(written_test: Any) -> SubjectRules:
    return rules_for_subject_id(getattr(written_test, "subject_id", None))


def subject_payload(subject_id: Optional[str]) -> Dict[str, Any]:
    """Campos de disciplina + min/max para to_dict."""
    if not subject_id:
        return {
            "subjectId": None,
            "subjectName": None,
            "minQuestions": None,
            "maxQuestions": None,
        }
    subject = db.session.get(Subject, str(subject_id))
    name = subject.name if subject else None
    try:
        rules = rules_for_subject_id(subject_id)
        return {
            "subjectId": str(subject_id),
            "subjectName": name,
            "minQuestions": rules.min_questions,
            "maxQuestions": rules.max_questions,
        }
    except ValueError:
        return {
            "subjectId": str(subject_id),
            "subjectName": name,
            "minQuestions": None,
            "maxQuestions": None,
        }


def is_matematica(written_test: Any) -> bool:
    try:
        return resolve_subject_key(getattr(written_test, "subject_id", None)) == SUBJECT_KEY_MATEMATICA
    except ValueError:
        return False


def assert_not_matematica(written_test: Any) -> None:
    if is_matematica(written_test):
        raise ValueError(MSG_MATH_NOT_APPLICABLE)


def _type_key(question_type: Optional[str]) -> Optional[str]:
    if question_type in OBJECTIVE_DB_TYPES:
        return QUESTION_TYPE_MULTIPLE_CHOICE
    if question_type in (QUESTION_TYPE_DICTATION, QUESTION_TYPE_TEXT_PRODUCTION):
        return question_type
    return None


def assert_question_matches_rules(
    question: Any,
    rules: SubjectRules,
    assessment_subject_id: str,
) -> None:
    type_key = _type_key(getattr(question, "question_type", None))
    if type_key is None or type_key not in rules.allowed_types:
        if rules.key == SUBJECT_KEY_MATEMATICA:
            raise ValueError(MSG_MATH_FORBIDDEN_TYPE)
        raise ValueError(
            f"A questão {question.id} é do tipo {question.question_type or 'sem tipo'}, "
            "que não é aceito na avaliação escrita. Tipos permitidos: "
            "multipleChoice, dictation e text_production."
        )
    if type_key in rules.forbid_types:
        raise ValueError(MSG_MATH_FORBIDDEN_TYPE)
    # Compara pela disciplina resolvida (portugues|matematica), não pelo UUID exato —
    # "Português" e "Língua Portuguesa" contam como a mesma.
    assessment_key = resolve_subject_key(assessment_subject_id)
    question_subject_id = str(getattr(question, "subject_id", None) or "").strip()
    try:
        question_key = resolve_subject_key(question_subject_id) if question_subject_id else None
    except ValueError:
        question_key = None
    if question_key != assessment_key:
        raise ValueError(MSG_QUESTION_SUBJECT_MISMATCH.format(question_id=question.id))


def assert_publish_composition(
    links: Sequence[Any],
    found: Dict[str, Any],
    rules: SubjectRules,
) -> None:
    count = len(links)
    if rules.key == SUBJECT_KEY_MATEMATICA:
        if count < rules.min_questions or count > rules.max_questions:
            raise ValueError(f"{MSG_MATH_COUNT} (hoje tem {count}).")
        for link in links:
            question = found[link.question_id]
            if _type_key(question.question_type) != QUESTION_TYPE_MULTIPLE_CHOICE:
                raise ValueError(MSG_MATH_FORBIDDEN_TYPE)
        return

    if count != rules.min_questions:
        raise ValueError(f"{MSG_PORTUGUES_COUNT} (hoje tem {count}).")
    by_order = {int(link.order): found[link.question_id] for link in links}
    for orders, expected, label in rules.publish_pattern or ():
        for order in orders:
            actual = _type_key(by_order[order].question_type)
            if actual != expected:
                raise ValueError(
                    f"A posição {order} precisa ser {label}. "
                    "A prova tem 16 questões de múltipla escolha (1 a 16), "
                    "2 ditados (17 e 18) e 1 bilhete (19)."
                )


def max_questions_message(rules: SubjectRules) -> str:
    if rules.key == SUBJECT_KEY_MATEMATICA:
        return MSG_MATH_COUNT + "."
    return f"A avaliação aceita no máximo {rules.max_questions} questões."
