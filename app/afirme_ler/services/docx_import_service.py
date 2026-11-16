# -*- coding: utf-8 -*-
"""Importação DOCX exclusiva do Afirme Ler (preview e commit)."""
from __future__ import annotations

import io
import json
import re
import unicodedata
from typing import Any, Dict, List, Optional
from uuid import UUID

from app import db
from app.models.grades import Grade
from app.models.subject import Subject
from app.question_import.docx_parser import parse_questions_docx
from app.question_import.importer import validate_import_defaults
from app.afirme_ler.services.question_bank_service import (
    QuestionBankService,
    parse_create_payload,
    validate_dictation_marks,
)
from app.afirme_ler.services.written_test_service import (
    WrittenTestService,
    _optional_description,
    _required_title,
    to_detail,
    validate_scope,
)

MAX_DOCX_BYTES = 25 * 1024 * 1024


def _is_uuid(value: Any) -> bool:
    if value is None:
        return False
    try:
        UUID(str(value).strip())
        return True
    except (ValueError, AttributeError, TypeError):
        return False


def _norm_name(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text).strip().lower()


def _resolve_subject(meta: Dict[str, Any], defaults: Dict[str, Any]) -> str:
    """
    Disciplina por bloco.
    Prioridade: SubjectId do DOCX → nome Disciplina → subjectId/default do formulário.
    Se allowedSubjectIds existir, a disciplina precisa estar na lista.
    """
    allowed = defaults.get("allowedSubjectIds")
    allowed_set = {str(a) for a in allowed} if allowed else None

    subject_id = None
    if _is_uuid(meta.get("subjectId")):
        subject_id = str(meta.get("subjectId")).strip()
    elif _is_uuid(meta.get("subject")):
        subject_id = str(meta.get("subject")).strip()

    subject_name = meta.get("subject") if not _is_uuid(meta.get("subject")) else None

    if subject_id:
        subject = Subject.query.get(subject_id)
        if not subject:
            raise ValueError("Disciplina não encontrada neste bloco. Confira o nome da disciplina.")
        if allowed_set is not None and str(subject.id) not in allowed_set:
            name = (subject.name or "").strip() or "informada"
            raise ValueError(
                f"A disciplina '{name}' não está entre as disciplinas selecionadas na importação."
            )
        return str(subject.id)

    if subject_name:
        needle = _norm_name(str(subject_name))
        if allowed_set is not None:
            candidates = [Subject.query.get(sid) for sid in allowed_set]
            candidates = [s for s in candidates if s]
        else:
            candidates = Subject.query.all()
        match = next((s for s in candidates if _norm_name(s.name or "") == needle), None)
        if not match:
            match = next((s for s in candidates if needle in _norm_name(s.name or "")), None)
        if not match:
            raise ValueError(
                f"Disciplina não encontrada: {subject_name}. "
                "Use o nome exato de uma das disciplinas selecionadas na importação."
            )
        return str(match.id)

    form_sid = defaults.get("subjectId") or defaults.get("defaultSubjectId")
    if form_sid and _is_uuid(form_sid):
        subject = Subject.query.get(str(form_sid).strip())
        if not subject:
            raise ValueError("Disciplina padrão da importação não encontrada. Selecione novamente.")
        if allowed_set is not None and str(subject.id) not in allowed_set:
            name = (subject.name or "").strip() or "informada"
            raise ValueError(
                f"A disciplina '{name}' não está entre as disciplinas selecionadas na importação."
            )
        return str(subject.id)

    raise ValueError(
        "Disciplina obrigatória neste bloco. Informe o nome da disciplina "
        "ou selecione as disciplinas no formulário de importação."
    )


def _resolve_grade(meta: Dict[str, Any], defaults: Dict[str, Any]) -> str:
    """Prioriza série do formulário; fallback GradeId/Série do bloco."""
    for key in ("grade", "gradeId"):
        value = defaults.get(key)
        if value and _is_uuid(value):
            return str(value).strip()
    for key in ("gradeId", "grade"):
        value = meta.get(key)
        if value and _is_uuid(value):
            return str(value).strip()
    raise ValueError("Série (grade) obrigatória. Selecione a série no formulário.")


