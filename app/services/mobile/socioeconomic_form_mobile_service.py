# -*- coding: utf-8 -*-
"""
Integração de formulários socioeconômicos com mobile/offline.
Serializa formulários enviados e processa respostas do app.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy import or_, and_

from app import db
from app.models.student import Student
from app.models.studentClass import Class
from app.models.user import User
from app.socioeconomic_forms.models import Form, FormRecipient, FormResponse
from app.socioeconomic_forms.services.response_service import ResponseService
from app.services.mobile.content_hash import compute_form_content_version

logger = logging.getLogger(__name__)

STUDENT_FORM_TYPES = frozenset({"aluno-jovem", "aluno-velho"})


class SocioeconomicFormMobileError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def serialize_form_for_mobile(form: Form) -> Dict[str, Any]:
    """Serializa formulário completo (metadados + questões) para o app mobile."""
    questions = [q.to_dict() for q in form.questions]
    return {
        "form_id": str(form.id),
        "title": form.title,
        "description": form.description,
        "form_type": form.form_type,
        "instructions": form.instructions,
        "deadline": form.deadline.isoformat() + "Z" if form.deadline else None,
        "is_active": bool(form.is_active),
        "questions": questions,
    }


def build_forms_content_versions(
    forms_map: Dict[str, Dict[str, Any]],
) -> Dict[str, str]:
    return {fid: compute_form_content_version(payload) for fid, payload in forms_map.items()}


def _recipient_query_for_school(
    school_id: str,
    form_ids: Optional[Set[str]] = None,
):
    q = (
        FormRecipient.query.join(Form)
        .filter(Form.is_active.is_(True))
        .filter(
            or_(
                FormRecipient.school_id == school_id,
                and_(
                    FormRecipient.school_id.is_(None),
                    Form.form_type == "secretario",
                ),
            )
        )
    )
    if form_ids:
        q = q.filter(Form.id.in_(list(form_ids)))
    return q


def collect_forms_for_school(
    school_id: str,
    form_ids: Optional[Set[str]] = None,
    class_ids: Optional[Set[str]] = None,
) -> Tuple[Dict[str, Dict[str, Any]], List[Tuple[str, str]], List[Tuple[str, str]]]:
    """
    Coleta formulários já enviados (com FormRecipient) para uma escola.

    Returns:
        (forms_dict, student_form_links, user_form_links)
        - student_form_links: [(student_id, form_id), ...]
        - user_form_links: [(user_id, form_id), ...] professor/diretor/secretario
    """
    recipients = _recipient_query_for_school(school_id, form_ids).all()
    if not recipients:
        return {}, [], []

    forms_dict: Dict[str, Dict[str, Any]] = {}
    student_links: List[Tuple[str, str]] = []
    user_links: List[Tuple[str, str]] = []
    seen_student: Set[Tuple[str, str]] = set()
    seen_user: Set[Tuple[str, str]] = set()

    user_ids = {str(r.user_id) for r in recipients}
    students_by_user: Dict[str, Student] = {}
    if user_ids:
        for stu in Student.query.filter(Student.user_id.in_(list(user_ids))).all():
            if stu.user_id:
                students_by_user[str(stu.user_id)] = stu

    for rec in recipients:
        form = rec.form
        if not form:
            continue

        form_id = str(form.id)
        if form_id not in forms_dict:
            forms_dict[form_id] = serialize_form_for_mobile(form)

        if form.form_type in STUDENT_FORM_TYPES:
            stu = students_by_user.get(str(rec.user_id))
            if not stu or stu.school_id != school_id:
                continue
            if class_ids:
                cid = str(stu.class_id) if stu.class_id else None
                if not cid or cid not in class_ids:
                    continue
            key = (str(stu.id), form_id)
            if key not in seen_student:
                seen_student.add(key)
                student_links.append(key)
        else:
            key = (str(rec.user_id), form_id)
            if key not in seen_user:
                seen_user.add(key)
                user_links.append(key)

    return forms_dict, student_links, user_links


def _resolve_user_id(
    *,
    student_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> str:
    if user_id:
        return str(user_id)
    if not student_id:
        raise SocioeconomicFormMobileError("student_id ou user_id é obrigatório")
    stu = Student.query.get(student_id)
    if not stu or not stu.user_id:
        raise SocioeconomicFormMobileError("aluno não encontrado ou sem user_id", 404)
    return str(stu.user_id)


def _validate_form_content_version(form: Form, client_version: Optional[str]) -> None:
    if not client_version:
        raise SocioeconomicFormMobileError("form_content_version é obrigatório")
    expected = compute_form_content_version(serialize_form_for_mobile(form))
    if expected != client_version:
        raise SocioeconomicFormMobileError(
            "form_content_version inválido ou desatualizado",
            409,
        )


def get_form_entry(
    form_id: str,
    *,
    student_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Formulário + respostas parciais existentes para um aluno ou usuário."""
    form = Form.query.get(form_id)
    if not form:
        raise SocioeconomicFormMobileError("formulário não encontrado", 404)

    resolved_user_id = _resolve_user_id(student_id=student_id, user_id=user_id)
    try:
        form_data = ResponseService.get_form_for_response(form_id, resolved_user_id)
    except ValueError as e:
        raise SocioeconomicFormMobileError(str(e), 403) from e

    if not form_data:
        raise SocioeconomicFormMobileError("formulário não encontrado", 404)

    recipient = FormRecipient.query.filter_by(
        form_id=form_id, user_id=resolved_user_id
    ).first()

    payload = {
        "form_id": form_id,
        "form_type": form.form_type,
        "title": form_data.get("title"),
        "description": form_data.get("description"),
        "instructions": form_data.get("instructions"),
        "deadline": form_data.get("deadline"),
        "questions": form_data.get("questions") or [],
        "form_content_version": compute_form_content_version(serialize_form_for_mobile(form)),
        "recipient_status": recipient.status if recipient else "pending",
        "current_response": form_data.get("currentResponse"),
    }
    if student_id:
        payload["student_id"] = student_id
    else:
        payload["user_id"] = resolved_user_id
    return payload


