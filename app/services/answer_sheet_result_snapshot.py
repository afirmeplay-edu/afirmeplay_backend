# -*- coding: utf-8 -*-
"""
Snapshots de colocação escolar em answer_sheet_results.

Espelha a lógica de evaluation_result_snapshot: o resultado permanece vinculado à
turma/escola do momento da participação, mesmo se o aluno for removido ou transferido.
"""
from __future__ import annotations

from typing import Any, List, Optional, Set

from sqlalchemy import and_, or_

from app import db
from app.models.answerSheetResult import AnswerSheetResult
from app.models.student import Student
from app.services.evaluation_result_snapshot import build_placement_snapshots_from_student


def fill_answer_sheet_result_snapshots(
    result: AnswerSheetResult,
    student: Optional[Student] = None,
    *,
    only_if_empty: bool = True,
) -> None:
    """
    Preenche school/class/grade/enrollment snapshots no resultado.

    Com ``only_if_empty=True`` (padrão), não sobrescreve snapshot já gravado —
    mantém a colocação histórica em re-correções.
    """
    if result is None:
        return
    if only_if_empty and (
        getattr(result, "class_id_snapshot", None) is not None
        or getattr(result, "school_id_snapshot", None) is not None
    ):
        return

    if student is None and getattr(result, "student_id", None):
        student = Student.query.get(result.student_id)
    if student is None:
        return

    placement = build_placement_snapshots_from_student(student)
    if only_if_empty:
        if getattr(result, "school_id_snapshot", None) is None:
            result.school_id_snapshot = placement.get("school_id_snapshot")
        if getattr(result, "class_id_snapshot", None) is None:
            result.class_id_snapshot = placement.get("class_id_snapshot")
        if getattr(result, "grade_id_snapshot", None) is None:
            result.grade_id_snapshot = placement.get("grade_id_snapshot")
        if getattr(result, "enrollment_id_snapshot", None) is None:
            result.enrollment_id_snapshot = placement.get("enrollment_id_snapshot")
    else:
        result.school_id_snapshot = placement.get("school_id_snapshot")
        result.class_id_snapshot = placement.get("class_id_snapshot")
        result.grade_id_snapshot = placement.get("grade_id_snapshot")
        result.enrollment_id_snapshot = placement.get("enrollment_id_snapshot")


def student_ids_for_answer_sheet_class_group(
    gabarito_id: str,
    class_ids: List[Any],
    base_student_ids: Set[str],
) -> Set[str]:
    """Alunos atuais nas turmas ∪ alunos com snapshot nessas turmas (removidos/transferidos)."""
    if not gabarito_id or not class_ids:
        return set(base_student_ids)
    extra = (
        db.session.query(AnswerSheetResult.student_id)
        .filter(AnswerSheetResult.gabarito_id == str(gabarito_id))
        .filter(AnswerSheetResult.class_id_snapshot.in_(class_ids))
        .distinct()
        .all()
    )
    ids = {str(r[0]) for r in extra if r[0]}
    return set(base_student_ids) | ids


def query_answer_sheet_results_for_class_group(
    gabarito_id: str,
    class_ids: List[Any],
    base_student_ids: List[str],
):
    """
    Resultados do gabarito no grupo de turmas: snapshot de turma OU legado
    (sem snapshot) ainda no recorte atual de alunos.
    """
    q = AnswerSheetResult.query.filter(AnswerSheetResult.gabarito_id == str(gabarito_id))
    in_classes = (
        AnswerSheetResult.class_id_snapshot.in_(class_ids) if class_ids else None
    )
    legacy = and_(
        AnswerSheetResult.school_id_snapshot.is_(None),
        AnswerSheetResult.class_id_snapshot.is_(None),
        AnswerSheetResult.student_id.in_(base_student_ids if base_student_ids else []),
    )
    if in_classes is not None and base_student_ids:
        q = q.filter(or_(in_classes, legacy))
    elif in_classes is not None:
        q = q.filter(in_classes)
    elif base_student_ids:
        q = q.filter(AnswerSheetResult.student_id.in_(base_student_ids))
    else:
        q = q.filter(False)
    return q


def backfill_answer_sheet_result_snapshots_from_current_placement() -> int:
    """
    Preenche snapshots vazios a partir da colocação atual do aluno.
    Não altera linhas que já têm snapshot. Retorna quantidade atualizada.
    """
    rows = (
        AnswerSheetResult.query.filter(
            AnswerSheetResult.class_id_snapshot.is_(None),
            AnswerSheetResult.school_id_snapshot.is_(None),
        )
        .all()
    )
    updated = 0
    for result in rows:
        student = Student.query.get(result.student_id)
        if not student or not student.class_id:
            continue
        fill_answer_sheet_result_snapshots(result, student, only_if_empty=True)
        if result.class_id_snapshot is not None or result.school_id_snapshot is not None:
            updated += 1
    return updated