def _enrich_defaults(defaults: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Valida grade/disciplinas do form e acrescenta whitelist."""
    defaults = dict(defaults or {})
    if not defaults.get("grade") and not defaults.get("gradeId"):
        raise ValueError("Campo obrigatório do formulário ausente: grade.")
    ctx = validate_import_defaults(defaults)
    merged = {
        **defaults,
        "grade": ctx.get("gradeId") or defaults.get("grade"),
        "gradeId": ctx.get("gradeId"),
        "subjectId": ctx.get("defaultSubjectId") or defaults.get("subjectId"),
        "defaultSubjectId": ctx.get("defaultSubjectId"),
        "allowedSubjectIds": ctx.get("allowedSubjectIds"),
        "subjects": ctx.get("subjects") or [],
    }
    return merged


def _directive_marks(raw: Any) -> Dict[str, Any]:
    marks: Dict[str, Any] = {}
    text = str(raw or "").strip()
    if not text:
        return marks
    normalized = text.lower().replace(";", ",")
    for part in normalized.split(","):
        chunk = part.strip()
        if not chunk:
            continue
        if chunk.startswith(("titulo", "título")):
            marks["title"] = True
            continue
        if chunk.startswith(("enunciado", "comando")):
            marks["statement"] = True
            continue
        if chunk.startswith(("apoio", "texto de apoio")):
            marks["support"] = True
            continue
        if chunk.startswith(("alternativa", "alternativas")):
            letters = "".join(ch for ch in chunk.upper() if ch in "ABCDEFGH")
            if letters:
                marks.setdefault("options", [])
                marks["options"].extend(list(letters))
            continue
        raise ValueError(f"Item inválido em Ditar: {chunk}.")
    if "options" in marks:
        marks["options"] = list(dict.fromkeys(marks["options"]))
    return marks


def _merge_marks(block: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    marks: Dict[str, Any] = {}
    existing = block.get("dictationMarks")
    if isinstance(existing, dict):
        marks.update(existing)
    meta = block.get("meta") or {}
    directive = _directive_marks(meta.get("dictationDirective"))
    for key in ("title", "statement", "support"):
        if directive.get(key):
            marks[key] = True
    for key in ("images", "options"):
        if key in directive:
            values = list(dict.fromkeys([*(marks.get(key) or []), *directive[key]]))
            if values:
                marks[key] = values
    return validate_dictation_marks(marks or None)


def _payload(block: Dict[str, Any], defaults: Dict[str, Any]) -> Dict[str, Any]:
    meta = block.get("meta") or {}
    question_type = meta.get("type") or "multipleChoice"
    subject_id = _resolve_subject(meta, defaults)
    grade_id = _resolve_grade(meta, defaults)
    enunciado = block.get("enunciado") or {}
    solution = block.get("solution") or {}
    marks = _merge_marks(block)

    payload: Dict[str, Any] = {
        "text": (enunciado.get("text") or "").strip() or " ",
        "formattedText": enunciado.get("html") or "",
        "type": question_type,
        "subjectId": subject_id,
        "grade": grade_id,
        "title": meta.get("title"),
        "secondStatement": meta.get("secondStatement"),
        "difficulty": meta.get("difficulty"),
        "value": meta.get("value"),
        "skills": meta.get("skill"),
        "dictationMarks": marks,
    }

    canonical = str(question_type).strip().lower().replace(" ", "_")
    options = block.get("options") or []
    if marks and marks.get("options") and canonical not in ("dictation", "ditado"):
        available = [chr(65 + i) for i in range(min(len(options), 8))]
        invalid = next((letter for letter in marks["options"] if letter not in available), None)
        if invalid is not None:
            raise ValueError(f"dictationMarks.options contém alternativa inexistente: {invalid}.")
    if marks and marks.get("options") and canonical in ("dictation", "ditado"):
        raise ValueError("dictationMarks.options só é permitido em multipleChoice.")

    if canonical in ("dictation", "ditado"):
        payload["dictatedWord"] = (solution.get("text") or meta.get("dictatedWord") or "").strip() or None
    elif canonical in ("text_production", "producao_textual", "produção_textual", "bilhete"):
        payload["formattedSolution"] = solution.get("html") or solution.get("text")
    else:
        payload["options"] = [
            {
                "letter": opt.get("letter") or chr(65 + index),
                "text": "\n".join(opt.get("plain_parts") or []),
                "formattedText": "".join(opt.get("html_parts") or []),
                "isCorrect": bool(opt.get("is_correct")),
            }
            for index, opt in enumerate(options)
        ]
        # imagens embutidas nas alternativas já vêm no html
        for opt, raw in zip(payload["options"], options):
            images = raw.get("images") or []
            if images and not opt.get("formattedText"):
                opt["formattedText"] = "".join(
                    f'<img src="{img.get("dataUrl")}" />' for img in images if img.get("dataUrl")
                )
    return {key: value for key, value in payload.items() if value is not None or key == "dictationMarks"}


def _read_blocks(file_storage) -> List[Dict[str, Any]]:
    filename = str(getattr(file_storage, "filename", "") or "").lower()
    if not filename.endswith(".docx"):
        raise ValueError("Envie um arquivo .docx.")
    raw = file_storage.read()
    if not raw:
        raise ValueError("Arquivo vazio.")
    if len(raw) > MAX_DOCX_BYTES:
        raise ValueError("Arquivo excede o limite de 25 MB.")
    return parse_questions_docx(io.BytesIO(raw))


def prepare(file_storage, defaults: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    defaults = _enrich_defaults(defaults)
    blocks = _read_blocks(file_storage)
    items = []
    prepared = []
    for block in blocks:
        errors = list(block.get("parseErrors") or [])
        payload = None
        fields = None
        try:
            payload = _payload(block, defaults)
            fields = parse_create_payload(payload)
            if fields.get("subject_id") and not db.session.get(Subject, fields["subject_id"]):
                errors.append("Disciplina (subjectId) não encontrada.")
            if fields.get("grade_level") and not db.session.get(Grade, fields["grade_level"]):
                errors.append("Série (grade) não encontrada.")
        except ValueError as exc:
            errors.append(str(exc))
            fields = None
        item = {
            "index": block.get("index"),
            "valid": not errors,
            "errors": errors,
            "payload": payload or {},
            "dictationMarks": (payload or {}).get("dictationMarks"),
            "hasDictationMarks": bool((payload or {}).get("dictationMarks")),
        }
        items.append(item)
        prepared.append({"block": block, "item": item, "fields": fields})

    summary = {
        "total": len(items),
        "valid": sum(1 for item in items if item["valid"]),
        "invalid": sum(1 for item in items if not item["valid"]),
    }
    return {
        "items": items,
        "prepared": prepared,
        "summary": summary,
        "form": {
            "gradeId": defaults.get("gradeId") or defaults.get("grade"),
            "subjects": defaults.get("subjects") or [],
            "allowedSubjectIds": defaults.get("allowedSubjectIds"),
        },
    }


def _selected(pack: Dict[str, Any], indexes: Optional[List[int]]) -> List[Dict[str, Any]]:
    prepared = pack["prepared"]
    if not indexes:
        chosen = [row for row in prepared if row["item"]["valid"]]
        if not chosen:
            raise ValueError("Selecione ao menos uma questão para importar.")
        return chosen
    by_index = {row["item"]["index"]: row for row in prepared}
    chosen = []
    missing = []
    for index in sorted(indexes):
        row = by_index.get(index)
        if row is None:
            missing.append(index)
        else:
            chosen.append(row)
    if missing:
        raise ValueError(f"Índice {missing[0]} não existe no arquivo.")
    if not chosen:
        raise ValueError("Selecione ao menos uma questão para importar.")
    return chosen


def import_questions(
    file_storage,
    user: Dict[str, Any],
    defaults: Optional[Dict[str, Any]] = None,
    *,
    commit: bool = False,
    indexes: Optional[List[int]] = None,
    dictation_overrides: Optional[Dict[int, Any]] = None,
) -> Dict[str, Any]:
    pack = prepare(file_storage, defaults)
    if not commit:
        return {
            "mode": "preview",
            "form": pack.get("form"),
            "summary": pack["summary"],
            "questions": pack["items"],
        }

    overrides = dictation_overrides or {}
    for index, raw_marks in overrides.items():
        item = next((row for row in pack["items"] if row["index"] == index), None)
        if item is None:
            raise ValueError(f"Índice {index} não existe no arquivo.")
        marks = validate_dictation_marks(raw_marks)
        item["dictationMarks"] = marks
        item["hasDictationMarks"] = bool(marks)
        item["payload"]["dictationMarks"] = marks

    selected = _selected(pack, indexes)
    created = []
    failed = []
    for row in selected:
        item = row["item"]
        if not item["valid"]:
            failed.append({"index": item["index"], "errors": item["errors"]})
            continue
        try:
            question = QuestionBankService.create_pending(user, item["payload"])
            created.append({
                "index": item["index"],
                "id": question.id,
                "type": question.question_type,
                "origin": question.origin,
                "dictationMarks": question.dictation_marks,
            })
        except Exception as exc:  # noqa: BLE001 - agrega falhas por bloco
            failed.append({"index": item["index"], "errors": [str(exc)]})

    if failed and not created:
        db.session.rollback()
    else:
        db.session.commit()

    summary = {
        **pack["summary"],
        "created": len(created),
        "failed": len(failed),
    }
    return {
        "mode": "commit",
        "summary": summary,
        "questions": pack["items"],
        "created": created,
        "failed": failed,
    }


def import_written_test(
    file_storage,
    user: Dict[str, Any],
    defaults: Optional[Dict[str, Any]] = None,
    test_payload: Optional[Dict[str, Any]] = None,
    *,
    commit: bool = False,
    indexes: Optional[List[int]] = None,
) -> Dict[str, Any]:
    test_payload = test_payload or {}
    validated_test_payload = {
        "title": _required_title(test_payload.get("title")),
        "description": _optional_description(test_payload.get("description")),
    }
    scope = validate_scope(test_payload)
    validated_test_payload.update({
        "gradeIds": scope["grade_ids"],
        "schoolIds": scope["school_ids"],
        "classIds": scope["class_ids"],
    })
    pack = prepare(file_storage, defaults)
    selected = _selected(pack, indexes)
    if not commit:
        return {
            "mode": "preview",
            "summary": pack["summary"],
            "questions": pack["items"],
            "assessment": validated_test_payload,
        }

    created_questions = []
    question_refs = []
    for order, row in enumerate(selected, start=1):
        item = row["item"]
        if not item["valid"]:
            raise ValueError(
                f"A avaliação não foi criada: a questão {item['index']} é inválida."
            )
        question = QuestionBankService.create_pending(user, item["payload"])
        created_questions.append({
            "index": item["index"],
            "id": question.id,
            "type": question.question_type,
        })
        question_refs.append({"id": question.id, "order": order})

    payload = {
        **validated_test_payload,
        "questions": question_refs,
    }
    written_test = WrittenTestService.create(user, payload)
    return {
        "mode": "commit",
        "summary": {**pack["summary"], "created": len(created_questions), "failed": 0},
        "createdQuestions": created_questions,
        "writtenTest": to_detail(written_test),
    }


def parse_import_form(request) -> Dict[str, Any]:
    """Extrai defaults/commit/indexes/confirmation do multipart do FE."""
    commit_raw = str(request.form.get("commit") or "false").strip().lower()
    commit = commit_raw in ("1", "true", "yes", "sim")
    grade = request.form.get("grade") or request.form.get("gradeId")
    subject_id = request.form.get("subjectId") or request.form.get("subject_id")
    subject_ids_raw = request.form.get("subjectIds") or request.form.get("subjects")
    listed = request.form.getlist("subjectIds") or request.form.getlist("subjectIds[]")
    if listed and not subject_ids_raw:
        subject_ids_raw = ",".join(v.strip() for v in listed if v and str(v).strip())
    indexes_raw = request.form.get("indexes") or ""
    indexes = None
    if indexes_raw.strip():
        indexes = [int(part.strip()) for part in indexes_raw.split(",") if part.strip()]
    confirmation_raw = request.form.get("confirmation")
    overrides: Dict[int, Any] = {}
    if confirmation_raw:
        data = json.loads(confirmation_raw)
        for item in data.get("questions") or []:
            overrides[int(item["index"])] = item.get("dictationMarks")
    defaults: Dict[str, Any] = {"grade": grade, "subjectId": subject_id}
    if subject_ids_raw:
        defaults["subjectIds"] = subject_ids_raw
    return {
        "commit": commit,
        "defaults": defaults,
        "indexes": indexes,
        "dictation_overrides": overrides,
    }
