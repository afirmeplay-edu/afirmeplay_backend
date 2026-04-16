# -*- coding: utf-8 -*-
"""
Médias de nota e proficiência com **mesmo peso por escola**:
para cada escola calcula-se a média dos alunos dessa escola; depois a média
aritmética dessas médias (cada escola conta igual, independente do nº de alunos).

Usado nos consolidados de município / várias escolas (avaliações online e cartão-resposta).
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional, Sequence, Tuple

from app.models.student import Student
from app.models.studentClass import Class


def student_ids_to_school_id_map(student_ids: Sequence[str]) -> Dict[str, Optional[str]]:
    """Mapeia student.id -> school.id (string) ou None se não houver turma/escola."""
    if not student_ids:
        return {}
    uniq = list({str(x) for x in student_ids if x})
    if not uniq:
        return {}
    students = Student.query.filter(Student.id.in_(uniq)).all()
    class_ids = [s.class_id for s in students if s.class_id]
    if not class_ids:
        return {s.id: None for s in students}
    classes = {
        str(c.id): c for c in Class.query.filter(Class.id.in_(class_ids)).all()
    }
    out: Dict[str, Optional[str]] = {}
    for s in students:
        if not s.class_id:
            out[s.id] = None
            continue
        co = classes.get(str(s.class_id))
        out[s.id] = str(co.school_id) if co and co.school_id else None
    return out


def mean_grade_and_proficiency_equal_weight_by_school(
    results: Sequence[Any],
) -> Tuple[float, float]:
    """
    `results`: objetos com .student_id, .grade, .proficiency (AnswerSheetResult, EvaluationResult, ...).

    Se não houver agrupamento por escola possível, cai na média simples dos alunos.
    """
    if not results:
        return 0.0, 0.0
    ids = [getattr(r, "student_id", None) for r in results]
    m = student_ids_to_school_id_map([i for i in ids if i])
    by_school: Dict[str, List[Tuple[float, float]]] = defaultdict(list)
    for r in results:
        sid_stu = getattr(r, "student_id", None)
        sch = m.get(sid_stu) if sid_stu else None
        if not sch:
            continue
        g = float(getattr(r, "grade", None) or 0)
        p = float(getattr(r, "proficiency", None) or 0)
        by_school[str(sch)].append((g, p))

    if not by_school:
        g_mean = sum(float(getattr(r, "grade", None) or 0) for r in results) / len(results)
        p_mean = sum(float(getattr(r, "proficiency", None) or 0) for r in results) / len(results)
        return g_mean, p_mean

    g_means: List[float] = []
    p_means: List[float] = []
    for vals in by_school.values():
        if not vals:
            continue
        g_means.append(sum(x[0] for x in vals) / len(vals))
        p_means.append(sum(x[1] for x in vals) / len(vals))
    if not g_means:
        return 0.0, 0.0
    return sum(g_means) / len(g_means), sum(p_means) / len(p_means)


def mean_grade_and_proficiency_equal_weight_by_school_from_subject_rows(
    subject_rows: List[Dict[str, Any]],
    student_id_key: str = "student_id",
) -> Tuple[float, float, float]:
    """
    subject_rows: lista de dicts com student_id, grade, proficiency (e opcionalmente score_percentage).
    Retorna (avg_grade, avg_proficiency, avg_score_pct).
    """
    if not subject_rows:
        return 0.0, 0.0, 0.0
    ids = [row.get(student_id_key) for row in subject_rows]
    m = student_ids_to_school_id_map([i for i in ids if i])
    by_school: Dict[str, List[Tuple[float, float, float]]] = defaultdict(list)
    for row in subject_rows:
        sid_stu = row.get(student_id_key)
        sch = m.get(sid_stu) if sid_stu else None
        if not sch:
            continue
        g = float(row.get("grade") or 0)
        p = float(row.get("proficiency") or 0)
        sp = float(row.get("score_percentage") or 0)
        by_school[str(sch)].append((g, p, sp))

    if not by_school:
        g_mean = sum(float(row.get("grade") or 0) for row in subject_rows) / len(subject_rows)
        p_mean = sum(float(row.get("proficiency") or 0) for row in subject_rows) / len(subject_rows)
        s_mean = sum(float(row.get("score_percentage") or 0) for row in subject_rows) / len(subject_rows)
        return g_mean, p_mean, s_mean

    g_m: List[float] = []
    p_m: List[float] = []
    s_m: List[float] = []
    for vals in by_school.values():
        if not vals:
            continue
        g_m.append(sum(x[0] for x in vals) / len(vals))
        p_m.append(sum(x[1] for x in vals) / len(vals))
        s_m.append(sum(x[2] for x in vals) / len(vals))
    if not g_m:
        return 0.0, 0.0, 0.0
    return (
        sum(g_m) / len(g_m),
        sum(p_m) / len(p_m),
        sum(s_m) / len(s_m),
    )
