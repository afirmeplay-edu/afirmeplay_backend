# -*- coding: utf-8 -*-
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, Optional, Set, Tuple

from sqlalchemy import func

from app import db
from app.models.answerSheetGabarito import AnswerSheetGabarito
from app.models.city import City
from app.models.classTest import ClassTest
from app.models.grades import Grade
from app.models.school import School
from app.models.studentClass import Class
from app.models.test import Test
from app.permissions.utils import get_manager_school, get_teacher_schools
from app.utils.uuid_helpers import ensure_uuid

MESES_PT = {
    1: "janeiro",
    2: "fevereiro",
    3: "março",
    4: "abril",
    5: "maio",
    6: "junho",
    7: "julho",
    8: "agosto",
    9: "setembro",
    10: "outubro",
    11: "novembro",
    12: "dezembro",
}


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


def _parse_application_month_year(value: Optional[str]) -> Optional[Tuple[int, int]]:
    raw = str(value or "").strip()
    if not raw:
        return None

    iso_prefix = re.match(r"^(\d{4})-(\d{2})-(\d{2})", raw)
    if iso_prefix:
        year, month = int(iso_prefix.group(1)), int(iso_prefix.group(2))
        if 1 <= month <= 12:
            return month, year

    year_month = re.match(r"^(\d{4})-(\d{2})$", raw)
    if year_month:
        year, month = int(year_month.group(1)), int(year_month.group(2))
        if 1 <= month <= 12:
            return month, year

    return None


def _parse_application_datetime(value: Optional[str]) -> Optional[datetime]:
    raw = str(value or "").strip()
    if not raw:
        return None

    iso_datetime = re.match(
        r"^(\d{4})-(\d{2})-(\d{2})(?:[T\s](\d{2}):(\d{2})(?::(\d{2}))?)?",
        raw,
    )
    if iso_datetime:
        year = int(iso_datetime.group(1))
        month = int(iso_datetime.group(2))
        day = int(iso_datetime.group(3))
        hour = int(iso_datetime.group(4) or 0)
        minute = int(iso_datetime.group(5) or 0)
        second = int(iso_datetime.group(6) or 0)
        if 1 <= month <= 12 and 1 <= day <= 31:
            return datetime(year, month, day, hour, minute, second)

    parsed = _parse_application_month_year(raw)
    if parsed:
        month, year = parsed
        return datetime(year, month, 1)

    return None


def _application_datetime_from_test_id(test_id: str) -> Optional[datetime]:
    application_value = (
        db.session.query(func.min(ClassTest.application))
        .filter(ClassTest.test_id == test_id)
        .scalar()
    )
    parsed = _parse_application_datetime(application_value)
    if parsed:
        return parsed

    test = Test.query.get(test_id)
    if test and test.created_at:
        created = test.created_at
        if isinstance(created, datetime):
            return created

    return None


def _periodo_from_test_id(test_id: str) -> Tuple[str, int]:
    application_value = (
        db.session.query(func.min(ClassTest.application))
        .filter(ClassTest.test_id == test_id)
        .scalar()
    )
    parsed = _parse_application_month_year(application_value)
    if parsed:
        month, year = parsed
        return MESES_PT[month], year

    test = Test.query.get(test_id)
    if test and test.created_at:
        created = test.created_at
        if hasattr(created, "month"):
            return MESES_PT[created.month], created.year

    now = datetime.now()
    return MESES_PT[now.month], now.year


def _resolve_periodo_avaliacao(
    modo: str,
    evaluation_id: str,
    answer_sheet_id: str,
) -> Tuple[str, int]:
    if modo == "avaliacao" and evaluation_id:
        return _periodo_from_test_id(evaluation_id)

    if modo == "cartao_resposta" and answer_sheet_id:
        answer_sheet = AnswerSheetGabarito.query.get(answer_sheet_id)
        if answer_sheet and answer_sheet.test_id:
            return _periodo_from_test_id(str(answer_sheet.test_id))

    now = datetime.now()
    return MESES_PT[now.month], now.year


def _resolve_application_datetime_from_filters(
    modo: str,
    evaluation_id: str,
    answer_sheet_id: str,
) -> Optional[datetime]:
    if modo == "avaliacao" and evaluation_id:
        return _application_datetime_from_test_id(evaluation_id)

    if modo == "cartao_resposta" and answer_sheet_id:
        answer_sheet = AnswerSheetGabarito.query.get(answer_sheet_id)
        if answer_sheet and answer_sheet.test_id:
            return _application_datetime_from_test_id(str(answer_sheet.test_id))

    return None


