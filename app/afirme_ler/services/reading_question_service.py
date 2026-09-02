# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Dict, List

from app import db
from app.permissions.roles import Roles
from app.afirme_ler.models import ReadingTextQuestion
from app.afirme_ler.services.parsing import (
    get_field,
    options_declare_correct_flags,
    parse_reading_question_payload,
    validate_question_options,
)
from app.afirme_ler.services.reading_text_service import ReadingTextService
from app.afirme_ler.services.scope_service import user_can_modify
from app.afirme_ler.services.tenant_usage import question_has_answers_in_tenant


class ReadingQuestionService:
    @staticmethod
    def _parent_for_write(user: Dict[str, Any], text_id: str):
        text = ReadingTextService.get_visible_text(user, text_id)
        if not user_can_modify(user, text):
            raise PermissionError("Você não tem permissão para alterar questões deste texto.")
        return text

    @staticmethod
    def create(user: Dict[str, Any], text_id: str, data: dict) -> ReadingTextQuestion:
        ReadingQuestionService._parent_for_write(user, text_id)
        fields = parse_reading_question_payload(data)
        question = ReadingTextQuestion(reading_text_id=text_id, **fields)
        db.session.add(question)
        db.session.commit()
        return question

    @staticmethod
    def create_bulk(user: Dict[str, Any], text_id: str, items: List[dict]) -> List[ReadingTextQuestion]:
        ReadingQuestionService._parent_for_write(user, text_id)
        if not isinstance(items, list) or not items:
            raise ValueError("Informe ao menos uma questão em bulk.")

        created: List[ReadingTextQuestion] = []
        for item in items:
            fields = parse_reading_question_payload(item)
            question = ReadingTextQuestion(reading_text_id=text_id, **fields)
            db.session.add(question)
            created.append(question)
        db.session.commit()
        return created

    @staticmethod
    def list_questions(user: Dict[str, Any], text_id: str) -> List[ReadingTextQuestion]:
        ReadingTextService.get_visible_text(user, text_id)
        return (
            ReadingTextQuestion.query.filter_by(reading_text_id=text_id)
            .order_by(ReadingTextQuestion.created_at.asc())
            .all()
        )

    @staticmethod
    def get_question(user: Dict[str, Any], text_id: str, question_id: str) -> ReadingTextQuestion:
        ReadingTextService.get_visible_text(user, text_id)
        question = ReadingTextQuestion.query.filter_by(
            id=question_id,
            reading_text_id=text_id,
        ).first()
        if not question:
            raise LookupError("Questão não encontrada.")
        return question

    @staticmethod
    def update(user: Dict[str, Any], text_id: str, question_id: str, data: dict) -> ReadingTextQuestion:
        ReadingQuestionService._parent_for_write(user, text_id)
        question = ReadingQuestionService.get_question(user, text_id, question_id)

        if "statement" in data or "enunciado" in data:
            statement = get_field(data, "statement", "enunciado")
            if not statement or not str(statement).strip():
                raise ValueError("statement não pode ser vazio.")
            question.statement = str(statement).strip()

        if "descriptor" in data:
            descriptor = get_field(data, "descriptor")
            if not descriptor or not str(descriptor).strip():
                raise ValueError("descriptor não pode ser vazio.")
            question.descriptor = str(descriptor).strip()

        has_correct = "correctOption" in data or "correct_option" in data
        options_value = get_field(data, "options")
        if options_value is not None or has_correct:
            options = options_value if options_value is not None else question.options
            if has_correct:
                correct_option = get_field(data, "correctOption", "correct_option")
            elif options_declare_correct_flags(options):
                correct_option = None
            else:
                correct_option = question.correct_option
            parsed_options, parsed_correct = validate_question_options(options, correct_option)
            question.options = parsed_options
            question.correct_option = parsed_correct

        db.session.commit()
        return question

    @staticmethod
    def delete(user: Dict[str, Any], text_id: str, question_id: str) -> None:
        ReadingQuestionService._parent_for_write(user, text_id)
        question = ReadingQuestionService.get_question(user, text_id, question_id)

        role = Roles.normalize(user.get("role", ""))
        city_id = user.get("tenant_id") or user.get("city_id")
        if role == Roles.ADMIN:
            in_use = question_has_answers_in_tenant(question_id)
        else:
            in_use = question_has_answers_in_tenant(
                question_id,
                city_id=str(city_id) if city_id else None,
            )
        if in_use:
            raise ValueError(
                "Não é possível excluir a questão: existem respostas de alunos vinculadas."
            )

        db.session.delete(question)
        db.session.commit()
