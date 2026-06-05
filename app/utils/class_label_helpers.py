"""Helpers para rótulos de turma/série/turno em relatórios e documentos."""

from __future__ import annotations

from typing import Any, Dict, Optional


def normalize_shift(value: Any) -> Optional[str]:
    """Normaliza valor de turno (aceita None, vazio ou string)."""
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def format_grade_class_label(
    grade_name: Any,
    class_name: Any = None,
    shift: Any = None,
    *,
    include_shift: bool = False,
) -> str:
    """
    Monta rótulo visual de série + turma.
    Por padrão NÃO inclui turno (evita alterar chaves de agrupamento).
    Use include_shift=True apenas em exibição explícita.
    """
    grade = str(grade_name or "").strip() or "Sem série"
    turma = str(class_name or "").strip()
    if turma:
        label = f"{grade} - {turma}"
    else:
        label = grade
    if include_shift:
        shift_text = normalize_shift(shift)
        if shift_text:
            label = f"{label} ({shift_text})"
    return label


def format_serie_turno_label(
    grade_name: Any,
    class_name: Any = None,
    shift: Any = None,
) -> str:
    """Alias para colunas rotuladas SÉRIE/TURNO — inclui turno quando disponível."""
    return format_grade_class_label(
        grade_name, class_name, shift, include_shift=True
    )


def class_filter_option(
    class_id: Any,
    name: Any = None,
    shift: Any = None,
) -> Dict[str, str]:
    """Opção de turma para filtros de relatório (`id`, `name`, `shift`)."""
    cid = str(class_id)
    label = str(name or "").strip() or f"Turma {cid}"
    return {
        "id": cid,
        "name": label,
        "shift": normalize_shift(shift) or "",
    }


def class_model_filter_option(classe: Any) -> Dict[str, str]:
    return class_filter_option(
        getattr(classe, "id", ""),
        getattr(classe, "name", None),
        getattr(classe, "shift", None),
    )


def format_turma_display_name(turma: Any, shift: Any = None) -> str:
    """Rótulo visual de turma com turno opcional (não altera chave de agrupamento)."""
    name = str(turma or "").strip()
    shift_text = normalize_shift(shift)
    if name and shift_text:
        return f"{name} — {shift_text}"
    return name or "—"


def class_context_from_model(classe: Any) -> Dict[str, Optional[str]]:
    """
    Extrai contexto de turma a partir do modelo Class.
    Retorna grade_name, class_name, turma, shift e labels de exibição.
    """
    grade = getattr(classe, "grade", None)
    grade_name = str(getattr(grade, "name", None) or "").strip() or None
    class_name = str(getattr(classe, "name", None) or "").strip() or None
    turma = str(getattr(classe, "turma", None) or "").strip() or class_name
    shift = normalize_shift(getattr(classe, "shift", None))
    return {
        "grade_name": grade_name,
        "class_name": class_name,
        "turma": turma,
        "shift": shift,
        "label": format_grade_class_label(grade_name, class_name),
        "serie_turno_label": format_serie_turno_label(grade_name, class_name, shift),
    }
