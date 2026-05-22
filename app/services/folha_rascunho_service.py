# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

from app.models.answerSheetGabarito import AnswerSheetGabarito
from app.models.city import City
from app.models.school import School
from app.models.student import Student
from app.models.studentClass import Class
from app.models.test import Test
from app.models.classTest import ClassTest
from app.permissions.utils import get_manager_school, get_teacher_schools
from app.report_analysis.answer_sheet_report_builder import get_answer_sheet_target_classes_for_report
from app.routes.lista_frequencia_routes import (
    _status_estudante_avaliacao,
    _status_estudante_cartao_resposta,
)
from app.utils.uuid_helpers import ensure_uuid


VALID_MODOS = frozenset({"personalizada", "avaliacao", "cartao_resposta"})


class FolhaRascunhoValidationError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


def _user_role(user: Dict[str, Any]) -> str:
    role = user.get("role")
    return (role.value if hasattr(role, "value") else str(role or "")).lower()


def _allowed_school_ids(user: Dict[str, Any]) -> Optional[Set[str]]:
    role = _user_role(user)
    if role in ("admin", "tecadm"):
        return None
    if role in ("diretor", "coordenador"):
        school_id = get_manager_school(user["id"])
        return {school_id} if school_id else set()
    if role == "professor":
        return set(get_teacher_schools(user["id"]) or [])
    return set()


def _norm_param(value: Optional[str]) -> str:
    v = str(value or "").strip()
    if not v or v.lower() == "all":
        return ""
    return v


def _parse_filters(args: Dict[str, Any]) -> Dict[str, str]:
    modo = _norm_param(args.get("modo"))
    if modo not in VALID_MODOS:
        raise FolhaRascunhoValidationError("Parâmetro 'modo' inválido.")

    municipio = _norm_param(args.get("municipio"))
    if not municipio:
        raise FolhaRascunhoValidationError("Selecione o município.")

    escola = _norm_param(args.get("escola"))
    serie = _norm_param(args.get("serie"))
    turma = _norm_param(args.get("turma"))
    evaluation_id = _norm_param(args.get("evaluation_id"))
    answer_sheet_id = _norm_param(args.get("answer_sheet_id"))

    if modo == "personalizada" and not escola:
        raise FolhaRascunhoValidationError("Selecione a escola no modo personalizável.")

    if modo == "avaliacao" and not evaluation_id:
        raise FolhaRascunhoValidationError("Selecione uma avaliação.")

    if modo == "cartao_resposta" and not answer_sheet_id:
        raise FolhaRascunhoValidationError("Selecione um cartão-resposta.")

    return {
        "modo": modo,
        "municipio": municipio,
        "escola": escola,
        "serie": serie,
        "turma": turma,
        "evaluation_id": evaluation_id,
        "answer_sheet_id": answer_sheet_id,
    }


def _school_allowed(school_id: str, allowed: Optional[Set[str]]) -> bool:
    if allowed is None:
        return True
    return school_id in allowed


def _class_context(classe: Class) -> Tuple[str, str, str, str, str, str, str]:
    school = classe.school
    grade = classe.grade if hasattr(classe, "grade") else None
    school_id = str(school.id) if school else ""
    school_name = str(school.name or "").strip() if school else "Escola"
    grade_id = str(grade.id) if grade else ""
    grade_name = str(grade.name or "").strip() if grade else "Sem série"
    class_id = str(classe.id)
    class_name = str(classe.name or "").strip() or "Turma"
    turno = str(getattr(classe, "turno", None) or "").strip()
    turma_label = str(getattr(classe, "turma", None) or "").strip() or class_name
    return school_id, school_name, grade_id, grade_name, class_id, turma_label, turno


def _students_enrolled(classe: Class) -> List[Dict[str, str]]:
    rows = Student.query.filter_by(class_id=classe.id).order_by(Student.name).all()
    out: List[Dict[str, str]] = []
    for student in rows:
        name = str(student.name or "").strip()
        if name:
            out.append({"id": str(student.id), "name": name})
    return out


def _students_participants_avaliacao(classe: Class, test: Test) -> List[Dict[str, str]]:
    enrolled = Student.query.filter_by(class_id=classe.id).all()
    student_ids = [str(s.id) for s in enrolled]
    status_map = _status_estudante_avaliacao(student_ids, test.id)
    out: List[Dict[str, str]] = []
    for student in enrolled:
        if status_map.get(str(student.id)) != "P":
            continue
        name = str(student.name or "").strip()
        if name:
            out.append({"id": str(student.id), "name": name})
    return sorted(out, key=lambda item: item["name"].lower())


