# -*- coding: utf-8 -*-
"""Painel do Indicador Criança Alfabetizada da avaliação escrita.

Lê as correções já gravadas. O município é o da sessão. O recorte desce
escola → série → turma → aluno. Percentuais e a nota saem com uma casa.
"""
from __future__ import annotations

import csv
import io
import uuid
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import noload

from app import db
from app.afirme_ler.models.reading_written_test import (
    ReadingWrittenTest,
    ReadingWrittenTestCorrection,
)
from app.afirme_ler.services.written_test_writing_grade import TEXT_NUMBER, WORD_NUMBERS, _links
from app.models.grades import Grade
from app.models.school import School
from app.models.skill import Skill
from app.models.student import Student
from app.models.studentClass import Class

ONE = Decimal("0.1")
TOTAL_MAX = 34
SCORE_MIN = 70
READING_MIN = 11
WORDS_MIN = 2
TEXT_MIN = 7
TEXT_QUESTION_MAX = 14
CSV_HEADER = (
    "aluno_id",
    "aluno",
    "turma",
    "leitura",
    "palavras",
    "texto",
    "total",
    "nota_100",
    "apto_diagnostico",
)


def _one(value: Decimal) -> float:
    return float(value.quantize(ONE, rounding=ROUND_HALF_UP))


def _pct(part: int, whole: int) -> Optional[float]:
    if whole <= 0:
        return None
    return _one(Decimal(part) * Decimal(100) / Decimal(whole))


def _score(total: int) -> float:
    return _one(Decimal(total) * Decimal(100) / Decimal(TOTAL_MAX))


def _mean(values: List[float]) -> Optional[float]:
    if not values:
        return None
    total = sum((Decimal(str(value)) for value in values), Decimal(0))
    return _one(total / Decimal(len(values)))


