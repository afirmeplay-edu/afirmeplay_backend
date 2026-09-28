# -*- coding: utf-8 -*-
"""Tipo de área da escola (zona urbana / zona rural).

O valor só restringe quais escolas entram no recorte. Não entra em fórmula
de proficiência, nota, classificação, nível de leitura ou ICA.
"""
from __future__ import annotations

from typing import Any, Iterable, List, Optional, Sequence

AREA_TYPE_URBANA = "urbana"
AREA_TYPE_RURAL = "rural"
VALID_AREA_TYPES = frozenset({AREA_TYPE_URBANA, AREA_TYPE_RURAL})
_NO_FILTER = frozenset({"", "all", "todas", "todos"})

AREA_TYPE_LABELS = {
    AREA_TYPE_URBANA: "Zona urbana",
    AREA_TYPE_RURAL: "Zona rural",
}


def parse_area_type_body(value: Any) -> str:
    """Valor obrigatório de cadastro (POST/PUT)."""
    if value is None or (isinstance(value, str) and not str(value).strip()):
        raise ValueError("Tipo de área é obrigatório")
    code = str(value).strip().lower()
    if code not in VALID_AREA_TYPES:
        raise ValueError("Tipo de área inválido. Use 'urbana' ou 'rural'.")
    return code


def parse_area_type_filter(value: Any) -> Optional[str]:
    """Filtro de resultados. None = Todas (mesmo recorte de hoje)."""
    if value is None:
        return None
    code = str(value).strip().lower()
    if code in _NO_FILTER:
        return None
    if code not in VALID_AREA_TYPES:
        raise ValueError("tipo_area inválido. Use urbana, rural ou all.")
    return code


def area_type_label(code: Optional[str]) -> str:
    if not code:
        return "Não informado"
    return AREA_TYPE_LABELS.get(str(code).strip().lower(), "Não informado")


def filter_label(code: Optional[str]) -> str:
    if not code:
        return "Todas"
    return AREA_TYPE_LABELS.get(str(code).strip().lower(), "Todas")


def apply_area_type_to_query(query, area_type: Optional[str]):
    """Restringe uma query que já referencia School. Sem área, a query não muda."""
    if not area_type:
        return query
    from app.models.school import School

    return query.filter(School.area_type == area_type)


def school_ids_for_area(area_type: Optional[str]) -> Optional[List[str]]:
    """None quando não há recorte. Lista (possivelmente vazia) quando há zona."""
    if not area_type:
        return None
    from app.models.school import School

    rows = School.query.with_entities(School.id).filter(School.area_type == area_type).all()
    return [str(row[0]) for row in rows if row[0]]


def narrow_escola_options(items: Optional[Sequence[dict]], area_type: Optional[str]) -> list:
    """Encolhe a lista já limitada pelo perfil. Itens sem a zona saem."""
    if not area_type or not items:
        return list(items or [])
    from app.models.school import School

    ids = [str(item.get("id")) for item in items if item.get("id")]
    if not ids:
        return []
    matched = {
        str(row.id)
        for row in School.query.filter(
            School.id.in_(ids),
            School.area_type == area_type,
        ).all()
    }
    return [item for item in items if str(item.get("id")) in matched]


def apply_area_type_to_scope(
    scope: Optional[dict],
    area_type: Optional[str],
    *,
    fill_from_catalog: bool = False,
) -> Optional[dict]:
    """
    Marca o escopo com os ids de escola da zona.

    A lista ``escolas`` já veio do recorte de permissão. Sem área, o escopo
    não muda. Com área e lista vazia, o recorte continua vazio, salvo
    ``fill_from_catalog`` (comparação que ainda não montou a lista).
    """
    if not scope or not area_type:
        return scope

    allowed = set(school_ids_for_area(area_type) or [])
    escolas = list(scope.get("escolas") or [])
    if escolas:
        escolas = [item for item in escolas if str(getattr(item, "id", "")) in allowed]
        scope["escolas"] = escolas
        allowed_ids = [str(item.id) for item in escolas]
    elif fill_from_catalog:
        allowed_ids = list(allowed)
    else:
        allowed_ids = []

    escola = scope.get("escola")
    if escola and str(escola).strip().lower() not in ("", "all", "none"):
        escola_id = str(escola)
        visible = {str(item.id) for item in escolas} if escolas else set(allowed_ids)
        if escola_id not in allowed or escola_id not in visible:
            allowed_ids = []
        else:
            allowed_ids = [escola_id]

    scope["_area_type"] = area_type
    scope["_restrict_school_ids"] = allowed_ids
    return scope


def copy_area_restriction(scope_info: Optional[dict], escopo: dict) -> dict:
    """Repassa a restrição de escolas para o escopo usado nas consultas de alunos."""
    if not isinstance(scope_info, dict):
        return escopo
    if "_restrict_school_ids" in scope_info:
        escopo["_restrict_school_ids"] = list(scope_info.get("_restrict_school_ids") or [])
    if scope_info.get("_area_type"):
        escopo["_area_type"] = scope_info.get("_area_type")
    return escopo


def restrict_escopo_by_area(escopo: dict, area_type: Optional[str]) -> dict:
    """Acrescenta _restrict_school_ids no escopo de cálculo. Sem área, não altera."""
    if not area_type:
        return escopo
    area_ids = school_ids_for_area(area_type) or []
    escola_id = escopo.get("escola_id")
    if escola_id and str(escola_id) not in set(area_ids):
        area_ids = []
    elif escola_id:
        area_ids = [str(escola_id)]
    escopo["_restrict_school_ids"] = area_ids
    escopo["_area_type"] = area_type
    return escopo


def school_allowed(school_id: Any, restrict_ids: Optional[Iterable[Any]]) -> bool:
    if restrict_ids is None:
        return True
    allowed = {str(item) for item in restrict_ids}
    if not allowed:
        return False
    return str(school_id or "") in allowed