def _resolve_nome_aplicacao_referencia(
    modo: str,
    evaluation_id: str,
    answer_sheet_id: str,
) -> str:
    if modo == "avaliacao" and evaluation_id:
        test = Test.query.get(evaluation_id)
        if test:
            return str(test.title or "").strip()

    if modo == "cartao_resposta" and answer_sheet_id:
        answer_sheet = AnswerSheetGabarito.query.get(answer_sheet_id)
        if answer_sheet:
            title = str(answer_sheet.title or "").strip()
            if title:
                return title
            if answer_sheet.test_id:
                test = Test.query.get(str(answer_sheet.test_id))
                if test:
                    return str(test.title or "").strip()

    return ""


def _municipio_corpo(city: City) -> str:
    name = str(city.name or "").strip()
    state = str(city.state or "").strip()
    return f"{name}/{state}" if state else name


def _format_data_documento(city: City, modo: str, evaluation_id: str, answer_sheet_id: str) -> str:
    application_dt = _resolve_application_datetime_from_filters(modo, evaluation_id, answer_sheet_id)
    if application_dt:
        mes = MESES_PT[application_dt.month]
        return f"{str(city.name or '').strip()}, {application_dt.day:02d} de {mes} de {application_dt.year}"

    mes_avaliacao, ano = _resolve_periodo_avaliacao(modo, evaluation_id, answer_sheet_id)
    now = datetime.now()
    return f"{str(city.name or '').strip()}, {now.day:02d} de {mes_avaliacao} de {ano}"


def _parse_filters(args: Dict[str, Any]) -> Dict[str, str]:
    municipio = _norm_param(args.get("municipio"))
    escola = _norm_param(args.get("escola"))
    serie = _norm_param(args.get("serie"))
    turma = _norm_param(args.get("turma"))
    modo = _norm_param(args.get("modo")) or "manual"
    evaluation_id = _norm_param(args.get("evaluation_id"))
    answer_sheet_id = _norm_param(args.get("answer_sheet_id"))

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
    if evaluation_id and not ensure_uuid(evaluation_id):
        raise TermoCompromissoValidationError("evaluation_id inválido.")
    if answer_sheet_id and not ensure_uuid(answer_sheet_id):
        raise TermoCompromissoValidationError("answer_sheet_id inválido.")

    return {
        "municipio": municipio,
        "escola": escola,
        "serie": serie,
        "turma": turma,
        "modo": modo,
        "evaluation_id": evaluation_id,
        "answer_sheet_id": answer_sheet_id,
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
        shift = str(selected_class.shift or "").strip() if selected_class else ""
        mes_avaliacao, ano_avaliacao = _resolve_periodo_avaliacao(
            filters["modo"],
            filters["evaluation_id"],
            filters["answer_sheet_id"],
        )
        nome_aplicacao_referencia = _resolve_nome_aplicacao_referencia(
            filters["modo"],
            filters["evaluation_id"],
            filters["answer_sheet_id"],
        )
        municipio_corpo = _municipio_corpo(city)
        periodo_texto = f"no período de {mes_avaliacao} de {ano_avaliacao}"
        data_documento = _format_data_documento(
            city,
            filters["modo"],
            filters["evaluation_id"],
            filters["answer_sheet_id"],
        )
        secretaria_label = "SECRETARIA MUNICIPAL DE EDUCAÇÃO"

        return {
            "municipio": {
                "id": str(city.id),
                "name": str(city.name or ""),
                "state": str(city.state or ""),
                "prefeitura_label": prefeitura_label,
                "secretaria_label": secretaria_label,
            },
            "contexto": {
                "escola": escola_nome,
                "serie": serie_nome,
                "turma": turma_nome,
                "shift": shift,
                "mes_avaliacao": mes_avaliacao,
                "ano": ano_avaliacao,
                "municipio_corpo": municipio_corpo,
                "periodo_texto": periodo_texto,
                "nome_aplicacao_referencia": nome_aplicacao_referencia,
                "data_documento": data_documento,
            },
            "documento": {
                "titulo": "TERMO DE COMPROMISSO E CONFIDENCIALIDADE",
            },
            "filters": filters,
        }
