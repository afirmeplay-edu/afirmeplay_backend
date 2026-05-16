# -*- coding: utf-8 -*-
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from sqlalchemy import or_

from app import db
from app.models.answerSheetResult import AnswerSheetResult
from app.models.evaluationResult import EvaluationResult
from app.models.grades import Grade
from app.models.school import School
from app.models.student import Student
from app.models.studentClass import Class
from app.services.dashboard_service import DashboardService


RANKING_TYPES = {"general", "specific_evaluation", "specific_answer_sheet", "teachers"}


@dataclass
class RankingRequest:
    ranking_type: str
    page: int
    per_page: int
    filters: Dict[str, Any]


class RankingReportService:
    @staticmethod
    def _classification_from_proficiency(proficiency: float) -> str:
        if proficiency < 200:
            return "Abaixo do Básico"
        if proficiency < 500:
            return "Básico"
        if proficiency < 750:
            return "Adequado"
        return "Avançado"

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
            limit=req.per_page,
            offset=offset,
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

        response = cls._build_response(req, scope, total=school_total, items=paged_schools)
        response["students_items"] = students_items
        response["students_totals"] = {"count": students_total}
        response["students_pagination"] = cls._pagination(req.page, req.per_page, students_total)
        response["series_labels"] = cls._extract_series_labels(paged_schools)
        response["network_series_averages"] = cls._build_network_series_averages(paged_schools)
        return response

    @classmethod
    def _build_school_general_rows(cls, scope: Dict[str, Any], filters: Dict[str, Any]) -> List[Dict[str, Any]]:
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

        query = (
            db.session.query(
                School.id.label("school_id"),
                School.name.label("school_name"),
                Grade.id.label("grade_id"),
                Grade.name.label("grade_name"),
                db.func.avg(EvaluationResult.grade).label("average_score"),
                db.func.avg(EvaluationResult.proficiency).label("average_proficiency"),
                db.func.count(db.func.distinct(Student.id)).label("students_count"),
            )
            .select_from(EvaluationResult)
            .join(Student, Student.id == EvaluationResult.student_id)
            .outerjoin(School, School.id == Student.school_id)
            .outerjoin(Class, Class.id == Student.class_id)
            .outerjoin(Grade, Grade.id == Student.grade_id)
        )
        query = _apply_common_student_filters(query)

        grouped = query.group_by(School.id, School.name, Grade.id, Grade.name).all()
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

            current["series"].append(
                {
                    "grade_id": str(row.grade_id) if row.grade_id else None,
                    "grade_name": row.grade_name or "Sem série",
                    "average_score": round(avg_score, 1),
                    "average_proficiency": round(avg_prof, 1),
                    "classification": cls._classification_from_proficiency(avg_prof),
                    "students_count": students_count,
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
            school["classification"] = cls._classification_from_proficiency(float(school["average_proficiency"] or 0))
            school["series"].sort(key=lambda item: str(item.get("grade_name") or ""))

        return list(by_school.values())

    @staticmethod
    def _extract_series_labels(schools: List[Dict[str, Any]]) -> List[str]:
        labels = sorted({str(series.get("grade_name") or "Sem série") for school in schools for series in school.get("series", [])})
        return labels

    @classmethod
    def _build_network_series_averages(cls, schools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
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
            result.append(
                {
                    "grade_name": label,
                    "average_score": average_score,
                    "average_proficiency": average_proficiency,
                    "classification": cls._classification_from_proficiency(average_proficiency),
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
        teachers = DashboardService._build_teacher_ranking(scope)
        total = len(teachers)
        offset = (req.page - 1) * req.per_page
        selected = teachers[offset : offset + req.per_page]
        items = [
            {
                "position": row.get("position"),
                "teacher_id": row.get("teacher_id"),
                "teacher_name": row.get("teacher_name"),
                "teacher_email": row.get("teacher_email"),
                "average_score": row.get("average_score"),
                "average_proficiency": row.get("average_proficiency"),
                "classification": row.get("classification"),
                "total_evaluations": row.get("total_evaluations"),
                "classes_count": row.get("classes_count"),
            }
            for row in selected
        ]
        return cls._build_response(req, scope, total=total, items=items)
