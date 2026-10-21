# -*- coding: utf-8 -*-
"""Recorte regular/ADAP e nota válida, o mesmo contrato de Resultados.

A participação continua no censo, com o resultado cru. A nota usa o
pareamento: regular na prova regular, ADAP 1, 2 ou 3 na prova pareada.
"""
from __future__ import annotations

from typing import Any, Iterable, List, Optional, Sequence

from app.services.alunos_resultado_filtro import (
    filtrar_alunos_resultado,
    filtro_restringe,
)


def resultados_para_notas(
    test_ids: Sequence[Any],
    students: Sequence[Any],
    results: Sequence[Any],
    alunos_filtro: Optional[str],
    *,
    parear: bool,
) -> List[Any]:
    """Notas do recorte. Sem pareamento, só corta quem entra."""
    from app.services.adap_resultado_pareado import apply_pareamento_to_universe

    roster = list(filtrar_alunos_resultado(students, alunos_filtro))
    allowed = {str(getattr(student, "id", "") or "") for student in roster}
    ids = [str(test_id) for test_id in test_ids if test_id]
    if not ids:
        return []
    if not parear:
        return [
            row
            for row in results or []
            if str(getattr(row, "student_id", "") or "") in allowed
            and str(getattr(row, "test_id", "") or "") in set(ids)
        ]

    kept: List[Any] = []
    seen = set()
    for test_id in ids:
        _, rows, _ = apply_pareamento_to_universe(test_id, roster, results or [])
        for row in rows:
            student_id = str(getattr(row, "student_id", "") or "")
            if student_id not in allowed:
                continue
            if str(getattr(row, "test_id", "") or "") != test_id:
                continue
            key = (student_id, test_id)
            if key in seen:
                continue
            seen.add(key)
            kept.append(row)
    return kept


def linhas_com_nota_valida(
    linhas: Sequence[Any],
    notas: Sequence[Any],
    students: Sequence[Any],
    alunos_filtro: Optional[str],
) -> List[dict]:
    """Linhas de níveis/ranking com a nota da modalidade certa."""
    roster = {
        str(getattr(student, "id", "") or ""): student
        for student in filtrar_alunos_resultado(students, alunos_filtro)
    }
    existentes = {
        str(row.get("id") or ""): row for row in (linhas or []) if isinstance(row, dict)
    }
    saida: List[dict] = []
    for row in notas or []:
        student_id = str(getattr(row, "student_id", "") or "")
        if filtro_restringe(alunos_filtro) and student_id not in roster:
            continue
        if not filtro_restringe(alunos_filtro) and student_id not in roster:
            continue
        base = dict(existentes.get(student_id) or {})
        student = roster.get(student_id)
        base["id"] = student_id
        if not base.get("nome") and student is not None:
            base["nome"] = getattr(student, "name", "") or ""
        base["nota_geral"] = getattr(row, "grade", None)
        base["proficiencia_geral"] = getattr(row, "proficiency", None)
        base["nivel_proficiencia_geral"] = getattr(row, "classification", None)
        base["status_geral"] = (
            "concluida" if getattr(row, "classification", None) else "pendente"
        )
        base["total_acertos_geral"] = getattr(row, "correct_answers", 0) or 0
        base["total_questoes_geral"] = getattr(row, "total_questions", 0) or 0
        saida.append(base)
    return saida


def carregar_universo_da_prova(
    test_id: Any,
    *,
    municipio_id: Any = None,
    alunos_filtro: Optional[str] = "todos",
    parear: bool = False,
    class_ids: Optional[Iterable[Any]] = None,
    school_ids: Optional[Iterable[Any]] = None,
):
    """Matrícula da prova, notas do recorte e censo. O censo vê o resultado cru."""
    from app.models.classTest import ClassTest
    from app.models.evaluationResult import EvaluationResult
    from app.models.student import Student
    from app.services.participation_census_shadow import montar_censo_carregado

    class_tests = ClassTest.query.filter(ClassTest.test_id == str(test_id)).all()
    if class_ids is not None:
        permitidas = {str(item) for item in class_ids if item}
        class_tests = [
            item for item in class_tests if str(getattr(item, "class_id", "") or "") in permitidas
        ]
    turma_ids = [item.class_id for item in class_tests if getattr(item, "class_id", None)]
    students = (
        Student.query.filter(Student.class_id.in_(turma_ids)).all() if turma_ids else []
    )
    if school_ids:
        escolas = {str(item) for item in school_ids if item}
        students = [
            student
            for student in students
            if str(getattr(student, "school_id", "") or "") in escolas
        ]
        turmas_restantes = {str(getattr(student, "class_id", "") or "") for student in students}
        class_tests = [
            item
            for item in class_tests
            if str(getattr(item, "class_id", "") or "") in turmas_restantes
        ]
    student_ids = [student.id for student in students]
    results = (
        EvaluationResult.query.filter(
            EvaluationResult.test_id == str(test_id),
            EvaluationResult.student_id.in_(student_ids),
        ).all()
        if student_ids
        else []
    )
    notas = resultados_para_notas(
        [test_id], students, results, alunos_filtro, parear=parear
    )
    try:
        censo = montar_censo_carregado(
            municipio_id=municipio_id,
            universo=alunos_filtro or "todos",
            test_ids=[test_id],
            alunos=students,
            class_tests=class_tests,
            resultados=results,
        )
    except Exception:
        censo = None
    return students, notas, censo
