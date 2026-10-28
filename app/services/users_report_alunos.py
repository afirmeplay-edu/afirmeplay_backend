# -*- coding: utf-8 -*-
"""Recorte Regular / Educação Especial do relatório de usuários.

``todos`` não altera o payload. Os outros filtros usam a mesma regra de
``aluno_entra_no_filtro`` (subturma ADAP ou série antiga Suporte N).
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from app.services.alunos_resultado_filtro import aluno_entra_no_filtro, filtro_restringe
from app.services.special_education import SpecialEducationStatus

_NIVEIS = (1, 2, 3)


def nivel_adap(status: SpecialEducationStatus) -> Optional[int]:
    if status.is_special and status.level in _NIVEIS:
        return int(status.level)
    return None


def _vazio() -> Dict[str, int]:
    return {
        "students": 0,
        "regulares": 0,
        "educacao_especial": 0,
        "adap_1": 0,
        "adap_2": 0,
        "adap_3": 0,
    }


def _somar(acc: Dict[str, int], status: SpecialEducationStatus) -> None:
    acc["students"] += 1
    nivel = nivel_adap(status)
    if nivel is not None:
        acc["educacao_especial"] += 1
        acc[f"adap_{nivel}"] += 1
    elif not status.is_special:
        acc["regulares"] += 1


def escolhidos(registros: Iterable[Dict[str, Any]], filtro: Optional[str]) -> List[Dict[str, Any]]:
    if not filtro_restringe(filtro):
        return list(registros)
    return [
        row
        for row in registros
        if aluno_entra_no_filtro(row["status"], filtro or "todos")
    ]


def contatos_do_recorte(
    registros: Iterable[Dict[str, Any]], filtro: Optional[str]
) -> List[Dict[str, Any]]:
    """Lista de alunos do recorte, em ordem alfabética. ``adap`` só traz nível 1, 2 ou 3."""
    rows = escolhidos(registros, filtro)
    if filtro == "adap":
        rows = [row for row in rows if nivel_adap(row["status"]) is not None]
    rows.sort(key=lambda row: (str(row.get("name") or "")).upper())
    return rows


def _publico(row: Dict[str, Any]) -> Dict[str, Any]:
    status: SpecialEducationStatus = row["status"]
    return {
        "id": row.get("id"),
        "name": row.get("name") or "",
        "email": row.get("email") or "",
        "school_id": row.get("school_id") or None,
        "school_name": row.get("school_name") or "",
        "grade_id": row.get("grade_id") or None,
        "grade_name": row.get("grade_name") or "",
        "class_id": row.get("class_id") or None,
        "class_name": row.get("class_name") or "",
        "nivel_adap": nivel_adap(status),
    }


def aplicar_recorte_relatorio_usuarios(
    payload: Dict[str, Any],
    registros: Iterable[Dict[str, Any]],
    filtro: Optional[str],
) -> Dict[str, Any]:
    """Devolve o mesmo payload quando o filtro é ``todos``."""
    if not filtro_restringe(filtro):
        return payload

    rows = escolhidos(registros, filtro)
    geral_acc = _vazio()
    por_escola: Dict[str, Dict[str, Any]] = {}
    por_serie: Dict[str, Dict[str, Any]] = {}
    por_turma: Dict[str, Dict[str, Any]] = {}
    sem_escola = _vazio()

    origem_turma = {
        str(item.get("class_id") or ""): item for item in payload.get("by_class") or []
    }
    origem_escola = {
        str(item.get("school_id") or ""): item for item in payload.get("by_school") or []
    }
    origem_serie = {
        str(item.get("grade_id") or ""): item for item in payload.get("by_grade") or []
    }

    for row in rows:
        status = row["status"]
        _somar(geral_acc, status)
        school_id = str(row.get("school_id") or "")
        grade_id = str(row.get("grade_id") or "")
        class_id = str(row.get("class_id") or "")
        if not school_id:
            _somar(sem_escola, status)
        else:
            escola = por_escola.setdefault(school_id, _vazio())
            _somar(escola, status)
            escola["school_id"] = school_id
            escola["school_name"] = row.get("school_name") or ""
        if grade_id:
            serie = por_serie.setdefault(grade_id, _vazio())
            _somar(serie, status)
            serie["grade_id"] = grade_id
            serie["grade_name"] = row.get("grade_name") or ""
        if class_id:
            turma = por_turma.setdefault(class_id, _vazio())
            _somar(turma, status)
            turma["class_id"] = class_id
            turma["class_name"] = row.get("class_name") or ""
            turma["school_id"] = school_id or None
            turma["school_name"] = row.get("school_name") or ("Sem escola" if not school_id else "")
            turma["grade_id"] = grade_id or None
            turma["grade_name"] = row.get("grade_name") or ""

    def _linha_escola(school_id: str, acc: Dict[str, Any]) -> Dict[str, Any]:
        origem = origem_escola.get(school_id) or {}
        linha = {
            "school_id": school_id,
            "school_name": acc.get("school_name") or origem.get("school_name"),
            "students": acc["students"],
            "teachers": int(origem.get("teachers") or 0),
            "directors": int(origem.get("directors") or 0),
            "coordinators": int(origem.get("coordinators") or 0),
        }
        linha.update({k: acc[k] for k in ("regulares", "educacao_especial", "adap_1", "adap_2", "adap_3")})
        return linha

    def _linha_serie(grade_id: str, acc: Dict[str, Any]) -> Dict[str, Any]:
        origem = origem_serie.get(grade_id) or {}
        linha = {
            "grade_id": grade_id,
            "grade_name": acc.get("grade_name") or origem.get("grade_name"),
            "students": acc["students"],
            "teachers": int(origem.get("teachers") or 0),
        }
        linha.update({k: acc[k] for k in ("regulares", "educacao_especial", "adap_1", "adap_2", "adap_3")})
        return linha

    def _linha_turma(class_id: str, acc: Dict[str, Any]) -> Dict[str, Any]:
        origem = origem_turma.get(class_id) or {}
        school_id = str(acc.get("school_id") or "")
        escola = origem_escola.get(school_id) or {}
        linha = {
            "class_id": class_id,
            "class_name": acc.get("class_name") or origem.get("class_name"),
            "school_id": school_id or None,
            "school_name": acc.get("school_name") or origem.get("school_name"),
            "grade_id": acc.get("grade_id") or origem.get("grade_id"),
            "grade_name": acc.get("grade_name") or origem.get("grade_name"),
            "students": acc["students"],
            "teachers": int(origem.get("teachers") or 0),
            "directors": int(escola.get("directors") or origem.get("directors") or 0),
            "coordinators": int(escola.get("coordinators") or origem.get("coordinators") or 0),
        }
        linha.update({k: acc[k] for k in ("regulares", "educacao_especial", "adap_1", "adap_2", "adap_3")})
        return linha

    general = dict(payload.get("general") or {})
    general["students"] = geral_acc["students"]
    for chave in ("regulares", "educacao_especial", "adap_1", "adap_2", "adap_3"):
        general[chave] = geral_acc[chave]

    payload = dict(payload)
    payload["general"] = general
    payload["alunos_filtro"] = filtro
    payload["by_school"] = [
        _linha_escola(school_id, acc)
        for school_id, acc in sorted(
            por_escola.items(), key=lambda item: str(item[1].get("school_name") or "")
        )
        if acc["students"] > 0
    ]
    payload["by_grade"] = [
        _linha_serie(grade_id, acc)
        for grade_id, acc in por_serie.items()
        if acc["students"] > 0
    ]
    payload["by_class"] = [
        _linha_turma(class_id, acc)
        for class_id, acc in por_turma.items()
        if acc["students"] > 0
    ]
    payload["alunos"] = [_publico(row) for row in contatos_do_recorte(registros, filtro)]
    if sem_escola["students"] > 0:
        payload["sem_escola"] = sem_escola
    else:
        payload.pop("sem_escola", None)
    return payload


def carregar_registros_usuarios() -> List[Dict[str, Any]]:
    """Lê os alunos do tenant atual. Não grava nada."""
    from app.models.grades import Grade
    from app.models.school import School
    from app.models.student import Student
    from app.models.studentClass import Class
    from app.models.user import User
    from app.services.special_education import is_special_education_many

    students = Student.query.all()
    statuses = is_special_education_many(students)
    classes = {str(item.id): item for item in Class.query.all()}
    grades = {str(item.id): item for item in Grade.query.all()}
    schools = {str(item.id): item for item in School.query.all()}
    user_ids = [student.user_id for student in students if getattr(student, "user_id", None)]
    users = {}
    if user_ids:
        users = {str(user.id): user for user in User.query.filter(User.id.in_(user_ids)).all()}

    registros = []
    for student in students:
        classe = classes.get(str(student.class_id)) if student.class_id else None
        grade_id = None
        if classe is not None and getattr(classe, "grade_id", None) is not None:
            grade_id = classe.grade_id
        elif getattr(student, "grade_id", None) is not None:
            grade_id = student.grade_id
        grade = grades.get(str(grade_id)) if grade_id is not None else None
        school_id = getattr(student, "school_id", None) or (
            getattr(classe, "school_id", None) if classe is not None else None
        )
        school = schools.get(str(school_id)) if school_id else None
        user = users.get(str(student.user_id)) if getattr(student, "user_id", None) else None
        nome = (getattr(student, "name", None) or getattr(user, "name", None) or "").strip()
        email = (getattr(user, "email", None) or "").strip()
        registros.append(
            {
                "id": str(student.id),
                "name": nome,
                "email": email,
                "school_id": str(school_id) if school_id else None,
                "school_name": getattr(school, "name", None) or "",
                "grade_id": str(grade_id) if grade_id is not None else None,
                "grade_name": getattr(grade, "name", None) or "",
                "class_id": str(student.class_id) if student.class_id else None,
                "class_name": getattr(classe, "name", None) or "",
                "status": statuses.get(
                    str(student.id), SpecialEducationStatus(False, None, None)
                ),
            }
        )
    return registros
