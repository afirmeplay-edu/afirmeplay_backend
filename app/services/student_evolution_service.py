# -*- coding: utf-8 -*-
"""
Evolução por aluno no escopo de filtros (todas as avaliações/gabaritos que o aluno fez).
"""

from __future__ import annotations

import logging
import math
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

import dateutil.parser

from app.answer_sheets.models.answerSheetGabarito import AnswerSheetGabarito
from app.answer_sheets.models.answerSheetResult import AnswerSheetResult
from app.exams.models.classTest import ClassTest
from app.evaluations.models.evaluationResult import EvaluationResult
from app.models.student import Student
from app.exams.models.test import Test
from app.answer_sheets.services.answer_sheet_comparison_service import AnswerSheetComparisonService
from app.evaluations.services.evaluation_comparison_service import EvaluationComparisonService
from app.services.skills_map_service import _participating_answer_sheet_result

logger = logging.getLogger(__name__)


def _safe_parse_dt(value) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return dateutil.parser.parse(str(value))
    except Exception:
        return None


def _in_date_range(
    dt: Optional[datetime],
    data_inicio: Optional[datetime],
    data_fim: Optional[datetime],
) -> bool:
    if dt is None:
        return data_inicio is None and data_fim is None
    if data_inicio is not None and dt < data_inicio:
        return False
    if data_fim is not None:
        # inclusivo no dia final quando só data (sem hora)
        fim = data_fim
        if fim.hour == 0 and fim.minute == 0 and fim.second == 0 and fim.microsecond == 0:
            fim = fim.replace(hour=23, minute=59, second=59)
        if dt > fim:
            return False
    return True


def _dedupe_results_by_student_instrument(
    results: Sequence[Any],
    instrument_attr: str,
) -> List[Any]:
    """Uma entrada por (student_id, instrumento); preferir calculated_at/corrected_at mais recente."""
    best: Dict[Tuple[str, str], Any] = {}
    for r in results:
        sid = getattr(r, "student_id", None)
        iid = getattr(r, instrument_attr, None)
        if not sid or not iid:
            continue
        key = (str(sid), str(iid))
        prev = best.get(key)
        if prev is None:
            best[key] = r
            continue
        r_ts = getattr(r, "calculated_at", None) or getattr(r, "corrected_at", None)
        p_ts = getattr(prev, "calculated_at", None) or getattr(prev, "corrected_at", None)
        if r_ts and (p_ts is None or r_ts > p_ts):
            best[key] = r
    return list(best.values())


def _result_snapshot(result: Any) -> Dict[str, Any]:
    grade = getattr(result, "grade", None)
    proficiency = getattr(result, "proficiency", None)
    score = getattr(result, "score_percentage", None)
    return {
        "grade": round(float(grade), 2) if grade is not None else None,
        "proficiency": round(float(proficiency), 2) if proficiency is not None else None,
        "classification": getattr(result, "classification", None) or "Não definido",
        "correct_answers": getattr(result, "correct_answers", None),
        "total_questions": getattr(result, "total_questions", None),
        "score_percentage": round(float(score), 2) if score is not None else None,
    }


def _min_application_by_test(test_ids: List[str]) -> Dict[str, datetime]:
    if not test_ids:
        return {}
    out: Dict[str, datetime] = {}
    class_tests = ClassTest.query.filter(ClassTest.test_id.in_(test_ids)).all()
    for ct in class_tests:
        parsed = _safe_parse_dt(ct.application) if ct.application else None
        if parsed is None:
            continue
        tid = str(ct.test_id)
        if tid not in out or parsed < out[tid]:
            out[tid] = parsed
    return out


def _paginate(items: List[Any], page: int, per_page: int) -> Tuple[List[Any], Dict[str, Any]]:
    page = max(1, int(page or 1))
    per_page = min(100, max(1, int(per_page or 50)))
    total = len(items)
    total_pages = max(1, math.ceil(total / per_page)) if total else 0
    start = (page - 1) * per_page
    end = start + per_page
    return items[start:end], {
        "page": page,
        "per_page": per_page,
        "total_students": total,
        "total_pages": total_pages,
    }


