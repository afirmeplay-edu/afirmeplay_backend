# -*- coding: utf-8 -*-
"""Recorte de alunos do menu Resultados (regular / ADAP 1 e 2).

Parâmetro ausente ou ``todos`` devolve as mesmas listas, sem reordenar.
ADAP 3 fica de fora de regular, regular_adap e adap. Vale o vínculo atual
(subturma ou série antiga de Educação Especial), via special_education.
"""
from __future__ import annotations

from typing import Any, List, Optional, Sequence

from app.services.special_education import (
    SpecialEducationStatus,
    is_special_education_many,
)

ALUNOS_FILTRO_TODOS = "todos"
ALUNOS_FILTROS = ("regular", "regular_adap", "adap", ALUNOS_FILTRO_TODOS)
_ADAP_OBJETIVO = (1, 2)


class AlunosFiltroInvalido(ValueError):
    """Valor do query param ``alunos`` fora da lista aceita."""


def parse_alunos_filtro(raw: Any) -> str:
    """Ausente ou vazio significa ``todos`` (comportamento anterior)."""
    if raw is None:
        return ALUNOS_FILTRO_TODOS
    text = str(raw).strip().lower()
    if text == "":
        return ALUNOS_FILTRO_TODOS
    if text not in ALUNOS_FILTROS:
        raise AlunosFiltroInvalido(
            "Parâmetro alunos inválido. Use regular, regular_adap, adap ou todos."
        )
    return text


def filtro_restringe(filtro: Optional[str]) -> bool:
    return bool(filtro) and filtro != ALUNOS_FILTRO_TODOS


def aluno_entra_no_filtro(status: SpecialEducationStatus, filtro: str) -> bool:
    """
    regular: quem não é educação especial.
    adap: só nível 1 ou 2 (subturma ou série antiga).
    regular_adap: os dois grupos acima.
    Nível 3 e educação especial sem nível ficam de fora dessas três opções.
    """
    if not filtro_restringe(filtro):
        return True
    nivel = status.level if status.is_special else None
    adap_objetivo = bool(status.is_special and nivel in _ADAP_OBJETIVO)
    regular = not status.is_special
    if filtro == "regular":
        return regular
    if filtro == "adap":
        return adap_objetivo
    if filtro == "regular_adap":
        return regular or adap_objetivo
    return True


def filtrar_alunos_resultado(students: Sequence[Any], filtro: Optional[str]) -> Sequence[Any]:
    """Mantém a ordem. ``todos`` devolve a mesma sequência, sem cópia."""
    if not filtro_restringe(filtro):
        return students
    rows = [student for student in students if student is not None]
    statuses = is_special_education_many(rows)
    escolhidos: List[Any] = []
    for student in students:
        if student is None:
            continue
        key = str(getattr(student, "id", ""))
        status = statuses.get(key, SpecialEducationStatus(False, None, None))
        if aluno_entra_no_filtro(status, filtro):
            escolhidos.append(student)
    return escolhidos


def _ids_aluno(student: Any) -> str:
    return str(getattr(student, "id", "") or "")


def aplicar_universo_alunos(
    students: Sequence[Any],
    filtro: Optional[str],
    results: Optional[Sequence[Any]] = None,
) -> Any:
    """
    Corta alunos e, se houver resultados, só os desses alunos.

    Com ``todos``, devolve os mesmos objetos recebidos.
    Resultado cujo aluno não está em ``students`` é classificado junto
    (transferido que entra pelo snapshot).
    """
    if results is None:
        return filtrar_alunos_resultado(students, filtro)
    if not filtro_restringe(filtro):
        return students, results

    by_id = {}
    ordered: List[Any] = []
    for student in students:
        if student is None:
            continue
        key = _ids_aluno(student)
        if not key or key in by_id:
            continue
        by_id[key] = student
        ordered.append(student)

    missing = []
    for row in results:
        sid = getattr(row, "student_id", None)
        if sid is None:
            continue
        key = str(sid)
        if key and key not in by_id:
            missing.append(key)
    if missing:
        from app.models.student import Student

        extras = Student.query.filter(Student.id.in_(list(set(missing)))).all()
        for student in extras:
            key = _ids_aluno(student)
            if key and key not in by_id:
                by_id[key] = student
                ordered.append(student)

    filtered_students = filtrar_alunos_resultado(ordered, filtro)
    allowed = {_ids_aluno(student) for student in filtered_students}
    filtered_results = [
        row
        for row in results
        if str(getattr(row, "student_id", "") or "") in allowed
    ]
    return filtered_students, filtered_results
