# -*- coding: utf-8 -*-
"""Painel do Indicador Criança Alfabetizada da avaliação escrita.

Calcula, grava e devolve pronto: TCT, nota da proficiência, nível, situação
e os agregados do painel. O município é o da sessão. O recorte desce
escola → série → turma → aluno.
"""
from __future__ import annotations

import csv
import io
import math
import uuid
from datetime import datetime, timezone
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
TWO = Decimal("0.01")
TOTAL_MAX = 34
SCORE_MIN = 70
READING_MIN = 11
WORDS_MIN = 2
TEXT_MIN = 7
TEXT_QUESTION_MAX = 14
PROF_CUT = 743
LEVEL_BASIC = 700
LEVEL_ADEQUADO = 800
LEVEL_NAMES = (
    "Abaixo do Básico",
    "Básico",
    "Adequado",
    "Avançado",
)
STATUS_ALFABETIZADO = "Alfabetizado"
STATUS_NAO_ALFABETIZADO = "Não alfabetizado"
STATUS_NAO_AVALIADO = "Não avaliado"
CSV_HEADER = (
    "aluno_id",
    "aluno",
    "serie",
    "turma",
    "escola",
    "municipio",
    "leitura_16",
    "palavras_4",
    "texto_14",
    "pontos_34",
    "nota_tct_0_10",
    "nota_100",
    "apto_diagnostico",
    "proficiencia",
    "nota_prof_0_10",
    "nivel_aprendizagem",
    "status",
    "avaliado",
)


def _one(value: Decimal) -> float:
    return float(value.quantize(ONE, rounding=ROUND_HALF_UP))


def _two(value: Decimal) -> float:
    return float(value.quantize(TWO, rounding=ROUND_HALF_UP))


def _pct(part: int, whole: int) -> Optional[float]:
    if whole <= 0:
        return None
    return _one(Decimal(part) * Decimal(100) / Decimal(whole))


def _score(total: int) -> float:
    return _one(Decimal(total) * Decimal(100) / Decimal(TOTAL_MAX))


def _mean_one(values: List[float]) -> Optional[float]:
    if not values:
        return None
    total = sum((Decimal(str(value)) for value in values), Decimal(0))
    return _one(total / Decimal(len(values)))


def _mean_two(values: List[float]) -> Optional[float]:
    if not values:
        return None
    total = sum((Decimal(str(value)) for value in values), Decimal(0))
    return _two(total / Decimal(len(values)))


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


def _as_float(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, str) and not value.strip():
        return None
    try:
        if isinstance(value, str):
            value = value.replace(",", ".")
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


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


def _item_points(stored: ReadingWrittenTestCorrection) -> Dict[int, int]:
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


def _tct_grade(points: Optional[int]) -> Optional[float]:
    if points is None:
        return None
    return _two(Decimal(points) * Decimal(10) / Decimal(TOTAL_MAX))


def _proficiency_from_points(points: Optional[int]) -> Optional[float]:
    """(pontos ÷ 34) × 1000, sempre com 1 casa decimal."""
    if points is None:
        return None
    return round((points / TOTAL_MAX) * 1000, 1)


def _prof_grade_exact(proficiency: Optional[float]) -> Optional[float]:
    if proficiency is None:
        return None
    raw = 7 + (float(proficiency) - PROF_CUT) / 50
    return max(0.0, min(10.0, raw))


def _prof_grade(proficiency: Optional[float]) -> Optional[float]:
    exact = _prof_grade_exact(proficiency)
    if exact is None:
        return None
    return math.floor((exact + 1e-10) * 100) / 100


def _learning_level(proficiency: Optional[float]) -> str:
    if proficiency is None:
        return "Sem proficiência"
    if proficiency < LEVEL_BASIC:
        return "Abaixo do Básico"
    if proficiency < PROF_CUT:
        return "Básico"
    if proficiency < LEVEL_ADEQUADO:
        return "Adequado"
    return "Avançado"


