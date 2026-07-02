import re
from typing import Any, Optional, Set


# Exige contexto de série (ano/série/médio) para não confundir "1º AVALIA" com "1º ano".
_GRADE_NUMBER_WITH_CONTEXT = re.compile(
    r"\b([1-9]|1[0-2])\s*(?:[oº°])?\s*(?:ano|anos|série|serie|medio|médio)\b",
    re.IGNORECASE,
)


def _extract_grade_number(grade_lower: str) -> Optional[int]:
    match = _GRADE_NUMBER_WITH_CONTEXT.search(grade_lower)
    if not match:
        return None
    return int(match.group(1))


def looks_like_grade_label(text: str) -> bool:
    """True quando o texto parece nome de série/ano escolar (e não título genérico)."""
    if not text or not str(text).strip():
        return False
    grade_lower = str(text).strip().lower()
    if any(
        kw in grade_lower
        for kw in (
            "infantil",
            "especial",
            "eja",
            "médio",
            "medio",
            "anos iniciais",
            "anos finais",
            "fundamental i",
            "fundamental ii",
        )
    ):
        return True
    return _extract_grade_number(grade_lower) is not None


def infer_course_name_from_grade(grade_name: str) -> str:
    """
    Inferir nome do curso a partir de diferentes formatos de série.

    Exemplos aceitos:
    - "5º ano", "5° ANO", "5 ano", "5o ano"
    - "9º ano", "9 ano"
    - "1º médio", "2 medio"

    Títulos sem contexto de série (ex.: "1º AVALIA MUNICIPAL") não inferem número.
    """
    grade_lower = (grade_name or "").strip().lower()
    if not grade_lower:
        return "Anos Iniciais"

    if "infantil" in grade_lower or "pré" in grade_lower or "pre" in grade_lower:
        return "Educação Infantil"

    if "especial" in grade_lower:
        return "Educação Especial"

    if "eja" in grade_lower:
        return "EJA"

    if "médio" in grade_lower or "medio" in grade_lower:
        return "Ensino Médio"

    if "anos iniciais" in grade_lower or "fundamental i" in grade_lower:
        return "Anos Iniciais"

    if "anos finais" in grade_lower or "fundamental ii" in grade_lower:
        return "Anos Finais"

    grade_number = _extract_grade_number(grade_lower)
    if grade_number is not None:
        if 1 <= grade_number <= 5:
            return "Anos Iniciais"
        if 6 <= grade_number <= 9:
            return "Anos Finais"
        if 10 <= grade_number <= 12:
            return "Ensino Médio"

    return "Anos Iniciais"


def _grade_name_from_student(student: Any) -> Optional[str]:
    if not student:
        return None
    try:
        classe = getattr(student, "class_", None) or getattr(student, "class", None)
        if classe and getattr(classe, "grade", None) and getattr(classe.grade, "name", None):
            name = str(classe.grade.name).strip()
            return name or None
        grade_id = getattr(classe, "grade_id", None) if classe else getattr(student, "grade_id", None)
        if grade_id:
            from app.models.grades import Grade

            grade = Grade.query.get(grade_id)
            if grade and getattr(grade, "name", None):
                name = str(grade.name).strip()
                return name or None
    except Exception:
        return None
    return None


def _grade_names_from_scope_snapshot(gabarito_obj: Any) -> Set[str]:
    names: Set[str] = set()
    if not gabarito_obj or not getattr(gabarito_obj, "id", None):
        return names
    try:
        from app.services.cartao_resposta.answer_sheet_gabarito_generation import (
            AnswerSheetGabaritoGeneration,
        )

        rows = (
            AnswerSheetGabaritoGeneration.query.filter_by(gabarito_id=str(gabarito_obj.id))
            .order_by(AnswerSheetGabaritoGeneration.created_at.desc())
            .all()
        )
        for row in rows:
            snap = getattr(row, "scope_snapshot", None) or {}
            if not isinstance(snap, dict):
                continue
            for item in snap.get("class_ids") or []:
                if isinstance(item, dict):
                    gn = (item.get("grade_name") or "").strip()
                    if gn:
                        names.add(gn)
    except Exception:
        return names
    return names


def _pick_single_grade_name(names: Set[str]) -> Optional[str]:
    if not names:
        return None
    if len(names) == 1:
        return next(iter(names))
    ordered = sorted(names)
    return ordered[0]


def resolve_grade_name_for_proficiency(
    gabarito_obj: Any = None,
    grade_name: str = "",
    student: Any = None,
) -> str:
    """
    Resolve o rótulo de série usado no cálculo de proficiência.

    Ordem:
    1. grade_name explícito (se parecer série)
    2. gabarito.grade_name
    3. gabarito.grade_id → Grade.name
    4. scope_snapshot das gerações (única série ou primeira ordenada)
    5. gabarito.title (somente se parecer série)
    6. série da turma do aluno
    7. fallback: grade_name explícito ou title do gabarito (legado)
    """
    explicit = (grade_name or "").strip()
    if explicit and looks_like_grade_label(explicit):
        return explicit

    if gabarito_obj is not None:
        gab_grade = (getattr(gabarito_obj, "grade_name", None) or "").strip()
        if gab_grade:
            return gab_grade

        grade_id = getattr(gabarito_obj, "grade_id", None)
        if grade_id:
            try:
                from app.models.grades import Grade

                grade = Grade.query.get(grade_id)
                if grade and getattr(grade, "name", None):
                    name = str(grade.name).strip()
                    if name:
                        return name
            except Exception:
                pass

        from_scope = _pick_single_grade_name(_grade_names_from_scope_snapshot(gabarito_obj))
        if from_scope:
            return from_scope

        title = (getattr(gabarito_obj, "title", None) or "").strip()
        if title and looks_like_grade_label(title):
            return title

    from_student = _grade_name_from_student(student)
    if from_student:
        return from_student

    if explicit:
        return explicit
    if gabarito_obj is not None:
        return (getattr(gabarito_obj, "title", None) or "").strip()
    return ""
