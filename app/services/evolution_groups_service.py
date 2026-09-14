# -*- coding: utf-8 -*-
"""
Evolução por grupos (turma / série / escola) ao longo de múltiplas avaliações.
Nível do grupo = classificação da proficiência média hierárquica (CLASSIFICATION_CONFIG).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import dateutil.parser
from sqlalchemy.orm import joinedload

from app.models.studentClass import Class
from app.models.grades import Grade
from app.models.school import School
from app.models.student import Student
from app.models.test import Test
from app.services.evaluation_calculator import EvaluationCalculator
from app.utils.school_equal_weight_means import hierarchical_mean_grade_and_proficiency

LEVEL_ORDER = [
    "Abaixo do Básico",
    "Básico",
    "Adequado",
    "Avançado",
]


def _as_naive_utc(value: Any) -> datetime:
    if value is None:
        return datetime.min
    if not isinstance(value, datetime):
        try:
            value = dateutil.parser.parse(str(value))
        except Exception:
            return datetime.min
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def _valid_view_by(value: Optional[str]) -> str:
    v = (value or "turma").strip().lower()
    if v in ("turma", "serie", "escola"):
        return v
    if v in ("class", "série", "series", "school"):
        return {"class": "turma", "série": "serie", "series": "serie", "school": "escola"}[v]
    return "turma"


def _course_name_for_test(test: Optional[Test]) -> str:
    if not test or not getattr(test, "course", None):
        return "Anos Iniciais"
    try:
        from app.models.educationStage import EducationStage

        course_obj = EducationStage.query.get(test.course)
        if course_obj and course_obj.name:
            return course_obj.name
    except Exception:
        pass
    return "Anos Iniciais"


def _result_placement(result, classes_by_id, students_by_id) -> Optional[Tuple[str, str, str]]:
    """Retorna (school_id, grade_id, class_id) ou None."""
    snap_class = getattr(result, "class_id_snapshot", None)
    snap_school = getattr(result, "school_id_snapshot", None)
    snap_grade = getattr(result, "grade_id_snapshot", None)

    if snap_class is not None or snap_school:
        co = classes_by_id.get(snap_class) if snap_class is not None else None
        sch = str(snap_school) if snap_school else (str(co.school_id) if co and co.school_id else None)
        if not sch:
            return None
        if snap_grade is not None:
            gid = str(snap_grade)
        elif co and co.grade_id:
            gid = str(co.grade_id)
        else:
            gid = "_sem_serie"
        cid = str(snap_class) if snap_class is not None else "_sem_turma"
        return sch, gid, cid

    sid = getattr(result, "student_id", None)
    if not sid:
        return None
    st = students_by_id.get(str(sid))
    if not st or not st.class_id:
        return None
    co = st.class_ or classes_by_id.get(st.class_id)
    if not co or not co.school_id:
        return None
    return (
        str(co.school_id),
        str(co.grade_id) if co.grade_id else "_sem_serie",
        str(co.id),
    )


def _group_key(view_by: str, school_id: str, grade_id: str, class_id: str) -> str:
    if view_by == "escola":
        return f"escola:{school_id}"
    if view_by == "serie":
        return f"serie:{school_id}:{grade_id}"
    return f"turma:{class_id}"


def _pp_delta(from_val: float, to_val: float) -> float:
    """Variação em pontos percentuais da nota (0–10 → *10), ou da proficiência relativa."""
    return round(to_val - from_val, 2)


class EvolutionGroupsService:
    @staticmethod
    def compare_by_groups(
        test_ids: List[str],
        *,
        view_by: str = "turma",
        escopo_calculo: Optional[Dict[str, Any]] = None,
        filtros_aplicados: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        try:
            view_by = _valid_view_by(view_by)
            if len(test_ids) < 2:
                return None

            tests = Test.query.filter(Test.id.in_(test_ids)).all()
            if len(tests) != len(test_ids):
                return None

            from app.models.classTest import ClassTest

            tests_with_dates = []
            for test in tests:
                class_tests = ClassTest.query.filter_by(test_id=test.id).all()
                application_date = None
                for ct in class_tests:
                    if ct.application:
                        try:
                            parsed_date = _as_naive_utc(dateutil.parser.parse(ct.application))
                            if application_date is None or parsed_date < application_date:
                                application_date = parsed_date
                        except Exception:
                            pass
                if application_date is None:
                    application_date = _as_naive_utc(test.created_at) if test.created_at else datetime.min
                tests_with_dates.append({"test": test, "application_date": application_date})

            tests_with_dates.sort(key=lambda x: _as_naive_utc(x["application_date"]))
            ordered_tests = [item["test"] for item in tests_with_dates]

            from app.services.evaluation_result_snapshot import (
                class_ids_for_evaluation_in_scope,
                query_evaluation_results_for_class_group,
            )
            from app.routes.evaluation_results_routes import (
                _dedupe_evaluation_results_by_student,
            )

            all_results: Dict[str, List[Any]] = {}
            for test in ordered_tests:
                if escopo_calculo:
                    class_ids = class_ids_for_evaluation_in_scope(str(test.id), escopo_calculo)
                    base_ids = [
                        s.id
                        for s in Student.query.filter(Student.class_id.in_(class_ids)).all()
                    ] if class_ids else []
                    results = query_evaluation_results_for_class_group(
                        str(test.id), class_ids, base_ids
                    ).all()
                    results = _dedupe_evaluation_results_by_student(results)
                else:
                    from app.models.evaluationResult import EvaluationResult

                    results = EvaluationResult.query.filter_by(test_id=test.id).all()
                all_results[test.id] = results or []

            # Prefetch placement maps
            all_flat = [r for rs in all_results.values() for r in rs]
            student_ids = list({str(r.student_id) for r in all_flat if getattr(r, "student_id", None)})
            snap_class_ids = [
                r.class_id_snapshot
                for r in all_flat
                if getattr(r, "class_id_snapshot", None) is not None
            ]
            classes_by_id: Dict[Any, Class] = {}
            if snap_class_ids:
                for c in Class.query.options(joinedload(Class.grade)).filter(Class.id.in_(snap_class_ids)).all():
                    classes_by_id[c.id] = c
            students_by_id: Dict[str, Student] = {}
            if student_ids:
                for s in (
                    Student.query.options(joinedload(Student.class_).joinedload(Class.grade))
                    .filter(Student.id.in_(student_ids))
                    .all()
                ):
                    students_by_id[str(s.id)] = s
                    if s.class_ and s.class_.id not in classes_by_id:
                        classes_by_id[s.class_.id] = s.class_

            # Discover groups across all evaluations
            groups_meta: Dict[str, Dict[str, Any]] = {}
            for test in ordered_tests:
                for r in all_results.get(test.id, []):
                    placement = _result_placement(r, classes_by_id, students_by_id)
                    if not placement:
                        continue
                    school_id, grade_id, class_id = placement
                    key = _group_key(view_by, school_id, grade_id, class_id)
                    if key in groups_meta:
                        continue
                    school = School.query.get(school_id)
                    grade = Grade.query.get(grade_id) if grade_id != "_sem_serie" else None
                    class_obj = None
                    if class_id != "_sem_turma":
                        class_obj = classes_by_id.get(class_id) or classes_by_id.get(
                            next((c.id for c in classes_by_id.values() if str(c.id) == str(class_id)), None)
                        )
                        if class_obj is None:
                            try:
                                from uuid import UUID

                                try:
                                    class_obj = Class.query.get(UUID(str(class_id)))
                                except Exception:
                                    class_obj = Class.query.get(class_id)
                            except Exception:
                                class_obj = None
                        if class_obj is not None:
                            classes_by_id[class_obj.id] = class_obj
                            classes_by_id[str(class_obj.id)] = class_obj

                    if view_by == "escola":
                        name = (school.name if school else None) or "Escola"
                        groups_meta[key] = {
                            "id": key,
                            "name": name,
                            "school_id": school_id,
                            "school_name": name,
                            "grade_id": None,
                            "grade_name": None,
                            "class_id": None,
                            "class_name": None,
                        }
                    elif view_by == "serie":
                        gname = (grade.name if grade else None) or "Série"
                        sname = (school.name if school else None) or "Escola"
                        groups_meta[key] = {
                            "id": key,
                            "name": f"{gname} — {sname}",
                            "school_id": school_id,
                            "school_name": sname,
                            "grade_id": grade_id if grade_id != "_sem_serie" else None,
                            "grade_name": gname,
                            "class_id": None,
                            "class_name": None,
                        }
                    else:
                        cname = (class_obj.name if class_obj else None) or "Turma"
                        gname = (grade.name if grade else None) or (
                            class_obj.grade.name if class_obj and class_obj.grade else None
                        )
                        sname = (school.name if school else None) or "Escola"
                        groups_meta[key] = {
                            "id": key,
                            "name": cname,
                            "school_id": school_id,
                            "school_name": sname,
                            "grade_id": grade_id if grade_id != "_sem_serie" else None,
                            "grade_name": gname,
                            "class_id": class_id if class_id != "_sem_turma" else None,
                            "class_name": cname,
                        }

            aggregation_level = view_by  # turma | serie | escola
            evaluations_payload = []
            for i, item in enumerate(tests_with_dates):
                test = item["test"]
                evaluations_payload.append(
                    {
                        "order": i + 1,
                        "id": test.id,
                        "title": test.title or f"Avaliação {i + 1}",
                        "application_date": (
                            item["application_date"].isoformat()
                            if isinstance(item["application_date"], datetime)
                            else str(item["application_date"])
                        ),
                    }
                )

            groups_out: List[Dict[str, Any]] = []
            summary_counts = {lvl: 0 for lvl in LEVEL_ORDER}

            for key, meta in sorted(groups_meta.items(), key=lambda kv: (kv[1].get("name") or "").lower()):
                points = []
                for i, test in enumerate(ordered_tests):
                    group_results = []
                    for r in all_results.get(test.id, []):
                        placement = _result_placement(r, classes_by_id, students_by_id)
                        if not placement:
                            continue
                        school_id, grade_id, class_id = placement
                        if _group_key(view_by, school_id, grade_id, class_id) != key:
                            continue
                        group_results.append(r)

                    if not group_results:
                        points.append(
                            {
                                "evaluation_id": test.id,
                                "evaluation_title": test.title,
                                "order": i + 1,
                                "average_grade": None,
                                "average_proficiency": None,
                                "level": None,
                                "total_students": 0,
                            }
                        )
                        continue

                    course_name = _course_name_for_test(test)
                    avg_grade, avg_prof = hierarchical_mean_grade_and_proficiency(
                        group_results,
                        aggregation_level,
                        course_name=course_name,
                        subject_name="GERAL",
                    )
                    level = EvaluationCalculator.determine_classification(
                        avg_prof, course_name, "GERAL"
                    )
                    points.append(
                        {
                            "evaluation_id": test.id,
                            "evaluation_title": test.title,
                            "order": i + 1,
                            "average_grade": round(avg_grade, 2),
                            "average_proficiency": round(avg_prof, 2),
                            "level": level,
                            "total_students": len(group_results),
                        }
                    )

                transitions = []
                for i in range(len(points) - 1):
                    a, b = points[i], points[i + 1]
                    if a.get("level") and b.get("level"):
                        prof_delta = None
                        grade_delta = None
                        if a.get("average_proficiency") is not None and b.get("average_proficiency") is not None:
                            prof_delta = _pp_delta(a["average_proficiency"], b["average_proficiency"])
                        if a.get("average_grade") is not None and b.get("average_grade") is not None:
                            # pontos percentuais aproximados da nota (escala 0–10 → *10)
                            grade_delta = round((b["average_grade"] - a["average_grade"]) * 10, 1)
                        transitions.append(
                            {
                                "from_order": a["order"],
                                "to_order": b["order"],
                                "from_level": a["level"],
                                "to_level": b["level"],
                                "level_changed": a["level"] != b["level"],
                                "proficiency_delta": prof_delta,
                                "grade_pp_delta": grade_delta,
                            }
                        )

                # Nível atual = última prova com dados
                current_level = None
                for p in reversed(points):
                    if p.get("level"):
                        current_level = p["level"]
                        break
                if current_level in summary_counts:
                    summary_counts[current_level] += 1

                groups_out.append(
                    {
                        **meta,
                        "current_level": current_level,
                        "points": points,
                        "transitions": transitions,
                    }
                )

            return {
                "view_by": view_by,
                "filtros_aplicados": filtros_aplicados,
                "evaluations": evaluations_payload,
                "total_evaluations": len(ordered_tests),
                "total_groups": len(groups_out),
                "summary_by_level": summary_counts,
                "groups": groups_out,
            }
        except Exception as e:
            logging.error("Erro em EvolutionGroupsService.compare_by_groups: %s", e, exc_info=True)
            return None
