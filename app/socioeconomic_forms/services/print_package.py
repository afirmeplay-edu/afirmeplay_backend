# -*- coding: utf-8 -*-
"""
Pacote impresso do questionário socioeconômico.

Um PDF base, overlay só na capa, um ZIP com pastas
municipio/escola/serie/turma. Alunos sem user_id entram no ZIP.
Não cria FormRecipient e não grava FormResponse.

A URL do ZIP anterior só é substituída quando o upload deste pacote
retorna o objeto. Falha total ou upload vazio não apaga o pacote anterior.
"""
from __future__ import annotations

import importlib.util
import re
import sys
import unicodedata
import uuid
import zipfile
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Dict, List, Optional

PRINTABLE_FORM_TYPES = ("aluno-jovem", "aluno-velho")
ACTIVE_CELERY_STATES = frozenset({"PENDING", "STARTED", "RETRY"})
STALE_PROCESSING_SECONDS = 30 * 60
PROGRESS_EVERY = 25


class PrintRunSuperseded(Exception):
    """Outra geração assumiu o formulário. Esta não grava status."""


def _filter_utils():
    """Carrega filter_utils pelo arquivo.

    Importar pelo pacote services executa services/__init__.py e pode
    cair no ciclo FormRecipient antes de os models estarem prontos.
    """
    name = "socioeconomic_filter_utils_for_print"
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    path = str(Path(__file__).with_name("filter_utils.py"))
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Não foi possível carregar {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def sanitize_filename(name: str, max_length: int = 80, fallback: str = "item") -> str:
    """Nome seguro para pasta ou arquivo. Cópia local, sem o gerador de cartão."""
    if not name or not isinstance(name, str):
        return fallback
    normalized = unicodedata.normalize("NFKD", name)
    normalized = normalized.encode("ascii", "ignore").decode("ascii")
    normalized = re.sub(r"[^\w\s-]", "", normalized)
    normalized = re.sub(r"[-\s]+", "_", normalized).strip("_")
    normalized = normalized.lower() or fallback
    return normalized[:max_length] if max_length else normalized


def resolve_print_scope(form: Any) -> Dict[str, Any]:
    """Escopo impresso equivalente a student_matches_form_scope mais o recorte geográfico.

    filters.turma tem prioridade sobre selected_classes, como na distribuição.
    Todas as turmas permanecem. Não reduz a escola da primeira turma.
    Sem turma efetiva e sem série efetiva, não há o que imprimir.
    """
    filters_mod = _filter_utils()
    normalize_id_list = filters_mod.normalize_id_list
    form_scope_needs_geo_school_check = filters_mod.form_scope_needs_geo_school_check

    form_type = getattr(form, "form_type", None)
    filters = getattr(form, "filters", None) or {}
    selected_schools = normalize_id_list(getattr(form, "selected_schools", None))
    selected_grades = normalize_id_list(getattr(form, "selected_grades", None))
    selected_classes = normalize_id_list(getattr(form, "selected_classes", None))
    filter_classes = normalize_id_list(filters.get("turma")) if filters.get("turma") else []
    filter_grades = normalize_id_list(filters.get("serie")) if filters.get("serie") else []
    filter_schools = normalize_id_list(filters.get("escola")) if filters.get("escola") else []

    classes = filter_classes or selected_classes
    grades = filter_grades or selected_grades
    schools = selected_schools or filter_schools
    needs_geo = form_scope_needs_geo_school_check(selected_schools, filters)
    printable = form_type in PRINTABLE_FORM_TYPES and bool(classes or grades)
    return {
        "printable": printable,
        "form_type": form_type,
        "classes": classes,
        "grades": grades,
        "schools": schools,
        "municipio": str(filters["municipio"]) if needs_geo and filters.get("municipio") else None,
        "estado": filters.get("estado") if needs_geo and filters.get("estado") else None,
    }


def scope_rejection_message(scope: Dict[str, Any]) -> Optional[str]:
    if scope.get("form_type") not in PRINTABLE_FORM_TYPES:
        return "A impressão em PDF está disponível apenas para questionários de aluno."
    if not scope.get("printable"):
        return "O questionário precisa de séries ou turmas no escopo para gerar os PDFs."
    return None


def cover_place(students: List[Dict[str, Any]], filters: Optional[Dict[str, Any]] = None) -> SimpleNamespace:
    """Cidade da capa única. Vários municípios: estado do filtro e município em branco."""
    places = set()
    for student in students:
        state = (student.get("state") or "").strip()
        name = (student.get("municipality") or "").strip()
        if state or name:
            places.add((state, name))
    if len(places) == 1:
        state, name = next(iter(places))
        return SimpleNamespace(state=state, name=name)
    filters = filters or {}
    return SimpleNamespace(state=(filters.get("estado") or ""), name="")


def pdf_arcname(student: Dict[str, Any]) -> str:
    """Caminho dentro do ZIP. O sufixo do id separa homônimos da mesma turma."""
    city = sanitize_filename(student.get("municipality") or "", 60, "municipio")
    school = sanitize_filename(student.get("school_name") or "", 60, "escola")
    grade = sanitize_filename(student.get("grade_name") or "", 40, "serie")
    klass = sanitize_filename(student.get("class_name") or "", 40, "turma")
    person = sanitize_filename(student.get("name") or "", 60, "aluno")
    raw_id = str(student.get("student_id") or "").replace("-", "")
    suffix = sanitize_filename(raw_id[-8:], 8, "id")
    filename = f"{person}_{grade}_{klass}_{suffix}.pdf"
    return f"municipio_{city}/escola_{school}/serie_{grade}/turma_{klass}/{filename}"


def print_package_was_started(status: Optional[str], run_id: Optional[str], started_at: Optional[datetime]) -> bool:
    """False quando o formulário nunca teve geração. O GET de status responde 404."""
    return bool(status or run_id or started_at)


def print_generation_in_progress(
    status: Optional[str],
    started_at: Optional[datetime],
    celery_state: Optional[str],
    now: datetime,
) -> bool:
    """True quando um POST novo deve responder 409.

    PENDING também é o estado de task desconhecida. Depois do limite,
    uma geração marcada processing deixa de bloquear.
    """
    if status != "processing":
        return False
    if started_at is None:
        return True
    if getattr(started_at, "tzinfo", None) is not None:
        started_at = started_at.replace(tzinfo=None)
    if (now - started_at).total_seconds() > STALE_PROCESSING_SECONDS:
        return False
    if celery_state is None:
        return True
    return celery_state in ACTIVE_CELERY_STATES


def decide_print_outcome(stats: Dict[str, Any], upload_result: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """completed só com pelo menos um PDF e upload não nulo. Não troca a URL caso contrário."""
    generated = int(stats.get("generated") or 0)
    failed = int(stats.get("failed") or 0)
    total = int(stats.get("total") or 0)
    errors = [str(item) for item in (stats.get("errors") or [])]
    if failed and errors:
        partial = f"{failed} de {total} não gerados: " + "; ".join(errors)
    elif failed:
        partial = f"{failed} de {total} não gerados."
    else:
        partial = None

    if generated <= 0:
        return {
            "status": "failed",
            "replace_zip": False,
            "error": partial or "Nenhum PDF foi gerado.",
        }
    if not upload_result or not upload_result.get("object_name"):
        return {
            "status": "failed",
            "replace_zip": False,
            "error": "Falha ao enviar o ZIP. O pacote anterior, se existir, permanece disponível.",
        }
    return {
        "status": "completed",
        "replace_zip": True,
        "bucket": upload_result.get("bucket"),
        "object_name": upload_result.get("object_name"),
        "url": upload_result.get("url"),
        "error": partial,
    }


def write_print_zip(
    zip_path: str,
    base_pdf: bytes,
    form_id: str,
    students: List[Dict[str, Any]],
    personalize: Optional[Callable[..., bytes]] = None,
    on_progress: Optional[Callable[[int, int, int], None]] = None,
) -> Dict[str, Any]:
    """Grava um PDF por vez e descarta os bytes. Uma falha não interrompe os demais."""
    if personalize is None:
        from app.socioeconomic_forms.services.questionnaire_individual_pdf import (
            personalize_questionnaire_pdf,
        )
        personalize = personalize_questionnaire_pdf

    generated = 0
    failed = 0
    errors: List[str] = []
    total = len(students)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for student in students:
            student_id = str(student.get("student_id") or "")
            try:
                pdf_bytes = personalize(
                    base_pdf,
                    student_id=student_id,
                    form_id=str(form_id),
                    student_name=student.get("name") or "",
                    school_name=student.get("school_name") or "",
                    grade_name=student.get("grade_name") or "",
                    class_name=student.get("class_name") or "",
                )
                archive.writestr(pdf_arcname(student), pdf_bytes)
                generated += 1
                del pdf_bytes
            except PrintRunSuperseded:
                raise
            except Exception as exc:
                failed += 1
                if len(errors) < 20:
                    errors.append(f"{student_id}: {exc}")
            if on_progress is not None:
                on_progress(generated, failed, total)
    return {
        "generated": generated,
        "failed": failed,
        "errors": errors,
        "total": total,
    }


def _as_uuids(values: List[str]) -> List[uuid.UUID]:
    parsed = []
    for value in values:
        try:
            parsed.append(uuid.UUID(str(value)))
        except (ValueError, TypeError, AttributeError):
            continue
    return parsed


def list_print_students(form: Any) -> List[Dict[str, Any]]:
    """Alunos do escopo, com ou sem user_id, numa consulta.

    A série usada é a da turma, a mesma de ensure_recipients_for_student.
    """
    scope = resolve_print_scope(form)
    if not scope["printable"]:
        return []

    from sqlalchemy import nullslast

    from app import db
    from app.models.city import City
    from app.models.grades import Grade
    from app.models.school import School
    from app.models.student import Student
    from app.models.studentClass import Class

    query = (
        db.session.query(
            Student.id,
            Student.name,
            Student.user_id,
            Class.name,
            Grade.name,
            School.name,
            City.name,
            City.state,
        )
        .join(Class, Student.class_id == Class.id)
        .join(Grade, Class.grade_id == Grade.id)
        .join(School, Student.school_id == School.id)
        .outerjoin(City, School.city_id == City.id)
    )
    class_ids = _as_uuids(scope["classes"])
    grade_ids = _as_uuids(scope["grades"])
    if scope["classes"]:
        if not class_ids:
            return []
        query = query.filter(Class.id.in_(class_ids))
    if scope["grades"]:
        if not grade_ids:
            return []
        query = query.filter(Grade.id.in_(grade_ids))
    if scope["schools"]:
        query = query.filter(Student.school_id.in_(scope["schools"]))
    if scope["municipio"]:
        query = query.filter(School.city_id == scope["municipio"])
    if scope["estado"]:
        query = query.filter(City.state == scope["estado"])

    query = query.order_by(
        nullslast(City.name),
        School.name,
        Grade.name,
        Class.name,
        Student.name,
    )
    students = []
    for student_id, name, user_id, class_name, grade_name, school_name, city_name, state in query.all():
        students.append({
            "student_id": str(student_id),
            "name": name or "",
            "user_id": user_id,
            "class_name": class_name or "",
            "grade_name": grade_name or "",
            "school_name": school_name or "",
            "municipality": city_name or "",
            "state": state or "",
        })
    return students
