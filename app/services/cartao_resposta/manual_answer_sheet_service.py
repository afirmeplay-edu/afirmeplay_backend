# -*- coding: utf-8 -*-
"""
Entrada manual de respostas do cartão (alternativa à correção OMR por imagem).
Escopo: cartão resposta (AnswerSheetGabarito sem test_id) e prova física (gabarito com test_id).
Não inclui prova online virtual sem gabarito.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import desc

from app import db
from app.models.answerSheetGabarito import AnswerSheetGabarito
from app.models.answerSheetResult import AnswerSheetResult
from app.models.grades import Grade
from app.models.school import School
from app.models.student import Student
from app.models.studentClass import Class
from app.models.teacher import Teacher
from app.models.teacherClass import TeacherClass
from app.models.test import Test
from app.report_analysis.answer_sheet_report_builder import (
    get_answer_sheet_target_classes_for_report,
)
from app.services.cartao_resposta.correction_new_grid import AnswerSheetCorrectionNewGrid
from app.utils.uuid_helpers import ensure_uuid

logger = logging.getLogger(__name__)

STAFF_ROLES = frozenset({
    "admin",
    "professor",
    "coordenador",
    "diretor",
    "tecadm",
    "aplicador",
})


class ManualAnswerSheetError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def resolve_gabarito_for_manual(
    gabarito_id: Optional[str] = None,
    test_id: Optional[str] = None,
) -> AnswerSheetGabarito:
    """Resolve gabarito por id ou test_id. Exige registro em answer_sheet_gabaritos."""
    gid = (gabarito_id or "").strip() or None
    tid = (test_id or "").strip() or None

    if not gid and not tid:
        raise ManualAnswerSheetError(
            "Informe gabarito_id ou test_id.", 400
        )

    gabarito: Optional[AnswerSheetGabarito] = None
    if gid:
        gabarito = AnswerSheetGabarito.query.get(gid)
        if not gabarito:
            raise ManualAnswerSheetError("Gabarito não encontrado.", 404)
        if tid and gabarito.test_id and str(gabarito.test_id) != str(tid):
            raise ManualAnswerSheetError(
                "test_id não corresponde ao gabarito informado.", 400
            )
    else:
        gabarito = AnswerSheetGabarito.query.filter_by(test_id=tid).first()
        if not gabarito:
            raise ManualAnswerSheetError(
                "Gabarito não encontrado para esta prova. "
                "Entrada manual está disponível apenas para cartão resposta e prova física.",
                404,
            )

    return gabarito


def _gabarito_correct_answers_int(gabarito: AnswerSheetGabarito) -> Dict[int, str]:
    raw = gabarito.correct_answers
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            raw = {}
    out: Dict[int, str] = {}
    for key, value in (raw or {}).items():
        try:
            q = int(key)
            out[q] = str(value).upper() if value else ""
        except (ValueError, TypeError):
            continue
    return out


def _alternatives_by_question(gabarito: AnswerSheetGabarito) -> Dict[int, List[str]]:
    blocks_config = gabarito.blocks_config or {}
    if isinstance(blocks_config, str):
        try:
            blocks_config = json.loads(blocks_config)
        except json.JSONDecodeError:
            blocks_config = {}
    topology = blocks_config.get("topology") or {}
    blocks = topology.get("blocks") or []
    mapping: Dict[int, List[str]] = {}
    for block in blocks:
        for question in block.get("questions") or []:
            q = question.get("q")
            if q is None:
                continue
            try:
                q_num = int(q)
            except (ValueError, TypeError):
                continue
            alts = question.get("alternatives") or ["A", "B", "C", "D"]
            if isinstance(alts, list) and len(alts) >= 2:
                mapping[q_num] = [str(a).upper() for a in alts]
            else:
                mapping[q_num] = ["A", "B", "C", "D"]
    if not mapping:
        for q in range(1, (gabarito.num_questions or 0) + 1):
            mapping[q] = ["A", "B", "C", "D"]
    return mapping


def _blocks_for_form(gabarito: AnswerSheetGabarito) -> List[Dict[str, Any]]:
    blocks_config = gabarito.blocks_config or {}
    if isinstance(blocks_config, str):
        try:
            blocks_config = json.loads(blocks_config)
        except json.JSONDecodeError:
            blocks_config = {}
    topology = blocks_config.get("topology") or {}
    blocks_raw = topology.get("blocks") or []
    blocks_out: List[Dict[str, Any]] = []
    for block in blocks_raw:
        questions_out = []
        for question in block.get("questions") or []:
            q = question.get("q")
            if q is None:
                continue
            questions_out.append({
                "q": int(q),
                "alternatives": question.get("alternatives") or ["A", "B", "C", "D"],
            })
        blocks_out.append({
            "block_id": block.get("block_id"),
            "subject_id": block.get("subject_id"),
            "subject_name": block.get("subject_name"),
            "questions": questions_out,
        })
    return blocks_out


def _entry_kind(gabarito: AnswerSheetGabarito) -> str:
    if not gabarito.test_id:
        return "cartao_resposta"
    test = Test.query.get(gabarito.test_id)
    if test and (getattr(test, "evaluation_mode", None) or "virtual") == "physical":
        return "prova_fisica"
    return "cartao_resposta"


def assert_user_can_manual_correct(
    user: Dict[str, Any],
    gabarito: AnswerSheetGabarito,
    student: Student,
) -> None:
    role = (user.get("role") or "").lower()
    if role not in STAFF_ROLES:
        raise ManualAnswerSheetError("Sem permissão.", 403)

    # Admin, aplicador, diretor, coordenador, tecadm: qualquer gabarito/aluno do tenant.
    if role == "professor":
        if not gabarito.created_by or str(gabarito.created_by) != str(user.get("id")):
            raise ManualAnswerSheetError(
                "Você só pode registrar respostas manuais em avaliações que você criou.",
                403,
            )
        from app.models.teacher import Teacher
        from app.models.teacherClass import TeacherClass

        teacher = Teacher.query.filter_by(user_id=user["id"]).first()
        if not teacher:
            raise ManualAnswerSheetError("Professor não encontrado.", 403)
        allowed_class_ids = {
            tc.class_id
            for tc in TeacherClass.query.filter_by(teacher_id=teacher.id).all()
            if tc.class_id
        }
        if not student.class_id or student.class_id not in allowed_class_ids:
            raise ManualAnswerSheetError(
                "Aluno não pertence a uma turma vinculada a você.", 403
            )
        return

    # Demais papéis: gabarito e aluno no tenant (contexto de cidade já validado na rota)
    return


def _user_can_manual_correct_bool(
    user: Dict[str, Any],
    gabarito: AnswerSheetGabarito,
    student: Student,
) -> bool:
    try:
        assert_user_can_manual_correct(user, gabarito, student)
        return True
    except ManualAnswerSheetError:
        return False


def assert_user_can_list_gabarito_students(
    user: Dict[str, Any],
    gabarito: AnswerSheetGabarito,
) -> None:
    role = (user.get("role") or "").lower()
    if role not in STAFF_ROLES:
        raise ManualAnswerSheetError("Sem permissão.", 403)
    if role == "professor":
        if not gabarito.created_by or str(gabarito.created_by) != str(user.get("id")):
            raise ManualAnswerSheetError(
                "Você só pode listar alunos de avaliações que você criou.",
                403,
            )


def _resolve_report_scope_for_student_list(
    user: Dict[str, Any],
    city_id: str,
) -> Tuple[str, Optional[str]]:
    role = (user.get("role") or "").lower()
    if role == "professor":
        teacher = Teacher.query.filter_by(user_id=user["id"]).first()
        if not teacher:
            raise ManualAnswerSheetError("Professor não encontrado.", 403)
        return "teacher", str(teacher.id)
    return "city", city_id


def _filter_target_classes(
    classes: List[Class],
    class_id: Optional[str],
    grade_id: Optional[str],
    school_id: Optional[str],
) -> List[Class]:
    out = list(classes)
    if class_id:
        class_uuid = ensure_uuid(class_id)
        if not class_uuid:
            raise ManualAnswerSheetError("class_id inválido.", 400)
        out = [c for c in out if c.id == class_uuid]
        if not out:
            raise ManualAnswerSheetError(
                "Turma não está entre as turmas deste cartão.", 404
            )
    if grade_id:
        grade_uuid = ensure_uuid(grade_id)
        if not grade_uuid:
            raise ManualAnswerSheetError("grade_id inválido.", 400)
        out = [c for c in out if c.grade_id == grade_uuid]
        if not out:
            raise ManualAnswerSheetError(
                "Nenhuma turma desta série está vinculada a este cartão.", 404
            )
    if school_id:
        sid = str(school_id).strip()
        out = [c for c in out if c.school_id and str(c.school_id) == sid]
        if not out:
            raise ManualAnswerSheetError(
                "Nenhuma turma desta escola está vinculada a este cartão.", 404
            )
    return out


def _latest_results_by_student(gabarito_id: str) -> Dict[str, AnswerSheetResult]:
    rows = (
        AnswerSheetResult.query.filter_by(gabarito_id=gabarito_id)
        .order_by(desc(AnswerSheetResult.corrected_at))
        .all()
    )
    by_student: Dict[str, AnswerSheetResult] = {}
    for row in rows:
        sid = str(row.student_id)
        if sid not in by_student:
            by_student[sid] = row
    return by_student


def _student_row_payload(
    student: Student,
    result: Optional[AnswerSheetResult],
    gabarito: AnswerSheetGabarito,
    user: Dict[str, Any],
) -> Dict[str, Any]:
    has_result = result is not None
    return {
        "student_id": str(student.id),
        "name": (student.name or "").strip() or None,
        "registration": student.registration,
        "has_result": has_result,
        "correction_status": "P" if has_result else "A",
        "result_id": result.id if result else None,
        "detection_method": result.detection_method if result else None,
        "corrected_at": (
            result.corrected_at.isoformat()
            if result and result.corrected_at
            else None
        ),
        "can_manual_correct": _user_can_manual_correct_bool(user, gabarito, student),
    }


def _class_meta(classe: Class) -> Dict[str, Any]:
    school_name = None
    if classe.school_id:
        school = School.query.get(classe.school_id)
        school_name = school.name if school else None
    grade_name = None
    if classe.grade_id and classe.grade:
        grade_name = classe.grade.name
    elif classe.grade_id:
        grade = Grade.query.get(classe.grade_id)
        grade_name = grade.name if grade else None
    return {
        "class_id": str(classe.id),
        "class_name": classe.name,
        "grade_id": str(classe.grade_id) if classe.grade_id else None,
        "grade_name": grade_name,
        "school_id": str(classe.school_id) if classe.school_id else None,
        "school_name": school_name,
    }


def list_students_for_gabarito(
    gabarito_id: str,
    user: Dict[str, Any],
    city_id: str,
    class_id: Optional[str] = None,
    grade_id: Optional[str] = None,
    school_id: Optional[str] = None,
    flat: bool = False,
) -> Dict[str, Any]:
    """
    Lista alunos das turmas-alvo do gabarito (escopo de geração/relatório),
    com status de correção e flag para entrada manual.
    """
    gid = (gabarito_id or "").strip()
    if not gid:
        raise ManualAnswerSheetError("gabarito_id é obrigatório.", 400)
    if not (city_id or "").strip():
        raise ManualAnswerSheetError("Contexto de município é obrigatório.", 400)

    gabarito = AnswerSheetGabarito.query.get(gid)
    if not gabarito:
        raise ManualAnswerSheetError("Gabarito não encontrado.", 404)

    assert_user_can_list_gabarito_students(user, gabarito)

    scope_type, scope_ref = _resolve_report_scope_for_student_list(user, city_id.strip())
    turmas_alvo = get_answer_sheet_target_classes_for_report(
        gabarito, scope_type, scope_ref
    )
    if not turmas_alvo:
        raise ManualAnswerSheetError(
            "Nenhuma turma encontrada para este cartão neste escopo.", 404
        )

    turmas_filtradas = _filter_target_classes(
        turmas_alvo, class_id, grade_id, school_id
    )

    class_ids = [c.id for c in turmas_filtradas]
    alunos_por_turma: Dict[Any, List[Student]] = defaultdict(list)
    if class_ids:
        for aluno in (
            Student.query.filter(Student.class_id.in_(class_ids))
            .order_by(Student.class_id, Student.name)
            .all()
        ):
            alunos_por_turma[aluno.class_id].append(aluno)

    results_by_student = _latest_results_by_student(str(gabarito.id))

    classes_payload: List[Dict[str, Any]] = []
    flat_students: List[Dict[str, Any]] = []
    total_students = 0

    for classe in turmas_filtradas:
        meta = _class_meta(classe)
        students_payload = []
        for student in alunos_por_turma.get(classe.id, []):
            result = results_by_student.get(str(student.id))
            row = _student_row_payload(student, result, gabarito, user)
            students_payload.append(row)
            total_students += 1
            if flat:
                flat_students.append({
                    **row,
                    "class_id": meta["class_id"],
                    "class_name": meta["class_name"],
                    "grade_id": meta["grade_id"],
                    "grade_name": meta["grade_name"],
                    "school_id": meta["school_id"],
                    "school_name": meta["school_name"],
                })
        classes_payload.append({**meta, "students": students_payload})

    base = {
        "gabarito_id": gabarito.id,
        "gabarito_title": gabarito.title,
        "test_id": str(gabarito.test_id) if gabarito.test_id else None,
        "entry_kind": _entry_kind(gabarito),
        "num_questions": gabarito.num_questions,
        "scope_summary": {
            "scope_type": gabarito.scope_type,
            "class_count": len(turmas_filtradas),
            "student_count": total_students,
        },
    }

    if flat:
        return {**base, "student_count": total_students, "students": flat_students}
    return {**base, "classes": classes_payload}


def normalize_manual_answers(
    raw_answers: Dict[Any, Any],
    gabarito_dict: Dict[int, str],
    alternatives_map: Dict[int, List[str]],
) -> Dict[int, Optional[str]]:
    """
    Monta respostas para todas as questões do gabarito.
    Chave ausente ou null/'' = em branco.
    """
    if not isinstance(raw_answers, dict):
        raise ManualAnswerSheetError("Campo 'answers' deve ser um objeto.", 400)

    normalized: Dict[int, Optional[str]] = {}

    for q_num in sorted(gabarito_dict.keys()):
        val = raw_answers.get(str(q_num))
        if val is None:
            val = raw_answers.get(q_num)

        if val is None or (isinstance(val, str) and not val.strip()):
            normalized[q_num] = None
            continue

        letter = str(val).strip().upper()
        if letter == "INVALID":
            normalized[q_num] = "INVALID"
            continue

        allowed = alternatives_map.get(q_num, ["A", "B", "C", "D"])
        if letter not in allowed:
            raise ManualAnswerSheetError(
                f"Questão {q_num}: alternativa '{letter}' inválida. "
                f"Permitidas: {', '.join(allowed)}.",
                400,
            )
        normalized[q_num] = letter

    return normalized


def get_manual_entry_form(
    gabarito_id: Optional[str],
    test_id: Optional[str],
    student_id: str,
    user: Dict[str, Any],
) -> Dict[str, Any]:
    gabarito = resolve_gabarito_for_manual(gabarito_id=gabarito_id, test_id=test_id)
    student = Student.query.get(student_id)
    if not student:
        raise ManualAnswerSheetError("Aluno não encontrado.", 404)

    assert_user_can_manual_correct(user, gabarito, student)

    existing = AnswerSheetResult.query.filter_by(
        gabarito_id=gabarito.id,
        student_id=student_id,
    ).first()

    saved_answers: Dict[str, Any] = {}
    if existing and existing.detected_answers:
        da = existing.detected_answers
        if isinstance(da, dict):
            saved_answers = da

    return {
        "gabarito_id": gabarito.id,
        "test_id": str(gabarito.test_id) if gabarito.test_id else None,
        "kind": _entry_kind(gabarito),
        "title": gabarito.title,
        "num_questions": gabarito.num_questions,
        "use_blocks": bool(gabarito.use_blocks),
        "blocks": _blocks_for_form(gabarito),
        "correct_answers": gabarito.correct_answers,
        "student": {
            "id": student.id,
            "name": student.name,
            "class_id": str(student.class_id) if student.class_id else None,
        },
        "saved_answers": saved_answers,
        "existing_result_id": existing.id if existing else None,
        "detection_method": existing.detection_method if existing else None,
    }


def submit_manual_correction(
    gabarito_id: Optional[str],
    test_id: Optional[str],
    student_id: str,
    raw_answers: Dict[Any, Any],
    user: Dict[str, Any],
) -> Dict[str, Any]:
    gabarito = resolve_gabarito_for_manual(gabarito_id=gabarito_id, test_id=test_id)
    student = Student.query.get(student_id)
    if not student:
        raise ManualAnswerSheetError("Aluno não encontrado.", 404)

    assert_user_can_manual_correct(user, gabarito, student)

    gabarito_dict = _gabarito_correct_answers_int(gabarito)
    if not gabarito_dict:
        raise ManualAnswerSheetError("Gabarito sem respostas corretas configuradas.", 400)

    alternatives_map = _alternatives_by_question(gabarito)
    answers = normalize_manual_answers(raw_answers, gabarito_dict, alternatives_map)

    corrector = AnswerSheetCorrectionNewGrid(debug=False)
    correction = corrector._build_result(answers, gabarito_dict)
    correction["gabarito_id"] = gabarito.id
    correction["student_id"] = student_id
    correction["detection_method"] = "manual"
    if gabarito.test_id:
        correction["test_id"] = str(gabarito.test_id)

    saved = corrector.salvar_resultado(correction)
    if not saved:
        raise ManualAnswerSheetError(
            "Não foi possível salvar o resultado. Tente novamente.", 500
        )

    student_name = student.name
    logger.info(
        "Entrada manual salva: gabarito=%s student=%s user=%s",
        gabarito.id,
        student_id,
        user.get("id"),
    )

    return {
        "message": "Respostas registradas com sucesso",
        "system": "manual",
        "detection_method": "manual",
        "kind": _entry_kind(gabarito),
        "student_id": student_id,
        "student_name": student_name,
        "gabarito_id": gabarito.id,
        "test_id": str(gabarito.test_id) if gabarito.test_id else None,
        "correct": correction["correct_answers"],
        "wrong": correction["wrong_answers"],
        "blank": correction["blank_answers"],
        "invalid": correction["invalid_answers"],
        "total": correction["total_questions"],
        "score": correction["score"],
        "percentage": correction["score"],
        "detailed_answers": correction["detailed_answers"],
        "student_answers": correction["student_answers"],
        "answer_key": correction["answer_key"],
        "answer_sheet_result_id": saved.get("id") if isinstance(saved, dict) else None,
        "saved": saved,
    }
