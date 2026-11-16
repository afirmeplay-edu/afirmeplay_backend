# -*- coding: utf-8 -*-
"""Recorte de alunos do menu Resultados (regular / ADAP 1 e 2).

Parâmetro ausente ou ``todos`` exclui só o ADAP 3 (não faz prova objetiva).
Educação especial sem nível fica de fora de regular, regular_adap e adap.
Vale o vínculo atual (subturma ou série antiga de Educação Especial), via special_education.
"""
from __future__ import annotations

from typing import Any, List, Optional, Sequence

from app.services.adap_objetivo import ADAP_OBJETIVO_NIVEIS, e_adap_excluido_prova_objetiva
from app.services.special_education import (
    SpecialEducationStatus,
    is_special_education_many,
)

ALUNOS_FILTRO_TODOS = "todos"
ALUNOS_FILTROS = ("regular", "regular_adap", "adap", ALUNOS_FILTRO_TODOS)


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


def aluno_entra_no_filtro(
    status: SpecialEducationStatus,
    filtro: str,
    *,
    incluir_adap3: bool = False,
) -> bool:
    """
    Por padrão (prova objetiva/impressa) o ADAP 3 fica de fora.

    ``incluir_adap3=True`` só para cadastro/Relatório de Usuários, onde o
    nível 3 continua no filtro ADAP / Regular+ADAP / Todos.

    regular: quem não é educação especial.
    adap: níveis do recorte (1–2 na objetiva; 1–3 com incluir_adap3).
    regular_adap: regulares e esses níveis.
    Educação especial sem nível fica de fora de regular/adap/regular_adap,
    mas entra em todos.
    """
    nivel = status.level if status.is_special else None
    if not incluir_adap3 and e_adap_excluido_prova_objetiva(nivel):
        return False
    if not filtro_restringe(filtro):
        return True
    niveis = (1, 2, 3) if incluir_adap3 else ADAP_OBJETIVO_NIVEIS
    adap = bool(status.is_special and nivel in niveis)
    regular = not status.is_special
    if filtro == "regular":
        return regular
    if filtro == "adap":
        return adap
    if filtro == "regular_adap":
        return regular or adap
    return True


def _status_map(students: Sequence[Any]) -> dict:
    rows = [student for student in students if student is not None]
    if not rows:
        return {}
    return is_special_education_many(rows)


def _tem_adap_excluido(statuses: dict) -> bool:
    return any(
        status.is_special and e_adap_excluido_prova_objetiva(status.level)
        for status in statuses.values()
    )


def filtrar_alunos_resultado(
    students: Sequence[Any],
    filtro: Optional[str],
    *,
    incluir_adap3: bool = False,
) -> Sequence[Any]:
    """Mantém a ordem. Sem ADAP 3 no universo, ``todos`` devolve a mesma sequência.

    ``incluir_adap3=True`` para gabarito/prova dedicada ADAP 3 (geração continua
    permitida; o recorte de resultados daquela prova precisa ver o nível 3).
    """
    statuses = _status_map(students)
    if (
        not filtro_restringe(filtro)
        and (incluir_adap3 or not _tem_adap_excluido(statuses))
    ):
        return students
    escolhidos: List[Any] = []
    valor = filtro or ALUNOS_FILTRO_TODOS
    for student in students:
        if student is None:
            continue
        key = str(getattr(student, "id", ""))
        status = statuses.get(key, SpecialEducationStatus(False, None, None))
        if aluno_entra_no_filtro(status, valor, incluir_adap3=incluir_adap3):
            escolhidos.append(student)
    return escolhidos


def _ids_aluno(student: Any) -> str:
    return str(getattr(student, "id", "") or "")


def aplicar_universo_alunos(
    students: Sequence[Any],
    filtro: Optional[str],
    results: Optional[Sequence[Any]] = None,
    *,
    incluir_adap3: bool = False,
) -> Any:
    """
    Corta alunos e, se houver resultados, só os desses alunos.

    Por padrão exclui ADAP 3 (provas regulares). Com ``todos`` e sem ADAP 3 /
    extras, devolve os mesmos objetos. ``incluir_adap3`` para prova/gabarito ADAP 3.
    Resultado cujo aluno não está em ``students`` é classificado junto
    (transferido que entra pelo snapshot).
    """
    if results is None:
        return filtrar_alunos_resultado(students, filtro, incluir_adap3=incluir_adap3)

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

    statuses = _status_map(ordered)
    if (
        not filtro_restringe(filtro)
        and not missing
        and (incluir_adap3 or not _tem_adap_excluido(statuses))
    ):
        return students, results

    filtered_students = filtrar_alunos_resultado(
        ordered, filtro, incluir_adap3=incluir_adap3
    )
    allowed = {_ids_aluno(student) for student in filtered_students}
    filtered_results = [
        row
        for row in results
        if str(getattr(row, "student_id", "") or "") in allowed
    ]
    return filtered_students, filtered_results
