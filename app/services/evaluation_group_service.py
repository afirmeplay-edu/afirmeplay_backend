# -*- coding: utf-8 -*-
"""
Agrupa N provas online da mesma série em um único cálculo de relatório.

O frontend envia `avaliacao=id1,id2,...` + `group_id=1`. Sem `group_id`,
os IDs não são tratados como grupo. A fórmula do GERAL é a mesma da prova
multidisciplinar: média das disciplinas do aluno.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from app.services.evaluation_calculator import EvaluationCalculator
from app.utils.decimal_helpers import round_to_two_decimals

GROUP_FLAG_VALUES = {"1", "true", "yes", "on"}


def is_group_request(group_id_param: Optional[str]) -> bool:
    return str(group_id_param or "").strip().lower() in GROUP_FLAG_VALUES


def parse_avaliacao_ids(raw: Optional[str]) -> List[str]:
    if raw is None:
        return []
    text = str(raw).strip()
    if not text or text.lower() == "all":
        return []
    return [part.strip() for part in text.split(",") if part.strip()]


def test_ids_from_param(avaliacao: Optional[Any]) -> List[str]:
    if isinstance(avaliacao, (list, tuple, set)):
        return [str(x).strip() for x in avaliacao if str(x).strip()]
    return parse_avaliacao_ids(avaliacao)


def test_id_clause(column, avaliacao: Optional[Any]):
    """Expressão SQL para um ID ou a união de vários (CSV ou lista)."""
    ids = test_ids_from_param(avaliacao)
    if not ids:
        return column.is_(None)
    if len(ids) == 1:
        return column == ids[0]
    return column.in_(ids)


def apply_test_id_filter(query, column, avaliacao: Optional[Any]):
    """Filtra por um ID ou pela união de vários (CSV ou lista)."""
    ids = test_ids_from_param(avaliacao)
    if not ids:
        return query
    return query.filter(test_id_clause(column, ids))


@dataclass
class GroupTestInfo:
    id: str
    title: str
    grade_id: Optional[str]
    grade_nome: str
    subjects: List[Dict[str, str]] = field(default_factory=list)


@dataclass
class EvaluationGroupContext:
    tests: List[Any]
    test_ids: List[str]
    tests_info: List[GroupTestInfo]
    grade_id: str
    grade_nome: str
    disciplinas: List[str]
    payload: Dict[str, Any]


@dataclass
class MergedStudentResult:
    student_id: str
    grade: float
    proficiency: float
    classification: str
    correct_answers: int
    total_questions: int
    subject_results: Dict[str, Any]
    completo: bool
    participacao: Dict[str, Any]
    school_id_snapshot: Any = None
    class_id_snapshot: Any = None
    grade_id_snapshot: Any = None
    enrollment_id_snapshot: Any = None
    test_ids_realizados: List[str] = field(default_factory=list)


def _subject_entries_from_test(test: Any) -> List[Dict[str, str]]:
    from app.utils.response_formatters import _get_all_subjects_from_test

    entries: List[Dict[str, str]] = []
    for item in _get_all_subjects_from_test(test) or []:
        sid = str(item.get("id") or "").strip()
        name = str(item.get("name") or "").strip()
        if sid:
            entries.append({"id": sid, "name": name})
    return entries


def _resolve_test_grade(test: Any) -> Tuple[Optional[str], str]:
    grade_id = getattr(test, "grade_id", None)
    grade = getattr(test, "grade", None)
    if grade_id:
        return str(grade_id), (getattr(grade, "name", None) or "")
    try:
        from app.models.classTest import ClassTest
        from app.models.studentClass import Class

        class_test = (
            ClassTest.query.join(Class, ClassTest.class_id == Class.id)
            .filter(ClassTest.test_id == str(test.id))
            .first()
        )
        if class_test and getattr(class_test, "class_", None) and class_test.class_.grade_id:
            g = class_test.class_.grade
            return str(class_test.class_.grade_id), (getattr(g, "name", None) or "")
    except Exception:
        pass
    return None, ""


def build_tests_info(tests: Sequence[Any]) -> List[GroupTestInfo]:
    infos: List[GroupTestInfo] = []
    for test in tests:
        grade_id, grade_nome = _resolve_test_grade(test)
        infos.append(
            GroupTestInfo(
                id=str(test.id),
                title=getattr(test, "title", None) or "",
                grade_id=grade_id,
                grade_nome=grade_nome,
                subjects=_subject_entries_from_test(test),
            )
        )
    return infos


def validate_group_tests(tests_info: Sequence[GroupTestInfo]) -> Optional[str]:
    if len(tests_info) < 2:
        return "group_id exige duas ou mais avaliações"

    grade_ids = {info.grade_id for info in tests_info if info.grade_id}
    if not grade_ids:
        return "As avaliações do grupo não têm série cadastrada"
    if len(grade_ids) > 1:
        return "As avaliações do grupo devem ser da mesma série"

    seen_subjects: Dict[str, str] = {}
    for info in tests_info:
        for subject in info.subjects:
            sid = subject.get("id") or ""
            if not sid:
                continue
            if sid in seen_subjects and seen_subjects[sid] != info.id:
                name = subject.get("name") or sid
                return f"As avaliações do grupo não podem repetir a disciplina {name}"
            seen_subjects[sid] = info.id
    return None


def resolve_evaluation_group(
    avaliacao_raw: Optional[str],
    group_id_param: Optional[str],
) -> Tuple[Optional[EvaluationGroupContext], Optional[Tuple[str, int]]]:
    """
    Returns (context, None) when grouping, (None, None) when not grouping,
    or (None, (error, status)) on validation failure.
    """
    if not is_group_request(group_id_param):
        return None, None

    from app.models.test import Test
    from sqlalchemy.orm import joinedload

    ids = parse_avaliacao_ids(avaliacao_raw)
    if len(ids) < 2:
        return None, ("group_id exige duas ou mais avaliações em avaliacao (IDs separados por vírgula)", 400)

    tests = (
        Test.query.filter(Test.id.in_(ids))
        .options(joinedload(Test.subject_rel), joinedload(Test.grade))
        .all()
    )
    found = {str(t.id): t for t in tests}
    missing = [tid for tid in ids if tid not in found]
    if missing:
        return None, (f"Avaliações não encontradas: {', '.join(missing)}", 400)

    ordered_tests = [found[tid] for tid in ids]
    tests_info = build_tests_info(ordered_tests)
    error = validate_group_tests(tests_info)
    if error:
        return None, (error, 400)

    grade_id = next(info.grade_id for info in tests_info if info.grade_id)
    grade_nome = next((info.grade_nome for info in tests_info if info.grade_id == grade_id and info.grade_nome), "")
    disciplinas: List[str] = []
    for info in tests_info:
        for subject in info.subjects:
            name = subject.get("name") or ""
            if name and name not in disciplinas:
                disciplinas.append(name)

    payload = {
        "agrupado": True,
        "grade_id": grade_id,
        "grade_nome": grade_nome,
        "test_ids": [info.id for info in tests_info],
        "disciplinas": disciplinas,
    }
    return (
        EvaluationGroupContext(
            tests=ordered_tests,
            test_ids=[info.id for info in tests_info],
            tests_info=tests_info,
            grade_id=grade_id or "",
            grade_nome=grade_nome,
            disciplinas=disciplinas,
            payload=payload,
        ),
        None,
    )


def _first_subject(info: GroupTestInfo) -> Dict[str, str]:
    if info.subjects:
        return info.subjects[0]
    return {"id": info.id, "name": info.title or "Disciplina"}


def _subject_results_from_evaluation(result: Any, info: GroupTestInfo) -> Dict[str, Any]:
    raw = getattr(result, "subject_results", None)
    if isinstance(raw, dict) and raw:
        normalized: Dict[str, Any] = {}
        for key, value in raw.items():
            if not isinstance(value, dict):
                continue
            sid = str(key)
            entry = dict(value)
            if not entry.get("subject_name"):
                match = next((s for s in info.subjects if s.get("id") == sid), None)
                if match:
                    entry["subject_name"] = match.get("name")
            normalized[sid] = entry
        if normalized:
            return normalized

    subject = _first_subject(info)
    return {
        str(subject["id"]): {
            "subject_name": subject.get("name") or "",
            "correct_answers": int(getattr(result, "correct_answers", 0) or 0),
            "total_questions": int(getattr(result, "total_questions", 0) or 0),
            "grade": getattr(result, "grade", 0.0) or 0.0,
            "proficiency": getattr(result, "proficiency", 0.0) or 0.0,
            "classification": getattr(result, "classification", None),
        }
    }


def build_participacao(
    tests_info: Sequence[GroupTestInfo],
    test_ids_realizados: Sequence[str],
) -> Dict[str, Any]:
    realizados = {str(tid) for tid in test_ids_realizados}
    provas = []
    for info in tests_info:
        subject_name = ""
        if info.subjects:
            subject_name = info.subjects[0].get("name") or ""
        provas.append(
            {
                "test_id": info.id,
                "titulo": info.title,
                "disciplina": subject_name,
                "realizou": info.id in realizados,
            }
        )
    total = len(tests_info)
    feitas = sum(1 for p in provas if p["realizou"])
    return {
        "provas_grupo": total,
        "provas_realizadas": feitas,
        "completo": total > 0 and feitas == total,
        "provas": provas,
    }


def _pick_snapshot(results: Sequence[Any], attr: str) -> Any:
    for result in results:
        value = getattr(result, attr, None)
        if value is not None:
            return value
    return None


def build_virtual_multidisciplinary_results(
    results: Sequence[Any],
    tests_info: Sequence[GroupTestInfo],
    course_name: str = "Anos Iniciais",
    *,
    only_complete: bool = True,
) -> List[MergedStudentResult]:
    """
    Monta um dataset como se as N provas fossem UMA multidisciplinar.

    Cada aluno vira um único resultado virtual com ``subject_results`` de todas as
    disciplinas e GERAL = média das disciplinas (mesma regra de
    ``EvaluationResultService.calculate_and_save_result`` com subjects_info).

    ``only_complete=True`` (padrão): só alunos presentes em todas as provas do
    grupo — premissa de mesmo universo / mesma quantidade de alunos.
    """
    merged = merge_student_group_results(results, tests_info, course_name)
    if only_complete:
        return [m for m in merged if m.completo]
    return merged


def subject_statistics_from_virtual_results(
    merged_results: Sequence[MergedStudentResult],
    tests_info: Sequence[GroupTestInfo],
    course_name: str = "Anos Iniciais",
) -> Dict[str, Any]:
    """
    Estatísticas por disciplina no mesmo formato de
    ``EvaluationResultService.get_subject_detailed_statistics``, a partir do
    dataset virtual multidisciplinar (um universo, um cálculo).
    """
    from app.utils.school_equal_weight_means import (
        mean_grade_and_proficiency_equal_weight_by_school_from_subject_rows,
    )

    # Disciplinas na ordem do grupo (sem repetir)
    subjects_ordered: List[Dict[str, str]] = []
    seen_ids: set = set()
    for info in tests_info:
        for subject in info.subjects:
            sid = str(subject.get("id") or "")
            if not sid or sid in seen_ids:
                continue
            seen_ids.add(sid)
            subjects_ordered.append(
                {"id": sid, "name": subject.get("name") or sid}
            )

    subject_statistics: Dict[str, Any] = {}
    for subject in subjects_ordered:
        sid = subject["id"]
        subject_name = subject["name"]
        subject_rows: List[Dict[str, Any]] = []
        for result in merged_results:
            srs = result.subject_results or {}
            data = srs.get(sid) or srs.get(str(sid))
            if not isinstance(data, dict):
                continue
            subject_rows.append(
                {
                    "student_id": result.student_id,
                    "correct_answers": data.get("correct_answers", 0),
                    "total_questions": data.get("total_questions", 0),
                    "proficiency": data.get("proficiency", 0.0),
                    "grade": data.get("grade", 0.0),
                    "classification": data.get("classification") or "Abaixo do Básico",
                    "score_percentage": data.get("score_percentage", 0.0),
                    "school_id_snapshot": result.school_id_snapshot,
                    "class_id_snapshot": result.class_id_snapshot,
                    "grade_id_snapshot": result.grade_id_snapshot,
                }
            )

        if not subject_rows:
            continue

        total_students = len(subject_rows)
        avg_grade, avg_proficiency, avg_score_percentage = (
            mean_grade_and_proficiency_equal_weight_by_school_from_subject_rows(
                subject_rows,
                student_id_key="student_id",
                course_name=course_name,
                subject_name=subject_name,
            )
        )
        avg_grade = round_to_two_decimals(avg_grade)
        avg_proficiency = round_to_two_decimals(avg_proficiency)
        avg_score_percentage = round_to_two_decimals(avg_score_percentage)

        classification_distribution = {
            "abaixo_do_basico": 0,
            "basico": 0,
            "adequado": 0,
            "avancado": 0,
        }
        for sr in subject_rows:
            classification = str(sr.get("classification") or "").lower()
            if "abaixo" in classification:
                classification_distribution["abaixo_do_basico"] += 1
            elif "básico" in classification or "basico" in classification:
                classification_distribution["basico"] += 1
            elif "adequado" in classification:
                classification_distribution["adequado"] += 1
            elif "avançado" in classification or "avancado" in classification:
                classification_distribution["avancado"] += 1

        subject_statistics[subject_name] = {
            "subject_id": sid,
            "subject_name": subject_name,
            "total_questions": subject_rows[0].get("total_questions", 0),
            "questions_with_answer": subject_rows[0].get("total_questions", 0),
            "total_students": total_students,
            "average_proficiency": avg_proficiency,
            "average_grade": avg_grade,
            "average_score_percentage": avg_score_percentage,
            "classification_distribution": classification_distribution,
            "student_results": subject_rows,
        }

    return {
        "test_id": "grupo",
        "test_title": " + ".join(
            (info.subjects[0].get("name") if info.subjects else info.title)
            for info in tests_info
        ),
        "course_name": course_name,
        "subjects_count": len(subject_statistics),
        "subjects": subject_statistics,
    }


def filter_virtual_results_by_school(
    merged_results: Sequence[MergedStudentResult],
    school_id: Any,
) -> List[MergedStudentResult]:
    sid = str(school_id) if school_id is not None else ""
    if not sid:
        return list(merged_results)
    return [
        m
        for m in merged_results
        if m.school_id_snapshot is not None and str(m.school_id_snapshot) == sid
    ]


def filter_virtual_results_by_class(
    merged_results: Sequence[MergedStudentResult],
    class_id: Any,
) -> List[MergedStudentResult]:
    cid = str(class_id) if class_id is not None else ""
    if not cid:
        return list(merged_results)
    out: List[MergedStudentResult] = []
    for m in merged_results:
        if m.class_id_snapshot is None:
            continue
        if str(m.class_id_snapshot) == cid:
            out.append(m)
    return out


def merge_student_group_results(
    results: Sequence[Any],
    tests_info: Sequence[GroupTestInfo],
    course_name: str = "Anos Iniciais",
) -> List[MergedStudentResult]:
    """
    Junta EvaluationResult de várias provas por aluno em um resultado virtual
    com o mesmo shape da multidisciplinar (subject_results + GERAL médio).
    """
    info_by_id = {info.id: info for info in tests_info}
    by_student: Dict[str, List[Any]] = {}
    for result in results:
        sid = getattr(result, "student_id", None)
        if not sid:
            continue
        by_student.setdefault(str(sid), []).append(result)

    merged: List[MergedStudentResult] = []
    for student_id, student_results in by_student.items():
        subject_results: Dict[str, Any] = {}
        test_ids_realizados: List[str] = []
        correct_answers = 0
        total_questions = 0

        for result in student_results:
            test_id = str(getattr(result, "test_id", "") or "")
            info = info_by_id.get(test_id)
            if info is None:
                continue
            if test_id not in test_ids_realizados:
                test_ids_realizados.append(test_id)
            correct_answers += int(getattr(result, "correct_answers", 0) or 0)
            total_questions += int(getattr(result, "total_questions", 0) or 0)
            subject_results.update(_subject_results_from_evaluation(result, info))

        if not test_ids_realizados:
            continue

        participacao = build_participacao(tests_info, test_ids_realizados)
        grades = [float(sr.get("grade") or 0) for sr in subject_results.values()]
        proficiencies = [float(sr.get("proficiency") or 0) for sr in subject_results.values()]
        if proficiencies:
            proficiency_geral = sum(proficiencies) / len(proficiencies)
            grade_geral = sum(grades) / len(grades) if grades else 0.0
        else:
            proficiency_geral = 0.0
            grade_geral = 0.0

        has_matematica = any(
            "matem" in str(sr.get("subject_name") or "").lower()
            for sr in subject_results.values()
        )
        classification = EvaluationCalculator.determine_classification(
            proficiency_geral,
            course_name,
            "GERAL",
            has_matematica=has_matematica,
        )

        merged.append(
            MergedStudentResult(
                student_id=student_id,
                grade=round_to_two_decimals(grade_geral),
                proficiency=round_to_two_decimals(proficiency_geral),
                classification=classification,
                correct_answers=correct_answers,
                total_questions=total_questions,
                subject_results=subject_results,
                completo=bool(participacao["completo"]),
                participacao=participacao,
                school_id_snapshot=_pick_snapshot(student_results, "school_id_snapshot"),
                class_id_snapshot=_pick_snapshot(student_results, "class_id_snapshot"),
                grade_id_snapshot=_pick_snapshot(student_results, "grade_id_snapshot"),
                enrollment_id_snapshot=_pick_snapshot(student_results, "enrollment_id_snapshot"),
                test_ids_realizados=test_ids_realizados,
            )
        )
    return merged


def escopo_test_ids(escopo_calculo: Optional[Dict[str, Any]]) -> List[str]:
    if not isinstance(escopo_calculo, dict):
        return []
    ids = escopo_calculo.get("avaliacao_ids")
    if ids:
        return [str(x).strip() for x in ids if str(x).strip()]
    return parse_avaliacao_ids(escopo_calculo.get("avaliacao_id"))