def _students_participants_cartao(classe: Class, gab: AnswerSheetGabarito) -> List[Dict[str, str]]:
    enrolled = Student.query.filter_by(class_id=classe.id).all()
    student_ids = [str(s.id) for s in enrolled]
    status_map = _status_estudante_cartao_resposta(student_ids, gab.id)
    out: List[Dict[str, str]] = []
    for student in enrolled:
        if status_map.get(str(student.id)) != "P":
            continue
        name = str(student.name or "").strip()
        if name:
            out.append({"id": str(student.id), "name": name})
    return sorted(out, key=lambda item: item["name"].lower())


def _append_class_to_tree(
    tree: Dict[str, Dict[str, Any]],
    classe: Class,
    students: List[Dict[str, str]],
) -> None:
    if not students:
        return
    school_id, school_name, grade_id, grade_name, class_id, turma_label, turno = _class_context(classe)
    if not school_id:
        return

    school_bucket = tree.setdefault(
        school_id,
        {"id": school_id, "name": school_name, "_series": {}},
    )
    series_bucket = school_bucket["_series"].setdefault(
        grade_id or f"class-{class_id}",
        {"id": grade_id or "", "name": grade_name, "_classes": {}},
    )
    series_bucket["_classes"][class_id] = {
        "id": class_id,
        "name": turma_label,
        "turno": turno,
        "students": sorted(students, key=lambda s: s["name"].lower()),
    }


def _collect_personalizada(
    filters: Dict[str, str],
    allowed: Optional[Set[str]],
) -> Dict[str, Dict[str, Any]]:
    city_id = filters["municipio"]
    school_id = filters["escola"]
    grade_id = filters["serie"]
    class_id = filters["turma"]

    if not _school_allowed(school_id, allowed):
        return {}

    query = (
        Class.query.join(School, Class.school_id == School.id)
        .filter(School.city_id == city_id, School.id == school_id)
    )
    if grade_id:
        grade_uuid = ensure_uuid(grade_id)
        if not grade_uuid:
            raise FolhaRascunhoValidationError("serie inválida.")
        query = query.filter(Class.grade_id == grade_uuid)
    if class_id:
        class_uuid = ensure_uuid(class_id)
        if not class_uuid:
            raise FolhaRascunhoValidationError("turma inválida.")
        query = query.filter(Class.id == class_uuid)

    classes = query.order_by(Class.grade_id, Class.name).all()
    tree: Dict[str, Dict[str, Any]] = {}
    for classe in classes:
        students = _students_enrolled(classe)
        _append_class_to_tree(tree, classe, students)
    return tree


def _filter_classes_avaliacao(
    class_ids: List[Any],
    filters: Dict[str, str],
    allowed: Optional[Set[str]],
) -> List[Class]:
    city_id = filters["municipio"]
    query = (
        Class.query.filter(Class.id.in_(class_ids))
        .join(School, Class.school_id == School.id)
        .filter(School.city_id == city_id)
    )
    if filters["escola"]:
        query = query.filter(School.id == filters["escola"])
    if filters["serie"]:
        grade_uuid = ensure_uuid(filters["serie"])
        if not grade_uuid:
            raise FolhaRascunhoValidationError("serie inválida.")
        query = query.filter(Class.grade_id == grade_uuid)
    if filters["turma"]:
        class_uuid = ensure_uuid(filters["turma"])
        if not class_uuid:
            raise FolhaRascunhoValidationError("turma inválida.")
        query = query.filter(Class.id == class_uuid)

    classes = query.order_by(School.name, Class.grade_id, Class.name).all()
    return [c for c in classes if _school_allowed(str(c.school_id), allowed)]


def _collect_avaliacao(
    filters: Dict[str, str],
    allowed: Optional[Set[str]],
) -> Tuple[Dict[str, Dict[str, Any]], str]:
    test = Test.query.get(filters["evaluation_id"])
    if not test:
        raise FolhaRascunhoValidationError("Avaliação não encontrada.")

    class_tests = ClassTest.query.filter_by(test_id=test.id).all()
    if not class_tests:
        raise FolhaRascunhoValidationError("Avaliação não está vinculada a nenhuma turma.")

    class_ids = [ct.class_id for ct in class_tests]
    classes = _filter_classes_avaliacao(class_ids, filters, allowed)

    tree: Dict[str, Dict[str, Any]] = {}
    for classe in classes:
        students = _students_participants_avaliacao(classe, test)
        _append_class_to_tree(tree, classe, students)

    titulo = str(test.title or "").strip()
    return tree, titulo


