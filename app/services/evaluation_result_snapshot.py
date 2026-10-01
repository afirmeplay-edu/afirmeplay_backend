# -*- coding: utf-8 -*-
"""
Filtros e utilitários para contexto escolar imutável em evaluation_results.

Os snapshots são preenchidos na criação do resultado; linhas legadas sem snapshot
continuam a usar o universo de alunos atual (class_id/school_id) como fallback.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union

from sqlalchemy import and_, cast, or_
from sqlalchemy.dialects.postgresql import VARCHAR
from sqlalchemy.orm import joinedload

from app import db
from app.models.evaluationResult import EvaluationResult
from app.models.grades import Grade
from app.models.school import School
from app.models.student import Student
from app.models.studentClass import Class


from app.utils.uuid_helpers import ensure_uuid


def build_placement_snapshots_from_student(student: Student) -> Dict[str, Any]:
    """
    Lê a colocação atual do aluno (e matrícula vigente) para gravar em novo EvaluationResult.
    """
    from app.models.studentSchoolEnrollment import StudentSchoolEnrollment

    school_id = getattr(student, "school_id", None)
    class_id = getattr(student, "class_id", None)
    grade_id = getattr(student, "grade_id", None)
    if class_id is not None and grade_id is None:
        cls_obj = Class.query.get(class_id)
        if cls_obj is not None and getattr(cls_obj, "grade_id", None) is not None:
            grade_id = cls_obj.grade_id

    enrollment_id = None
    try:
        row = (
            StudentSchoolEnrollment.query.filter_by(student_id=student.id)
            .filter(StudentSchoolEnrollment.valid_to.is_(None))
            .first()
        )
        if row is not None:
            enrollment_id = row.id
    except Exception:
        enrollment_id = None

    return {
        "school_id_snapshot": str(school_id) if school_id else None,
        "class_id_snapshot": class_id,
        "grade_id_snapshot": grade_id,
        "enrollment_id_snapshot": enrollment_id,
    }


def snapshot_scope_filter_expression(
    escopo_calculo: Dict[str, Any],
    class_ids: List[Any],
) -> Any:
    """
    Expressão SQLAlchemy: resultado pertence ao escopo geográfico/pedagógico
    com base nos snapshots (não no Student atual).
    """
    tipo = escopo_calculo.get("tipo")
    class_ids = [c for c in (class_ids or []) if c is not None]

    parts = []

    if tipo == "turma" and escopo_calculo.get("turma_id"):
        tid = ensure_uuid(escopo_calculo["turma_id"])
        if tid:
            parts.append(EvaluationResult.class_id_snapshot == tid)

    elif tipo == "serie" and escopo_calculo.get("serie_id"):
        # Turmas da série na escola (quando informada)
        escola_id = escopo_calculo.get("escola_id")
        sub = db.session.query(Class.id).filter(Class.grade_id == escopo_calculo["serie_id"])
        if escola_id:
            sub = sub.filter(cast(Class._school_id, VARCHAR) == cast(str(escola_id), VARCHAR))
        class_ids_serie = [r[0] for r in sub.all()]
        if class_ids_serie:
            parts.append(EvaluationResult.class_id_snapshot.in_(class_ids_serie))

    elif tipo == "escola" and escopo_calculo.get("escola_id"):
        sid = str(escopo_calculo["escola_id"])
        school_match = EvaluationResult.school_id_snapshot == sid
        if class_ids:
            parts.append(
                and_(
                    school_match,
                    EvaluationResult.class_id_snapshot.in_(class_ids),
                )
            )
        else:
            parts.append(school_match)

    elif tipo == "municipio" and escopo_calculo.get("municipio_id"):
        mid = escopo_calculo["municipio_id"]
        schools_in_city = db.session.query(School.id).filter(School.city_id == mid)
        restrict_school_ids = escopo_calculo.get("_restrict_school_ids")
        if restrict_school_ids is not None:
            if not restrict_school_ids:
                schools_in_city = schools_in_city.filter(School.id.is_(None))
            else:
                schools_in_city = schools_in_city.filter(
                    School.id.in_([str(item) for item in restrict_school_ids])
                )
        mun_match = EvaluationResult.school_id_snapshot.in_(schools_in_city)
        if class_ids:
            parts.append(and_(mun_match, EvaluationResult.class_id_snapshot.in_(class_ids)))
        else:
            parts.append(mun_match)

    if not parts and class_ids:
        parts.append(EvaluationResult.class_id_snapshot.in_(class_ids))

    if not parts:
        return None

    if len(parts) == 1:
        return parts[0]
    return or_(*parts)


def internal_transfer_ids_outside_class_group(
    roster_ids: Set[str],
    class_ids: Set[str],
    school_ids: Set[str],
    participations: Sequence[Tuple[Any, Any, Any]],
) -> Set[str]:
    """
    Alunos da matrícula deste grupo que já têm resultado da prova na mesma escola,
    em turma fora do grupo, e não têm resultado neste grupo.

    Não entram no universo de faltantes da turma de destino.
    A nota continua na turma de class_id_snapshot.
    Transferência para outra escola (school_id_snapshot diferente) não é removida.
    """
    roster = {str(item) for item in roster_ids if item}
    classes = {str(item) for item in class_ids if item}
    schools = {str(item) for item in school_ids if item}
    if not roster or not classes or not schools:
        return set()

    has_result_in_group: Set[str] = set()
    has_result_elsewhere_same_school: Set[str] = set()
    for student_id, school_snapshot, class_snapshot in participations:
        sid = str(student_id) if student_id else None
        if not sid or sid not in roster:
            continue
        if school_snapshot is None or str(school_snapshot) not in schools:
            continue
        if class_snapshot is None:
            continue
        if str(class_snapshot) in classes:
            has_result_in_group.add(sid)
        else:
            has_result_elsewhere_same_school.add(sid)
    return has_result_elsewhere_same_school - has_result_in_group


def load_internal_transfer_ids_to_exclude(
    test_ids: Sequence[str],
    class_ids: Sequence[Any],
    roster_student_ids: Set[str],
) -> Set[str]:
    """Consulta os resultados e devolve quem deve sair do universo de faltantes."""
    class_ids_clean = [item for item in (class_ids or []) if item is not None]
    roster_list = [str(item) for item in roster_student_ids if item]
    test_list = [str(item) for item in (test_ids or []) if item]
    if not class_ids_clean or not roster_list or not test_list:
        return set()

    school_rows = (
        db.session.query(Class._school_id)
        .filter(Class.id.in_(class_ids_clean))
        .distinct()
        .all()
    )
    school_ids = {str(row[0]) for row in school_rows if row[0]}
    if not school_ids:
        return set()

    rows = (
        db.session.query(
            EvaluationResult.student_id,
            EvaluationResult.school_id_snapshot,
            EvaluationResult.class_id_snapshot,
        )
        .filter(EvaluationResult.test_id.in_(test_list))
        .filter(EvaluationResult.student_id.in_(roster_list))
        .filter(EvaluationResult.school_id_snapshot.in_(list(school_ids)))
        .all()
    )
    return internal_transfer_ids_outside_class_group(
        set(roster_list),
        {str(item) for item in class_ids_clean},
        school_ids,
        rows,
    )


def merge_participant_student_ids(
    test_ids: List[str],
    escopo_calculo: Dict[str, Any],
    class_ids: List[Any],
    base_student_ids: Set[str],
) -> Set[str]:
    """
    União do recorte atual de alunos com alunos que têm resultado nesta avaliação
    mas já saíram das turmas (snapshots dentro do escopo).
    """
    if not test_ids:
        return set(base_student_ids)

    snap_expr = snapshot_scope_filter_expression(escopo_calculo, class_ids)
    q = db.session.query(EvaluationResult.student_id).filter(EvaluationResult.test_id.in_(test_ids))
    if snap_expr is not None:
        q = q.filter(snap_expr)
    rows = q.distinct().all()
    extra = {str(r[0]) for r in rows if r[0]}
    scope_class_ids = list(class_ids or [])
    if escopo_calculo.get("tipo") == "turma" and escopo_calculo.get("turma_id"):
        turma_id = ensure_uuid(escopo_calculo["turma_id"])
        if turma_id is not None:
            scope_class_ids = [turma_id]
    removed = load_internal_transfer_ids_to_exclude(
        test_ids, scope_class_ids, set(base_student_ids)
    )
    merged = set(base_student_ids) | extra
    if not removed:
        return merged
    return {item for item in merged if str(item) not in removed}


def query_evaluation_results_for_stats(
    test_ids: List[str],
    escopo_calculo: Dict[str, Any],
    class_ids: List[Any],
    base_student_ids: List[str],
) -> Any:
    """
    Query de EvaluationResult para estatísticas: inclui snapshots no escopo
    OU linhas legadas sem snapshot ligadas a alunos ainda no recorte base.
    """
    q = EvaluationResult.query.filter(EvaluationResult.test_id.in_(test_ids))
    snap_expr = snapshot_scope_filter_expression(escopo_calculo, class_ids)
    legacy = and_(
        EvaluationResult.school_id_snapshot.is_(None),
        EvaluationResult.class_id_snapshot.is_(None),
        EvaluationResult.student_id.in_(base_student_ids if base_student_ids else []),
    )
    if snap_expr is not None:
        if base_student_ids:
            q = q.filter(or_(snap_expr, legacy))
        else:
            q = q.filter(snap_expr)
    else:
        if base_student_ids:
            q = q.filter(EvaluationResult.student_id.in_(base_student_ids))
        else:
            q = q.filter(False)
    return q


def query_evaluation_results_for_class_group(
    evaluation_id: str,
    class_ids: List[Any],
    base_student_ids: List[str],
) -> Any:
    """Grupo de turmas (class_tests): snapshot de turma OU legado no recorte atual."""
    q = EvaluationResult.query.filter(EvaluationResult.test_id == evaluation_id)
    in_classes = EvaluationResult.class_id_snapshot.in_(class_ids) if class_ids else None
    legacy = and_(
        EvaluationResult.school_id_snapshot.is_(None),
        EvaluationResult.class_id_snapshot.is_(None),
        EvaluationResult.student_id.in_(base_student_ids if base_student_ids else []),
    )
    if in_classes is not None and base_student_ids:
        q = q.filter(or_(in_classes, legacy))
    elif in_classes is not None:
        q = q.filter(in_classes)
    elif base_student_ids:
        q = q.filter(EvaluationResult.student_id.in_(base_student_ids))
    else:
        q = q.filter(False)
    return q


def municipal_evaluation_results_query(
    city_id: str,
    evaluation_id: Union[str, Sequence[str]],
) -> Any:
    """
    Resultados de uma ou mais avaliações contando para o município:
    escola em snapshot OU (linha legada sem snapshot e aluno atualmente no município).
    """
    if isinstance(evaluation_id, str):
        test_ids = [str(evaluation_id)]
    else:
        test_ids = [str(x) for x in evaluation_id if str(x).strip()]
    if not test_ids:
        return EvaluationResult.query.filter(False)

    test_filter = (
        EvaluationResult.test_id == test_ids[0]
        if len(test_ids) == 1
        else EvaluationResult.test_id.in_(test_ids)
    )
    in_city_schools = db.session.query(School.id).filter(School.city_id == city_id)
    legacy_students = (
        db.session.query(Student.id)
        .join(Class, Student.class_id == Class.id)
        .join(School, cast(Class._school_id, VARCHAR) == cast(School.id, VARCHAR))
        .filter(School.city_id == city_id)
    )
    return EvaluationResult.query.filter(
        test_filter,
        or_(
            EvaluationResult.school_id_snapshot.in_(in_city_schools),
            and_(
                EvaluationResult.school_id_snapshot.is_(None),
                EvaluationResult.class_id_snapshot.is_(None),
                EvaluationResult.student_id.in_(legacy_students),
            ),
        ),
    )


def class_ids_for_evaluation_in_scope(
    evaluation_id: str,
    escopo_calculo: Dict[str, Any],
    restrict_class_ids: Optional[Set[Any]] = None,
) -> List[Any]:
    """Turmas (ClassTest) onde a avaliação foi aplicada, respeitando o escopo hierárquico."""
    from app.models.classTest import ClassTest

    effective_restrict = restrict_class_ids
    if effective_restrict is None:
        effective_restrict = escopo_calculo.get("restrict_class_ids")

    q = ClassTest.query.filter(ClassTest.test_id == str(evaluation_id))
    if effective_restrict is not None:
        if not effective_restrict:
            return []
        q = q.filter(ClassTest.class_id.in_(list(effective_restrict)))

    tipo = escopo_calculo.get("tipo")
    if tipo == "turma" and escopo_calculo.get("turma_id"):
        turma_uuid = ensure_uuid(escopo_calculo["turma_id"])
        if turma_uuid:
            q = q.filter(ClassTest.class_id == turma_uuid)
    elif tipo in ("serie", "escola", "municipio"):
        q = q.join(Class, ClassTest.class_id == Class.id)
        if tipo == "serie" and escopo_calculo.get("serie_id"):
            q = q.filter(Class.grade_id == escopo_calculo["serie_id"])
            if escopo_calculo.get("escola_id"):
                q = q.filter(
                    cast(Class._school_id, VARCHAR) == cast(str(escopo_calculo["escola_id"]), VARCHAR)
                )
        elif tipo == "escola" and escopo_calculo.get("escola_id"):
            q = q.filter(
                cast(Class._school_id, VARCHAR) == cast(str(escopo_calculo["escola_id"]), VARCHAR)
            )
        elif tipo == "municipio" and escopo_calculo.get("municipio_id"):
            q = q.join(
                School,
                cast(Class._school_id, VARCHAR) == cast(School.id, VARCHAR),
            ).filter(School.city_id == escopo_calculo["municipio_id"])

    class_ids = list({ct.class_id for ct in q.all() if ct.class_id})
    restrict_school_ids = escopo_calculo.get("_restrict_school_ids")
    if restrict_school_ids is None:
        return class_ids
    if not restrict_school_ids or not class_ids:
        return []
    allowed = {str(item) for item in restrict_school_ids}
    rows = Class.query.filter(Class.id.in_(class_ids)).all()
    return [row.id for row in rows if str(row.school_id) in allowed]


def prefetch_placement_from_results(
    evaluation_results: List[Any],
) -> Tuple[Dict[str, School], Dict[Any, Class], Dict[Any, Grade]]:
    """Carrega escolas/turmas/séries referenciadas nos snapshots (em lote)."""
    school_ids: Set[str] = set()
    class_ids: Set[Any] = set()
    grade_ids: Set[Any] = set()
    for er in evaluation_results or []:
        if getattr(er, "school_id_snapshot", None):
            school_ids.add(str(er.school_id_snapshot))
        if getattr(er, "class_id_snapshot", None):
            class_ids.add(er.class_id_snapshot)
        if getattr(er, "grade_id_snapshot", None):
            grade_ids.add(er.grade_id_snapshot)

    schools_by_id: Dict[str, School] = {}
    if school_ids:
        schools_by_id = {
            str(s.id): s for s in School.query.filter(School.id.in_(school_ids)).all()
        }

    classes_by_id: Dict[Any, Class] = {}
    if class_ids:
        for c in (
            Class.query.options(joinedload(Class.grade))
            .filter(Class.id.in_(class_ids))
            .all()
        ):
            classes_by_id[c.id] = c
            if getattr(c, "grade_id", None):
                grade_ids.add(c.grade_id)

    grades_by_id: Dict[Any, Grade] = {}
    if grade_ids:
        grades_by_id = {g.id: g for g in Grade.query.filter(Grade.id.in_(grade_ids)).all()}

    return schools_by_id, classes_by_id, grades_by_id


def resolve_participant_display_context(
    student: Optional[Student],
    evaluation_result: EvaluationResult,
    schools_by_id: Dict[str, School],
    classes_by_id: Dict[Any, Class],
    grades_by_id: Optional[Dict[Any, Grade]] = None,
) -> Dict[str, Any]:
    """
    Nome do aluno (Student) e colocação escolar preferindo snapshots do resultado.
    """
    from app.utils.class_label_helpers import normalize_shift

    nome = (getattr(student, "name", None) or "").strip() or "N/A"
    grades_by_id = grades_by_id or {}

    has_snapshot = bool(
        getattr(evaluation_result, "school_id_snapshot", None)
        or getattr(evaluation_result, "class_id_snapshot", None)
    )

    if has_snapshot:
        escola_id = (
            str(evaluation_result.school_id_snapshot)
            if evaluation_result.school_id_snapshot
            else None
        )
        escola_nome = "N/A"
        if escola_id and escola_id in schools_by_id:
            escola_nome = schools_by_id[escola_id].name or "N/A"

        turma_nome = "N/A"
        serie_nome = "N/A"
        turma_shift = ""
        cid = evaluation_result.class_id_snapshot
        if cid and cid in classes_by_id:
            cls_obj = classes_by_id[cid]
            turma_nome = cls_obj.name or "N/A"
            turma_shift = normalize_shift(getattr(cls_obj, "shift", None)) or ""
            if cls_obj.grade:
                serie_nome = cls_obj.grade.name or "N/A"
            elif getattr(cls_obj, "grade_id", None) and cls_obj.grade_id in grades_by_id:
                serie_nome = grades_by_id[cls_obj.grade_id].name or "N/A"
        elif evaluation_result.grade_id_snapshot and evaluation_result.grade_id_snapshot in grades_by_id:
            serie_nome = grades_by_id[evaluation_result.grade_id_snapshot].name or "N/A"

        return {
            "nome": nome,
            "escola_id": escola_id,
            "escola": escola_nome,
            "serie": serie_nome,
            "turma": turma_nome,
            "shift": turma_shift,
            "contexto_colocacao": "snapshot",
        }

    turma_nome = "N/A"
    serie_nome = "N/A"
    escola_nome = "N/A"
    escola_id = None
    turma_shift = ""
    if student and getattr(student, "class_", None):
        turma_nome = student.class_.name or "N/A"
        turma_shift = normalize_shift(getattr(student.class_, "shift", None)) or ""
        if student.class_.grade:
            serie_nome = student.class_.grade.name or "N/A"
        sid = getattr(student.class_, "school_id", None)
        if sid:
            escola_id = str(sid)
            school = schools_by_id.get(escola_id)
            if not school:
                school = School.query.get(escola_id)
            if school:
                escola_nome = school.name or "N/A"

    return {
        "nome": nome,
        "escola_id": escola_id,
        "escola": escola_nome,
        "serie": serie_nome,
        "turma": turma_nome,
        "shift": turma_shift,
        "contexto_colocacao": "atual",
    }


def student_ids_for_class_group_with_snapshots(
    evaluation_id: str,
    class_ids: List[Any],
    base_student_ids: Set[str],
) -> Set[str]:
    extra = (
        db.session.query(EvaluationResult.student_id)
        .filter(EvaluationResult.test_id == evaluation_id)
        .filter(EvaluationResult.class_id_snapshot.in_(class_ids))
        .distinct()
        .all()
    )
    roster = {str(item) for item in base_student_ids if item}
    ids = {str(r[0]) for r in extra if r[0]}
    merged = roster | ids
    removed = load_internal_transfer_ids_to_exclude([evaluation_id], class_ids, roster)
    if not removed:
        return merged
    return {item for item in merged if str(item) not in removed}
