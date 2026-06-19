# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import joinedload

from app import db
from app.models.grades import Grade
from app.permissions.roles import Roles
from app.afirme_ler.models import ReadingText
from app.afirme_ler.services.parsing import get_field, parse_string_list, validate_difficulty_level
from app.afirme_ler.services.scope_service import (
    apply_visibility_filter,
    resolve_scope_on_create,
    user_can_modify,
)
from app.afirme_ler.services.tenant_usage import count_evaluations_using_text


class ReadingTextService:
    @staticmethod
    def _get_grade(grade_id: str) -> Grade:
        grade = Grade.query.get(grade_id)
        if not grade:
            raise ValueError("Série (gradeId) não encontrada.")
        return grade

    @staticmethod
    def create(user: Dict[str, Any], data: dict) -> ReadingText:
        title = get_field(data, "title")
        content = get_field(data, "content")
        grade_id = get_field(data, "gradeId", "grade_id")
        difficulty = get_field(data, "difficultyLevel", "difficulty_level")

        if not title or not str(title).strip():
            raise ValueError("title é obrigatório.")
        if not content or not str(content).strip():
            raise ValueError("content é obrigatório.")
        if not grade_id:
            raise ValueError("gradeId é obrigatório.")

        ReadingTextService._get_grade(str(grade_id))
        difficulty_level = validate_difficulty_level(difficulty)
        target_skills = parse_string_list(get_field(data, "targetSkills", "target_skills", default=[]))

        scope_type, owner_city_id, owner_user_id = resolve_scope_on_create(user)
        user_id = user.get("id") or user.get("user_id")

        text = ReadingText(
            title=str(title).strip(),
            content=str(content).strip(),
            grade_id=grade_id,
            difficulty_level=difficulty_level,
            target_skills=target_skills,
            source=get_field(data, "source"),
            is_calibrated=bool(get_field(data, "isCalibrated", "is_calibrated", default=False)),
            scope_type=scope_type,
            owner_city_id=owner_city_id,
            owner_user_id=owner_user_id,
            created_by=user_id,
        )
        db.session.add(text)
        db.session.commit()
        return ReadingText.query.options(
            joinedload(ReadingText.grade),
            joinedload(ReadingText.questions),
        ).get(text.id)

    @staticmethod
    def list_texts(user: Dict[str, Any], filters: dict) -> List[ReadingText]:
        query = ReadingText.query.options(joinedload(ReadingText.grade))
        query = apply_visibility_filter(query, ReadingText, user)

        grade_id = filters.get("gradeId") or filters.get("grade_id")
        if grade_id:
            query = query.filter(ReadingText.grade_id == grade_id)

        difficulty = filters.get("difficultyLevel") or filters.get("difficulty_level")
        if difficulty:
            query = query.filter(
                ReadingText.difficulty_level == validate_difficulty_level(difficulty)
            )

        is_calibrated = filters.get("isCalibrated")
        if is_calibrated is None:
            is_calibrated = filters.get("is_calibrated")
        if is_calibrated is not None:
            if str(is_calibrated).lower() in ("true", "1", "yes"):
                query = query.filter(ReadingText.is_calibrated.is_(True))
            elif str(is_calibrated).lower() in ("false", "0", "no"):
                query = query.filter(ReadingText.is_calibrated.is_(False))

        order_by = (filters.get("orderBy") or filters.get("order_by") or "title").lower()
        if order_by == "difficulty":
            query = query.order_by(ReadingText.difficulty_level.asc())
        elif order_by in ("grade", "gradelevel", "grade_level"):
            query = query.join(Grade, ReadingText.grade_id == Grade.id).order_by(Grade.name.asc())
        else:
            query = query.order_by(ReadingText.title.asc())

        return query.all()

    @staticmethod
    def get_visible_text(user: Dict[str, Any], text_id: str, *, include_questions=False) -> ReadingText:
        options = [joinedload(ReadingText.grade)]
        if include_questions:
            options.append(joinedload(ReadingText.questions))

        query = ReadingText.query.options(*options)
        query = apply_visibility_filter(query, ReadingText, user)
        text = query.filter(ReadingText.id == text_id).first()
        if not text:
            raise LookupError("Texto de leitura não encontrado.")
        return text

    @staticmethod
    def update(user: Dict[str, Any], text_id: str, data: dict) -> ReadingText:
        text = ReadingText.query.options(
            joinedload(ReadingText.grade),
            joinedload(ReadingText.questions),
        ).get(text_id)
        if not text:
            raise LookupError("Texto de leitura não encontrado.")
        if not user_can_modify(user, text):
            raise PermissionError("Você não tem permissão para editar este texto.")

        if "title" in data:
            title = get_field(data, "title")
            if not title or not str(title).strip():
                raise ValueError("title não pode ser vazio.")
            text.title = str(title).strip()

        if "content" in data:
            content = get_field(data, "content")
            if not content or not str(content).strip():
                raise ValueError("content não pode ser vazio.")
            text.content = str(content).strip()

        if get_field(data, "gradeId", "grade_id") is not None:
            grade_id = get_field(data, "gradeId", "grade_id")
            ReadingTextService._get_grade(str(grade_id))
            text.grade_id = grade_id

        if get_field(data, "difficultyLevel", "difficulty_level") is not None:
            text.difficulty_level = validate_difficulty_level(
                get_field(data, "difficultyLevel", "difficulty_level")
            )

        if get_field(data, "targetSkills", "target_skills") is not None:
            text.target_skills = parse_string_list(
                get_field(data, "targetSkills", "target_skills")
            )

        if "source" in data:
            text.source = data.get("source")

        if get_field(data, "isCalibrated", "is_calibrated") is not None:
            text.is_calibrated = bool(get_field(data, "isCalibrated", "is_calibrated"))

        db.session.commit()
        return text

    @staticmethod
    def delete(user: Dict[str, Any], text_id: str) -> None:
        text = ReadingText.query.get(text_id)
        if not text:
            raise LookupError("Texto de leitura não encontrado.")
        if not user_can_modify(user, text):
            raise PermissionError("Você não tem permissão para excluir este texto.")

        role = Roles.normalize(user.get("role", ""))
        city_id = user.get("tenant_id") or user.get("city_id")
        if role == Roles.ADMIN:
            in_use = count_evaluations_using_text(text_id)
        else:
            in_use = count_evaluations_using_text(
                text_id,
                city_id=str(city_id) if city_id else None,
            )
        if in_use > 0:
            raise ValueError(
                "Não é possível excluir o texto: existem avaliações de leitura vinculadas."
            )

        db.session.delete(text)
        db.session.commit()
