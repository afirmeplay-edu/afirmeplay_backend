# -*- coding: utf-8 -*-
"""
Catálogo de campos disponíveis no overlay da capa.

Somente chaves que o backend consegue resolver a partir de Test, Student,
Class, School, City, Grade e subjects_info — os mesmos dados já usados na
capa Afirme e em PhysicalTestFormService.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional


FIELD_CATALOG: List[Dict[str, str]] = [
    {"key": "aluno.nome", "label": "Nome do aluno", "group": "aluno"},
    {"key": "aluno.matricula", "label": "Matrícula do aluno", "group": "aluno"},
    {"key": "aluno.data_nascimento", "label": "Data de nascimento do aluno", "group": "aluno"},
    {"key": "avaliacao.titulo", "label": "Título da avaliação", "group": "avaliacao"},
    {"key": "avaliacao.descricao", "label": "Descrição da avaliação", "group": "avaliacao"},
    {"key": "avaliacao.modelo", "label": "Modelo da avaliação", "group": "avaliacao"},
    {"key": "avaliacao.tipo", "label": "Tipo da avaliação", "group": "avaliacao"},
    {"key": "avaliacao.ano", "label": "Ano da capa", "group": "avaliacao"},
    {"key": "turma.nome", "label": "Nome da turma", "group": "turma"},
    {"key": "turma.turno", "label": "Turno da turma", "group": "turma"},
    {"key": "serie.nome", "label": "Nome da série", "group": "serie"},
    {"key": "escola.nome", "label": "Nome da escola", "group": "escola"},
    {"key": "escola.endereco", "label": "Endereço da escola", "group": "escola"},
    {"key": "municipio.nome", "label": "Nome do município", "group": "municipio"},
    {"key": "municipio.estado", "label": "Estado do município", "group": "municipio"},
    {"key": "disciplinas.nomes", "label": "Nomes das disciplinas", "group": "disciplinas"},
]

FIELD_KEYS = frozenset(item["key"] for item in FIELD_CATALOG)

SAMPLE_VALUES: Dict[str, str] = {
    "aluno.nome": "MARIA SILVA SANTOS",
    "aluno.matricula": "202600123",
    "aluno.data_nascimento": "12/03/2012",
    "avaliacao.titulo": "Avaliação Diagnóstica",
    "avaliacao.descricao": "Avaliação de acompanhamento",
    "avaliacao.modelo": "SAEB",
    "avaliacao.tipo": "PROVA",
    "avaliacao.ano": str(datetime.now().year),
    "turma.nome": "Turma A",
    "turma.turno": "Manhã",
    "serie.nome": "5º Ano",
    "escola.nome": "Escola Municipal Exemplo",
    "escola.endereco": "Rua Exemplo, 100",
    "municipio.nome": "Município Exemplo",
    "municipio.estado": "AL",
    "disciplinas.nomes": "LÍNGUA PORTUGUESA E MATEMÁTICA",
}


def catalog_payload() -> Dict[str, Any]:
    return {
        "fields": FIELD_CATALOG,
        "sample_values": SAMPLE_VALUES,
    }


def _format_date(value: Any) -> str:
    if value is None:
        return ""
    if hasattr(value, "strftime"):
        return value.strftime("%d/%m/%Y")
    text = str(value).strip()
    if not text:
        return ""
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(text[:10], fmt).strftime("%d/%m/%Y")
        except ValueError:
            continue
    return text


def _cover_year(test_data: Optional[Dict[str, Any]]) -> str:
    test_data = test_data or {}
    for key in ("year", "application_year", "school_year"):
        value = test_data.get(key)
        if value is not None:
            try:
                return str(int(value))
            except (TypeError, ValueError):
                text = str(value).strip()
                if text:
                    return text
    return str(datetime.now().year)


def _subject_names(test_data: Optional[Dict[str, Any]]) -> str:
    test_data = test_data or {}
    subjects_info = test_data.get("subjects_info")
    names: List[str] = []
    if isinstance(subjects_info, list):
        for item in subjects_info:
            if isinstance(item, dict) and item.get("name"):
                names.append(str(item["name"]))
    elif isinstance(subjects_info, dict):
        for item in subjects_info.values():
            if isinstance(item, dict) and item.get("name"):
                names.append(str(item["name"]))
            elif isinstance(item, str):
                names.append(item)
    if test_data.get("subject_name") and not names:
        names.append(str(test_data["subject_name"]))
    unique = []
    seen = set()
    for name in names:
        key = name.strip().upper()
        if key and key not in seen:
            seen.add(key)
            unique.append(name.strip().upper())
    return " E ".join(unique)


def resolve_field_value(
    key: str,
    student: Optional[Dict[str, Any]] = None,
    test_data: Optional[Dict[str, Any]] = None,
) -> str:
    student = student or {}
    test_data = test_data or {}

    mapping = {
        "aluno.nome": student.get("name") or student.get("nome") or "",
        "aluno.matricula": student.get("registration") or student.get("matricula") or "",
        "aluno.data_nascimento": _format_date(
            student.get("birth_date") or student.get("data_nascimento")
        ),
        "avaliacao.titulo": test_data.get("title") or "",
        "avaliacao.descricao": test_data.get("description") or "",
        "avaliacao.modelo": test_data.get("model") or "",
        "avaliacao.tipo": test_data.get("type") or "",
        "avaliacao.ano": _cover_year(test_data),
        "turma.nome": student.get("class_name") or test_data.get("class_name") or "",
        "turma.turno": student.get("class_shift") or student.get("shift") or "",
        "serie.nome": student.get("grade_name") or test_data.get("grade_name") or "",
        "escola.nome": student.get("school_name") or test_data.get("institution") or "",
        "escola.endereco": student.get("school_address") or "",
        "municipio.nome": student.get("municipality_name")
        or test_data.get("municipality")
        or "",
        "municipio.estado": student.get("state_name") or test_data.get("state") or "",
        "disciplinas.nomes": _subject_names(test_data),
    }
    value = mapping.get(key, "")
    if value is None:
        return ""
    return str(value).strip()


def resolve_all_values(
    student: Optional[Dict[str, Any]] = None,
    test_data: Optional[Dict[str, Any]] = None,
    sample: bool = False,
) -> Dict[str, str]:
    if sample:
        return dict(SAMPLE_VALUES)
    return {key: resolve_field_value(key, student, test_data) for key in FIELD_KEYS}