def submit_form_response(
    form_id: str,
    *,
    responses: Dict[str, Any],
    is_complete: bool,
    form_content_version: Optional[str],
    student_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    form = Form.query.get(form_id)
    if not form:
        raise SocioeconomicFormMobileError("formulário não encontrado", 404)

    _validate_form_content_version(form, form_content_version)
    resolved_user_id = _resolve_user_id(student_id=student_id, user_id=user_id)

    try:
        response = ResponseService.save_response(
            form_id,
            resolved_user_id,
            responses or {},
            is_complete=is_complete,
        )
    except ValueError as e:
        raise SocioeconomicFormMobileError(str(e), 400) from e

    result: Dict[str, Any] = {
        "form_id": form_id,
        "response_id": str(response.id),
        "user_id": resolved_user_id,
        "status": response.status,
        "progress": float(response.progress),
        "saved_at": response.updated_at.isoformat() + "Z" if response.updated_at else None,
    }
    if student_id:
        result["student_id"] = student_id
    if response.completed_at:
        result["completed_at"] = response.completed_at.isoformat() + "Z"
    return result


def _recipient_status_map(form_id: str, user_ids: List[str]) -> Dict[str, str]:
    if not user_ids:
        return {}
    rows = FormRecipient.query.filter(
        FormRecipient.form_id == form_id,
        FormRecipient.user_id.in_(user_ids),
    ).all()
    return {str(r.user_id): r.status for r in rows}


def _response_status_map(form_id: str, user_ids: List[str]) -> Dict[str, Optional[str]]:
    if not user_ids:
        return {}
    rows = FormResponse.query.filter(
        FormResponse.form_id == form_id,
        FormResponse.user_id.in_(user_ids),
    ).all()
    return {str(r.user_id): r.status for r in rows}


def list_students_for_form(
    form_id: str,
    *,
    school_id: Optional[str] = None,
    class_id: Optional[str] = None,
    grade_id: Optional[str] = None,
    flat: bool = False,
) -> Dict[str, Any]:
    form = Form.query.get(form_id)
    if not form:
        raise SocioeconomicFormMobileError("formulário não encontrado", 404)
    if form.form_type not in STUDENT_FORM_TYPES:
        raise SocioeconomicFormMobileError(
            "este formulário não é destinado a alunos; use /users",
            400,
        )

    q = FormRecipient.query.filter_by(form_id=form_id)
    if school_id:
        q = q.filter(FormRecipient.school_id == school_id)
    recipients = q.all()
    user_ids = [str(r.user_id) for r in recipients]

    stu_q = Student.query.filter(Student.user_id.in_(user_ids))
    if school_id:
        stu_q = stu_q.filter_by(school_id=school_id)
    if class_id:
        stu_q = stu_q.filter_by(class_id=class_id)
    if grade_id:
        stu_q = stu_q.filter_by(grade_id=grade_id)
    students = stu_q.order_by(Student.name.asc()).all()

    recipient_status = _recipient_status_map(form_id, user_ids)
    response_status = _response_status_map(form_id, user_ids)

    if flat:
        students_out = []
        for stu in students:
            uid = str(stu.user_id)
            students_out.append({
                "student_id": str(stu.id),
                "name": stu.name,
                "class_id": str(stu.class_id) if stu.class_id else None,
                "recipient_status": recipient_status.get(uid, "pending"),
                "response_status": response_status.get(uid),
                "has_response": response_status.get(uid) is not None,
            })
        return {
            "form_id": form_id,
            "form_title": form.title,
            "form_type": form.form_type,
            "students": students_out,
        }

    by_class: Dict[str, Dict[str, Any]] = {}
    for stu in students:
        cid = str(stu.class_id) if stu.class_id else "_sem_turma"
        if cid not in by_class:
            cls = Class.query.get(stu.class_id) if stu.class_id else None
            by_class[cid] = {
                "class_id": cid if stu.class_id else None,
                "class_name": cls.name if cls else "Sem turma",
                "students": [],
            }
        uid = str(stu.user_id)
        by_class[cid]["students"].append({
            "student_id": str(stu.id),
            "name": stu.name,
            "recipient_status": recipient_status.get(uid, "pending"),
            "response_status": response_status.get(uid),
            "has_response": response_status.get(uid) is not None,
        })

    return {
        "form_id": form_id,
        "form_title": form.title,
        "form_type": form.form_type,
        "classes": list(by_class.values()),
    }


def list_users_for_form(
    form_id: str,
    *,
    school_id: Optional[str] = None,
) -> Dict[str, Any]:
    form = Form.query.get(form_id)
    if not form:
        raise SocioeconomicFormMobileError("formulário não encontrado", 404)
    if form.form_type in STUDENT_FORM_TYPES:
        raise SocioeconomicFormMobileError(
            "este formulário é destinado a alunos; use /students",
            400,
        )

    q = FormRecipient.query.join(Form).filter(FormRecipient.form_id == form_id)
    if school_id:
        q = q.filter(
            or_(
                FormRecipient.school_id == school_id,
                and_(
                    FormRecipient.school_id.is_(None),
                    Form.form_type == "secretario",
                ),
            )
        )
    recipients = q.all()
    user_ids = [str(r.user_id) for r in recipients]

    users_by_id: Dict[str, User] = {}
    if user_ids:
        for u in User.query.filter(User.id.in_(user_ids)).all():
            users_by_id[str(u.id)] = u

    recipient_status = _recipient_status_map(form_id, user_ids)
    response_status = _response_status_map(form_id, user_ids)

    users_out = []
    for rec in recipients:
        uid = str(rec.user_id)
        user = users_by_id.get(uid)
        users_out.append({
            "user_id": uid,
            "name": user.name if user else None,
            "email": user.email if user else None,
            "role": user.role.value if user and hasattr(user.role, "value") else None,
            "school_id": rec.school_id,
            "recipient_status": recipient_status.get(uid, "pending"),
            "response_status": response_status.get(uid),
            "has_response": response_status.get(uid) is not None,
        })

    return {
        "form_id": form_id,
        "form_title": form.title,
        "form_type": form.form_type,
        "users": users_out,
    }
