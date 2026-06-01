# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional, Set

from app.models.city import City
from app.models.grades import Grade
from app.models.school import School
from app.models.studentClass import Class
from app.permissions.utils import get_manager_school, get_teacher_schools
from app.utils.uuid_helpers import ensure_uuid


class TermoCompromissoValidationError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


def _norm_param(value: Optional[str]) -> str:
    v = str(value or "").strip()
    if not v or v.lower() == "all":
        return ""
    return v


def _user_role(user: Dict[str, Any]) -> str:
    role = user.get("role")
    return (role.value if hasattr(role, "value") else str(role or "")).lower()


def _allowed_school_ids(user: Dict[str, Any]) -> Optional[Set[str]]:
    role = _user_role(user)
    if role in ("admin", "tecadm"):
        return None
    if role in ("diretor", "coordenador"):
        school_id = get_manager_school(user["id"])
        return {school_id} if school_id else set()
    if role == "professor":
        return set(get_teacher_schools(user["id"]) or [])
    return set()


def _parse_filters(args: Dict[str, Any]) -> Dict[str, str]:
    municipio = _norm_param(args.get("municipio"))
    escola = _norm_param(args.get("escola"))
    serie = _norm_param(args.get("serie"))
    turma = _norm_param(args.get("turma"))

    if not municipio:
        raise TermoCompromissoValidationError("Selecione o município.")
    if not ensure_uuid(municipio):
        raise TermoCompromissoValidationError("município inválido.")
    if escola and not ensure_uuid(escola):
        raise TermoCompromissoValidationError("escola inválida.")
    if serie and not ensure_uuid(serie):
        raise TermoCompromissoValidationError("serie inválida.")
    if turma and not ensure_uuid(turma):
        raise TermoCompromissoValidationError("turma inválida.")

    return {
        "municipio": municipio,
        "escola": escola,
        "serie": serie,
        "turma": turma,
    }


class TermoCompromissoService:
    @staticmethod
    def get_dados(user: Dict[str, Any], args: Dict[str, Any]) -> Dict[str, Any]:
        filters = _parse_filters(args)
        allowed = _allowed_school_ids(user)

        city = City.query.get(filters["municipio"])
        if not city:
            raise TermoCompromissoValidationError("Município não encontrado.")

        selected_school: Optional[School] = None
        selected_grade: Optional[Grade] = None
        selected_class: Optional[Class] = None

        if filters["escola"]:
            selected_school = School.query.filter(
                School.id == filters["escola"], School.city_id == filters["municipio"]
            ).first()
            if not selected_school:
                raise TermoCompromissoValidationError("Escola não encontrada para o município selecionado.")
            if allowed is not None and str(selected_school.id) not in allowed:
                raise TermoCompromissoValidationError("Você não tem permissão para acessar esta escola.")

        if filters["serie"]:
            selected_grade = Grade.query.get(filters["serie"])
            if not selected_grade:
                raise TermoCompromissoValidationError("Série não encontrada.")

        if filters["turma"]:
            class_query = Class.query.join(School, Class._school_id == School.id).filter(
                Class.id == filters["turma"],
                School.city_id == filters["municipio"],
            )
            if selected_school:
                class_query = class_query.filter(School.id == selected_school.id)
            if selected_grade:
                class_query = class_query.filter(Class.grade_id == selected_grade.id)
            selected_class = class_query.first()
            if not selected_class:
                raise TermoCompromissoValidationError("Turma não encontrada para os filtros selecionados.")
            if allowed is not None and str(selected_class.school_id) not in allowed:
                raise TermoCompromissoValidationError("Você não tem permissão para acessar esta turma.")

        city_name = str(city.name or "").strip().upper()
        prefeitura_label = f"PREFEITURA MUNICIPAL DE {city_name}"

        escola_nome = str(selected_school.name or "").strip() if selected_school else "Todas as escolas"
        serie_nome = str(selected_grade.name or "").strip() if selected_grade else "Todas as séries"
        turma_nome = str(selected_class.name or "").strip() if selected_class else "Todas as turmas"
        turno = str(getattr(selected_class, "turno", None) or "").strip() if selected_class else ""

        return {
            "municipio": {
                "id": str(city.id),
                "name": str(city.name or ""),
                "state": str(city.state or ""),
                "prefeitura_label": prefeitura_label,
            },
            "contexto": {
                "escola": escola_nome,
                "serie": serie_nome,
                "turma": turma_nome,
                "turno": turno,
                "ano": datetime.now().year,
            },
            "filters": filters,
        }
