# -*- coding: utf-8 -*-
"""
Séries aplicáveis a um gabarito de cartão-resposta.

Fonte da verdade: coluna JSON ``grades`` = [{"id": "<uuid>", "name": "9º Ano"}, ...].
``grade_id`` / ``grade_name`` permanecem como atalho legado (1ª série, ou a única).
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


def _norm_id(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _norm_name(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def normalize_grades_list(
    raw: Any,
    *,
    resolve_names: bool = True,
) -> List[Dict[str, str]]:
    """
    Normaliza payload de séries:
    - ["uuid", ...]
    - [{"id": "...", "name": "..."}, ...]
    - grade_id singular + grade_name
    """
    if raw is None:
        return []

    items: List[Any]
    if isinstance(raw, dict):
        items = [raw]
    elif isinstance(raw, (list, tuple)):
        items = list(raw)
    else:
        sid = _norm_id(raw)
        items = [sid] if sid else []

    out: List[Dict[str, str]] = []
    seen = set()
    for item in items:
        gid = ""
        gname = ""
        if isinstance(item, dict):
            gid = _norm_id(item.get("id") or item.get("grade_id"))
            gname = _norm_name(item.get("name") or item.get("grade_name"))
        else:
            gid = _norm_id(item)
        if not gid or gid in seen:
            continue
        seen.add(gid)
        if resolve_names and not gname:
            gname = _lookup_grade_name(gid) or ""
        out.append({"id": gid, "name": gname})
    return out


def _lookup_grade_name(grade_id: str) -> Optional[str]:
    try:
        from app.models.grades import Grade

        grade = Grade.query.get(grade_id)
        if grade and getattr(grade, "name", None):
            return str(grade.name).strip() or None
    except Exception:
        return None
    return None


def grades_from_classes(classes: Sequence[Any]) -> List[Dict[str, str]]:
    """Séries distintas das turmas (ordem estável por nome)."""
    by_id: Dict[str, str] = {}
    for cls in classes or []:
        gid = _norm_id(getattr(cls, "grade_id", None))
        if not gid:
            continue
        if gid in by_id:
            continue
        gname = ""
        grade = getattr(cls, "grade", None)
        if grade and getattr(grade, "name", None):
            gname = _norm_name(grade.name)
        if not gname:
            gname = _lookup_grade_name(gid) or ""
        by_id[gid] = gname
    ordered = sorted(by_id.items(), key=lambda kv: (kv[1].lower(), kv[0]))
    return [{"id": gid, "name": name} for gid, name in ordered]


def get_gabarito_grades(gabarito: Any) -> List[Dict[str, str]]:
    """Lê ``grades``; fallback legado ``grade_id``/``grade_name``."""
    if not gabarito:
        return []
    raw = getattr(gabarito, "grades", None)
    grades = normalize_grades_list(raw, resolve_names=True)
    if grades:
        return grades
    gid = _norm_id(getattr(gabarito, "grade_id", None))
    if not gid:
        return []
    gname = _norm_name(getattr(gabarito, "grade_name", None)) or (_lookup_grade_name(gid) or "")
    return [{"id": gid, "name": gname}]


def apply_grades_to_gabarito(gabarito: Any, grades: Sequence[Dict[str, str]]) -> List[Dict[str, str]]:
    """
    Persiste séries no gabarito.
    - ``grades``: lista completa
    - ``grade_id`` / ``grade_name``: preenchidos só se houver exatamente 1 série
      (evita sugerir série única em gabarito multi-série)
    """
    normalized = normalize_grades_list(list(grades or []), resolve_names=True)
    gabarito.grades = normalized
    if len(normalized) == 1:
        gabarito.grade_id = normalized[0]["id"]
        gabarito.grade_name = normalized[0]["name"] or None
    else:
        gabarito.grade_id = None
        gabarito.grade_name = None
    return normalized


def merge_grade_sources(
    *,
    payload_grade_ids: Optional[Iterable[Any]] = None,
    payload_grades: Optional[Any] = None,
    classes: Optional[Sequence[Any]] = None,
) -> List[Dict[str, str]]:
    """Prioridade: grades explícitas do payload → grade_ids → séries das turmas."""
    if payload_grades is not None:
        grades = normalize_grades_list(payload_grades, resolve_names=True)
        if grades:
            return grades
    if payload_grade_ids is not None:
        grades = normalize_grades_list(list(payload_grade_ids), resolve_names=True)
        if grades:
            return grades
    if classes:
        return grades_from_classes(classes)
    return []


def pick_grade_for_scope(
    gabarito: Any,
    serie_id: Optional[str] = None,
) -> Optional[Dict[str, str]]:
    """Série efetiva para agregação: filtro ``serie`` ou única série do gabarito."""
    grades = get_gabarito_grades(gabarito)
    sid = _norm_id(serie_id)
    if sid and sid.lower() != "all":
        for g in grades:
            if g["id"] == sid:
                return g
        # Filtro pode apontar série do escopo mesmo se ainda não estiver em grades
        name = _lookup_grade_name(sid) or ""
        return {"id": sid, "name": name}
    if len(grades) == 1:
        return grades[0]
    return None


def course_name_for_grade_label(grade_name: str) -> str:
    from app.services.cartao_resposta.course_name_resolver import infer_course_name_from_grade

    return infer_course_name_from_grade(grade_name or "")


def course_meta_for_gabarito_serie(
    gabarito: Any,
    serie_id: Optional[str] = None,
) -> Tuple[str, Optional[str], Optional[str]]:
    """
    Retorna (course_name, grade_name, grade_id) para agregação.
    Sem série única resolvível → course_name vazio (caller não deve misturar escalas).
    """
    picked = pick_grade_for_scope(gabarito, serie_id)
    if not picked:
        return "", None, None
    gname = picked.get("name") or ""
    if not gname and picked.get("id"):
        gname = _lookup_grade_name(picked["id"]) or ""
    return course_name_for_grade_label(gname), gname or None, picked.get("id")
