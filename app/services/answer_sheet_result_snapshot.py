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
        if getattr(result, "student_name_snapshot", None) is None and getattr(student, "name", None):
            result.student_name_snapshot = student.name
    else:
        result.school_id_snapshot = placement.get("school_id_snapshot")
        result.class_id_snapshot = placement.get("class_id_snapshot")
        result.grade_id_snapshot = placement.get("grade_id_snapshot")
        result.enrollment_id_snapshot = placement.get("enrollment_id_snapshot")
        if getattr(student, "name", None):
            result.student_name_snapshot = student.name


def student_ids_for_answer_sheet_class_group(
    gabarito_id: str,
    class_ids: List[Any],
    base_student_ids: Set[str],
) -> Set[str]:
    """Alunos atuais nas turmas ∪ snapshot, menos transferência interna na mesma escola."""
    if not gabarito_id or not class_ids:
        return set(base_student_ids)
    extra = (
        db.session.query(AnswerSheetResult.student_id)
        .filter(AnswerSheetResult.gabarito_id == str(gabarito_id))
        .filter(AnswerSheetResult.class_id_snapshot.in_(class_ids))
        .distinct()
        .all()
    )
    ids = set(base_student_ids) | {str(r[0]) for r in extra if r[0]}
    try:
        from app.services.evaluation_result_snapshot import (
            load_internal_transfer_ids_to_exclude,
        )

        # Reusa a ideia do online: quem fez em outra turma da mesma escola
        # e não tem resultado neste grupo não entra como faltante.
        # Para cartão, consulta AnswerSheetResult com school_id_snapshot.
        transferidos = set()
        if class_ids:
            group = {str(c) for c in class_ids}
            rows = (
                db.session.query(
                    AnswerSheetResult.student_id,
                    AnswerSheetResult.class_id_snapshot,
                    AnswerSheetResult.school_id_snapshot,
                )
                .filter(AnswerSheetResult.gabarito_id == str(gabarito_id))
                .all()
            )
            by_student = {}
            for sid, cid, sch in rows:
                if not sid:
                    continue
                by_student.setdefault(str(sid), []).append(
                    (str(cid) if cid else None, str(sch) if sch else None)
                )
            for sid in list(ids):
                placements = by_student.get(sid) or []
                in_group = any(cid and cid in group for cid, _sch in placements)
                if in_group:
                    continue
                # Fez em outra turma da mesma escola dos class_ids?
                if sid in base_student_ids and placements:
                    transferidos.add(sid)
            ids -= transferidos
    except Exception:
        pass
    return ids


def query_answer_sheet_results_for_class_group(
    gabarito_id: str,
    class_ids: List[Any],
    base_student_ids: List[str],
):
    """
    Resultados do gabarito no grupo de turmas: só snapshot de turma.
    Legado sem snapshot fica fora da agregação (bucket explícito).
    """
    q = AnswerSheetResult.query.filter(AnswerSheetResult.gabarito_id == str(gabarito_id))
    if class_ids:
        q = q.filter(AnswerSheetResult.class_id_snapshot.in_(class_ids))
    else:
        q = q.filter(False)
    return q


def query_legacy_answer_sheet_results_without_snapshot(gabarito_id: str):
    """Bucket explícito: cartões sem snapshot (fora de agregação por turma)."""
    return AnswerSheetResult.query.filter(
        AnswerSheetResult.gabarito_id == str(gabarito_id),
        AnswerSheetResult.school_id_snapshot.is_(None),
        AnswerSheetResult.class_id_snapshot.is_(None),
    )


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