def _collect_cartao_resposta(
    filters: Dict[str, str],
    allowed: Optional[Set[str]],
) -> Tuple[Dict[str, Dict[str, Any]], str]:
    gab = AnswerSheetGabarito.query.get(filters["answer_sheet_id"])
    if not gab:
        raise FolhaRascunhoValidationError("Cartão-resposta não encontrado.")

    turmas_alvo = get_answer_sheet_target_classes_for_report(gab, "city", filters["municipio"])
    if not turmas_alvo:
        raise FolhaRascunhoValidationError("Nenhuma turma encontrada para este cartão neste município.")

    classes = list(turmas_alvo)
    if filters["escola"]:
        classes = [c for c in classes if str(c.school_id) == filters["escola"]]
    if filters["serie"]:
        grade_uuid = ensure_uuid(filters["serie"])
        if not grade_uuid:
            raise FolhaRascunhoValidationError("serie inválida.")
        classes = [c for c in classes if c.grade_id == grade_uuid]
    if filters["turma"]:
        class_uuid = ensure_uuid(filters["turma"])
        if not class_uuid:
            raise FolhaRascunhoValidationError("turma inválida.")
        classes = [c for c in classes if c.id == class_uuid]

    classes = [c for c in classes if _school_allowed(str(c.school_id), allowed)]
    classes.sort(key=lambda c: (str(c.school.name if c.school else ""), str(c.grade_id or ""), str(c.name or "")))

    tree: Dict[str, Dict[str, Any]] = {}
    for classe in classes:
        students = _students_participants_cartao(classe, gab)
        _append_class_to_tree(tree, classe, students)

    titulo = str(gab.title or "").strip() if getattr(gab, "title", None) else ""
    return tree, titulo


def _tree_to_response(tree: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
    escolas: List[Dict[str, Any]] = []
    for school_id in sorted(tree.keys(), key=lambda k: tree[k]["name"].lower()):
        school = tree[school_id]
        series_list: List[Dict[str, Any]] = []
        for _grade_key in sorted(
            school["_series"].keys(),
            key=lambda k: school["_series"][k]["name"].lower(),
        ):
            serie = school["_series"][_grade_key]
            classes_list = [
                {
                    "id": c["id"],
                    "name": c["name"],
                    "turno": c.get("turno") or "",
                    "students": c["students"],
                }
                for c in sorted(serie["_classes"].values(), key=lambda x: x["name"].lower())
            ]
            if not classes_list:
                continue
            series_list.append(
                {
                    "id": serie["id"],
                    "name": serie["name"],
                    "classes": classes_list,
                }
            )
        if not series_list:
            continue
        escolas.append(
            {
                "id": school["id"],
                "name": school["name"],
                "series": series_list,
            }
        )
    return escolas


def _count_covers(escolas: List[Dict[str, Any]]) -> int:
    covers = 0
    if len(escolas) > 1:
        covers += len(escolas)
    for escola in escolas:
        series = escola.get("series") or []
        if len(series) > 1:
            covers += len(series)
        for serie in series:
            classes = serie.get("classes") or []
            if len(classes) > 1:
                covers += len(classes)
    return covers


def _count_totals(escolas: List[Dict[str, Any]]) -> Dict[str, int]:
    schools = len(escolas)
    series = sum(len(e.get("series") or []) for e in escolas)
    classes = 0
    students = 0
    for escola in escolas:
        for serie in escola.get("series") or []:
            for turma in serie.get("classes") or []:
                classes += 1
                students += len(turma.get("students") or [])
    return {
        "schools": schools,
        "series": series,
        "classes": classes,
        "students": students,
        "covers": _count_covers(escolas),
        "pages": _count_covers(escolas) + students,
    }


class FolhaRascunhoService:
    @staticmethod
    def get_dados(user: Dict[str, Any], args: Dict[str, Any]) -> Dict[str, Any]:
        filters = _parse_filters(args)
        allowed = _allowed_school_ids(user)

        city = City.query.get(filters["municipio"])
        if not city:
            raise FolhaRascunhoValidationError("Município não encontrado.")

        city_name = str(city.name or "").strip().upper()
        prefeitura_label = f"PREFEITURA MUNICIPAL DE {city_name}"

        avaliacao_titulo = ""
        modo = filters["modo"]

        if modo == "personalizada":
            tree = _collect_personalizada(filters, allowed)
        elif modo == "avaliacao":
            tree, avaliacao_titulo = _collect_avaliacao(filters, allowed)
        else:
            tree, avaliacao_titulo = _collect_cartao_resposta(filters, allowed)

        escolas = _tree_to_response(tree)
        if not escolas:
            raise FolhaRascunhoValidationError("Nenhum aluno encontrado para os filtros selecionados.")

        return {
            "municipio": {
                "id": str(city.id),
                "name": str(city.name or ""),
                "state": str(city.state or ""),
                "prefeitura_label": prefeitura_label,
            },
            "ano": datetime.now().year,
            "avaliacao_titulo": avaliacao_titulo or None,
            "modo": modo,
            "escolas": escolas,
            "totals": _count_totals(escolas),
        }
