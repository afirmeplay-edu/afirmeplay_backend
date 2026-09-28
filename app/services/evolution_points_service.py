# -*- coding: utf-8 -*-
"""Pontos da evolução: um ID (compatível) ou um grupo mesclado como em Resultados."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Sequence, Tuple

import dateutil.parser

from app.services.evaluation_group_service import (
    build_tests_info,
    build_virtual_multidisciplinary_results,
    validate_group_tests,
)

MAX_EVOLUTION_POINTS = 10


def resolve_request_points(
    data: Dict[str, Any],
    *,
    min_message: str = "Mínimo de 2 avaliações necessário para comparação",
) -> Tuple[List[List[str]], List[str]]:
    """
    `grupos` opcional: lista de pontos, cada ponto uma lista de IDs.
    Sem `grupos`, cada item de `test_ids` continua sendo um ponto.
    """
    raw_groups = data.get("grupos") if isinstance(data, dict) else None
    if raw_groups is not None:
        points = _parse_grupos(raw_groups, min_message=min_message)
    else:
        if not isinstance(data, dict) or "test_ids" not in data:
            raise ValueError("Campo 'test_ids' é obrigatório no body JSON")
        test_ids = data["test_ids"]
        if not isinstance(test_ids, list):
            raise ValueError("Campo 'test_ids' deve ser uma lista de strings")
        clean = [item.strip() for item in test_ids if item and isinstance(item, str) and item.strip()]
        if len(clean) < 2:
            raise ValueError(min_message)
        if len(clean) != len(set(clean)):
            raise ValueError("IDs de avaliações duplicados encontrados")
        points = [[item] for item in clean]
    flat = [item for group in points for item in group]
    return points, flat


def points_need_merge(points: Sequence[Sequence[str]]) -> bool:
    return any(len(group) > 1 for group in points)


def validate_merge_points(points: Sequence[Sequence[str]], tests: Sequence[Any]) -> Optional[str]:
    """Mesma regra de Resultados, aplicada a cada ponto com 2+ provas."""
    by_id = {str(test.id): test for test in tests}
    for group in points:
        if len(group) < 2:
            continue
        ordered = []
        missing = []
        for test_id in group:
            test = by_id.get(str(test_id))
            if test is None:
                missing.append(str(test_id))
            else:
                ordered.append(test)
        if missing:
            return f"Avaliações não encontradas: {', '.join(missing)}"
        error = validate_group_tests(build_tests_info(ordered))
        if error:
            return error
    return None


def _parse_grupos(raw_groups: Any, *, min_message: str) -> List[List[str]]:
    if not isinstance(raw_groups, list):
        raise ValueError("Campo 'grupos' deve ser uma lista de grupos")
    points: List[List[str]] = []
    seen: set = set()
    for group in raw_groups:
        if isinstance(group, str):
            ids = [group.strip()] if group.strip() else []
        elif isinstance(group, list):
            ids = []
            for item in group:
                if item is None:
                    continue
                text = str(item).strip()
                if text:
                    ids.append(text)
        else:
            raise ValueError("Cada grupo deve ser uma lista de IDs")
        if not ids:
            raise ValueError("Grupo de avaliações vazio")
        if len(ids) != len(set(ids)):
            raise ValueError("IDs de avaliações duplicados encontrados")
        for test_id in ids:
            if test_id in seen:
                raise ValueError("IDs de avaliações duplicados encontrados")
            seen.add(test_id)
        points.append(ids)
    if len(points) < 2:
        raise ValueError(min_message)
    if len(points) > MAX_EVOLUTION_POINTS:
        raise ValueError("Máximo de 10 avaliações por comparação")
    return points


def _as_naive_utc(value: Any) -> datetime:
    if value is None:
        return datetime.min
    if not isinstance(value, datetime):
        try:
            value = dateutil.parser.parse(str(value))
        except Exception:
            return datetime.min
    if value.tzinfo is not None:
        from datetime import timezone

        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def _earliest_application(test: Any) -> datetime:
    from app.models.classTest import ClassTest

    application_date = None
    for class_test in ClassTest.query.filter_by(test_id=str(test.id)).all():
        if not class_test.application:
            continue
        try:
            parsed = _as_naive_utc(dateutil.parser.parse(class_test.application))
        except Exception:
            continue
        if application_date is None or parsed < application_date:
            application_date = parsed
    if application_date is None:
        application_date = _as_naive_utc(getattr(test, "created_at", None)) if getattr(test, "created_at", None) else datetime.min
    return application_date


def _load_scoped_results(test_id: str, escopo_calculo: Optional[Dict[str, Any]]):
    from app.models.evaluationResult import EvaluationResult
    from app.models.student import Student
    from app.routes.evaluation_results_routes import _dedupe_evaluation_results_by_student
    from app.services.evaluation_result_snapshot import (
        class_ids_for_evaluation_in_scope,
        query_evaluation_results_for_class_group,
    )

    if escopo_calculo:
        class_ids = class_ids_for_evaluation_in_scope(str(test_id), escopo_calculo)
        base_ids = [
            student.id
            for student in Student.query.filter(Student.class_id.in_(class_ids)).all()
        ] if class_ids else []
        results = query_evaluation_results_for_class_group(str(test_id), class_ids, base_ids).all()
        results = _dedupe_evaluation_results_by_student(results)
        return results, class_ids

    from app.models.classTest import ClassTest

    class_ids = [
        class_test.class_id
        for class_test in ClassTest.query.filter_by(test_id=str(test_id)).all()
        if class_test.class_id
    ]
    results = EvaluationResult.query.filter_by(test_id=test_id).all()
    return results, class_ids


def _course_of(test: Any) -> Any:
    return getattr(test, "course", None)


@dataclass
class ComparisonPointData:
    ids: List[str]
    point_id: str
    title: str
    application_date: datetime
    course: Any
    created_at: Any
    results: list
    class_ids: list
    is_group: bool
    grade_info: Dict[str, Any]
    tests_info: list = field(default_factory=list)
    representative_test: Any = None

    def as_test(self) -> SimpleNamespace:
        return SimpleNamespace(
            id=self.point_id,
            title=self.title,
            course=self.course,
            created_at=self.created_at,
        )


def _grade_info_for_tests(tests: Sequence[Any]) -> Dict[str, Any]:
    from app.services.evaluation_comparison_service import EvaluationComparisonService

    classes: Dict[str, Dict[str, str]] = {}
    grade_names: List[str] = []
    grade_id = None
    grade_name = None
    for test in tests:
        info = EvaluationComparisonService._resolve_test_grade_info(test)
        for class_ref in info.get("classes") or []:
            class_id = str(class_ref.get("id") or "")
            if class_id and class_id not in classes:
                classes[class_id] = {"id": class_id, "name": class_ref.get("name") or ""}
        if grade_id is None and info.get("grade_id"):
            grade_id = info.get("grade_id")
            grade_name = info.get("grade_name")
        for name in info.get("grade_names") or []:
            if name and name not in grade_names:
                grade_names.append(name)
    class_list = list(classes.values())
    class_list.sort(key=lambda item: (item.get("name") or "").lower())
    return {
        "grade_id": grade_id,
        "grade_name": grade_name,
        "grade_names": grade_names,
        "classes": class_list,
    }


def _group_title(tests_info: Sequence[Any], tests: Sequence[Any]) -> str:
    names: List[str] = []
    for info in tests_info:
        for subject in getattr(info, "subjects", None) or []:
            name = (subject.get("name") or "").strip()
            if name and name not in names:
                names.append(name)
    if names:
        return " + ".join(names)
    return " + ".join((getattr(test, "title", None) or "Avaliação") for test in tests)


def build_comparison_points(
    points: Sequence[Sequence[str]],
    escopo_calculo: Optional[Dict[str, Any]],
) -> List[ComparisonPointData]:
    """Monta um ponto por grupo. Grupo com 2+ IDs usa a mescla de Resultados."""
    from app.models.test import Test
    from sqlalchemy.orm import joinedload

    flat = [test_id for group in points for test_id in group]
    tests = (
        Test.query.filter(Test.id.in_(flat))
        .options(joinedload(Test.subject_rel), joinedload(Test.grade))
        .all()
    )
    by_id = {str(test.id): test for test in tests}
    built: List[ComparisonPointData] = []
    for group in points:
        ordered = []
        for test_id in group:
            test = by_id.get(str(test_id))
            if test is None:
                raise ValueError(f"Avaliações não encontradas: {test_id}")
            ordered.append(test)
        if len(ordered) == 1:
            test = ordered[0]
            results, class_ids = _load_scoped_results(str(test.id), escopo_calculo)
            if not results:
                raise ValueError(f"Avaliação {test.id} não possui resultados no escopo")
            built.append(
                ComparisonPointData(
                    ids=[str(test.id)],
                    point_id=str(test.id),
                    title=test.title or "Avaliação",
                    application_date=_earliest_application(test),
                    course=_course_of(test),
                    created_at=getattr(test, "created_at", None),
                    results=results,
                    class_ids=list(class_ids or []),
                    is_group=False,
                    grade_info=_grade_info_for_tests(ordered),
                    representative_test=test,
                )
            )
            continue

        infos = build_tests_info(ordered)
        error = validate_group_tests(infos)
        if error:
            raise ValueError(error)
        combined_results = []
        class_ids: List[Any] = []
        seen_classes = set()
        for test in ordered:
            results, scoped_classes = _load_scoped_results(str(test.id), escopo_calculo)
            if not results:
                raise ValueError(f"Avaliação {test.id} não possui resultados no escopo")
            combined_results.extend(results)
            for class_id in scoped_classes or []:
                key = str(class_id)
                if key in seen_classes:
                    continue
                seen_classes.add(key)
                class_ids.append(class_id)
        course_name = "Anos Iniciais"
        course = _course_of(ordered[0])
        if course:
            try:
                from app.models.educationStage import EducationStage

                course_obj = EducationStage.query.get(course)
                if course_obj and course_obj.name:
                    course_name = course_obj.name
            except Exception:
                pass
        merged = build_virtual_multidisciplinary_results(
            combined_results,
            infos,
            course_name,
            only_complete=True,
        )
        if not merged:
            raise ValueError("As avaliações do grupo não possuem alunos em comum no escopo selecionado")
        dates = [_earliest_application(test) for test in ordered]
        built.append(
            ComparisonPointData(
                ids=[str(test.id) for test in ordered],
                point_id=",".join(str(test.id) for test in ordered),
                title=_group_title(infos, ordered),
                application_date=min(dates) if dates else datetime.min,
                course=course,
                created_at=getattr(ordered[0], "created_at", None),
                results=merged,
                class_ids=class_ids,
                is_group=True,
                grade_info=_grade_info_for_tests(ordered),
                tests_info=list(infos),
                representative_test=ordered[0],
            )
        )
    return built
