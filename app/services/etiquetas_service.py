# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional, Set

from app.models.answerSheetGabarito import AnswerSheetGabarito
from app.models.city import City
from app.models.educationStage import EducationStage
from app.models.grades import Grade
from app.models.school import School
from app.models.studentClass import Class
from app.models.test import Test
from app.permissions.utils import get_manager_school, get_teacher_schools
from app.utils.uuid_helpers import ensure_uuid

VALID_MODOS = frozenset({"manual", "avaliacao", "cartao_resposta"})


class EtiquetasValidationError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


def _norm_param(value: Optional[str]) -> str:
    normalized = str(value or "").strip()
    if not normalized or normalized.lower() == "all":
        return ""
    return normalized


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


def _validate_uuid(value: str, field_name: str) -> None:
    if value and not ensure_uuid(value):
        raise EtiquetasValidationError(f"{field_name} inválido.")


def _parse_filters(args: Dict[str, Any]) -> Dict[str, str]:
    modo = _norm_param(args.get("modo")) or "manual"
    if modo not in VALID_MODOS:
        raise EtiquetasValidationError("Parâmetro 'modo' inválido.")

    municipio = _norm_param(args.get("municipio"))
    if not municipio:
        raise EtiquetasValidationError("Selecione o município.")
    _validate_uuid(municipio, "município")

    escola = _norm_param(args.get("escola"))
    nivel = _norm_param(args.get("nivel"))
    serie = _norm_param(args.get("serie"))
    turma = _norm_param(args.get("turma"))
    turno = _norm_param(args.get("turno"))
    evaluation_id = _norm_param(args.get("evaluation_id"))
    answer_sheet_id = _norm_param(args.get("answer_sheet_id"))

    _validate_uuid(escola, "escola")
    _validate_uuid(nivel, "nível")
    _validate_uuid(serie, "serie")
    _validate_uuid(turma, "turma")

    if modo == "avaliacao":
        if not evaluation_id:
            raise EtiquetasValidationError("Selecione uma avaliação.")
        _validate_uuid(evaluation_id, "evaluation_id")

    if modo == "cartao_resposta":
        if not answer_sheet_id:
            raise EtiquetasValidationError("Selecione um cartão-resposta.")
        _validate_uuid(answer_sheet_id, "answer_sheet_id")

    return {
        "modo": modo,
        "municipio": municipio,
        "escola": escola,
        "nivel": nivel,
        "serie": serie,
        "turma": turma,
        "turno": turno,
        "evaluation_id": evaluation_id,
        "answer_sheet_id": answer_sheet_id,
    }


class EtiquetasService:
    @staticmethod
    def get_dados(user: Dict[str, Any], args: Dict[str, Any]) -> Dict[str, Any]:
        filters = _parse_filters(args)
        allowed = _allowed_school_ids(user)

        city = City.query.get(filters["municipio"])
        if not city:
            raise EtiquetasValidationError("Município não encontrado.")

        selected_school: Optional[School] = None
        selected_grade: Optional[Grade] = None
        selected_stage: Optional[EducationStage] = None
        selected_class: Optional[Class] = None

        if filters["escola"]:
            selected_school = School.query.filter(
                School.id == filters["escola"], School.city_id == filters["municipio"]
            ).first()
            if not selected_school:
                raise EtiquetasValidationError("Escola não encontrada para o município selecionado.")
            if allowed is not None and str(selected_school.id) not in allowed:
                raise EtiquetasValidationError("Você não tem permissão para acessar esta escola.")

        if filters["nivel"]:
            selected_stage = EducationStage.query.get(filters["nivel"])
            if not selected_stage:
                raise EtiquetasValidationError("Nível não encontrado.")

        if filters["serie"]:
            selected_grade = Grade.query.get(filters["serie"])
            if not selected_grade:
                raise EtiquetasValidationError("Série não encontrada.")
            if selected_stage and selected_grade.education_stage_id != selected_stage.id:
                raise EtiquetasValidationError("A série informada não pertence ao nível selecionado.")

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
                raise EtiquetasValidationError("Turma não encontrada para os filtros selecionados.")
            if allowed is not None and str(selected_class.school_id) not in allowed:
                raise EtiquetasValidationError("Você não tem permissão para acessar esta turma.")

        if selected_class and not selected_grade:
            selected_grade = selected_class.grade

        if selected_grade and not selected_stage:
            selected_stage = selected_grade.education_stage

        title_reference = ""
        if filters["modo"] == "avaliacao" and filters["evaluation_id"]:
            test = Test.query.get(filters["evaluation_id"])
            if not test:
                raise EtiquetasValidationError("Avaliação não encontrada.")
            title_reference = str(test.title or "").strip()
        elif filters["modo"] == "cartao_resposta" and filters["answer_sheet_id"]:
            answer_sheet = AnswerSheetGabarito.query.get(filters["answer_sheet_id"])
            if not answer_sheet:
                raise EtiquetasValidationError("Cartão-resposta não encontrado.")
            title_reference = str(answer_sheet.title or "").strip()

        city_name = str(city.name or "").strip().upper()
        prefeitura_label = f"PREFEITURA MUNICIPAL DE {city_name}"

        class_turno = str(getattr(selected_class, "turno", None) or "").strip() if selected_class else ""
        turno = filters["turno"] or class_turno

        return {
            "municipio": {
                "id": str(city.id),
                "name": str(city.name or ""),
                "state": str(city.state or ""),
                "prefeitura_label": prefeitura_label,
            },
            "contexto": {
                "escola": str(selected_school.name or "").strip() if selected_school else "Todas as escolas",
                "nivel": str(selected_stage.name or "").strip() if selected_stage else "Todos os níveis",
                "serie": str(selected_grade.name or "").strip() if selected_grade else "Todas as séries",
                "turma": str(selected_class.name or "").strip() if selected_class else "Todas as turmas",
                "turno": turno,
                "ano": datetime.now().year,
            },
            "modo": filters["modo"],
            "title_reference": title_reference or None,
            "filters": filters,
        }
