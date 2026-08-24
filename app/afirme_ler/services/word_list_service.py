# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Dict, List

from sqlalchemy import and_
from sqlalchemy.orm import joinedload

from app import db
from app.afirme_ler.models import ReadingWordList
from app.afirme_ler.services.parsing import (
    SCOPE_CITY,
    SCOPE_GLOBAL,
    SCOPE_PRIVATE,
    get_field,
    parse_grade_id_filters,
    parse_string_list,
    validate_word_list_kind,
)
from app.afirme_ler.services.scope_service import (
    apply_visibility_filter,
    resolve_scope_on_create,
    user_can_modify,
)
from app.models.grades import Grade


class WordListService:
    @staticmethod
    def _get_grade(grade_id: str) -> Grade:
        grade = Grade.query.get(grade_id)
        if not grade:
            raise ValueError("Série (gradeId) não encontrada.")
        return grade

    @staticmethod
    def _clear_default_flag(word_list: ReadingWordList) -> None:
        query = ReadingWordList.query.filter(
            ReadingWordList.kind == word_list.kind,
            ReadingWordList.is_default.is_(True),
            ReadingWordList.id != word_list.id,
        )
        if word_list.grade_id:
            query = query.filter(ReadingWordList.grade_id == word_list.grade_id)
        else:
            query = query.filter(ReadingWordList.grade_id.is_(None))
        if word_list.scope_type == SCOPE_GLOBAL:
            query = query.filter(ReadingWordList.scope_type == SCOPE_GLOBAL)
        elif word_list.scope_type == SCOPE_CITY:
            query = query.filter(
                and_(
                    ReadingWordList.scope_type == SCOPE_CITY,
                    ReadingWordList.owner_city_id == word_list.owner_city_id,
                )
            )
        else:
            query = query.filter(
                and_(
                    ReadingWordList.scope_type == SCOPE_PRIVATE,
                    ReadingWordList.owner_user_id == word_list.owner_user_id,
                )
            )
        query.update({"is_default": False}, synchronize_session=False)

    @staticmethod
    def create(user: Dict[str, Any], data: dict) -> ReadingWordList:
        name = get_field(data, "name")
        if not name or not str(name).strip():
            raise ValueError("name é obrigatório.")

        grade_id = get_field(data, "gradeId", "grade_id")
        if not grade_id:
            raise ValueError("gradeId é obrigatório.")
        WordListService._get_grade(str(grade_id))

        kind = validate_word_list_kind(
            get_field(data, "kind", default="PALAVRAS_CONHECIDAS")
        )
        items = parse_string_list(get_field(data, "items", default=[]), split_words=True)
        scope_type, owner_city_id, owner_user_id = resolve_scope_on_create(user)
        user_id = user.get("id") or user.get("user_id")

        word_list = ReadingWordList(
            name=str(name).strip(),
            kind=kind,
            grade_id=grade_id,
            items=items,
            description=get_field(data, "description"),
            is_default=bool(get_field(data, "isDefault", "is_default", default=False)),
            active=bool(get_field(data, "active", default=True)),
            scope_type=scope_type,
            owner_city_id=owner_city_id,
            owner_user_id=owner_user_id,
            created_by=user_id,
        )
        if word_list.is_default:
            WordListService._clear_default_flag(word_list)
        db.session.add(word_list)
        db.session.commit()
        return ReadingWordList.query.options(
            joinedload(ReadingWordList.grade)
        ).get(word_list.id)

    @staticmethod
    def list_word_lists(user: Dict[str, Any], filters: dict) -> List[ReadingWordList]:
        query = ReadingWordList.query.options(joinedload(ReadingWordList.grade))
        query = apply_visibility_filter(query, ReadingWordList, user)

        kind = filters.get("kind")
        if kind:
            query = query.filter(ReadingWordList.kind == validate_word_list_kind(kind))

        grade_ids = parse_grade_id_filters(filters)
        if grade_ids:
            query = query.filter(ReadingWordList.grade_id.in_(grade_ids))

        active = filters.get("active")
        if active is not None:
            if str(active).lower() in ("true", "1", "yes"):
                query = query.filter(ReadingWordList.active.is_(True))
            elif str(active).lower() in ("false", "0", "no"):
                query = query.filter(ReadingWordList.active.is_(False))

        return query.order_by(
            ReadingWordList.is_default.desc(),
            ReadingWordList.created_at.desc(),
        ).all()

    @staticmethod
    def get_visible(user: Dict[str, Any], word_list_id: str) -> ReadingWordList:
        query = ReadingWordList.query.options(joinedload(ReadingWordList.grade))
        query = apply_visibility_filter(query, ReadingWordList, user)
        word_list = query.filter(ReadingWordList.id == word_list_id).first()
        if not word_list:
            raise LookupError("Lista de palavras não encontrada.")
        return word_list

    @staticmethod
    def update(user: Dict[str, Any], word_list_id: str, data: dict) -> ReadingWordList:
        word_list = ReadingWordList.query.get(word_list_id)
        if not word_list:
            raise LookupError("Lista de palavras não encontrada.")
        if not user_can_modify(user, word_list):
            raise PermissionError("Você não tem permissão para editar esta lista.")

        if "name" in data:
            name = get_field(data, "name")
            if not name or not str(name).strip():
                raise ValueError("name não pode ser vazio.")
            word_list.name = str(name).strip()

        if "kind" in data:
            word_list.kind = validate_word_list_kind(data["kind"])

        if get_field(data, "gradeId", "grade_id") is not None:
            grade_id = get_field(data, "gradeId", "grade_id")
            WordListService._get_grade(str(grade_id))
            word_list.grade_id = grade_id

        if "items" in data:
            word_list.items = parse_string_list(data["items"], split_words=True)

        if "description" in data:
            word_list.description = data.get("description")

        if get_field(data, "isDefault", "is_default") is not None:
            word_list.is_default = bool(get_field(data, "isDefault", "is_default"))

        if "active" in data:
            word_list.active = bool(data.get("active"))

        if word_list.is_default:
            WordListService._clear_default_flag(word_list)

        db.session.commit()
        return ReadingWordList.query.options(
            joinedload(ReadingWordList.grade)
        ).get(word_list.id)

    @staticmethod
    def delete(user: Dict[str, Any], word_list_id: str) -> None:
        word_list = ReadingWordList.query.get(word_list_id)
        if not word_list:
            raise LookupError("Lista de palavras não encontrada.")
        if not user_can_modify(user, word_list):
            raise PermissionError("Você não tem permissão para excluir esta lista.")
        db.session.delete(word_list)
        db.session.commit()