def _status(avaliado: bool, proficiency: Optional[float]) -> str:
    if not avaliado or proficiency is None:
        return STATUS_NAO_AVALIADO
    if proficiency >= PROF_CUT:
        return STATUS_ALFABETIZADO
    return STATUS_NAO_ALFABETIZADO


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def compute_ica_result(
    reading: Optional[int],
    words: Optional[int],
    text: Optional[int],
    finalized: bool,
) -> Dict[str, Any]:
    """Monta o bloco ICA já pronto para gravar e devolver."""
    points = None
    score = None
    apt = False
    if finalized and reading is not None and words is not None and text is not None:
        points = reading + words + text
        score = _score(points)
        apt = (
            Decimal(str(score)) >= Decimal(SCORE_MIN)
            and reading >= READING_MIN
            and words >= WORDS_MIN
            and text >= TEXT_MIN
        )
    else:
        reading = None
        words = None
        text = None

    proficiency = _proficiency_from_points(points)
    nota_tct = _tct_grade(points)
    nota_prof_exact = _prof_grade_exact(proficiency)
    nota_prof = _prof_grade(proficiency)
    avaliado = points is not None
    return {
        "leitura_16": reading,
        "palavras_4": words,
        "texto_14": text,
        "pontos_34": points,
        "nota_100": score,
        "nota_tct_0_10": nota_tct,
        "apto_diagnostico": apt,
        "proficiencia": proficiency,
        "nota_prof_0_10": nota_prof,
        "nota_prof_exata": nota_prof_exact,
        "nivel_aprendizagem": _learning_level(proficiency),
        "status": _status(avaliado, proficiency),
        "avaliado": avaliado,
        "finalized": finalized,
        "computed_at": _now_iso(),
    }


def refresh_correction_ica(row: ReadingWrittenTestCorrection) -> Dict[str, Any]:
    """Recalcula e grava o bloco ICA da correção. Não faz commit."""
    finalized = _is_finalized(row)
    reading = words = text = None
    if finalized:
        reading = _as_int((row.objective or {}).get("points"))
        writing = row.writing or {}
        words = _as_int(writing.get("wordPoints"))
        text = _as_int(writing.get("textPoints"))
    result = compute_ica_result(reading, words, text, finalized)
    row.ica = result
    return result


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


def _municipio_context() -> Dict[str, Optional[str]]:
    from app.afirme_ler.services.written_test_pdf_service import resolve_context_city

    city = resolve_context_city()
    if city is None:
        return {"municipio": None, "uf": None, "municipio_id": None}
    return {
        "municipio": city.name or None,
        "uf": city.state or None,
        "municipio_id": str(city.id),
    }


def _ensure_ica(person: Dict[str, Any], correction: Optional[ReadingWrittenTestCorrection]) -> Dict[str, Any]:
    if correction is None:
        return compute_ica_result(None, None, None, False)
    # Sempre recalcula a partir dos pontos (proficiência = pontos/34×1000).
    return refresh_correction_ica(correction)


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

    city = _municipio_context()
    municipio_name = city["municipio"]
    people = []
    dirty = False
    for student in students:
        klass = by_class.get(str(student.class_id))
        school = schools.get(str(klass.school_id)) if klass and klass.school_id else None
        grade = grades.get(str(klass.grade_id)) if klass and klass.grade_id else None
        correction = corrections.get(str(student.id))
        before = dict(correction.ica or {}) if correction is not None else {}
        before.pop("computed_at", None)
        ica = _ensure_ica({}, correction)
        after = dict(correction.ica or {}) if correction is not None else {}
        after.pop("computed_at", None)
        if correction is not None and before != after:
            dirty = True
        person = {
            "student_id": str(student.id),
            "student_name": student.name or "",
            "class_id": str(klass.id) if klass else None,
            "class_name": (klass.name if klass else "") or "",
            "school_id": str(klass.school_id) if klass and klass.school_id else None,
            "school_name": (school.name if school else "") or "",
            "serie_id": str(klass.grade_id) if klass and klass.grade_id else None,
            "serie_name": (grade.name if grade else "") or "",
            "municipio": municipio_name,
            "uf": city["uf"],
            "finalized": bool(ica.get("finalized")),
            "reading": ica.get("leitura_16"),
            "words": ica.get("palavras_4"),
            "text": ica.get("texto_14"),
            "score": ica.get("nota_100"),
            "apt": bool(ica.get("apto_diagnostico")),
            "item_points": _item_points(correction) if correction is not None and ica.get("finalized") else {},
            "ica": ica,
        }
        people.append(person)

    if dirty:
        db.session.commit()

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
    return {
        "written_test": written_test,
        "people": people,
        "scope": scope,
        "municipio": municipio_name,
        "uf": city["uf"],
    }


