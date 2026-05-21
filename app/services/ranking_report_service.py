# -*- coding: utf-8 -*-
from __future__ import annotations

import math
import json
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from sqlalchemy import Float, String, and_, case, cast, func, or_

from app import db
from app.models.answerSheetResult import AnswerSheetResult
from app.models.answerSheetGabarito import AnswerSheetGabarito
from app.models.evaluationResult import EvaluationResult
from app.models.grades import Grade
from app.models.school import School
from app.models.student import Student
from app.models.studentClass import Class
from app.models.subject import Subject
from app.models.teacher import Teacher
from app.models.teacherClass import TeacherClass
from app.models.test import Test
from app.services.dashboard_service import DashboardService
from app.services.evaluation_calculator import EvaluationCalculator


RANKING_TYPES = {"general", "specific_evaluation", "specific_answer_sheet", "teachers"}

# Limite alto para listar todos os professores com participação no instrumento selecionado.
TEACHER_RANKING_FETCH_LIMIT = 50_000


@dataclass
class RankingRequest:
    ranking_type: str
    page: int
    per_page: int
    filters: Dict[str, Any]


class RankingReportService:
    @staticmethod
    def _normalize_text(value: str) -> str:
        normalized = unicodedata.normalize("NFD", str(value or ""))
        return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn").strip().lower()

    @staticmethod
    def _format_grade_class_label(grade_name: Any, class_name: Any = None) -> str:
        grade = str(grade_name or "").strip() or "Sem série"
        turma = str(class_name or "").strip()
        if turma:
            return f"{grade} - {turma}"
        return grade

    @staticmethod
    def _class_row_sort_key(row: Dict[str, Any]) -> tuple:
        return (
            -float(row.get("average_score") or row.get("media") or 0),
            -float(row.get("average_proficiency") or 0),
            str(row.get("turma") or row.get("class_name") or ""),
        )

    @classmethod
    def _enrich_class_rows_with_school_id(cls, class_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        missing_class_ids = [
            str(row.get("class_id") or "")
            for row in class_rows
            if str(row.get("class_id") or "") and not str(row.get("school_id") or "").strip()
        ]
        if not missing_class_ids:
            return class_rows

        school_by_class = {
            str(row.id): str(row._school_id or "")
            for row in db.session.query(Class.id, Class._school_id).filter(Class.id.in_(missing_class_ids)).all()
        }
        enriched: List[Dict[str, Any]] = []
        for row in class_rows:
            item = dict(row)
            if not str(item.get("school_id") or "").strip():
                item["school_id"] = school_by_class.get(str(item.get("class_id") or ""), "")
            enriched.append(item)
        return enriched

    @classmethod
    def _build_best_class_by_school(cls, class_rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, str]]:
        grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for row in class_rows:
            school_id = str(row.get("school_id") or "").strip()
            if school_id:
                grouped[school_id].append(row)

        best_by_school: Dict[str, Dict[str, str]] = {}
        for school_id, rows in grouped.items():
            top = sorted(rows, key=cls._class_row_sort_key)[0]
            grade_name = str(top.get("serie") or top.get("grade_name") or "Sem série")
            class_name = str(top.get("turma") or top.get("class_name") or "").strip()
            best_by_school[school_id] = {
                "grade": grade_name,
                "turma": class_name,
                "label": cls._format_grade_class_label(grade_name, class_name),
            }
        return best_by_school

    @classmethod
    def _build_school_class_items_from_classes(
        cls,
        school_ids_ordered: List[str],
        class_rows: List[Dict[str, Any]],
        school_grade_teachers: Dict[tuple[str, str], str],
        filters: Dict[str, Any],
    ) -> Dict[str, List[Dict[str, Any]]]:
        subject_name = cls._resolve_subject_name_for_filters(filters)
        grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for row in class_rows:
            school_id = str(row.get("school_id") or "").strip()
            if school_id:
                grouped[school_id].append(row)

        items_by_school: Dict[str, List[Dict[str, Any]]] = {}
        for school_id in school_ids_ordered:
            school_classes = sorted(grouped.get(school_id, []), key=cls._class_row_sort_key)
            rows: List[Dict[str, Any]] = []
            for idx, raw in enumerate(school_classes):
                grade_name = str(raw.get("serie") or raw.get("grade_name") or "Sem série")
                turma = str(raw.get("turma") or raw.get("class_name") or "Turma").strip() or "Turma"
                course_label = cls._derive_course_label(grade_name)
                participating = int(raw.get("participating_students") or raw.get("alunos") or 0)
                total_students = int(raw.get("total_students") or participating)
                participation_rate = float(raw.get("participation_rate") or 0)
                if not participation_rate and total_students > 0:
                    participation_rate = round((participating / total_students) * 100, 1)
                avg_prof = float(raw.get("average_proficiency") or 0)
                avg_score = float(raw.get("average_score") or raw.get("media") or 0)
                classification = str(raw.get("classification") or "") or cls._classification_from_proficiency(
                    avg_prof,
                    course_label=course_label,
                    subject_name=subject_name,
                )
                rows.append(
                    {
                        "position": idx + 1,
                        "course_label": course_label,
                        "series_class_name": cls._format_grade_class_label(grade_name, turma),
                        "grade_name": grade_name,
                        "class_name": turma,
                        "teacher_name": school_grade_teachers.get((school_id, grade_name), "N/A"),
                        "participation_rate": participation_rate,
                        "participating_students": participating,
                        "total_students": total_students,
                        "average_proficiency": round(avg_prof, 1),
                        "average_score": round(avg_score, 1),
                        "adequado_avancado_count": int(raw.get("adequado_avancado_count") or 0),
                        "adequado_avancado_pct": round(float(raw.get("adequado_avancado_pct") or 0), 1),
                        "level_tag": classification or "N/A",
                        "is_critical": classification == "Abaixo do Básico",
                    }
                )
            items_by_school[school_id] = rows
        return items_by_school

    @classmethod
    def _derive_course_label(cls, grade_name: str) -> str:
        normalized = cls._normalize_text(grade_name)
        if "anos iniciais" in normalized or "inicial" in normalized:
            return "Anos Iniciais"
        if "anos finais" in normalized or "final" in normalized:
            return "Anos Finais"

        numeric_match = re.search(r"\d+", normalized)
        grade_number = int(numeric_match.group(0)) if numeric_match else None
        if grade_number is not None:
            if 1 <= grade_number <= 5:
                return "Anos Iniciais"
            if 6 <= grade_number <= 9:
                return "Anos Finais"

        grade_name_clean = str(grade_name or "").strip()
        return f"Curso: {grade_name_clean}" if grade_name_clean else "Curso não identificado"

    @classmethod
    def _looks_like_course_label(cls, name: str) -> bool:
        normalized = cls._normalize_text(name)
        if normalized in ("anos iniciais", "anos finais"):
            return True
        if normalized.startswith("curso:") or normalized.startswith("curso "):
            return True
        if normalized in ("geral", "curso nao identificado", "curso não identificado"):
            return True
        return False

    @classmethod
    def _subject_display_name(cls, subject_id: str, fallback: str = "") -> str:
        sid = str(subject_id or "").strip()
        if not sid or sid.lower() == "geral":
            return ""
        row = db.session.query(Subject.name).filter(Subject.id == sid).first()
        if row and row.name:
            return str(row.name).strip()
        fb = str(fallback or "").strip()
        if fb and not cls._looks_like_course_label(fb):
            return fb
        return ""

    @classmethod
    def _register_discipline_option(cls, bucket: Dict[str, str], subject_id: str, fallback_name: str = "") -> None:
        sid = str(subject_id or "").strip()
        if not sid or sid.lower() == "geral":
            return
        if cls._looks_like_course_label(sid) or sid.lower().startswith("curso"):
            return
        name = cls._subject_display_name(sid, fallback_name)
        if not name or cls._looks_like_course_label(name):
            return
        bucket[sid] = name

    @classmethod
    def _discipline_options_from_evaluation(cls, evaluation_id: str) -> Dict[str, str]:
        from app.models.question import Question
        from app.models.testQuestion import TestQuestion
        from app.utils.response_formatters import _get_all_subjects_from_test

        options: Dict[str, str] = {}
        test = db.session.query(Test).filter(Test.id == evaluation_id).first()
        if not test:
            return options

        try:
            for entry in _get_all_subjects_from_test(test):
                cls._register_discipline_option(options, str(entry.get("id") or ""), str(entry.get("name") or ""))
        except Exception:
            pass

        results = (
            db.session.query(EvaluationResult.subject_results)
            .filter(EvaluationResult.test_id == evaluation_id, EvaluationResult.subject_results.isnot(None))
            .limit(800)
            .all()
        )
        for (payload,) in results:
            if not isinstance(payload, dict):
                continue
            for subject_id, subject_data in payload.items():
                fallback = ""
                if isinstance(subject_data, dict):
                    fallback = str(
                        subject_data.get("subject_name")
                        or subject_data.get("name")
                        or subject_data.get("nome")
                        or ""
                    ).strip()
                cls._register_discipline_option(options, str(subject_id), fallback)

        question_subject_rows = (
            db.session.query(Question.subject_id)
            .join(TestQuestion, TestQuestion.question_id == Question.id)
            .filter(TestQuestion.test_id == evaluation_id, Question.subject_id.isnot(None))
            .distinct()
            .all()
        )
        for (subject_id,) in question_subject_rows:
            cls._register_discipline_option(options, str(subject_id))

        return options

    @classmethod
    def _discipline_options_from_answer_sheet(cls, answer_sheet_id: str) -> Dict[str, str]:
        from app.services.cartao_resposta.proficiency_by_subject import (
            _extract_blocks_with_questions,
            _resolve_subject_name,
        )

        options: Dict[str, str] = {}
        gabarito = db.session.query(AnswerSheetGabarito).filter(AnswerSheetGabarito.id == answer_sheet_id).first()
        if not gabarito:
            return options

        blocks_config = getattr(gabarito, "blocks_config", None)
        if isinstance(blocks_config, str):
            try:
                blocks_config = json.loads(blocks_config)
            except Exception:
                blocks_config = None

        for block in _extract_blocks_with_questions(blocks_config if isinstance(blocks_config, dict) else None):
            subject_id = block.get("subject_id")
            if not subject_id:
                subject_id = f"block_{block.get('block_id', 0)}"
            subject_id = str(subject_id)
            subject_name = _resolve_subject_name(subject_id, block.get("subject_name"))
            cls._register_discipline_option(options, subject_id, subject_name)

        result_rows = (
            db.session.query(AnswerSheetResult.proficiency_by_subject)
            .filter(
                AnswerSheetResult.gabarito_id == answer_sheet_id,
                AnswerSheetResult.proficiency_by_subject.isnot(None),
            )
            .limit(800)
            .all()
        )
        for (payload,) in result_rows:
            if not isinstance(payload, dict):
                continue
            for subject_id, subject_data in payload.items():
                fallback = ""
                if isinstance(subject_data, dict):
                    fallback = str(
                        subject_data.get("subject_name")
                        or subject_data.get("name")
                        or subject_data.get("nome")
                        or ""
                    ).strip()
                cls._register_discipline_option(options, str(subject_id), fallback)

        test_id = str(getattr(gabarito, "test_id", "") or "").strip()
        if test_id:
            for sid, name in cls._discipline_options_from_evaluation(test_id).items():
                if sid not in options:
                    options[sid] = name

        return options

    @classmethod
    def _resolve_discipline_options(cls, filters: Dict[str, Any]) -> List[Dict[str, str]]:
        evaluation_id = str(filters.get("evaluation_id") or "").strip()
        answer_sheet_id = str(filters.get("answer_sheet_id") or "").strip()

        if answer_sheet_id:
            options = cls._discipline_options_from_answer_sheet(answer_sheet_id)
        elif evaluation_id:
            options = cls._discipline_options_from_evaluation(evaluation_id)
        else:
            options = {}

        return [
            {"id": sid, "name": name}
            for sid, name in sorted(options.items(), key=lambda item: cls._normalize_text(item[1]))
            if name and not cls._looks_like_course_label(name)
        ]

    @classmethod
    def _resolve_subject_name_for_filters(cls, filters: Dict[str, Any]) -> str:
        discipline_id = str(filters.get("disciplina") or "").strip()
        if not discipline_id:
            return "GERAL"
        for option in cls._resolve_discipline_options(filters):
            if str(option.get("id") or "") == discipline_id:
                return str(option.get("name") or "GERAL")
        return "GERAL"

    @classmethod
    def _extract_discipline_keys_from_payload(cls, payload: Any) -> Dict[str, str]:
        key_names: Dict[str, str] = {}
        if not isinstance(payload, dict):
            return key_names
        for subject_id, subject_data in payload.items():
            sid = str(subject_id or "").strip()
            if not sid or sid.lower() == "geral":
                continue
            name = ""
            if isinstance(subject_data, dict):
                name = str(
                    subject_data.get("subject_name")
                    or subject_data.get("name")
                    or subject_data.get("nome")
                    or ""
                ).strip()
            key_names[sid] = name or key_names.get(sid, "")
        return key_names

    @classmethod
    def _collect_discipline_keys_from_results(cls, filters: Dict[str, Any]) -> Dict[str, str]:
        evaluation_id = str(filters.get("evaluation_id") or "").strip()
        answer_sheet_id = str(filters.get("answer_sheet_id") or "").strip()
        key_names: Dict[str, str] = {}

        if answer_sheet_id:
            rows = (
                db.session.query(AnswerSheetResult.proficiency_by_subject)
                .filter(
                    AnswerSheetResult.gabarito_id == answer_sheet_id,
                    AnswerSheetResult.proficiency_by_subject.isnot(None),
                )
                .limit(500)
                .all()
            )
            for (payload,) in rows:
                for sid, name in cls._extract_discipline_keys_from_payload(payload).items():
                    if sid not in key_names or not key_names[sid]:
                        key_names[sid] = name
        elif evaluation_id:
            rows = (
                db.session.query(EvaluationResult.subject_results)
                .filter(
                    EvaluationResult.test_id == evaluation_id,
                    EvaluationResult.subject_results.isnot(None),
                )
                .limit(500)
                .all()
            )
            for (payload,) in rows:
                for sid, name in cls._extract_discipline_keys_from_payload(payload).items():
                    if sid not in key_names or not key_names[sid]:
                        key_names[sid] = name

        return key_names

    @classmethod
    def _match_discipline_storage_key(
        cls,
        discipline_id: str,
        key_names: Dict[str, str],
        *,
        subject_label: str = "",
    ) -> str:
        discipline_id = str(discipline_id or "").strip()
        if not discipline_id:
            return ""
        if discipline_id in key_names:
            return discipline_id

        target_name = cls._normalize_text(subject_label)
        if target_name:
            for key, name in key_names.items():
                if name and cls._normalize_text(name) == target_name:
                    return key

        lowered = discipline_id.lower()
        for key in key_names:
            if str(key).lower() == lowered:
                return str(key)

        return discipline_id

    @classmethod
    def _resolve_discipline_storage_key(cls, discipline_id: str, filters: Dict[str, Any]) -> str:
        discipline_id = str(discipline_id or "").strip()
        if not discipline_id:
            return ""
        key_names = cls._collect_discipline_keys_from_results(filters)
        subject_label = cls._resolve_subject_name_for_filters({**filters, "disciplina": discipline_id})
        return cls._match_discipline_storage_key(
            discipline_id,
            key_names,
            subject_label=subject_label,
        )

    @classmethod
    def _classification_from_proficiency(
        cls,
        proficiency: float,
        *,
        course_label: str = "Anos Iniciais",
        subject_name: str = "GERAL",
    ) -> str:
        return EvaluationCalculator.determine_classification(
            float(proficiency or 0),
            str(course_label or "Anos Iniciais"),
            str(subject_name or "GERAL"),
        )

    @classmethod
    def _resolve_teacher_course_label(cls, grade_names: List[str], filters: Dict[str, Any]) -> str:
        serie_id = str(filters.get("serie") or "").strip()
        if serie_id:
            grade_row = Grade.query.filter(Grade.id == serie_id).first()
            if grade_row and grade_row.name:
                return cls._derive_course_label(str(grade_row.name))

        course_labels = [
            cls._derive_course_label(str(name))
            for name in (grade_names or [])
            if str(name or "").strip()
        ]
        if not course_labels:
            return "Anos Iniciais"

        counts: Dict[str, int] = defaultdict(int)
        for label in course_labels:
            counts[label] += 1
        return max(counts.items(), key=lambda item: (item[1], item[0]))[0]

    @classmethod
    def _classification_for_teacher(
        cls,
        *,
        average_proficiency: float,
        grade_names: List[str],
        filters: Dict[str, Any],
    ) -> str:
        return cls._classification_from_proficiency(
            float(average_proficiency or 0),
            course_label=cls._resolve_teacher_course_label(grade_names, filters),
            subject_name=cls._resolve_subject_name_for_filters(filters),
        )

    @classmethod
    def _build_general_course_sections(
        cls,
        school_rows: List[Dict[str, Any]],
        *,
        subject_name: str = "GERAL",
    ) -> List[Dict[str, Any]]:
        buckets: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

        for school in school_rows:
            series = school.get("series") or []
            grouped_series: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
            for item in series:
                grade_name = str(item.get("grade_name") or "Sem série")
                course_label = cls._derive_course_label(grade_name)
                grouped_series[course_label].append(item)

            for course_label, course_series in grouped_series.items():
                students_with_results = sum(int(item.get("students_count") or 0) for item in course_series)
                participating_students = sum(
                    int(item.get("participating_students") or item.get("students_count") or 0) for item in course_series
                )
                total_students = sum(
                    int(item.get("total_students") or item.get("students_count") or 0) for item in course_series
                )
                if total_students < participating_students:
                    total_students = participating_students
                weighted_score = sum(
                    float(item.get("average_score") or 0) * int(item.get("students_count") or 0) for item in course_series
                )
                weighted_prof = sum(
                    float(item.get("average_proficiency") or 0) * int(item.get("students_count") or 0) for item in course_series
                )

                average_score = round((weighted_score / students_with_results), 1) if students_with_results > 0 else 0.0
                average_proficiency = round((weighted_prof / students_with_results), 1) if students_with_results > 0 else 0.0
                classification = cls._classification_from_proficiency(
                    average_proficiency,
                    course_label=course_label,
                    subject_name=subject_name,
                )

                participation_rate = round((participating_students / total_students) * 100, 1) if total_students > 0 else 0.0

                buckets[course_label].append(
                    {
                        "school_id": school.get("school_id"),
                        "school_name": school.get("school_name"),
                        "average_score": average_score,
                        "average_proficiency": average_proficiency,
                        "classification": classification,
                        "participation_rate": participation_rate,
                        "participating_students": participating_students,
                        "total_students": total_students,
                        "students_count": students_with_results,
                        "series": course_series,
                    }
                )

        def _course_sort_priority(label: str) -> int:
            if label == "Anos Iniciais":
                return 0
            if label == "Anos Finais":
                return 1
            return 2

        sections: List[Dict[str, Any]] = []
        for course_label in sorted(buckets.keys(), key=lambda label: (_course_sort_priority(label), label)):
            rows = buckets[course_label]
            rows.sort(
                key=lambda row: (
                    -float(row.get("average_score") or 0),
                    -float(row.get("average_proficiency") or 0),
                    str(row.get("school_name") or ""),
                )
            )
            for idx, row in enumerate(rows):
                row["position"] = idx + 1

            avg_score = round(
                sum(float(row.get("average_score") or 0) for row in rows) / len(rows),
                1,
            ) if rows else 0.0
            critical_count = sum(1 for row in rows if row.get("classification") == "Abaixo do Básico")

            sections.append(
                {
                    "course_label": course_label,
                    "totals": {
                        "count": len(rows),
                        "average_score": avg_score,
                        "critical_schools_count": critical_count,
                    },
                    "items": rows,
                }
            )

        return sections

    @staticmethod
    def _pagination_block(total: int, per_page: int = 0, page: int = 1) -> Dict[str, int]:
        safe_per_page = per_page if per_page > 0 else max(total, 1)
        return {
            "page": page,
            "per_page": safe_per_page,
            "total": total,
            "total_pages": math.ceil(total / safe_per_page) if total else 0,
        }

    @classmethod
    def _build_series_by_school_and_course(cls, school_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        school_sections: List[Dict[str, Any]] = []
        for school in school_rows:
            series = school.get("series") or []
            grouped_series: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
            for item in series:
                grade_name = str(item.get("grade_name") or "Sem série")
                course_label = cls._derive_course_label(grade_name)
                grouped_series[course_label].append(item)

            course_sections: List[Dict[str, Any]] = []
            for course_label in sorted(grouped_series.keys()):
                course_series_rows: List[Dict[str, Any]] = []
                for raw in grouped_series[course_label]:
                    total_students = int(raw.get("total_students") or raw.get("students_count") or 0)
                    participating_students = int(raw.get("participating_students") or raw.get("students_count") or 0)
                    if total_students < participating_students:
                        total_students = participating_students
                    participation_rate = round((participating_students / total_students) * 100, 1) if total_students > 0 else 0.0
                    course_series_rows.append(
                        {
                            "grade_id": raw.get("grade_id"),
                            "grade_name": raw.get("grade_name"),
                            "average_score": float(raw.get("average_score") or 0),
                            "average_proficiency": float(raw.get("average_proficiency") or 0),
                            "classification": str(raw.get("classification") or ""),
                            "students_count": int(raw.get("students_count") or 0),
                            "participating_students": participating_students,
                            "total_students": total_students,
                            "participation_rate": participation_rate,
                        }
                    )

                course_series_rows.sort(
                    key=lambda row: (
                        -float(row.get("average_score") or 0),
                        -float(row.get("average_proficiency") or 0),
                        str(row.get("grade_name") or ""),
                    )
                )
                for idx, row in enumerate(course_series_rows):
                    row["position"] = idx + 1

                avg_score = (
                    round(
                        sum(float(row.get("average_score") or 0) for row in course_series_rows) / len(course_series_rows),
                        1,
                    )
                    if course_series_rows
                    else 0.0
                )
                critical_count = sum(1 for row in course_series_rows if row.get("classification") == "Abaixo do Básico")
                course_sections.append(
                    {
                        "course_label": course_label,
                        "totals": {
                            "count": len(course_series_rows),
                            "average_score": avg_score,
                            "critical_series_count": critical_count,
                        },
                        "items": course_series_rows,
                    }
                )

            school_sections.append(
                {
                    "school_id": school.get("school_id"),
                    "school_name": school.get("school_name"),
                    "school_position": int(school.get("position") or 0),
                    "totals": {
                        "course_count": len(course_sections),
                        "series_count": sum(len(section.get("items") or []) for section in course_sections),
                    },
                    "course_sections": course_sections,
                }
            )

        return school_sections

    @classmethod
    def _build_classes_by_series(
        cls,
        class_rows: List[Dict[str, Any]],
        selected_grade_name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        selected_grade_name_norm = cls._normalize_text(selected_grade_name or "")
        for row in class_rows:
            grade_name = str(row.get("serie") or "Sem série")
            if selected_grade_name_norm and cls._normalize_text(grade_name) != selected_grade_name_norm:
                continue
            participating = int(row.get("participating_students") or row.get("alunos") or 0)
            total_students = int(row.get("total_students") or participating)
            grouped[grade_name].append(
                {
                    "class_id": row.get("class_id"),
                    "class_name": row.get("turma"),
                    "grade_name": grade_name,
                    "average_score": float(row.get("media") or 0),
                    "average_proficiency": float(row.get("average_proficiency") or 0),
                    "accuracy_percent": float(row.get("acerto_percent") or 0),
                    "completion_rate": float(row.get("conclusao") or 0),
                    "students_count": participating,
                    "participating_students": participating,
                    "total_students": total_students,
                    "participation_rate": float(row.get("participation_rate") or 0),
                    "classification": row.get("classification"),
                    "evaluations_count": int(row.get("avaliacoes") or 0),
                }
            )

        sections: List[Dict[str, Any]] = []
        for grade_name in sorted(grouped.keys()):
            rows = grouped[grade_name]
            rows.sort(
                key=lambda row: (
                    -float(row.get("average_score") or 0),
                    -float(row.get("accuracy_percent") or 0),
                    str(row.get("class_name") or ""),
                )
            )
            for idx, row in enumerate(rows):
                row["position"] = idx + 1
            sections.append(
                {
                    "grade_name": grade_name,
                    "totals": {"count": len(rows)},
                    "items": rows,
                }
            )

        return sections

    @classmethod
    def _build_students_by_course(cls, student_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for row in student_rows:
            course_label = cls._derive_course_label(str(row.get("serie") or "Sem série"))
            grouped[course_label].append(
                {
                    "student_id": row.get("student_id"),
                    "name": row.get("name"),
                    "school_name": row.get("school_name"),
                    "class_name": row.get("class_name"),
                    "serie": row.get("serie"),
                    "average_score": float(row.get("average_score") or 0),
                    "average_proficiency": float(row.get("average_proficiency") or 0),
                    "classification": row.get("classification"),
                    "completed_evaluations": int(row.get("completed_evaluations") or 0),
                }
            )

        sections: List[Dict[str, Any]] = []
        for course_label in sorted(grouped.keys(), key=lambda value: (0 if value == "Anos Iniciais" else 1 if value == "Anos Finais" else 2, value)):
            rows = grouped[course_label]
            rows.sort(
                key=lambda row: (
                    -float(row.get("average_proficiency") or 0),
                    -float(row.get("average_score") or 0),
                    str(row.get("name") or ""),
                )
            )
            for idx, row in enumerate(rows):
                row["position"] = idx + 1
            sections.append(
                {
                    "course_label": course_label,
                    "totals": {"count": len(rows)},
                    "items": rows,
                }
            )
        return sections

    @classmethod
    def _build_teachers_by_course(cls, teacher_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for row in teacher_rows:
            grade_names = row.get("grade_names") or []
            # Um professor pode atuar em mais de um curso; incluir em todos os cursos detectados.
            course_candidates = sorted(
                {
                    cls._derive_course_label(str(name))
                    for name in grade_names
                    if str(name or "").strip()
                },
                key=lambda value: (0 if value == "Anos Iniciais" else 1 if value == "Anos Finais" else 2, value),
            )
            if not course_candidates:
                course_candidates = ["Curso não identificado"]

            teacher_payload = {
                "teacher_id": row.get("teacher_id"),
                "teacher_name": row.get("teacher_name"),
                "teacher_email": row.get("teacher_email"),
                "average_score": float(row.get("average_score") or 0),
                "average_proficiency": float(row.get("average_proficiency") or 0),
                "classification": row.get("classification"),
                "total_evaluations": int(row.get("total_evaluations") or 0),
                "classes_count": int(row.get("classes_count") or 0),
                "grade_names": grade_names,
            }

            for course_label in course_candidates:
                grouped[course_label].append(dict(teacher_payload))

        sections: List[Dict[str, Any]] = []
        for course_label in sorted(grouped.keys(), key=lambda value: (0 if value == "Anos Iniciais" else 1 if value == "Anos Finais" else 2, value)):
            rows = grouped[course_label]
            rows.sort(
                key=lambda row: (
                    -float(row.get("average_proficiency") or 0),
                    -float(row.get("average_score") or 0),
                    str(row.get("teacher_name") or ""),
                )
            )
            for idx, row in enumerate(rows):
                row["position"] = idx + 1
            sections.append(
                {
                    "course_label": course_label,
                    "totals": {"count": len(rows)},
                    "items": rows,
                }
            )
        return sections

    @staticmethod
    def _is_adequado_or_avancado_classification(classification: Any) -> bool:
        text = str(classification or "").strip().lower()
        if not text or "abaixo" in text:
            return False
        if "adequado" in text:
            return True
        return "avancado" in text or "avançado" in text

    @classmethod
    def _subject_classification_expr(cls, model: Any, discipline_id: str):
        if not discipline_id:
            return model.classification
        if model is EvaluationResult:
            return cast(model.subject_results[discipline_id]["classification"].astext, String)
        if model is AnswerSheetResult:
            return cast(model.proficiency_by_subject[discipline_id]["classification"].astext, String)
        return model.classification

    @classmethod
    def _adequado_avancado_student_condition(cls, model: Any, discipline_id: str):
        class_expr = func.lower(cls._subject_classification_expr(model, discipline_id))
        return and_(
            or_(
                class_expr.like("%adequado%"),
                class_expr.like("%avancado%"),
                class_expr.like("%avançado%"),
            ),
            ~class_expr.like("%abaixo%"),
        )

    @classmethod
    def _infer_school_status(cls, classification: str) -> str:
        normalized = cls._normalize_text(classification)
        if "abaixo" in normalized:
            return "atencao"
        if normalized in ("avancado", "adequado"):
            return "destaque"
        if normalized == "basico":
            return "desenvolvimento"
        return "desenvolvimento"

    @classmethod
    def _build_model_sections(
        cls,
        *,
        school_rows: List[Dict[str, Any]],
        schools_by_course_sections: List[Dict[str, Any]],
        series_by_school_sections: List[Dict[str, Any]],
        classes_by_series_sections: List[Dict[str, Any]],
        class_rows: List[Dict[str, Any]],
        teacher_rows: List[Dict[str, Any]],
        filters: Dict[str, Any],
        teacher_student_metrics: Optional[Dict[str, Dict[str, int]]] = None,
    ) -> Dict[str, Any]:
        school_ids = [str(row.get("school_id") or "") for row in school_rows if str(row.get("school_id") or "").strip()]
        school_grade_teachers = cls._build_school_grade_teacher_map(school_ids, filters)
        teacher_schools = cls._build_teacher_school_map(school_ids, filters)
        teacher_series_class_labels = cls._build_teacher_series_class_labels_map(school_ids, filters)
        overview_course_stats: Dict[str, Dict[str, Any]] = {}
        for section in schools_by_course_sections:
            course_label = str(section.get("course_label") or "Curso não identificado")
            items = section.get("items") or []
            status_counts = {"destaque": 0, "desenvolvimento": 0, "atencao": 0}
            chart_rows = []
            table_rows = []
            for idx, school in enumerate(items):
                avg_score = float(school.get("average_score") or 0)
                level_tag = str(school.get("classification") or "")
                status = cls._infer_school_status(level_tag)
                is_critical = level_tag == "Abaixo do Básico"
                status_counts[status] += 1
                participating_students = int(school.get("participating_students") or 0)
                total_students = int(school.get("total_students") or 0)
                participation_rate = round(float(school.get("participation_rate") or 0), 1)
                series = school.get("series") or []
                adequado_avancado_count = sum(
                    int(series_item.get("adequado_avancado_count") or 0)
                    for series_item in series
                    if isinstance(series_item, dict)
                )
                adequado_avancado_pct = (
                    round((adequado_avancado_count / participating_students) * 100, 1)
                    if participating_students > 0
                    else 0.0
                )
                row_payload = {
                    "position": idx + 1,
                    "school_id": school.get("school_id"),
                    "school_name": school.get("school_name"),
                    "average_score": round(avg_score, 2),
                    "average_proficiency": round(float(school.get("average_proficiency") or 0), 1),
                    "participation_rate": participation_rate,
                    "participating_students": participating_students,
                    "total_students": total_students,
                    "adequado_avancado_count": adequado_avancado_count,
                    "adequado_avancado_pct": adequado_avancado_pct,
                    "status": status,
                    "level_tag": level_tag,
                    "is_critical": is_critical,
                }
                chart_rows.append(row_payload)
                table_rows.append(dict(row_payload))

            overview_course_stats[course_label] = {
                "counts_by_status": status_counts,
                "chart_rows": chart_rows,
                "table_rows": table_rows,
            }

        total_students = sum(int(row.get("total_students") or 0) for row in school_rows)
        total_participants = sum(int(row.get("participating_students") or 0) for row in school_rows)
        participation_rate = round((total_participants / total_students) * 100, 1) if total_students > 0 else 0.0
        schools_sorted = sorted(
            school_rows,
            key=lambda row: (
                -float(row.get("average_score") or 0),
                -float(row.get("average_proficiency") or 0),
                str(row.get("school_name") or ""),
            ),
        )

        best_class_by_school = cls._build_best_class_by_school(class_rows)
        municipal_items: List[Dict[str, Any]] = []
        for idx, school in enumerate(schools_sorted):
            classification = str(school.get("classification") or "")
            participating_students = int(school.get("participating_students") or 0)
            adequado_avancado_count = int(school.get("adequado_avancado_count") or 0)
            level_pct = (
                round((adequado_avancado_count / participating_students) * 100, 1)
                if participating_students > 0
                else 0.0
            )

            school_id = str(school.get("school_id") or "")
            best_class_info = best_class_by_school.get(school_id) or {}
            best_class_name = best_class_info.get("label") or "N/A"

            municipal_items.append(
                {
                    "position": idx + 1,
                    "school_id": school.get("school_id"),
                    "school_name": school.get("school_name"),
                    "participation_rate": round(float(school.get("participation_rate") or 0), 1),
                    "participating_students": int(school.get("participating_students") or 0),
                    "total_students": int(school.get("total_students") or 0),
                    "average_proficiency": round(float(school.get("average_proficiency") or 0), 1),
                    "average_score": round(float(school.get("average_score") or 0), 1),
                    "adequado_avancado_count": adequado_avancado_count,
                    "adequado_avancado_pct": level_pct,
                    "best_class_name": best_class_name,
                    "best_class_grade": best_class_info.get("grade"),
                    "best_class_turma": best_class_info.get("turma"),
                    "level_tag": classification or "N/A",
                    "is_critical": classification == "Abaixo do Básico",
                }
            )

        school_options = [
            {"id": str(s.get("school_id") or ""), "name": str(s.get("school_name") or "Escola")}
            for s in schools_sorted
            if str(s.get("school_id") or "").strip()
        ]
        school_ids_ordered = [
            str(s.get("school_id") or "")
            for s in schools_sorted
            if str(s.get("school_id") or "").strip()
        ]
        school_class_items = cls._build_school_class_items_from_classes(
            school_ids_ordered,
            class_rows,
            school_grade_teachers,
            filters,
        )

        teacher_sorted = sorted(
            teacher_rows,
            key=lambda row: (
                -float(row.get("average_proficiency") or 0),
                -float(row.get("average_score") or 0),
                str(row.get("teacher_name") or ""),
            ),
        )
        teachers_top = []
        metrics_by_teacher = teacher_student_metrics or {}
        for idx, row in enumerate(teacher_sorted):
            teacher_id = str(row.get("teacher_id") or "")
            grade_names = [str(name) for name in (row.get("grade_names") or []) if name]
            classification = cls._classification_for_teacher(
                average_proficiency=float(row.get("average_proficiency") or 0),
                grade_names=grade_names,
                filters=filters,
            )
            student_metrics = metrics_by_teacher.get(teacher_id, {})
            participating_students = int(student_metrics.get("participating_students") or 0)
            adequado_avancado_count = int(student_metrics.get("adequado_avancado_count") or 0)
            adequado_avancado_pct = (
                round((adequado_avancado_count / participating_students) * 100, 1)
                if participating_students > 0
                else 0.0
            )
            series_labels = teacher_series_class_labels.get(teacher_id) or [
                cls._format_grade_class_label(name) for name in grade_names
            ]
            teachers_top.append(
                {
                    "position": idx + 1,
                    "teacher_id": row.get("teacher_id"),
                    "teacher_name": row.get("teacher_name"),
                    "teacher_email": row.get("teacher_email"),
                    "school_name": teacher_schools.get(teacher_id, "N/A"),
                    "series_class_name": cls._format_teacher_series_class_display(series_labels),
                    "participating_students": participating_students,
                    "adequado_avancado_count": adequado_avancado_count,
                    "adequado_avancado_pct": adequado_avancado_pct,
                    "average_proficiency": round(float(row.get("average_proficiency") or 0), 1),
                    "average_score": round(float(row.get("average_score") or 0), 1),
                    "classification": classification or "N/A",
                    "level_tag": classification or "N/A",
                    "is_critical": classification == "Abaixo do Básico",
                }
            )

        return {
            "overview": {
                "by_course": overview_course_stats,
                "summary": {
                    "total_schools": len(school_rows),
                    "total_students": total_students,
                    "participating_students": total_participants,
                    "participation_rate": participation_rate,
                    "top_school": municipal_items[0] if municipal_items else None,
                },
            },
            "municipal_ranking": {
                "items": municipal_items,
                "totals": {"count": len(municipal_items)},
            },
            "school_class_ranking": {
                "school_options": school_options,
                "items_by_school": school_class_items,
                "classes_by_series": classes_by_series_sections,
            },
            "teachers_top": {
                "items": teachers_top,
                "totals": {"count": len(teachers_top)},
            },
        }

    @classmethod
    def _build_school_grade_teacher_map(
        cls,
        school_ids: List[str],
        filters: Dict[str, Any],
    ) -> Dict[tuple[str, str], str]:
        if not school_ids:
            return {}

        query = (
            db.session.query(
                Class._school_id.label("school_id"),
                Grade.name.label("grade_name"),
                Teacher.name.label("teacher_name"),
            )
            .select_from(TeacherClass)
            .join(Class, Class.id == TeacherClass.class_id)
            .join(Teacher, Teacher.id == TeacherClass.teacher_id)
            .outerjoin(Grade, Grade.id == Class.grade_id)
            .filter(Class._school_id.in_(school_ids))
        )

        selected_school = str(filters.get("escola") or "").strip()
        selected_grade = str(filters.get("serie") or "").strip()
        if selected_school:
            query = query.filter(Class._school_id == selected_school)
        if selected_grade:
            query = query.filter(Class.grade_id == selected_grade)

        bucket: Dict[tuple[str, str], List[str]] = defaultdict(list)
        for row in query.all():
            sid = str(getattr(row, "school_id", "") or "")
            grade_name = str(getattr(row, "grade_name", "") or "").strip()
            teacher_name = str(getattr(row, "teacher_name", "") or "").strip()
            if not sid or not grade_name or not teacher_name:
                continue
            key = (sid, grade_name)
            if teacher_name not in bucket[key]:
                bucket[key].append(teacher_name)

        result: Dict[tuple[str, str], str] = {}
        for key, names in bucket.items():
            if not names:
                continue
            if len(names) <= 2:
                result[key] = ", ".join(names)
            else:
                result[key] = f"{names[0]}, {names[1]} (+{len(names) - 2})"
        return result

    @classmethod
    def _build_teacher_school_map(
        cls,
        school_ids: List[str],
        filters: Dict[str, Any],
    ) -> Dict[str, str]:
        if not school_ids:
            return {}

        query = (
            db.session.query(
                TeacherClass.teacher_id.label("teacher_id"),
                School.name.label("school_name"),
                Class.grade_id.label("grade_id"),
                Class.id.label("class_id"),
            )
            .select_from(TeacherClass)
            .join(Class, Class.id == TeacherClass.class_id)
            .join(School, School.id == Class._school_id)
            .join(Student, Student.class_id == Class.id)
            .filter(Class._school_id.in_(school_ids))
        )

        selected_school = str(filters.get("escola") or "").strip()
        selected_grade = str(filters.get("serie") or "").strip()
        selected_class = str(filters.get("turma") or "").strip()
        if selected_school:
            query = query.filter(Class._school_id == selected_school)
        if selected_grade:
            query = query.filter(Class.grade_id == selected_grade)
        if selected_class:
            query = query.filter(Class.id == selected_class)

        evaluation_id = str(filters.get("evaluation_id") or "").strip()
        answer_sheet_id = str(filters.get("answer_sheet_id") or "").strip()
        if answer_sheet_id:
            query = query.join(
                AnswerSheetResult,
                and_(
                    AnswerSheetResult.student_id == Student.id,
                    AnswerSheetResult.gabarito_id == answer_sheet_id,
                ),
            )
        elif evaluation_id:
            query = query.join(
                EvaluationResult,
                and_(
                    EvaluationResult.student_id == Student.id,
                    EvaluationResult.test_id == evaluation_id,
                    or_(
                        EvaluationResult.class_id_snapshot == Class.id,
                        and_(
                            EvaluationResult.class_id_snapshot.is_(None),
                            Student.class_id == Class.id,
                        ),
                    ),
                ),
            )

        schools_by_teacher: Dict[str, List[str]] = defaultdict(list)
        for row in query.all():
            teacher_id = str(getattr(row, "teacher_id", "") or "")
            school_name = str(getattr(row, "school_name", "") or "").strip()
            if not teacher_id or not school_name:
                continue
            if school_name not in schools_by_teacher[teacher_id]:
                schools_by_teacher[teacher_id].append(school_name)

        result: Dict[str, str] = {}
        for teacher_id, school_names in schools_by_teacher.items():
            if not school_names:
                continue
            if len(school_names) <= 2:
                result[teacher_id] = ", ".join(school_names)
            else:
                result[teacher_id] = f"{school_names[0]}, {school_names[1]} (+{len(school_names) - 2})"
        return result

    @classmethod
    def _format_teacher_series_class_display(cls, labels: List[str]) -> str:
        cleaned = [str(label or "").strip() for label in labels if str(label or "").strip()]
        if not cleaned:
            return "N/A"
        if len(cleaned) <= 3:
            return ", ".join(cleaned)
        return f"{cleaned[0]}, {cleaned[1]}, {cleaned[2]} (+{len(cleaned) - 3})"

    @classmethod
    def _build_teacher_series_class_labels_map(
        cls,
        school_ids: List[str],
        filters: Dict[str, Any],
    ) -> Dict[str, List[str]]:
        if not school_ids:
            return {}

        discipline_id = str(filters.get("disciplina") or "").strip()
        storage_key = cls._resolve_discipline_storage_key(discipline_id, filters) if discipline_id else ""
        evaluation_id = str(filters.get("evaluation_id") or "").strip()
        answer_sheet_id = str(filters.get("answer_sheet_id") or "").strip()

        query = (
            db.session.query(
                TeacherClass.teacher_id.label("teacher_id"),
                func.coalesce(Grade.name, "").label("grade_name"),
                Class.name.label("class_name"),
            )
            .select_from(TeacherClass)
            .join(Class, Class.id == TeacherClass.class_id)
            .join(Student, Student.class_id == Class.id)
            .outerjoin(Grade, Grade.id == Class.grade_id)
            .filter(Class._school_id.in_(school_ids))
        )

        selected_school = str(filters.get("escola") or "").strip()
        selected_grade = str(filters.get("serie") or "").strip()
        selected_class = str(filters.get("turma") or "").strip()
        if selected_school:
            query = query.filter(Class._school_id == selected_school)
        if selected_grade:
            query = query.filter(Class.grade_id == selected_grade)
        if selected_class:
            query = query.filter(Class.id == selected_class)

        if answer_sheet_id:
            join_conditions = [
                AnswerSheetResult.student_id == Student.id,
                AnswerSheetResult.gabarito_id == answer_sheet_id,
            ]
            if storage_key:
                join_conditions.append(
                    cast(
                        AnswerSheetResult.proficiency_by_subject[storage_key]["proficiency"].astext,
                        Float,
                    ).isnot(None)
                )
            query = query.join(AnswerSheetResult, and_(*join_conditions))
        elif evaluation_id:
            join_conditions = [
                EvaluationResult.student_id == Student.id,
                EvaluationResult.test_id == evaluation_id,
                or_(
                    EvaluationResult.class_id_snapshot == Class.id,
                    and_(
                        EvaluationResult.class_id_snapshot.is_(None),
                        Student.class_id == Class.id,
                    ),
                ),
            ]
            if storage_key:
                join_conditions.append(
                    cast(
                        EvaluationResult.subject_results[storage_key]["proficiency"].astext,
                        Float,
                    ).isnot(None)
                )
            query = query.join(EvaluationResult, and_(*join_conditions))

        labels_by_teacher: Dict[str, List[str]] = defaultdict(list)
        seen_labels: Dict[str, set[str]] = defaultdict(set)
        for row in query.distinct().all():
            teacher_id = str(getattr(row, "teacher_id", "") or "")
            if not teacher_id:
                continue
            label = cls._format_grade_class_label(
                getattr(row, "grade_name", ""),
                getattr(row, "class_name", ""),
            )
            if label in seen_labels[teacher_id]:
                continue
            seen_labels[teacher_id].add(label)
            labels_by_teacher[teacher_id].append(label)

        for teacher_id in labels_by_teacher:
            labels_by_teacher[teacher_id].sort(
                key=lambda value: cls._normalize_text(value)
            )
        return dict(labels_by_teacher)

    @classmethod
    def _resolve_school_ids_for_scope(cls, scope: Dict[str, Any], filters: Dict[str, Any]) -> List[str]:
        school_ids = [str(value).strip() for value in (scope.get("school_ids") or []) if str(value).strip()]
        if school_ids:
            return school_ids
        city_id = scope.get("city_id") or filters.get("municipio")
        if city_id:
            return [
                str(row[0])
                for row in School.query.with_entities(School.id).filter(School.city_id == str(city_id)).all()
                if row[0]
            ]
        return []

    @classmethod
    def _build_teacher_student_metrics_map(
        cls,
        scope: Dict[str, Any],
        filters: Dict[str, Any],
    ) -> Dict[str, Dict[str, int]]:
        """Contagem de alunos participantes e em Adequado/Avançado por professor no instrumento."""
        evaluation_id = str(filters.get("evaluation_id") or "").strip()
        answer_sheet_id = str(filters.get("answer_sheet_id") or "").strip()
        if not evaluation_id and not answer_sheet_id:
            return {}

        from sqlalchemy.dialects.postgresql import VARCHAR

        from app.utils.uuid_helpers import uuid_list_to_str

        discipline_id = str(filters.get("disciplina") or "").strip()
        storage_key = cls._resolve_discipline_storage_key(discipline_id, filters) if discipline_id else ""
        use_answer_sheet = bool(answer_sheet_id and not evaluation_id)
        results_model = AnswerSheetResult if use_answer_sheet else EvaluationResult

        discipline_prof_expr = None
        if storage_key:
            if use_answer_sheet:
                discipline_prof_expr = cast(
                    AnswerSheetResult.proficiency_by_subject[storage_key]["proficiency"].astext,
                    Float,
                )
            else:
                discipline_prof_expr = cast(
                    EvaluationResult.subject_results[storage_key]["proficiency"].astext,
                    Float,
                )

        result_join_conditions = [results_model.student_id == Student.id]
        if use_answer_sheet:
            result_join_conditions.append(results_model.gabarito_id == answer_sheet_id)
            result_join_conditions.append(Student.class_id == Class.id)
        else:
            if evaluation_id:
                result_join_conditions.append(results_model.test_id == evaluation_id)
            result_join_conditions.append(
                or_(
                    EvaluationResult.class_id_snapshot == Class.id,
                    and_(
                        EvaluationResult.class_id_snapshot.is_(None),
                        Student.class_id == Class.id,
                    ),
                )
            )
        if discipline_prof_expr is not None:
            result_join_conditions.append(discipline_prof_expr.isnot(None))

        adequado_condition = cls._adequado_avancado_student_condition(results_model, storage_key)
        has_result = results_model.id.isnot(None)
        participating_student_id = case((has_result, Student.id), else_=None)
        adequado_student_id = case((and_(has_result, adequado_condition), Student.id), else_=None)

        query = (
            db.session.query(
                TeacherClass.teacher_id.label("teacher_id"),
                func.count(func.distinct(participating_student_id)).label("participating_students"),
                func.count(func.distinct(adequado_student_id)).label("adequado_avancado_count"),
            )
            .select_from(TeacherClass)
            .join(Class, Class.id == TeacherClass.class_id)
            .join(Student, Student.class_id == Class.id)
            .outerjoin(School, School.id == Class._school_id)
            .outerjoin(results_model, and_(*result_join_conditions))
        )

        selected_school_id = str(filters.get("escola") or "").strip()
        selected_grade_id = str(filters.get("serie") or "").strip()
        selected_class_id = str(filters.get("turma") or "").strip()
        if selected_school_id:
            query = query.filter(Class._school_id == selected_school_id)
        if selected_grade_id:
            query = query.filter(Class.grade_id == selected_grade_id)
        if selected_class_id:
            query = query.filter(Student.class_id == selected_class_id)
        if filters.get("municipio"):
            query = query.filter(School.city_id == str(filters["municipio"]))

        school_ids = scope.get("school_ids") or []
        city_id = scope.get("city_id")
        if school_ids:
            school_ids_str = uuid_list_to_str(school_ids) if school_ids else []
            query = query.filter(cast(Class._school_id, VARCHAR).in_(school_ids_str)) if school_ids_str else query.filter(False)
        elif city_id:
            municipal_school_ids = [
                str(row[0])
                for row in School.query.with_entities(School.id).filter(School.city_id == str(city_id)).all()
                if row[0]
            ]
            if not municipal_school_ids:
                return {}
            query = query.filter(cast(Class._school_id, VARCHAR).in_(municipal_school_ids))

        rows = (
            query.group_by(TeacherClass.teacher_id)
            .having(func.count(func.distinct(participating_student_id)) > 0)
            .all()
        )
        return {
            str(row.teacher_id): {
                "participating_students": int(row.participating_students or 0),
                "adequado_avancado_count": int(row.adequado_avancado_count or 0),
            }
            for row in rows
            if row.teacher_id
        }

    @classmethod
    def build_request(
        cls,
        ranking_type: str,
        *,
        page: int = 1,
        per_page: int = 20,
        filters: Optional[Dict[str, Any]] = None,
    ) -> RankingRequest:
        rt = (ranking_type or "").strip().lower()
        if rt not in RANKING_TYPES:
            raise ValueError("ranking_type inválido. Use: general, specific_evaluation, specific_answer_sheet, teachers.")
        if page < 1:
            raise ValueError("page deve ser maior ou igual a 1.")
        if per_page < 1:
            raise ValueError("per_page deve ser maior ou igual a 1.")
        return RankingRequest(ranking_type=rt, page=page, per_page=min(per_page, 100), filters=filters or {})

    @classmethod
    def get_report(cls, user: Dict[str, Any], req: RankingRequest) -> Dict[str, Any]:
        scope = cls._resolve_scope(user, req.filters)

        if req.ranking_type == "general":
            return cls._general_ranking(scope, req)
        if req.ranking_type == "specific_evaluation":
            return cls._evaluation_ranking(scope, req)
        if req.ranking_type == "specific_answer_sheet":
            return cls._answer_sheet_ranking(scope, req)
        return cls._teacher_ranking(scope, req)

    @classmethod
    def _resolve_scope(cls, user: Dict[str, Any], filters: Dict[str, Any]) -> Dict[str, Any]:
        scope = DashboardService._resolve_scope(user) or {}
        requested_scope = (filters.get("scope") or "").strip().lower()
        turma_id = filters.get("turma")
        escola_id = filters.get("escola")
        municipio_id = filters.get("municipio")

        explicit_scope = None
        if requested_scope == "turma" and turma_id:
            explicit_scope = DashboardService._resolve_explicit_ranking_scope(user, "turma", turma_id)
        elif requested_scope == "escola" and escola_id:
            explicit_scope = DashboardService._resolve_explicit_ranking_scope(user, "escola", escola_id)
        elif requested_scope == "municipio" and municipio_id:
            explicit_scope = DashboardService._resolve_explicit_ranking_scope(user, "municipio", municipio_id)

        if explicit_scope:
            scope = explicit_scope

        if escola_id:
            scope["school_ids"] = [str(escola_id)]
        if turma_id:
            scope["class_ids"] = [str(turma_id)]
        if municipio_id:
            scope["city_id"] = str(municipio_id)
        return scope

    @staticmethod
    def _pagination(page: int, per_page: int, total: int) -> Dict[str, int]:
        total_pages = math.ceil(total / per_page) if total else 0
        return {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
        }

    @classmethod
    def _build_response(
        cls,
        req: RankingRequest,
        scope: Dict[str, Any],
        *,
        total: int,
        items: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        return {
            "ranking_type": req.ranking_type,
            "scope": {
                "scope": scope.get("scope"),
                "city_id": scope.get("city_id"),
                "school_ids": scope.get("school_ids") or [],
                "class_ids": scope.get("class_ids") or [],
            },
            "filters": req.filters,
            "items": items,
            "totals": {"count": total},
            "pagination": cls._pagination(req.page, req.per_page, total),
        }

    @classmethod
    def _general_ranking(cls, scope: Dict[str, Any], req: RankingRequest) -> Dict[str, Any]:
        selected_grade_id = str(req.filters.get("serie") or "").strip()
        selected_grade_name: Optional[str] = None
        if selected_grade_id:
            grade = db.session.query(Grade.name).filter(Grade.id == selected_grade_id).first()
            selected_grade_name = str(getattr(grade, "name", "") or "").strip() if grade else None

        subject_name = cls._resolve_subject_name_for_filters(req.filters)
        school_rows = cls._build_school_general_rows(scope, req.filters)
        school_card_data = DashboardService.get_school_ranking_card(scope, limit=1000, offset=0) or {}
        school_card_rows = school_card_data.get("ranking") or []
        school_card_map = {str(row.get("escola_id") or ""): row for row in school_card_rows}

        for row in school_rows:
            school_card = school_card_map.get(str(row.get("school_id") or ""))
            if not school_card:
                continue
            # A participação do ranking geral deve seguir a regra:
            # % de alunos da escola que participaram de alguma avaliação ou cartão-resposta.
            # Portanto, manter o valor calculado em `_build_school_general_rows` e
            # não sobrescrever por `taxa_conclusao` (métrica diferente do card).
            row["participation_rate"] = float(row.get("participation_rate") or 0)
            row["total_evaluations"] = int(school_card.get("quantidade_avaliacoes") or row.get("total_evaluations") or 0)
            row["total_students"] = int(school_card.get("quantidade_alunos") or row.get("total_students") or row.get("students_count") or 0)
            row["total_classes"] = int(school_card.get("total_turmas") or 0)

        school_rows.sort(
            key=lambda row: (
                -float(row.get("average_score") or 0),
                -float(row.get("average_proficiency") or 0),
                str(row.get("school_name") or ""),
            )
        )
        for idx, row in enumerate(school_rows):
            row["position"] = idx + 1

        school_total = len(school_rows)
        offset = (req.page - 1) * req.per_page
        paged_schools = school_rows[offset : offset + req.per_page]

        students_data = DashboardService.get_ranking_alunos(
            scope,
            limit=500,
            offset=0,
            filters=req.filters,
        ) or {}
        student_rows = students_data.get("ranking") or []
        students_items = [
            {
                "position": row.get("position"),
                "student_id": row.get("student_id"),
                "name": row.get("name"),
                "school_name": row.get("school_name"),
                "class_name": row.get("class_name"),
                "serie": row.get("serie"),
                "average_score": row.get("media_nota", row.get("media")),
                "average_proficiency": row.get("media_proficiencia", row.get("media")),
                "classification": row.get("classification"),
                "completed_evaluations": row.get("completed_evaluations"),
                "medalha": row.get("medalha"),
            }
            for row in student_rows
        ]
        students_total = int(students_data.get("total") or 0)

        evaluation_id = str(req.filters.get("evaluation_id") or "").strip()
        answer_sheet_id = str(req.filters.get("answer_sheet_id") or "").strip()
        if evaluation_id or answer_sheet_id:
            class_rows = cls._build_evaluation_class_rows(scope, req.filters)
        else:
            class_rows_data = DashboardService.get_class_ranking_card(scope, limit=1000, offset=0) or {}
            class_rows = class_rows_data.get("ranking") or []

        schools_selected = bool(str(req.filters.get("escola") or "").strip())
        series_selected = bool(selected_grade_id)
        class_selected = bool(str(req.filters.get("turma") or "").strip())
        visibility = {
            "schools_by_course": not schools_selected and not series_selected and not class_selected,
            "series_by_school_and_course": (not class_selected) and (not series_selected),
            "classes_by_series": (not class_selected) and (schools_selected or series_selected),
            "students_by_course": True,
        }

        schools_by_course_sections = (
            cls._build_general_course_sections(school_rows, subject_name=subject_name)
            if visibility["schools_by_course"]
            else []
        )
        series_by_school_sections = cls._build_series_by_school_and_course(school_rows) if visibility["series_by_school_and_course"] else []
        classes_by_series_sections = (
            cls._build_classes_by_series(class_rows, selected_grade_name=selected_grade_name)
            if visibility["classes_by_series"]
            else []
        )
        for section in classes_by_series_sections:
            grade_name = str(section.get("grade_name") or "Sem série")
            for item in section.get("items") or []:
                item["class_name"] = cls._format_grade_class_label(grade_name, item.get("class_name"))
        students_by_course_sections = cls._build_students_by_course(students_items)

        response = cls._build_response(req, scope, total=school_total, items=paged_schools)
        response["students_items"] = students_items
        response["students_totals"] = {"count": students_total}
        response["students_pagination"] = cls._pagination(req.page, req.per_page, students_total)
        response["series_labels"] = cls._extract_series_labels(paged_schools)
        response["network_series_averages"] = cls._build_network_series_averages(
            paged_schools,
            subject_name=subject_name,
        )
        response["course_sections"] = schools_by_course_sections
        response["general_rankings"] = {
            "visibility": visibility,
            "schools_by_course": {
                "sections": schools_by_course_sections,
                "totals": {"count": len(schools_by_course_sections)},
                "pagination": cls._pagination_block(len(schools_by_course_sections)),
            },
            "series_by_school_and_course": {
                "schools": series_by_school_sections,
                "totals": {
                    "schools_count": len(series_by_school_sections),
                    "series_count": sum(
                        len(course.get("items") or [])
                        for school in series_by_school_sections
                        for course in school.get("course_sections") or []
                    ),
                },
                "pagination": cls._pagination_block(len(series_by_school_sections)),
            },
            "classes_by_series": {
                "sections": classes_by_series_sections,
                "totals": {
                    "series_count": len(classes_by_series_sections),
                    "classes_count": sum(len(section.get("items") or []) for section in classes_by_series_sections),
                },
                "pagination": cls._pagination_block(
                    sum(len(section.get("items") or []) for section in classes_by_series_sections)
                ),
            },
            "students_by_course": {
                "sections": students_by_course_sections,
                "totals": {
                    "courses_count": len(students_by_course_sections),
                    "students_count": sum(len(section.get("items") or []) for section in students_by_course_sections),
                },
                "pagination": cls._pagination_block(
                    sum(len(section.get("items") or []) for section in students_by_course_sections)
                ),
            },
        }
        class_rows = cls._enrich_class_rows_with_school_id(class_rows)
        teacher_rows = DashboardService._build_teacher_ranking(
            scope, limit=TEACHER_RANKING_FETCH_LIMIT, filters=req.filters
        ) or []
        teacher_student_metrics = cls._build_teacher_student_metrics_map(scope, req.filters)
        report_sections = cls._build_model_sections(
            school_rows=school_rows,
            schools_by_course_sections=schools_by_course_sections,
            series_by_school_sections=series_by_school_sections,
            classes_by_series_sections=classes_by_series_sections,
            class_rows=class_rows,
            teacher_rows=teacher_rows,
            filters=req.filters,
            teacher_student_metrics=teacher_student_metrics,
        )
        response.update(report_sections)
        response["discipline_options"] = cls._resolve_discipline_options(req.filters)
        response["selected_discipline"] = str(req.filters.get("disciplina") or "").strip() or None
        response["grade_options"] = cls._resolve_grade_options(school_rows, req.filters)
        if str(req.filters.get("serie") or "").strip():
            response["classes_ranking"] = cls._build_class_ranking_payload(class_rows, req.filters)
        else:
            response["classes_ranking"] = {"items": [], "totals": {"count": 0}}
        return response

    @classmethod
    def _build_school_general_rows(cls, scope: Dict[str, Any], filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        evaluation_id = str(filters.get("evaluation_id") or "").strip()
        answer_sheet_id = str(filters.get("answer_sheet_id") or "").strip()
        discipline_id = str(filters.get("disciplina") or "").strip()
        storage_key = cls._resolve_discipline_storage_key(discipline_id, filters) if discipline_id else ""
        subject_name = cls._resolve_subject_name_for_filters(filters)

        def _apply_common_student_filters(query):
            if filters.get("escola"):
                query = query.filter(Student.school_id == str(filters["escola"]))
            if filters.get("turma"):
                query = query.filter(Student.class_id == filters["turma"])
            if filters.get("serie"):
                serie_id = str(filters["serie"])
                query = query.filter(
                    or_(
                        Student.grade_id == serie_id,
                        Class.grade_id == serie_id,
                    )
                )
            if filters.get("municipio"):
                query = query.filter(School.city_id == str(filters["municipio"]))

            school_ids = scope.get("school_ids") or []
            class_ids = scope.get("class_ids") or []
            city_id = scope.get("city_id")
            if school_ids:
                query = query.filter(Student.school_id.in_([str(x) for x in school_ids]))
            if class_ids:
                query = query.filter(Student.class_id.in_(class_ids))
            if city_id:
                query = query.filter(School.city_id == str(city_id))
            return query

        def _apply_entity_filter(query, model):
            if model is EvaluationResult and evaluation_id:
                return query.filter(model.test_id == evaluation_id)
            if model is AnswerSheetResult and answer_sheet_id:
                return query.filter(model.gabarito_id == answer_sheet_id)
            return query

        def _subject_metric_expr(model, metric: str):
            if not storage_key:
                return None
            if model is EvaluationResult:
                return cast(model.subject_results[storage_key][metric].astext, Float)
            if model is AnswerSheetResult:
                return cast(model.proficiency_by_subject[storage_key][metric].astext, Float)
            return None

        grade_ref = db.func.coalesce(Student.grade_id, Class.grade_id)
        results_model = AnswerSheetResult if answer_sheet_id else EvaluationResult
        subject_score_expr = _subject_metric_expr(results_model, "grade")
        subject_prof_expr = _subject_metric_expr(results_model, "proficiency")
        use_discipline_metrics = bool(storage_key)
        score_expr = subject_score_expr if use_discipline_metrics else results_model.grade
        prof_expr = subject_prof_expr if use_discipline_metrics else results_model.proficiency

        query = (
            db.session.query(
                School.id.label("school_id"),
                School.name.label("school_name"),
                grade_ref.label("grade_id"),
                Grade.name.label("grade_name"),
                db.func.avg(score_expr).label("average_score"),
                db.func.avg(prof_expr).label("average_proficiency"),
                db.func.count(db.func.distinct(Student.id)).label("students_count"),
            )
            .select_from(results_model)
            .join(Student, Student.id == results_model.student_id)
            .outerjoin(School, School.id == Student.school_id)
            .outerjoin(Class, Class.id == Student.class_id)
            .outerjoin(Grade, Grade.id == grade_ref)
        )
        query = _apply_entity_filter(query, results_model)
        if use_discipline_metrics and subject_prof_expr is not None:
            query = query.filter(subject_prof_expr.isnot(None))
        query = _apply_common_student_filters(query)

        grouped = query.group_by(School.id, School.name, grade_ref, Grade.name).all()
        if not grouped:
            return []

        totals_query = (
            db.session.query(
                School.id.label("school_id"),
                db.func.count(db.func.distinct(Student.id)).label("total_students"),
            )
            .select_from(Student)
            .outerjoin(School, School.id == Student.school_id)
            .outerjoin(Class, Class.id == Student.class_id)
        )
        totals_query = _apply_common_student_filters(totals_query)
        totals_by_school = {
            str(row.school_id): int(row.total_students or 0)
            for row in totals_query.group_by(School.id).all()
        }

        totals_by_school_grade_query = (
            db.session.query(
                School.id.label("school_id"),
                grade_ref.label("grade_id"),
                db.func.count(db.func.distinct(Student.id)).label("total_students"),
            )
            .select_from(Student)
            .outerjoin(School, School.id == Student.school_id)
            .outerjoin(Class, Class.id == Student.class_id)
        )
        totals_by_school_grade_query = _apply_common_student_filters(totals_by_school_grade_query)
        totals_by_school_grade = {
            (str(row.school_id or ""), str(row.grade_id or "")): int(row.total_students or 0)
            for row in totals_by_school_grade_query.group_by(School.id, grade_ref).all()
        }

        if answer_sheet_id:
            participating_query = (
                db.session.query(
                    School.id.label("school_id"),
                    db.func.count(db.func.distinct(Student.id)).label("participating_students"),
                )
                .select_from(Student)
                .outerjoin(School, School.id == Student.school_id)
                .outerjoin(Class, Class.id == Student.class_id)
                .join(
                    AnswerSheetResult,
                    and_(
                        AnswerSheetResult.student_id == Student.id,
                        AnswerSheetResult.gabarito_id == answer_sheet_id,
                    ),
                )
            )
            if use_discipline_metrics:
                subject_prof = _subject_metric_expr(AnswerSheetResult, "proficiency")
                if subject_prof is not None:
                    participating_query = participating_query.filter(subject_prof.isnot(None))
        elif evaluation_id:
            participating_query = (
                db.session.query(
                    School.id.label("school_id"),
                    db.func.count(db.func.distinct(Student.id)).label("participating_students"),
                )
                .select_from(Student)
                .outerjoin(School, School.id == Student.school_id)
                .outerjoin(Class, Class.id == Student.class_id)
                .join(
                    EvaluationResult,
                    and_(
                        EvaluationResult.student_id == Student.id,
                        EvaluationResult.test_id == evaluation_id,
                    ),
                )
            )
            if use_discipline_metrics:
                subject_prof = _subject_metric_expr(EvaluationResult, "proficiency")
                if subject_prof is not None:
                    participating_query = participating_query.filter(subject_prof.isnot(None))
        else:
            participating_query = (
                db.session.query(
                    School.id.label("school_id"),
                    db.func.count(db.func.distinct(Student.id)).label("participating_students"),
                )
                .select_from(Student)
                .outerjoin(School, School.id == Student.school_id)
                .outerjoin(Class, Class.id == Student.class_id)
                .outerjoin(EvaluationResult, EvaluationResult.student_id == Student.id)
                .outerjoin(AnswerSheetResult, AnswerSheetResult.student_id == Student.id)
                .filter(
                    or_(
                        EvaluationResult.id.isnot(None),
                        AnswerSheetResult.id.isnot(None),
                    )
                )
            )
        participating_query = _apply_common_student_filters(participating_query)
        participating_by_school = {
            str(row.school_id): int(row.participating_students or 0)
            for row in participating_query.group_by(School.id).all()
        }

        if answer_sheet_id:
            participating_by_school_grade_query = (
                db.session.query(
                    School.id.label("school_id"),
                    grade_ref.label("grade_id"),
                    db.func.count(db.func.distinct(Student.id)).label("participating_students"),
                )
                .select_from(Student)
                .outerjoin(School, School.id == Student.school_id)
                .outerjoin(Class, Class.id == Student.class_id)
                .join(
                    AnswerSheetResult,
                    and_(
                        AnswerSheetResult.student_id == Student.id,
                        AnswerSheetResult.gabarito_id == answer_sheet_id,
                    ),
                )
            )
            if use_discipline_metrics:
                subject_prof = _subject_metric_expr(AnswerSheetResult, "proficiency")
                if subject_prof is not None:
                    participating_by_school_grade_query = participating_by_school_grade_query.filter(subject_prof.isnot(None))
        elif evaluation_id:
            participating_by_school_grade_query = (
                db.session.query(
                    School.id.label("school_id"),
                    grade_ref.label("grade_id"),
                    db.func.count(db.func.distinct(Student.id)).label("participating_students"),
                )
                .select_from(Student)
                .outerjoin(School, School.id == Student.school_id)
                .outerjoin(Class, Class.id == Student.class_id)
                .join(
                    EvaluationResult,
                    and_(
                        EvaluationResult.student_id == Student.id,
                        EvaluationResult.test_id == evaluation_id,
                    ),
                )
            )
            if use_discipline_metrics:
                subject_prof = _subject_metric_expr(EvaluationResult, "proficiency")
                if subject_prof is not None:
                    participating_by_school_grade_query = participating_by_school_grade_query.filter(subject_prof.isnot(None))
        else:
            participating_by_school_grade_query = (
                db.session.query(
                    School.id.label("school_id"),
                    grade_ref.label("grade_id"),
                    db.func.count(db.func.distinct(Student.id)).label("participating_students"),
                )
                .select_from(Student)
                .outerjoin(School, School.id == Student.school_id)
                .outerjoin(Class, Class.id == Student.class_id)
                .outerjoin(EvaluationResult, EvaluationResult.student_id == Student.id)
                .outerjoin(AnswerSheetResult, AnswerSheetResult.student_id == Student.id)
                .filter(
                    or_(
                        EvaluationResult.id.isnot(None),
                        AnswerSheetResult.id.isnot(None),
                    )
                )
            )
        participating_by_school_grade_query = _apply_common_student_filters(participating_by_school_grade_query)
        participating_by_school_grade = {
            (str(row.school_id or ""), str(row.grade_id or "")): int(row.participating_students or 0)
            for row in participating_by_school_grade_query.group_by(School.id, grade_ref).all()
        }

        adequado_condition = cls._adequado_avancado_student_condition(results_model, storage_key)
        adequado_student_id = case((adequado_condition, Student.id), else_=None)

        def _build_adequado_count_query(group_fields):
            query = (
                db.session.query(
                    *group_fields,
                    func.count(func.distinct(adequado_student_id)).label("adequado_avancado_count"),
                )
                .select_from(results_model)
                .join(Student, Student.id == results_model.student_id)
                .outerjoin(School, School.id == Student.school_id)
                .outerjoin(Class, Class.id == Student.class_id)
            )
            query = _apply_entity_filter(query, results_model)
            if use_discipline_metrics and subject_prof_expr is not None:
                query = query.filter(subject_prof_expr.isnot(None))
            return _apply_common_student_filters(query)

        adequado_avancado_by_school = {
            str(row.school_id): int(row.adequado_avancado_count or 0)
            for row in _build_adequado_count_query([School.id.label("school_id")]).group_by(School.id).all()
        }
        adequado_avancado_by_school_grade = {
            (str(row.school_id or ""), str(row.grade_id or "")): int(row.adequado_avancado_count or 0)
            for row in _build_adequado_count_query(
                [School.id.label("school_id"), grade_ref.label("grade_id")]
            ).group_by(School.id, grade_ref).all()
        }

        by_school: Dict[str, Dict[str, Any]] = {}
        for row in grouped:
            school_id = str(row.school_id or "")
            if not school_id:
                continue
            current = by_school.get(school_id)
            if not current:
                current = {
                    "school_id": school_id,
                    "school_name": row.school_name or "Escola sem nome",
                    "average_score": 0.0,
                    "average_proficiency": 0.0,
                    "classification": "Abaixo do Básico",
                    "students_count": 0,
                    "participation_rate": 0.0,
                    "total_evaluations": 0,
                    "total_students": 0,
                    "total_classes": 0,
                    "series": [],
                }
                by_school[school_id] = current

            avg_score = float(row.average_score or 0)
            avg_prof = float(row.average_proficiency or 0)
            students_count = int(row.students_count or 0)
            grade_id = str(row.grade_id or "")
            series_total_students = int(totals_by_school_grade.get((school_id, grade_id), students_count) or 0)
            series_participating_students = int(
                participating_by_school_grade.get((school_id, grade_id), students_count) or 0
            )
            if series_total_students < series_participating_students:
                series_total_students = series_participating_students

            series_adequado_count = int(
                adequado_avancado_by_school_grade.get((school_id, grade_id), 0)
            )
            series_adequado_pct = (
                round((series_adequado_count / series_participating_students) * 100, 1)
                if series_participating_students > 0
                else 0.0
            )
            grade_name = str(row.grade_name or "Sem série")
            course_label = cls._derive_course_label(grade_name)
            current["series"].append(
                {
                    "grade_id": str(row.grade_id) if row.grade_id else None,
                    "grade_name": grade_name,
                    "average_score": round(avg_score, 1),
                    "average_proficiency": round(avg_prof, 1),
                    "classification": cls._classification_from_proficiency(
                        avg_prof,
                        course_label=course_label,
                        subject_name=subject_name,
                    ),
                    "students_count": students_count,
                    "total_students": series_total_students,
                    "participating_students": series_participating_students,
                    "adequado_avancado_count": series_adequado_count,
                    "adequado_avancado_pct": series_adequado_pct,
                }
            )

        for school in by_school.values():
            series = school["series"]
            students_with_results = sum(int(item.get("students_count") or 0) for item in series)
            total_students = int(totals_by_school.get(str(school["school_id"]), students_with_results) or 0)
            participating_students = int(participating_by_school.get(str(school["school_id"]), students_with_results) or 0)
            school["students_count"] = students_with_results
            school["total_students"] = total_students
            school["participating_students"] = participating_students
            school["participation_rate"] = round((participating_students / total_students) * 100, 1) if total_students > 0 else 0.0

            if students_with_results > 0:
                weighted_score = sum(float(item["average_score"]) * int(item["students_count"]) for item in series)
                weighted_prof = sum(float(item["average_proficiency"]) * int(item["students_count"]) for item in series)
                school["average_score"] = round(weighted_score / students_with_results, 1)
                school["average_proficiency"] = round(weighted_prof / students_with_results, 1)
            else:
                school["average_score"] = round(
                    sum(float(item["average_score"]) for item in series) / len(series),
                    1,
                )
                school["average_proficiency"] = round(
                    sum(float(item["average_proficiency"]) for item in series) / len(series),
                    1,
                )
            dominant_course = "Anos Iniciais"
            if series:
                dominant_series = max(series, key=lambda item: int(item.get("students_count") or 0))
                dominant_course = cls._derive_course_label(str(dominant_series.get("grade_name") or ""))
            school["classification"] = cls._classification_from_proficiency(
                float(school["average_proficiency"] or 0),
                course_label=dominant_course,
                subject_name=subject_name,
            )
            school["series"].sort(key=lambda item: str(item.get("grade_name") or ""))

            school_id = str(school["school_id"])
            adequado_avancado_count = int(adequado_avancado_by_school.get(school_id, 0))
            school["adequado_avancado_count"] = adequado_avancado_count
            school["adequado_avancado_pct"] = (
                round((adequado_avancado_count / participating_students) * 100, 1)
                if participating_students > 0
                else 0.0
            )

        return list(by_school.values())

    @classmethod
    def _resolve_grade_options(
        cls,
        school_rows: List[Dict[str, Any]],
        filters: Dict[str, Any],
    ) -> List[Dict[str, str]]:
        school_id = str(filters.get("escola") or "").strip()
        if not school_id:
            return []
        school = next((row for row in school_rows if str(row.get("school_id") or "") == school_id), None)
        if not school:
            return []
        options: Dict[str, str] = {}
        for item in school.get("series") or []:
            grade_id = str(item.get("grade_id") or "").strip()
            grade_name = str(item.get("grade_name") or "Sem série").strip()
            if grade_id:
                options[grade_id] = grade_name
        return [{"id": grade_id, "name": name} for grade_id, name in sorted(options.items(), key=lambda item: item[1].lower())]

    @classmethod
    def _build_evaluation_class_rows(cls, scope: Dict[str, Any], filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        evaluation_id = str(filters.get("evaluation_id") or "").strip()
        answer_sheet_id = str(filters.get("answer_sheet_id") or "").strip()
        if not evaluation_id and not answer_sheet_id:
            return []

        discipline_id = str(filters.get("disciplina") or "").strip()
        storage_key = cls._resolve_discipline_storage_key(discipline_id, filters) if discipline_id else ""
        subject_name = cls._resolve_subject_name_for_filters(filters)

        def _apply_common_student_filters(query):
            if filters.get("escola"):
                query = query.filter(Student.school_id == str(filters["escola"]))
            if filters.get("turma"):
                query = query.filter(Student.class_id == filters["turma"])
            if filters.get("serie"):
                serie_id = str(filters["serie"])
                query = query.filter(
                    or_(
                        Student.grade_id == serie_id,
                        Class.grade_id == serie_id,
                    )
                )
            if filters.get("municipio"):
                query = query.filter(School.city_id == str(filters["municipio"]))
            school_ids = scope.get("school_ids") or []
            class_ids = scope.get("class_ids") or []
            city_id = scope.get("city_id")
            if school_ids:
                query = query.filter(Student.school_id.in_([str(x) for x in school_ids]))
            if class_ids:
                query = query.filter(Student.class_id.in_(class_ids))
            if city_id:
                query = query.filter(School.city_id == str(city_id))
            return query

        def _apply_entity_filter(query, model):
            if model is EvaluationResult and evaluation_id:
                return query.filter(model.test_id == evaluation_id)
            if model is AnswerSheetResult and answer_sheet_id:
                return query.filter(model.gabarito_id == answer_sheet_id)
            return query

        def _subject_metric_expr(model, metric: str):
            if not storage_key:
                return None
            if model is EvaluationResult:
                return cast(model.subject_results[storage_key][metric].astext, Float)
            if model is AnswerSheetResult:
                return cast(model.proficiency_by_subject[storage_key][metric].astext, Float)
            return None

        results_model = AnswerSheetResult if answer_sheet_id else EvaluationResult
        subject_score_expr = _subject_metric_expr(results_model, "grade")
        subject_prof_expr = _subject_metric_expr(results_model, "proficiency")
        use_discipline_metrics = bool(storage_key)
        score_expr = subject_score_expr if use_discipline_metrics else results_model.grade
        prof_expr = subject_prof_expr if use_discipline_metrics else results_model.proficiency

        grouped_query = (
            db.session.query(
                Class.id.label("class_id"),
                Class.name.label("turma"),
                Class._school_id.label("school_id"),
                Grade.id.label("grade_id"),
                Grade.name.label("serie"),
                db.func.avg(score_expr).label("media"),
                db.func.avg(prof_expr).label("average_proficiency"),
                db.func.count(db.func.distinct(Student.id)).label("alunos"),
            )
            .select_from(results_model)
            .join(Student, Student.id == results_model.student_id)
            .join(Class, Class.id == Student.class_id)
            .outerjoin(Grade, Grade.id == db.func.coalesce(Student.grade_id, Class.grade_id))
            .outerjoin(School, School.id == Student.school_id)
        )
        grouped_query = _apply_entity_filter(grouped_query, results_model)
        if use_discipline_metrics and subject_prof_expr is not None:
            grouped_query = grouped_query.filter(subject_prof_expr.isnot(None))
        grouped_query = _apply_common_student_filters(grouped_query)
        grouped = grouped_query.group_by(
            Class.id,
            Class.name,
            Class._school_id,
            Grade.id,
            Grade.name,
        ).all()
        if not grouped:
            return []

        totals_by_class_query = (
            db.session.query(
                Class.id.label("class_id"),
                db.func.count(db.func.distinct(Student.id)).label("total_students"),
            )
            .select_from(Student)
            .join(Class, Class.id == Student.class_id)
            .outerjoin(School, School.id == Student.school_id)
        )
        totals_by_class_query = _apply_common_student_filters(totals_by_class_query)
        totals_by_class = {
            str(row.class_id): int(row.total_students or 0)
            for row in totals_by_class_query.group_by(Class.id).all()
        }

        adequado_condition = cls._adequado_avancado_student_condition(results_model, storage_key)
        adequado_student_id = case((adequado_condition, Student.id), else_=None)
        adequado_by_class_query = (
            db.session.query(
                Class.id.label("class_id"),
                func.count(func.distinct(adequado_student_id)).label("adequado_avancado_count"),
            )
            .select_from(results_model)
            .join(Student, Student.id == results_model.student_id)
            .join(Class, Class.id == Student.class_id)
            .outerjoin(School, School.id == Student.school_id)
        )
        adequado_by_class_query = _apply_entity_filter(adequado_by_class_query, results_model)
        if use_discipline_metrics and subject_prof_expr is not None:
            adequado_by_class_query = adequado_by_class_query.filter(subject_prof_expr.isnot(None))
        adequado_by_class_query = _apply_common_student_filters(adequado_by_class_query)
        adequado_avancado_by_class = {
            str(row.class_id): int(row.adequado_avancado_count or 0)
            for row in adequado_by_class_query.group_by(Class.id).all()
        }

        rows: List[Dict[str, Any]] = []
        for row in grouped:
            class_id = str(row.class_id or "")
            if not class_id:
                continue
            participating = int(row.alunos or 0)
            total_students = int(totals_by_class.get(class_id, participating) or 0)
            if total_students < participating:
                total_students = participating
            avg_prof = float(row.average_proficiency or 0)
            grade_name = str(row.serie or "Sem série")
            course_label = cls._derive_course_label(grade_name)
            adequado_avancado_count = int(adequado_avancado_by_class.get(class_id, 0))
            adequado_avancado_pct = (
                round((adequado_avancado_count / participating) * 100, 1)
                if participating > 0
                else 0.0
            )
            rows.append(
                {
                    "class_id": class_id,
                    "school_id": str(row.school_id or ""),
                    "turma": row.turma or "Turma",
                    "serie": grade_name,
                    "grade_id": str(row.grade_id or ""),
                    "media": round(float(row.media or 0), 1),
                    "average_score": round(float(row.media or 0), 1),
                    "average_proficiency": round(avg_prof, 1),
                    "alunos": participating,
                    "participating_students": participating,
                    "total_students": total_students,
                    "participation_rate": round((participating / total_students) * 100, 1) if total_students > 0 else 0.0,
                    "adequado_avancado_count": adequado_avancado_count,
                    "adequado_avancado_pct": adequado_avancado_pct,
                    "classification": cls._classification_from_proficiency(
                        avg_prof,
                        course_label=course_label,
                        subject_name=subject_name,
                    ),
                    "acerto_percent": 0.0,
                    "conclusao": round((participating / total_students) * 100, 1) if total_students > 0 else 0.0,
                    "avaliacoes": 1,
                }
            )
        return rows

    @classmethod
    def _build_class_ranking_payload(
        cls,
        class_rows: List[Dict[str, Any]],
        filters: Dict[str, Any],
    ) -> Dict[str, Any]:
        selected_grade_id = str(filters.get("serie") or "").strip()
        selected_grade_name = None
        if selected_grade_id:
            grade = db.session.query(Grade.name).filter(Grade.id == selected_grade_id).first()
            selected_grade_name = str(getattr(grade, "name", "") or "").strip() if grade else None

        sections = cls._build_classes_by_series(class_rows, selected_grade_name=selected_grade_name)
        items: List[Dict[str, Any]] = []
        for section in sections:
            for raw in section.get("items") or []:
                avg_prof = float(raw.get("average_proficiency") or 0)
                participating = int(raw.get("students_count") or 0)
                total_students = int(raw.get("total_students") or participating)
                participation_rate = float(raw.get("participation_rate") or 0)
                if not participation_rate and total_students > 0:
                    participation_rate = round((participating / total_students) * 100, 1)
                grade_name = str(raw.get("grade_name") or "Sem série")
                course_label = cls._derive_course_label(grade_name)
                subject_name = cls._resolve_subject_name_for_filters(filters)
                classification = str(raw.get("classification") or "") or cls._classification_from_proficiency(
                    avg_prof,
                    course_label=course_label,
                    subject_name=subject_name,
                )
                turma = str(raw.get("class_name") or "Turma").strip() or "Turma"
                items.append(
                    {
                        "class_id": raw.get("class_id"),
                        "class_name": cls._format_grade_class_label(grade_name, turma),
                        "grade_name": grade_name,
                        "participation_rate": participation_rate,
                        "participating_students": participating,
                        "total_students": total_students,
                        "average_proficiency": round(avg_prof, 1),
                        "average_score": round(float(raw.get("average_score") or 0), 1),
                        "adequado_avancado_count": int(raw.get("adequado_avancado_count") or 0),
                        "adequado_avancado_pct": round(float(raw.get("adequado_avancado_pct") or 0), 1),
                        "level_tag": classification,
                        "is_critical": classification == "Abaixo do Básico",
                    }
                )
        items.sort(
            key=lambda row: (
                -float(row.get("average_score") or 0),
                -float(row.get("average_proficiency") or 0),
                str(row.get("class_name") or ""),
            )
        )
        for idx, row in enumerate(items):
            row["position"] = idx + 1
        return {
            "grade_name": selected_grade_name,
            "items": items,
            "totals": {"count": len(items)},
        }

    @staticmethod
    def _extract_series_labels(schools: List[Dict[str, Any]]) -> List[str]:
        labels = sorted({str(series.get("grade_name") or "Sem série") for school in schools for series in school.get("series", [])})
        return labels

    @classmethod
    def _build_network_series_averages(
        cls,
        schools: List[Dict[str, Any]],
        *,
        subject_name: str = "GERAL",
    ) -> List[Dict[str, Any]]:
        if not schools:
            return []
        bucket: Dict[str, Dict[str, float]] = defaultdict(lambda: {"score_total": 0.0, "prof_total": 0.0, "students": 0.0})
        for school in schools:
            for series in school.get("series", []):
                label = str(series.get("grade_name") or "Sem série")
                students = float(series.get("students_count") or 0)
                if students <= 0:
                    students = 1.0
                bucket[label]["score_total"] += float(series.get("average_score") or 0) * students
                bucket[label]["prof_total"] += float(series.get("average_proficiency") or 0) * students
                bucket[label]["students"] += students

        result: List[Dict[str, Any]] = []
        for label in sorted(bucket.keys()):
            total_students = bucket[label]["students"] or 1.0
            average_score = round(bucket[label]["score_total"] / total_students, 1)
            average_proficiency = round(bucket[label]["prof_total"] / total_students, 1)
            course_label = cls._derive_course_label(label)
            result.append(
                {
                    "grade_name": label,
                    "average_score": average_score,
                    "average_proficiency": average_proficiency,
                    "classification": cls._classification_from_proficiency(
                        average_proficiency,
                        course_label=course_label,
                        subject_name=subject_name,
                    ),
                }
            )
        return result

    @classmethod
    def _evaluation_ranking(cls, scope: Dict[str, Any], req: RankingRequest) -> Dict[str, Any]:
        evaluation_id = req.filters.get("evaluation_id")
        if not evaluation_id:
            raise ValueError("evaluation_id é obrigatório para ranking_type=specific_evaluation.")

        # Alinha com a tela de resultados: considera o registro mais recente por aluno
        # para a avaliação selecionada, evitando média/moda entre múltiplas tentativas.
        latest_per_student = (
            db.session.query(
                EvaluationResult.student_id.label("student_id"),
                EvaluationResult.grade.label("grade"),
                EvaluationResult.proficiency.label("proficiency"),
                EvaluationResult.classification.label("classification"),
                EvaluationResult.correct_answers.label("correct_answers"),
                EvaluationResult.total_questions.label("total_questions"),
                db.func.row_number()
                .over(
                    partition_by=EvaluationResult.student_id,
                    order_by=(
                        EvaluationResult.calculated_at.desc().nullslast(),
                        EvaluationResult.id.desc(),
                    ),
                )
                .label("row_num"),
            )
            .filter(EvaluationResult.test_id == str(evaluation_id))
            .subquery()
        )

        query = (
            db.session.query(
                latest_per_student.c.student_id.label("student_id"),
                Student.name.label("student_name"),
                School.name.label("school_name"),
                Class.name.label("class_name"),
                Grade.name.label("grade_name"),
                latest_per_student.c.grade.label("average_grade"),
                latest_per_student.c.proficiency.label("average_proficiency"),
                latest_per_student.c.classification.label("classification"),
                latest_per_student.c.correct_answers.label("total_correct_answers"),
                latest_per_student.c.total_questions.label("total_questions"),
            )
            .select_from(latest_per_student)
            .join(Student, Student.id == latest_per_student.c.student_id)
            .outerjoin(School, School.id == Student.school_id)
            .outerjoin(Class, Class.id == Student.class_id)
            .outerjoin(Grade, Grade.id == Student.grade_id)
            .filter(latest_per_student.c.row_num == 1)
        )

        if req.filters.get("escola"):
            query = query.filter(Student.school_id == str(req.filters["escola"]))
        if req.filters.get("turma"):
            query = query.filter(Student.class_id == req.filters["turma"])
        if req.filters.get("serie"):
            query = query.filter(Student.grade_id == req.filters["serie"])
        if req.filters.get("municipio"):
            query = query.filter(School.city_id == str(req.filters["municipio"]))

        school_ids = scope.get("school_ids") or []
        class_ids = scope.get("class_ids") or []
        city_id = scope.get("city_id")
        if school_ids:
            query = query.filter(Student.school_id.in_([str(x) for x in school_ids]))
        if class_ids:
            query = query.filter(Student.class_id.in_(class_ids))
        if city_id:
            query = query.filter(School.city_id == str(city_id))

        ranked = query.order_by(
            db.func.coalesce(latest_per_student.c.grade, 0).desc(),
            db.func.coalesce(latest_per_student.c.proficiency, 0).desc(),
        )

        total = ranked.count()
        offset = (req.page - 1) * req.per_page
        rows = ranked.offset(offset).limit(req.per_page).all()
        items = []
        for idx, row in enumerate(rows):
            items.append(
                {
                    "position": offset + idx + 1,
                    "student_id": row.student_id,
                    "name": row.student_name,
                    "school_name": row.school_name,
                    "class_name": row.class_name,
                    "serie": row.grade_name,
                    "average_score": float(row.average_grade or 0),
                    "average_proficiency": float(row.average_proficiency or 0),
                    "classification": row.classification,
                    "total_correct_answers": int(row.total_correct_answers or 0),
                    "total_questions": int(row.total_questions or 0),
                }
            )
        return cls._build_response(req, scope, total=total, items=items)

    @classmethod
    def _answer_sheet_ranking(cls, scope: Dict[str, Any], req: RankingRequest) -> Dict[str, Any]:
        answer_sheet_id = req.filters.get("answer_sheet_id")
        if not answer_sheet_id:
            raise ValueError("answer_sheet_id é obrigatório para ranking_type=specific_answer_sheet.")

        # Alinha com a tela de resultados: considera a correção mais recente por aluno
        # para o gabarito selecionado, sem agregar múltiplas correções antigas.
        latest_per_student = (
            db.session.query(
                AnswerSheetResult.student_id.label("student_id"),
                AnswerSheetResult.grade.label("grade"),
                AnswerSheetResult.proficiency.label("proficiency"),
                AnswerSheetResult.classification.label("classification"),
                AnswerSheetResult.correct_answers.label("correct_answers"),
                AnswerSheetResult.total_questions.label("total_questions"),
                db.func.row_number()
                .over(
                    partition_by=AnswerSheetResult.student_id,
                    order_by=(
                        AnswerSheetResult.corrected_at.desc().nullslast(),
                        AnswerSheetResult.id.desc(),
                    ),
                )
                .label("row_num"),
            )
            .filter(AnswerSheetResult.gabarito_id == str(answer_sheet_id))
            .subquery()
        )

        query = (
            db.session.query(
                latest_per_student.c.student_id.label("student_id"),
                Student.name.label("student_name"),
                School.name.label("school_name"),
                Class.name.label("class_name"),
                Grade.name.label("grade_name"),
                latest_per_student.c.grade.label("average_grade"),
                latest_per_student.c.proficiency.label("average_proficiency"),
                latest_per_student.c.classification.label("classification"),
                latest_per_student.c.correct_answers.label("total_correct_answers"),
                latest_per_student.c.total_questions.label("total_questions"),
            )
            .select_from(latest_per_student)
            .join(Student, Student.id == latest_per_student.c.student_id)
            .outerjoin(School, School.id == Student.school_id)
            .outerjoin(Class, Class.id == Student.class_id)
            .outerjoin(Grade, Grade.id == Student.grade_id)
            .filter(latest_per_student.c.row_num == 1)
        )

        if req.filters.get("escola"):
            query = query.filter(Student.school_id == str(req.filters["escola"]))
        if req.filters.get("turma"):
            query = query.filter(Student.class_id == req.filters["turma"])
        if req.filters.get("serie"):
            query = query.filter(Student.grade_id == req.filters["serie"])
        if req.filters.get("municipio"):
            query = query.filter(School.city_id == str(req.filters["municipio"]))

        school_ids = scope.get("school_ids") or []
        class_ids = scope.get("class_ids") or []
        city_id = scope.get("city_id")
        if school_ids:
            query = query.filter(Student.school_id.in_([str(x) for x in school_ids]))
        if class_ids:
            query = query.filter(Student.class_id.in_(class_ids))
        if city_id:
            query = query.filter(School.city_id == str(city_id))

        ranked = query.order_by(
            db.func.coalesce(latest_per_student.c.grade, 0).desc(),
            db.func.coalesce(latest_per_student.c.proficiency, 0).desc(),
        )

        total = ranked.count()
        offset = (req.page - 1) * req.per_page
        rows = ranked.offset(offset).limit(req.per_page).all()
        items = []
        for idx, row in enumerate(rows):
            items.append(
                {
                    "position": offset + idx + 1,
                    "student_id": row.student_id,
                    "name": row.student_name,
                    "school_name": row.school_name,
                    "class_name": row.class_name,
                    "serie": row.grade_name,
                    "average_score": float(row.average_grade or 0),
                    "average_proficiency": float(row.average_proficiency or 0),
                    "classification": row.classification,
                    "total_correct_answers": int(row.total_correct_answers or 0),
                    "total_questions": int(row.total_questions or 0),
                }
            )
        return cls._build_response(req, scope, total=total, items=items)

    @classmethod
    def _teacher_ranking(cls, scope: Dict[str, Any], req: RankingRequest) -> Dict[str, Any]:
        teachers = DashboardService._build_teacher_ranking(
            scope, limit=TEACHER_RANKING_FETCH_LIMIT, filters=req.filters
        )
        teacher_student_metrics = cls._build_teacher_student_metrics_map(scope, req.filters)
        teacher_series_class_labels = cls._build_teacher_series_class_labels_map(
            cls._resolve_school_ids_for_scope(scope, req.filters),
            req.filters,
        )
        total = len(teachers)
        offset = (req.page - 1) * req.per_page
        selected = teachers[offset : offset + req.per_page]
        items = []
        for row in selected:
            teacher_id = str(row.get("teacher_id") or "")
            grade_names = [str(name) for name in (row.get("grade_names") or []) if name]
            series_labels = teacher_series_class_labels.get(teacher_id) or [
                cls._format_grade_class_label(name) for name in grade_names
            ]
            classification = cls._classification_for_teacher(
                average_proficiency=float(row.get("average_proficiency") or 0),
                grade_names=grade_names,
                filters=req.filters,
            )
            student_metrics = teacher_student_metrics.get(teacher_id, {})
            participating_students = int(student_metrics.get("participating_students") or 0)
            adequado_avancado_count = int(student_metrics.get("adequado_avancado_count") or 0)
            adequado_avancado_pct = (
                round((adequado_avancado_count / participating_students) * 100, 1)
                if participating_students > 0
                else 0.0
            )
            items.append(
                {
                    "position": row.get("position"),
                    "teacher_id": row.get("teacher_id"),
                    "teacher_name": row.get("teacher_name"),
                    "teacher_email": row.get("teacher_email"),
                    "average_score": row.get("average_score"),
                    "average_proficiency": row.get("average_proficiency"),
                    "classification": classification,
                    "level_tag": classification,
                    "total_evaluations": row.get("total_evaluations"),
                    "classes_count": row.get("classes_count"),
                    "grade_names": row.get("grade_names") or [],
                    "series_class_name": cls._format_teacher_series_class_display(series_labels),
                    "participating_students": participating_students,
                    "adequado_avancado_count": adequado_avancado_count,
                    "adequado_avancado_pct": adequado_avancado_pct,
                }
            )
        response = cls._build_response(req, scope, total=total, items=items)
        response["teacher_course_sections"] = cls._build_teachers_by_course(items)
        return response
