# -*- coding: utf-8 -*-
"""
Normalização de filtros hierárquicos dos relatórios socioeconômicos.

O frontend pode enviar escola/série/turma como:
- UUID único (string)
- lista JSON
- string com vários UUIDs separados por vírgula

O backend deve tratar todos como lista de IDs.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional


ID_FILTER_KEYS = ("escola", "serie", "turma")


def normalize_id_list(value: Any) -> List[str]:
    """Converte valor de filtro em lista de IDs (string), sem duplicatas."""
    if value is None or value == "":
        return []
    if isinstance(value, (list, tuple, set)):
        items: Iterable[Any] = value
    else:
        items = str(value).split(",")
    out: List[str] = []
    seen = set()
    for item in items:
        s = str(item).strip()
        if not s or s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out


def filter_value_includes_id(filter_value: Any, target_id: Optional[str]) -> bool:
    """True se target_id está contido no valor do filtro (único, lista ou CSV)."""
    if not target_id:
        return False
    return str(target_id) in normalize_id_list(filter_value)


def id_lists_intersect(a: Any, b: Any) -> bool:
    """True se há interseção entre dois valores de filtro de IDs."""
    set_a = set(normalize_id_list(a))
    set_b = set(normalize_id_list(b))
    return bool(set_a & set_b)


def canonicalize_results_filters(filters: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Normaliza filtros para cálculo/hash/cache.
    escola/serie/turma viram lista ordenada (1+ itens) ou são omitidos se vazios.
    """
    if not filters:
        return {}
    out: Dict[str, Any] = {}
    for key, value in filters.items():
        if value is None or value == "":
            continue
        if key in ID_FILTER_KEYS:
            ids = sorted(normalize_id_list(value))
            if not ids:
                continue
            out[key] = ids
        else:
            out[key] = value
    return out


def apply_id_filter(query, column, value: Any):
    """Aplica coluna == x ou coluna.in_(...) para qualquer filtro de ID."""
    ids = normalize_id_list(value)
    if not ids:
        return query
    if len(ids) == 1:
        return query.filter(column == ids[0])
    return query.filter(column.in_(ids))


def student_matches_form_scope(
    form_type: Optional[str],
    school_id: Optional[str],
    grade_id: Optional[str],
    class_id: Optional[str],
    selected_schools: Any = None,
    selected_grades: Any = None,
    selected_classes: Any = None,
    filters: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    True se a colocação atual do aluno entra no escopo persistido do form
    (selected_* ou filters). Não consulta banco (município/estado ficam a cargo
    do caller quando escola não vem explícita).
    """
    if form_type not in ('aluno-jovem', 'aluno-velho'):
        return False
    if not school_id or not grade_id:
        return False

    school_id = str(school_id)
    grade_id = str(grade_id)
    class_id = str(class_id) if class_id else None
    filters = filters or {}

    selected_schools = normalize_id_list(selected_schools)
    selected_grades = normalize_id_list(selected_grades)
    selected_classes = normalize_id_list(selected_classes)
    filter_classes = normalize_id_list(filters.get('turma')) if filters.get('turma') else []
    filter_grades = normalize_id_list(filters.get('serie')) if filters.get('serie') else []
    filter_schools = normalize_id_list(filters.get('escola')) if filters.get('escola') else []

    effective_classes = filter_classes or selected_classes
    if effective_classes and (not class_id or class_id not in effective_classes):
        return False

    effective_grades = filter_grades or selected_grades
    if effective_grades and grade_id not in effective_grades:
        return False

    if selected_schools and school_id not in selected_schools:
        return False
    if not selected_schools and filter_schools and school_id not in filter_schools:
        return False

    if effective_classes or effective_grades:
        return True
    return False


def form_scope_needs_geo_school_check(
    selected_schools: Any = None,
    filters: Optional[Dict[str, Any]] = None,
) -> bool:
    """True quando o form não lista escola e o caller precisa checar município/estado."""
    filters = filters or {}
    if normalize_id_list(selected_schools):
        return False
    if filters.get('escola') and normalize_id_list(filters.get('escola')):
        return False
    return bool(filters.get('municipio') or filters.get('estado'))