def _filter_people(people: List[Dict[str, Any]], filters: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    filters = filters or {}
    status = _param(filters, "status")
    nivel = _param(filters, "nivel", "nivel_aprendizagem", "nivelAprendizagem")
    query = (_param(filters, "q", "busca", "search") or "").casefold()
    out = []
    for person in people:
        ica = person["ica"]
        if status and ica.get("status") != status:
            continue
        if nivel and ica.get("nivel_aprendizagem") != nivel:
            continue
        if query:
            hay = " ".join([
                person.get("student_name") or "",
                person.get("school_name") or "",
                person.get("class_name") or "",
                person.get("municipio") or "",
            ]).casefold()
            if query not in hay:
                continue
        out.append(person)
    return out


def _stats(people: List[Dict[str, Any]]) -> Dict[str, Any]:
    previstos = len(people)
    avaliados = sum(1 for row in people if row["ica"].get("avaliado"))
    with_prof = [row for row in people if row["ica"].get("proficiencia") is not None]
    alpha = [row for row in with_prof if float(row["ica"]["proficiencia"]) >= PROF_CUT]
    tct_values = [
        float(row["ica"]["nota_tct_0_10"])
        for row in people
        if row["ica"].get("nota_tct_0_10") is not None
    ]
    prof_values = [float(row["ica"]["proficiencia"]) for row in with_prof]
    nota_exact = [
        float(row["ica"]["nota_prof_exata"])
        for row in with_prof
        if row["ica"].get("nota_prof_exata") is not None
    ]
    finalized = [row for row in people if row["ica"].get("finalized")]
    apt = sum(1 for row in finalized if row["ica"].get("apto_diagnostico"))
    level_counts = {name: 0 for name in LEVEL_NAMES}
    for row in with_prof:
        name = row["ica"].get("nivel_aprendizagem")
        if name in level_counts:
            level_counts[name] += 1
    return {
        "previstos": previstos,
        "avaliados": avaliados,
        "participacao_percentual": _pct(avaliados, previstos),
        "com_proficiencia": len(with_prof),
        "alfabetizados": len(alpha),
        "nao_alfabetizados": len(with_prof) - len(alpha),
        "sem_proficiencia": previstos - len(with_prof),
        "percentual_ge_743": _pct(len(alpha), len(with_prof)),
        "proficiencia_media": _mean_one(prof_values),
        "nota_prof_media": _mean_two(nota_exact),
        "nota_tct_media": _mean_two(tct_values),
        "diagnostic_valid": len(finalized),
        "diagnostic_apt": apt,
        "iad_percentage": _pct(apt, len(finalized)),
        "score_media": _mean_one([
            float(row["ica"]["nota_100"])
            for row in finalized
            if row["ica"].get("nota_100") is not None
        ]),
        "level_counts": level_counts,
    }


def _kpis(stats: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "previstos": stats["previstos"],
        "avaliados": stats["avaliados"],
        "participacao_percentual": stats["participacao_percentual"],
        "alfabetizados": stats["alfabetizados"],
        "nao_alfabetizados": stats["nao_alfabetizados"],
        "sem_proficiencia": stats["sem_proficiencia"],
        "percentual_ge_743": stats["percentual_ge_743"],
        "proficiencia_media": stats["proficiencia_media"],
        "nota_prof_media": stats["nota_prof_media"],
        "nota_tct_media": stats["nota_tct_media"],
    }


def _levels_payload(stats: Dict[str, Any]) -> Dict[str, Any]:
    validos = stats["com_proficiencia"]
    items = []
    for name in LEVEL_NAMES:
        count = stats["level_counts"].get(name, 0)
        items.append({
            "name": name,
            "count": count,
            "percentage": _pct(count, validos),
        })
    return {"validos": validos, "items": items}


def _cards(people: List[Dict[str, Any]]) -> Dict[str, Any]:
    stats = _stats(people)
    return {
        "participation": {
            "expected": stats["previstos"],
            "evaluated_diagnostic": stats["diagnostic_valid"],
            "percentage": _pct(stats["diagnostic_valid"], stats["previstos"]),
        },
        "diagnostic": {
            "valid": stats["diagnostic_valid"],
            "apt": stats["diagnostic_apt"],
            "iad_percentage": stats["iad_percentage"],
        },
        "kpis": _kpis(stats),
        "niveis": _levels_payload(stats),
        "_stats": stats,
    }


def _student_public(person: Dict[str, Any]) -> Dict[str, Any]:
    ica = person["ica"]
    return {
        "id": person["student_id"],
        "rowLevel": "aluno",
        "student_id": person["student_id"],
        "aluno": person["student_name"],
        "student_name": person["student_name"],
        "serie_id": person["serie_id"],
        "serie": person["serie_name"],
        "serie_name": person["serie_name"],
        "class_id": person["class_id"],
        "turma": person["class_name"],
        "class_name": person["class_name"],
        "school_id": person["school_id"],
        "escola": person["school_name"],
        "school_name": person["school_name"],
        "municipio": person.get("municipio"),
        "uf": person.get("uf"),
        "leitura_16": ica.get("leitura_16"),
        "palavras_4": ica.get("palavras_4"),
        "texto_14": ica.get("texto_14"),
        "pontos_34": ica.get("pontos_34"),
        "reading": ica.get("leitura_16"),
        "words": ica.get("palavras_4"),
        "text": ica.get("texto_14"),
        "score": ica.get("nota_100"),
        "nota_100": ica.get("nota_100"),
        "nota_tct_0_10": ica.get("nota_tct_0_10"),
        "nota_prof_0_10": ica.get("nota_prof_0_10"),
        "nota_prof_exata": ica.get("nota_prof_exata"),
        "proficiencia": ica.get("proficiencia"),
        "nivel_aprendizagem": ica.get("nivel_aprendizagem"),
        "status": ica.get("status"),
        "avaliado": bool(ica.get("avaliado")),
        "finalized": bool(ica.get("finalized")),
        "apto": bool(ica.get("apto_diagnostico")),
        "apto_diagnostico": bool(ica.get("apto_diagnostico")),
    }


def _group_row(people: List[Dict[str, Any]], row_id: str, name: str, row_level: str, **extra) -> Dict[str, Any]:
    stats = _stats(people)
    payload = {
        "id": row_id,
        "name": name,
        "rowLevel": row_level,
        "expected": stats["previstos"],
        "evaluated_diagnostic": stats["diagnostic_valid"],
        "percentage": _pct(stats["diagnostic_valid"], stats["previstos"]),
        "apt": stats["diagnostic_apt"],
        "iad_percentage": stats["iad_percentage"],
        "score": stats["score_media"],
        "previstos": stats["previstos"],
        "avaliados": stats["avaliados"],
        "participacao_percentual": stats["participacao_percentual"],
        "alfabetizados": stats["alfabetizados"],
        "percentual_ge_743": stats["percentual_ge_743"],
        "niveis": dict(stats["level_counts"]),
        "nota_tct_media": stats["nota_tct_media"],
        "nota_prof_media": stats["nota_prof_media"],
        "proficiencia_media": stats["proficiencia_media"],
    }
    payload.update(extra)
    return payload


def _rows(level: str, people: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if level == "aluno":
        return [_student_public(people[0])] if people else []
    if level == "turma":
        return [_student_public(row) for row in people]

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
    detail = _student_public(person)
    detail.update({
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
    people = _filter_people(loaded["people"], filters)
    scope = loaded["scope"]
    cards = _cards(people)
    payload = {
        "writtenTestId": str(loaded["written_test"].id),
        "title": loaded["written_test"].title,
        "scope": scope,
        "municipio": loaded["municipio"],
        "uf": loaded["uf"],
        "participation": cards["participation"],
        "diagnostic": cards["diagnostic"],
        "kpis": cards["kpis"],
        "niveis": cards["niveis"],
        "rows": _rows(scope["level"], people),
        "students": [_student_public(row) for row in people],
        "student": None,
    }
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
    people = _filter_people(loaded["people"], filters)
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";", lineterminator="\n")
    writer.writerow(CSV_HEADER)
    for person in people:
        ica = person["ica"]

        def cell(value: Any) -> str:
            if value is None:
                return ""
            if value is True:
                return "SIM"
            if value is False:
                return "NAO"
            return value

        writer.writerow([
            person["student_id"],
            person["student_name"],
            person["serie_name"],
            person["class_name"],
            person["school_name"],
            person.get("municipio") or "",
            cell(ica.get("leitura_16")),
            cell(ica.get("palavras_4")),
            cell(ica.get("texto_14")),
            cell(ica.get("pontos_34")),
            cell(ica.get("nota_tct_0_10")),
            cell(ica.get("nota_100")),
            "SIM" if ica.get("apto_diagnostico") else "NAO",
            cell(ica.get("proficiencia")),
            cell(ica.get("nota_prof_0_10")),
            cell(ica.get("nivel_aprendizagem")),
            cell(ica.get("status")),
            "SIM" if ica.get("avaliado") else "NAO",
        ])
    return buffer.getvalue().encode("utf-8"), "resultados_ica.csv"