class StudentEvolutionService:
    """Monta evolução completa por aluno (digital e cartão-resposta)."""

    @staticmethod
    def build_digital_evolution_for_students(
        students: Sequence[Student],
        *,
        data_inicio: Optional[datetime] = None,
        data_fim: Optional[datetime] = None,
        page: int = 1,
        per_page: int = 50,
    ) -> Dict[str, Any]:
        students_list = list(students or [])
        if not students_list:
            return {"students": [], "pagination": _paginate([], page, per_page)[1]}

        student_ids = [s.id for s in students_list]
        raw_results = EvaluationResult.query.filter(
            EvaluationResult.student_id.in_(student_ids)
        ).all()
        results = _dedupe_results_by_student_instrument(raw_results, "test_id")

        by_student: Dict[str, List[EvaluationResult]] = defaultdict(list)
        test_ids: set = set()
        for r in results:
            by_student[str(r.student_id)].append(r)
            test_ids.add(str(r.test_id))

        tests = Test.query.filter(Test.id.in_(list(test_ids))).all() if test_ids else []
        tests_by_id = {str(t.id): t for t in tests}
        app_dates = _min_application_by_test(list(test_ids))

        # Só alunos com pelo menos um resultado no recorte de datas
        eligible: List[Student] = []
        timeline_by_student: Dict[str, List[Tuple[Test, datetime, EvaluationResult]]] = {}

        for student in students_list:
            sid = str(student.id)
            student_results = by_student.get(sid) or []
            timeline: List[Tuple[Test, datetime, EvaluationResult]] = []
            for r in student_results:
                test = tests_by_id.get(str(r.test_id))
                if not test:
                    continue
                app_dt = app_dates.get(str(test.id)) or _safe_parse_dt(test.created_at)
                if data_inicio is not None or data_fim is not None:
                    if app_dt is None or not _in_date_range(app_dt, data_inicio, data_fim):
                        continue
                timeline.append((test, app_dt or datetime.min, r))
            if not timeline:
                continue
            timeline.sort(key=lambda x: x[1])
            timeline_by_student[sid] = timeline
            eligible.append(student)

        eligible.sort(key=lambda s: (s.name or "").lower())
        page_students, pagination = _paginate(eligible, page, per_page)

        payloads = []
        for student in page_students:
            timeline = timeline_by_student[str(student.id)]
            payloads.append(
                StudentEvolutionService._build_digital_student_payload(student, timeline)
            )

        return {"students": payloads, "pagination": pagination}

    @staticmethod
    def _build_digital_student_payload(
        student: Student,
        timeline: List[Tuple[Test, datetime, EvaluationResult]],
    ) -> Dict[str, Any]:
        ordered_tests = [t for t, _, _ in timeline]
        results_by_test = {str(r.test_id): r for _, _, r in timeline}
        grade_info_by_test = {
            str(test.id): EvaluationComparisonService._resolve_test_grade_info(test)
            for test in ordered_tests
        }

        evaluations_data = []
        for i, (test, app_dt, result) in enumerate(timeline):
            entry = EvaluationComparisonService._build_test_evaluation_entry(
                test,
                i + 1,
                app_dt if app_dt != datetime.min else None,
                grade_info_by_test.get(str(test.id)),
            )
            entry["result"] = _result_snapshot(result)
            evaluations_data.append(entry)

        comparison_cache = None
        if len(ordered_tests) >= 2:
            try:
                comparison_cache = EvaluationComparisonService._build_student_comparison_cache(
                    ordered_tests, student.id
                )
            except Exception as cache_err:
                logger.warning(
                    "Cache de evolução digital ignorado (aluno %s): %s",
                    student.id,
                    cache_err,
                    exc_info=True,
                )

        comparisons = []
        for i in range(len(ordered_tests) - 1):
            test_from = ordered_tests[i]
            test_to = ordered_tests[i + 1]
            result_from = results_by_test.get(str(test_from.id))
            result_to = results_by_test.get(str(test_to.id))
            if not result_from or not result_to:
                continue
            try:
                comparisons.append(
                    {
                        "from_evaluation": EvaluationComparisonService._build_test_evaluation_ref(
                            test_from, i + 1, grade_info_by_test.get(str(test_from.id))
                        ),
                        "to_evaluation": EvaluationComparisonService._build_test_evaluation_ref(
                            test_to, i + 2, grade_info_by_test.get(str(test_to.id))
                        ),
                        "general_comparison": EvaluationComparisonService._get_student_general_comparison(
                            result_from, result_to
                        ),
                        "subject_comparison": EvaluationComparisonService._get_student_subject_comparison(
                            student.id, test_from, test_to, cache=comparison_cache
                        )
                        or {},
                        "skills_comparison": EvaluationComparisonService._get_student_skills_comparison(
                            student.id, test_from, test_to, cache=comparison_cache
                        )
                        or {},
                    }
                )
            except Exception as pair_err:
                logger.warning(
                    "Par de evolução digital %s->%s ignorado: %s",
                    test_from.id,
                    test_to.id,
                    pair_err,
                    exc_info=True,
                )

        return {
            "id": student.id,
            "user_id": student.user_id,
            "name": student.name,
            "school_id": student.school_id,
            "class_id": str(student.class_id) if student.class_id else None,
            "grade_id": str(student.grade_id) if student.grade_id else None,
            "evaluations": evaluations_data,
            "total_evaluations": len(evaluations_data),
            "comparisons": comparisons,
            "total_comparisons": len(comparisons),
        }

    @staticmethod
    def build_answer_sheet_evolution_for_students(
        students: Sequence[Student],
        *,
        data_inicio: Optional[datetime] = None,
        data_fim: Optional[datetime] = None,
        page: int = 1,
        per_page: int = 50,
    ) -> Dict[str, Any]:
        students_list = list(students or [])
        if not students_list:
            return {"students": [], "pagination": _paginate([], page, per_page)[1]}

        student_ids = [s.id for s in students_list]
        raw_results = AnswerSheetResult.query.filter(
            AnswerSheetResult.student_id.in_(student_ids)
        ).all()
        participating = [r for r in raw_results if _participating_answer_sheet_result(r)]
        results = _dedupe_results_by_student_instrument(participating, "gabarito_id")

        by_student: Dict[str, List[AnswerSheetResult]] = defaultdict(list)
        gabarito_ids: set = set()
        for r in results:
            by_student[str(r.student_id)].append(r)
            gabarito_ids.add(str(r.gabarito_id))

        gabaritos = (
            AnswerSheetGabarito.query.filter(AnswerSheetGabarito.id.in_(list(gabarito_ids))).all()
            if gabarito_ids
            else []
        )
        gabaritos_by_id = {str(g.id): g for g in gabaritos}

        eligible: List[Student] = []
        timeline_by_student: Dict[str, List[Tuple[AnswerSheetGabarito, datetime, AnswerSheetResult]]] = {}

        for student in students_list:
            sid = str(student.id)
            student_results = by_student.get(sid) or []
            timeline: List[Tuple[AnswerSheetGabarito, datetime, AnswerSheetResult]] = []
            for r in student_results:
                gab = gabaritos_by_id.get(str(r.gabarito_id))
                if not gab:
                    continue
                app_dt = (
                    _safe_parse_dt(getattr(r, "corrected_at", None))
                    or _safe_parse_dt(gab.created_at)
                    or datetime.min
                )
                if data_inicio is not None or data_fim is not None:
                    if app_dt == datetime.min or not _in_date_range(app_dt, data_inicio, data_fim):
                        continue
                timeline.append((gab, app_dt, r))
            if not timeline:
                continue
            timeline.sort(key=lambda x: x[1])
            timeline_by_student[sid] = timeline
            eligible.append(student)

        eligible.sort(key=lambda s: (s.name or "").lower())
        page_students, pagination = _paginate(eligible, page, per_page)

        payloads = []
        for student in page_students:
            timeline = timeline_by_student[str(student.id)]
            payloads.append(
                StudentEvolutionService._build_answer_sheet_student_payload(student, timeline)
            )

        return {"students": payloads, "pagination": pagination}

    @staticmethod
    def _build_answer_sheet_student_payload(
        student: Student,
        timeline: List[Tuple[AnswerSheetGabarito, datetime, AnswerSheetResult]],
    ) -> Dict[str, Any]:
        ordered = [g for g, _, _ in timeline]
        results_by_gab = {str(r.gabarito_id): r for _, _, r in timeline}
        grade_info_by_gab = {
            str(gab.id): AnswerSheetComparisonService._resolve_gabarito_grade_info(gab)
            for gab in ordered
        }

        evaluations_data = []
        for i, (gab, app_dt, result) in enumerate(timeline):
            entry = AnswerSheetComparisonService._build_gabarito_evaluation_entry(
                gab,
                i + 1,
                app_dt if app_dt != datetime.min else None,
                grade_info_by_gab.get(str(gab.id)),
            )
            entry["result"] = _result_snapshot(result)
            evaluations_data.append(entry)

        comparisons = []
        for i in range(len(ordered) - 1):
            gab_from = ordered[i]
            gab_to = ordered[i + 1]
            result_from = results_by_gab.get(str(gab_from.id))
            result_to = results_by_gab.get(str(gab_to.id))
            if not result_from or not result_to:
                continue
            try:
                comparisons.append(
                    {
                        "from_evaluation": AnswerSheetComparisonService._build_gabarito_evaluation_ref(
                            gab_from, i + 1, grade_info_by_gab.get(str(gab_from.id))
                        ),
                        "to_evaluation": AnswerSheetComparisonService._build_gabarito_evaluation_ref(
                            gab_to, i + 2, grade_info_by_gab.get(str(gab_to.id))
                        ),
                        "general_comparison": AnswerSheetComparisonService._get_student_general_comparison(
                            result_from, result_to
                        ),
                        "subject_comparison": AnswerSheetComparisonService._get_student_subject_comparison(
                            gab_from, gab_to, result_from, result_to
                        )
                        or {},
                        "skills_comparison": AnswerSheetComparisonService._get_student_skills_comparison(
                            gab_from, gab_to, result_from, result_to
                        )
                        or {},
                    }
                )
            except Exception as pair_err:
                logger.warning(
                    "Par de evolução cartão %s->%s ignorado: %s",
                    gab_from.id,
                    gab_to.id,
                    pair_err,
                    exc_info=True,
                )

        return {
            "id": student.id,
            "user_id": student.user_id,
            "name": student.name,
            "school_id": student.school_id,
            "class_id": str(student.class_id) if student.class_id else None,
            "grade_id": str(student.grade_id) if student.grade_id else None,
            "source_type": "cartao_resposta",
            "evaluations": evaluations_data,
            "total_evaluations": len(evaluations_data),
            "comparisons": comparisons,
            "total_comparisons": len(comparisons),
        }