def _param(filters: Dict[str, Any], *keys: str) -> Optional[str]:
    for key in keys:
        value = filters.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _uuid_param(value: str, label: str) -> str:
    try:
        return str(uuid.UUID(value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} deve ser um UUID.") from exc


def _as_int(value: Any) -> Optional[int]:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _max_points(number: int) -> int:
    if 1 <= number <= 16:
        return 1
    if number in WORD_NUMBERS:
        return 2
    if number == TEXT_NUMBER:
        return TEXT_QUESTION_MAX
    return 0


def _class_ids(written_test: ReadingWrittenTest) -> List[str]:
    raw = [str(item) for item in (written_test.class_ids or []) if item]
    if raw:
        return raw
    return sorted({str(row.class_id) for row in (written_test.applications or [])})


def _parse_uuid_list(values: List[str]) -> List[uuid.UUID]:
    parsed = []
    for value in values:
        try:
            parsed.append(uuid.UUID(str(value)))
        except (TypeError, ValueError):
            continue
    return parsed


def _scope_level(escola_id, serie_id, turma_id, estudante_id) -> str:
    if estudante_id:
        return "aluno"
    if turma_id:
        return "turma"
    if serie_id:
        return "serie"
    if escola_id:
        return "escola"
    return "municipio"


def _item_points(stored: Dict[str, Any]) -> Dict[int, int]:
    points: Dict[int, int] = {}
    objective = stored.objective or {}
    for item in objective.get("items") or []:
        number = _as_int(item.get("number"))
        value = _as_int(item.get("points"))
        if number is not None and value is not None:
            points[number] = value
    writing = stored.writing or {}
    for item in writing.get("words") or []:
        number = _as_int(item.get("number"))
        value = _as_int(item.get("points"))
        if number is not None and value is not None:
            points[number] = value
    production = writing.get("production") or {}
    value = _as_int(production.get("points"))
    if value is not None:
        points[TEXT_NUMBER] = value
    return points


def _is_finalized(row: ReadingWrittenTestCorrection) -> bool:
    writing = row.writing or {}
    if writing.get("published") is not True:
        return False
    reading = _as_int((row.objective or {}).get("points"))
    words = _as_int(writing.get("wordPoints"))
    text = _as_int(writing.get("textPoints"))
    return reading is not None and words is not None and text is not None


def _skills_by_id(skill_ids: List[str]) -> Dict[str, Skill]:
    parsed = _parse_uuid_list(skill_ids)
    if not parsed:
        return {}
    rows = (
        Skill.query.options(noload(Skill.grades))
        .filter(Skill.id.in_(parsed))
        .all()
    )
    return {str(row.id): row for row in rows}


def _question_catalog(written_test_id: str) -> List[Dict[str, Any]]:
    catalog = []
    skill_ids = []
    for entry in _links(written_test_id):
        number = int(entry["number"])
        if _max_points(number) <= 0:
            continue
        question = entry["question"]
        skill_id = str(question.skill).strip() if question.skill else ""
        if skill_id:
            skill_ids.append(skill_id)
        catalog.append({
            "number": number,
            "code": f"Q{number}",
            "max_points": _max_points(number),
            "skill_id": skill_id or None,
        })
    found = _skills_by_id(skill_ids)
    for item in catalog:
        skill = found.get(item["skill_id"] or "")
        if skill is None:
            item["skill_code"] = item["skill_id"]
            item["skill_label"] = item["skill_id"]
        else:
            item["skill_code"] = skill.code
            item["skill_label"] = skill.description
    return catalog


def _load(written_test_id: str, filters: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    filters = filters or {}
    written_test = db.session.get(ReadingWrittenTest, str(written_test_id))
    if written_test is None:
        raise LookupError("Avaliação escrita não encontrada.")

    escola_id = _param(filters, "escolaId", "escola_id", "schoolId", "school_id")
    serie_raw = _param(filters, "serieId", "serie_id", "gradeId", "grade_id")
    turma_raw = _param(filters, "turmaId", "turma_id", "classId", "class_id")
    estudante_id = _param(filters, "estudanteId", "estudante_id", "studentId", "student_id")
    serie_id = _uuid_param(serie_raw, "serieId") if serie_raw else None
    turma_id = _uuid_param(turma_raw, "turmaId") if turma_raw else None

    class_ids = _class_ids(written_test)
    classes = (
        Class.query.filter(Class.id.in_(_parse_uuid_list(class_ids))).all()
        if class_ids else []
    )
    by_class = {str(klass.id): klass for klass in classes}
    school_ids = {str(klass.school_id) for klass in classes if klass.school_id}
    grade_ids = {str(klass.grade_id) for klass in classes if klass.grade_id}

    if escola_id and escola_id not in school_ids:
        raise ValueError("A escola não faz parte desta avaliação.")
    if serie_id and serie_id not in grade_ids:
        raise ValueError("A série não faz parte desta avaliação.")
    if turma_id and turma_id not in by_class:
        raise ValueError("A turma não faz parte desta avaliação.")

    selected = []
    for klass in classes:
        if escola_id and str(klass.school_id or "") != escola_id:
            continue
        if serie_id and str(klass.grade_id or "") != serie_id:
            continue
        if turma_id and str(klass.id) != turma_id:
            continue
        selected.append(klass)

    schools = {
        str(row.id): row
        for row in School.query.filter(School.id.in_(list(school_ids))).all()
    } if school_ids else {}
    grades = {
        str(row.id): row
        for row in Grade.query.filter(Grade.id.in_(_parse_uuid_list(list(grade_ids)))).all()
    } if grade_ids else {}

    selected_ids = [klass.id for klass in selected]
    students = (
        Student.query.filter(Student.class_id.in_(selected_ids)).all()
        if selected_ids else []
    )
    by_student = {str(student.id): student for student in students}
    if estudante_id and estudante_id not in by_student:
        raise ValueError("O aluno não está no recorte desta avaliação.")
    if estudante_id:
        students = [by_student[estudante_id]]

    corrections = {}
    student_ids = [str(student.id) for student in students]
    if student_ids:
        rows = (
            ReadingWrittenTestCorrection.query
            .filter(ReadingWrittenTestCorrection.written_test_id == str(written_test.id))
            .filter(ReadingWrittenTestCorrection.student_id.in_(student_ids))
            .all()
        )
        corrections = {str(row.student_id): row for row in rows}

    people = []
    for student in students:
        klass = by_class.get(str(student.class_id))
        school = schools.get(str(klass.school_id)) if klass and klass.school_id else None
        grade = grades.get(str(klass.grade_id)) if klass and klass.grade_id else None
        correction = corrections.get(str(student.id))
        person = {
            "student_id": str(student.id),
            "student_name": student.name or "",
            "class_id": str(klass.id) if klass else None,
            "class_name": (klass.name if klass else "") or "",
            "school_id": str(klass.school_id) if klass and klass.school_id else None,
            "school_name": (school.name if school else "") or "",
            "serie_id": str(klass.grade_id) if klass and klass.grade_id else None,
            "serie_name": (grade.name if grade else "") or "",
            "finalized": False,
            "reading": None,
            "words": None,
            "text": None,
            "score": None,
            "apt": False,
            "item_points": {},
        }
        if correction is not None and _is_finalized(correction):
            reading = _as_int((correction.objective or {}).get("points"))
            words = _as_int((correction.writing or {}).get("wordPoints"))
            text = _as_int((correction.writing or {}).get("textPoints"))
            score = _score(reading + words + text)
            person.update({
                "finalized": True,
                "reading": reading,
                "words": words,
                "text": text,
                "score": score,
                "apt": (
                    Decimal(str(score)) >= Decimal(SCORE_MIN)
                    and reading >= READING_MIN
                    and words >= WORDS_MIN
                    and text >= TEXT_MIN
                ),
                "item_points": _item_points(correction),
            })
        people.append(person)

    people.sort(key=lambda row: (row["student_name"].casefold(), row["student_id"]))
    scope = {
        "level": _scope_level(escola_id, serie_id, turma_id, estudante_id),
        "escolaId": escola_id,
        "escolaName": schools[escola_id].name if escola_id and escola_id in schools else None,
        "serieId": serie_id,
        "serieName": grades[serie_id].name if serie_id and serie_id in grades else None,
        "turmaId": turma_id,
        "turmaName": by_class[turma_id].name if turma_id and turma_id in by_class else None,
        "estudanteId": estudante_id,
        "estudanteName": by_student[estudante_id].name if estudante_id and estudante_id in by_student else None,
    }
    return {"written_test": written_test, "people": people, "scope": scope}


def _cards(people: List[Dict[str, Any]]) -> Dict[str, Any]:
    finalized = [row for row in people if row["finalized"]]
    expected = len(people)
    evaluated = len(finalized)
    apt = sum(1 for row in finalized if row["apt"])
    return {
        "participation": {
            "expected": expected,
            "evaluated_diagnostic": evaluated,
            "percentage": _pct(evaluated, expected),
        },
        "diagnostic": {
            "valid": evaluated,
            "apt": apt,
            "iad_percentage": _pct(apt, evaluated),
        },
        "proficiency_inep": {
            "imported_valid": 0,
            "ica_percentage": None,
            "status": "SEM_DADOS",
        },
    }


def _group_row(people: List[Dict[str, Any]], row_id: str, name: str, row_level: str, **extra) -> Dict[str, Any]:
    cards = _cards(people)
    finalized = [row for row in people if row["finalized"]]
    payload = {
        "id": row_id,
        "name": name,
        "rowLevel": row_level,
        "expected": cards["participation"]["expected"],
        "evaluated_diagnostic": cards["participation"]["evaluated_diagnostic"],
        "percentage": cards["participation"]["percentage"],
        "apt": cards["diagnostic"]["apt"],
        "iad_percentage": cards["diagnostic"]["iad_percentage"],
        "score": _mean([row["score"] for row in finalized if row["score"] is not None]),
    }
    payload.update(extra)
    return payload


def _student_row(person: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": person["student_id"],
        "rowLevel": "aluno",
        "student_id": person["student_id"],
        "student_name": person["student_name"],
        "class_id": person["class_id"],
        "class_name": person["class_name"],
        "reading": person["reading"],
        "words": person["words"],
        "text": person["text"],
        "score": person["score"],
        "apt": person["apt"] if person["finalized"] else False,
    }


def _rows(level: str, people: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if level == "aluno":
        return [_student_row(people[0])] if people else []
    if level == "turma":
        return [_student_row(row) for row in people if row["finalized"]]

    if level == "municipio":
        key_name = "school_id"
        row_level = "escola"
        label = "school_name"
        extra_key = "escolaId"
    elif level == "escola":
        key_name = "serie_id"
        row_level = "serie"
        label = "serie_name"
        extra_key = "serieId"
    else:
        key_name = "class_id"
        row_level = "turma"
        label = "class_name"
        extra_key = "turmaId"

    buckets: Dict[str, List[Dict[str, Any]]] = {}
    for person in people:
        buckets.setdefault(person.get(key_name) or "", []).append(person)
    rows = []
    for key, group in buckets.items():
        sample = group[0]
        rows.append(_group_row(
            group,
            key,
            sample.get(label) or "",
            row_level,
            **{extra_key: key or None},
        ))
    rows.sort(key=lambda row: ((row.get("name") or "").casefold(), row.get("id") or ""))
    return rows


def _student_detail(person: Dict[str, Any], catalog: List[Dict[str, Any]]) -> Dict[str, Any]:
    detail = _student_row(person)
    detail.update({
        "finalized": person["finalized"],
        "school_id": person["school_id"],
        "school_name": person["school_name"],
        "serie_id": person["serie_id"],
        "serie_name": person["serie_name"],
        "items": [
            {
                "number": item["number"],
                "code": item["code"],
                "points": person["item_points"].get(item["number"]) if person["finalized"] else None,
                "max_points": item["max_points"],
                "skill_code": item["skill_code"],
                "skill_label": item["skill_label"],
            }
            for item in catalog
        ],
    })
    return detail


def ica_dashboard(written_test_id: str, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    loaded = _load(written_test_id, filters)
    people = loaded["people"]
    scope = loaded["scope"]
    payload = _cards(people)
    payload.update({
        "writtenTestId": str(loaded["written_test"].id),
        "title": loaded["written_test"].title,
        "scope": scope,
        "rows": _rows(scope["level"], people),
        "student": None,
    })
    if scope["level"] == "aluno" and people:
        payload["student"] = _student_detail(people[0], _question_catalog(written_test_id))
    return payload


def skill_map(written_test_id: str, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    loaded = _load(written_test_id, filters)
    people = [row for row in loaded["people"] if row["finalized"]]
    attempts = len(people)
    grouped: Dict[str, Dict[str, Any]] = {}
    for item in _question_catalog(written_test_id):
        if not item["skill_id"]:
            continue
        bucket = grouped.setdefault(item["skill_id"], {
            "skill_code": item["skill_code"] or item["skill_id"],
            "skill_label": item["skill_label"] or item["skill_code"] or item["skill_id"],
            "items": [],
            "numbers": [],
            "max_points_student": 0,
        })
        bucket["items"].append(item["code"])
        bucket["numbers"].append(item["number"])
        bucket["max_points_student"] += item["max_points"]

    skills = []
    for bucket in grouped.values():
        obtained = 0
        for person in people:
            obtained += sum(person["item_points"].get(number, 0) for number in bucket["numbers"])
        maximum = bucket["max_points_student"]
        weight = _pct(maximum, TOTAL_MAX)
        performance = None
        if attempts and maximum:
            performance = _pct(obtained, maximum * attempts)
        skills.append({
            "skill_code": bucket["skill_code"],
            "skill_label": bucket["skill_label"],
            "items": bucket["items"],
            "max_points_student": maximum,
            "relative_weight_percentage": weight,
            "performance_percentage": performance,
        })
    skills.sort(key=lambda row: (row["skill_code"] or "", row["skill_label"] or ""))
    return {
        "writtenTestId": str(loaded["written_test"].id),
        "scope": loaded["scope"],
        "max_points": TOTAL_MAX,
        "valid_attempts": attempts,
        "skills": skills,
    }


def ica_csv(written_test_id: str, filters: Optional[Dict[str, Any]] = None) -> tuple:
    loaded = _load(written_test_id, filters)
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";", lineterminator="\n")
    writer.writerow(CSV_HEADER)
    for person in loaded["people"]:
        if not person["finalized"]:
            continue
        writer.writerow([
            person["student_id"],
            person["student_name"],
            person["class_name"],
            person["reading"],
            person["words"],
            person["text"],
            person["reading"] + person["words"] + person["text"],
            f"{person['score']:.1f}",
            "SIM" if person["apt"] else "NAO",
        ])
    filename = "resultados_ica.csv"
    return buffer.getvalue().encode("utf-8"), filename
