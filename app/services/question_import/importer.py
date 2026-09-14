# -*- coding: utf-8 -*-
"""Valida, resolve FKs e cria questões a partir do DOCX parseado."""

from __future__ import annotations

import logging
import re
import unicodedata
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from app import db
from app.models.grades import Grade
from app.models.question import Question
from app.models.skill import Skill
from app.models.subject import Subject
from app.services.question_import.constants import ALLOWED_DIFFICULTIES
from app.services.question_import.docx_parser import parse_questions_docx

logger = logging.getLogger(__name__)

UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)

MAX_DOCX_BYTES = 25 * 1024 * 1024  # 25 MB


def _parse_indexes(raw_values: Any) -> Optional[List[int]]:
    """
    Aceita:
      - None / ausente → None (commit de todas as válidas)
      - "1,3,5"
      - "[1, 3, 5]"
      - lista de strings/ints (getlist)
    Retorna lista ordenada sem duplicatas, ou None.
    """
    if raw_values is None:
        return None

    chunks: List[str] = []
    if isinstance(raw_values, (list, tuple)):
        if len(raw_values) == 0:
            return []
        for item in raw_values:
            if item is None:
                continue
            chunks.append(str(item).strip())
    else:
        text = str(raw_values).strip()
        if not text:
            return None
        chunks.append(text)

    indexes: List[int] = []
    seen = set()
    for chunk in chunks:
        if not chunk:
            continue
        # JSON array
        if chunk.startswith("[") and chunk.endswith("]"):
            try:
                import json

                parsed = json.loads(chunk)
                if not isinstance(parsed, list):
                    raise ValueError("indexes deve ser uma lista de inteiros")
                for n in parsed:
                    idx = int(n)
                    if idx not in seen:
                        seen.add(idx)
                        indexes.append(idx)
                continue
            except (TypeError, ValueError) as exc:
                raise ValueError(f"indexes inválido: {chunk}") from exc

        for part in re.split(r"[,\s;]+", chunk):
            if not part:
                continue
            try:
                idx = int(part)
            except ValueError as exc:
                raise ValueError(
                    f"indexes inválido: '{part}'. Use inteiros (ex.: 1,3,5)."
                ) from exc
            if idx < 1:
                raise ValueError("indexes deve conter apenas números >= 1")
            if idx not in seen:
                seen.add(idx)
                indexes.append(idx)

    return indexes


def parse_indexes_from_request(form, args=None) -> Optional[List[int]]:
    """Lê indexes do multipart/query: indexes, indexes[], index."""
    args = args or {}
    candidates = []

    if form is not None:
        if hasattr(form, "getlist"):
            listed = form.getlist("indexes") or form.getlist("indexes[]") or form.getlist("index")
            if listed:
                candidates.extend(listed)
        single = form.get("indexes") if hasattr(form, "get") else None
        if single not in (None, "") and single not in candidates:
            candidates.append(single)

    if args:
        if hasattr(args, "getlist"):
            listed = args.getlist("indexes") or args.getlist("indexes[]")
            if listed:
                candidates.extend(listed)
        single = args.get("indexes") if hasattr(args, "get") else None
        if single not in (None, "") and single not in candidates:
            candidates.append(single)

    if not candidates:
        return None
    return _parse_indexes(candidates)


def _strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def _norm_name(value: str) -> str:
    value = _strip_accents((value or "").strip().lower())
    value = re.sub(r"\s+", " ", value)
    return value


def _is_uuid(value: Any) -> bool:
    if value is None:
        return False
    text = str(value).strip()
    if not UUID_RE.match(text):
        return False
    try:
        UUID(text)
        return True
    except Exception:
        return False


def _looks_like_data_url(value: Any) -> bool:
    return isinstance(value, str) and value.startswith("data:image/")


def _sanitize_option_for_preview(option: Dict[str, Any]) -> Dict[str, Any]:
    """Mantém estrutura, mas resume base64 grande para o JSON de preview."""
    out = dict(option)
    image = out.get("image")
    if _looks_like_data_url(image):
        out["image"] = {
            "present": True,
            "mime": image.split(";")[0].replace("data:", ""),
            "sizeEstimate": len(image),
            "previewDataUrl": image if len(image) < 200_000 else None,
        }
        if out["image"]["previewDataUrl"] is None:
            out["image"]["note"] = "Imagem grande omitida no preview; será enviada no commit."
    formatted = out.get("formattedText")
    if isinstance(formatted, str) and "data:image/" in formatted and len(formatted) > 250_000:
        out["formattedTextPreview"] = re.sub(
            r'src="data:image/[^"]+"',
            'src="[imagem]"',
            formatted,
        )
        out.pop("formattedText", None)
        out["hasEmbeddedImages"] = True
    return out


def _sanitize_html_for_preview(html_content: Optional[str]) -> Optional[str]:
    if not html_content:
        return html_content
    if len(html_content) <= 250_000:
        return html_content
    return re.sub(r'src="data:image/[^"]+"', 'src="[imagem]"', html_content)


def _form_subject_id(defaults: Dict[str, Any]) -> Optional[str]:
    """IDs do formulário têm prioridade absoluta sobre o DOCX."""
    for key in ("subjectId", "subject"):
        value = defaults.get(key)
        if value and _is_uuid(value):
            return str(value).strip()
    return None


def _form_grade_id(defaults: Dict[str, Any]) -> Optional[str]:
    for key in ("gradeId", "grade"):
        value = defaults.get(key)
        if value and _is_uuid(value):
            return str(value).strip()
    return None


def _parse_subject_ids_list(raw: Any) -> List[str]:
    """Aceita 'id1,id2', JSON list, ou lista."""
    if raw is None or raw == "":
        return []
    if isinstance(raw, (list, tuple)):
        return [str(x).strip() for x in raw if str(x).strip() and _is_uuid(str(x).strip())]
    text = str(raw).strip()
    if text.startswith("["):
        try:
            import json

            parsed = json.loads(text)
            if isinstance(parsed, list):
                return [str(x).strip() for x in parsed if str(x).strip() and _is_uuid(str(x).strip())]
        except Exception:
            pass
    out = []
    for part in re.split(r"[,\s;]+", text):
        part = part.strip()
        if part and _is_uuid(part):
            out.append(part)
    return out


def validate_import_defaults(defaults: Dict[str, Any]) -> Dict[str, Any]:
    """
    Valida grade obrigatória do formulário.
    subjectId é opcional (default para questões sem disciplina no DOCX).
    subjectIds (lista) lista as disciplinas permitidas / do template.

    Retorna:
      gradeId, gradeName,
      defaultSubjectId?, defaultSubjectName?,
      subjects: [{id, name}, ...]
    """
    defaults = defaults or {}
    grade_id = _form_grade_id(defaults)
    if not grade_id:
        raise ValueError(
            "Campo obrigatório do formulário ausente: grade. "
            "Selecione a série antes de baixar/enviar o arquivo."
        )

    grade = Grade.query.get(grade_id)
    if not grade:
        raise ValueError(f"Série não encontrada para grade={grade_id}")

    subject_ids = _parse_subject_ids_list(
        defaults.get("subjectIds") or defaults.get("subjects")
    )
    single = _form_subject_id(defaults)
    if single and single not in subject_ids:
        subject_ids.insert(0, single)

    subjects: List[Dict[str, Any]] = []
    seen = set()
    for sid in subject_ids:
        if sid in seen:
            continue
        seen.add(sid)
        subject = Subject.query.get(sid)
        if not subject:
            raise ValueError(f"Disciplina não encontrada para subjectId={sid}")
        subjects.append({"id": subject.id, "name": subject.name})

    default_subject = subjects[0] if len(subjects) == 1 else None
    if single and not default_subject:
        # default explícito mesmo com várias disciplinas na lista
        match = next((s for s in subjects if s["id"] == single), None)
        default_subject = match

    ctx: Dict[str, Any] = {
        "gradeId": str(grade.id),
        "gradeName": grade.name,
        "subjects": subjects,
        # compat: campos antigos quando há exatamente 1 disciplina
        "subjectId": default_subject["id"] if default_subject and len(subjects) <= 1 else (
            single if single else None
        ),
        "subjectName": default_subject["name"] if default_subject and len(subjects) <= 1 else (
            next((s["name"] for s in subjects if s["id"] == single), None) if single else None
        ),
        "defaultSubjectId": single or (subjects[0]["id"] if len(subjects) == 1 else None),
        "defaultSubjectName": (
            next((s["name"] for s in subjects if s["id"] == single), None)
            if single
            else (subjects[0]["name"] if len(subjects) == 1 else None)
        ),
        "allowedSubjectIds": [s["id"] for s in subjects] if subjects else None,
    }
    return ctx


def normalize_difficulty(raw: Any) -> Optional[str]:
    """
    Aceita variação leve de acento/caixa/espaços e devolve o label canônico.
    Retorna None se não mapear para nenhum dos 4 níveis.
    """
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    needle = _norm_name(text)
    for label in ALLOWED_DIFFICULTIES:
        if _norm_name(label) == needle:
            return label
    return None


def _resolve_question_type(meta: Dict[str, Any]) -> Tuple[str, List[str]]:
    """
    Importador só aceita múltipla escolha.
    Sem Tipo no arquivo → multipleChoice.
    Com Tipo diferente de objetiva → erro.
    """
    errors: List[str] = []
    raw = meta.get("type")
    if raw in (None, ""):
        return "multipleChoice", errors

    from app.services.question_import.docx_parser import _normalize_type

    mapped = _normalize_type(str(raw))
    if mapped == "multipleChoice":
        return "multipleChoice", errors

    errors.append(
        "Este importador aceita apenas questões de múltipla escolha. "
        f"Tipo informado no arquivo: {raw!r}. Remova o campo Tipo ou use uma questão objetiva."
    )
    return "multipleChoice", errors


def _resolve_subject(meta: Dict[str, Any], defaults: Dict[str, Any]) -> Tuple[Optional[str], Optional[str], List[str]]:
    """
    Disciplina por questão.
    Prioridade: SubjectId do DOCX → nome Disciplina no DOCX → subjectId default do formulário.
    Se allowedSubjectIds estiver definido, a disciplina precisa estar na lista.
    """
    errors: List[str] = []
    allowed = defaults.get("allowedSubjectIds")

    subject_id = None
    if _is_uuid(meta.get("subjectId")):
        subject_id = str(meta.get("subjectId")).strip()
    elif _is_uuid(meta.get("subject")):
        subject_id = str(meta.get("subject")).strip()

    subject_name = meta.get("subject") if not _is_uuid(meta.get("subject")) else None

    if subject_id:
        subject = Subject.query.get(subject_id)
        if not subject:
            errors.append(f"Disciplina não encontrada para SubjectId={subject_id}")
            return None, None, errors
        if allowed and subject.id not in allowed and str(subject.id) not in [str(a) for a in allowed]:
            errors.append(
                f"Disciplina '{subject.name}' (SubjectId={subject.id}) não está entre as "
                "disciplinas permitidas deste arquivo. Use um SubjectId da lista do template."
            )
            return None, None, errors
        return subject.id, subject.name, errors

    if subject_name:
        needle = _norm_name(str(subject_name))
        # restringe busca às permitidas se houver lista
        if allowed:
            candidates = [Subject.query.get(sid) for sid in allowed]
            candidates = [s for s in candidates if s]
        else:
            candidates = Subject.query.all()
        match = next((s for s in candidates if _norm_name(s.name or "") == needle), None)
        if not match:
            match = next((s for s in candidates if needle in _norm_name(s.name or "")), None)
        if not match:
            errors.append(
                f"Disciplina não encontrada: {subject_name}. "
                "Copie o SubjectId da lista do template para evitar erro de nome."
            )
            return None, None, errors
        return match.id, match.name, errors

    # fallback: default do formulário (1 disciplina ou subjectId explícito)
    form_sid = _form_subject_id(defaults) or defaults.get("defaultSubjectId")
    if form_sid and _is_uuid(form_sid):
        subject = Subject.query.get(str(form_sid).strip())
        if not subject:
            errors.append(f"Disciplina padrão do formulário não encontrada: {form_sid}")
            return None, None, errors
        return subject.id, subject.name, errors

    errors.append(
        "Disciplina obrigatória neste bloco. Informe SubjectId (copie da lista do template) "
        "ou envie subjectId único no formulário como padrão."
    )
    return None, None, errors


def _resolve_grade(meta: Dict[str, Any], defaults: Dict[str, Any]) -> Tuple[Optional[str], Optional[str], List[str]]:
    """Prioriza grade do formulário; retorna (grade_id, grade_name, errors)."""
    errors: List[str] = []
    grade_id = _form_grade_id(defaults)
    if not grade_id and _is_uuid(meta.get("gradeId")):
        grade_id = str(meta.get("gradeId")).strip()
    if not grade_id and _is_uuid(meta.get("grade")):
        grade_id = str(meta.get("grade")).strip()

    if grade_id:
        grade = Grade.query.get(str(grade_id).strip())
        if not grade:
            errors.append(f"Série não encontrada para GradeId={grade_id}")
            return None, None, errors
        return str(grade.id), grade.name, errors

    grade_name = meta.get("grade") if not _is_uuid(meta.get("grade")) else None
    if grade_name:
        needle = _norm_name(str(grade_name))
        grades = Grade.query.all()
        match = next((g for g in grades if _norm_name(g.name or "") == needle), None)
        if not match:
            match = next((g for g in grades if needle in _norm_name(g.name or "")), None)
        if not match:
            errors.append(f"Série não encontrada: {grade_name}")
            return None, None, errors
        return str(match.id), match.name, errors

    errors.append("Série obrigatória (envie grade no formulário de upload)")
    return None, None, errors


def _resolve_skill(meta: Dict[str, Any], subject_id: Optional[str]) -> Tuple[Optional[str], List[str]]:
    errors: List[str] = []
    raw = meta.get("skill")
    if not raw:
        return None, errors

    raw = str(raw).strip()
    if _is_uuid(raw):
        skill = Skill.query.get(raw)
        if not skill:
            errors.append(f"Habilidade não encontrada: {raw}")
            return None, errors
        return str(skill.id), errors

    query = Skill.query.filter(db.func.lower(Skill.code) == raw.lower())
    if subject_id:
        skill = query.filter(Skill.subject_id == subject_id).first() or query.first()
    else:
        skill = query.first()

    if not skill:
        errors.append(f"Habilidade não encontrada pelo código: {raw}")
        return None, errors
    return str(skill.id), errors


def _build_payload(
    block: Dict[str, Any],
    defaults: Dict[str, Any],
    created_by: str,
) -> Tuple[Dict[str, Any], Dict[str, Any], List[str], List[str]]:
    """
    Retorna (payload_para_create, resolved_info, errors, warnings).
    Sempre múltipla escolha; dificuldade vem do bloco DOCX.
    """
    errors: List[str] = list(block.get("parseErrors") or [])
    warnings: List[str] = []
    meta = dict(block.get("meta") or {})

    # Tópicos não são usados neste fluxo
    meta.pop("topics", None)

    q_type, type_errors = _resolve_question_type(meta)
    errors.extend(type_errors)

    subject_id, subject_name, subject_errors = _resolve_subject(meta, defaults)
    errors.extend(subject_errors)

    grade_id, grade_name, grade_errors = _resolve_grade(meta, defaults)
    errors.extend(grade_errors)

    skill_id, skill_errors = _resolve_skill(meta, subject_id)
    errors.extend(skill_errors)

    raw_difficulty = meta.get("difficulty")
    if raw_difficulty in (None, ""):
        difficulty = None
        errors.append(
            "Dificuldade obrigatória neste bloco. "
            "Copie e cole um destes textos: " + " | ".join(ALLOWED_DIFFICULTIES)
        )
    else:
        difficulty = normalize_difficulty(raw_difficulty)
        if not difficulty:
            errors.append(
                f"Dificuldade inválida: {raw_difficulty!r}. "
                "Copie e cole um destes textos: " + " | ".join(ALLOWED_DIFFICULTIES)
            )

    enunciado = block.get("enunciado") or {}
    text = (enunciado.get("text") or "").strip()
    formatted_text = enunciado.get("html") or None
    if not text and formatted_text:
        text = " "
        warnings.append("Enunciado sem texto (apenas imagem); text preenchido com espaço.")
    if not text.strip() and not (formatted_text and "<img" in formatted_text):
        errors.append("Enunciado obrigatório")

    options = block.get("options") or []
    if not options:
        errors.append("Questão de múltipla escolha precisa de alternativas")
    else:
        for i, opt in enumerate(options):
            has_text = bool((opt.get("text") or "").strip())
            has_image = bool(opt.get("image")) or (
                isinstance(opt.get("formattedText"), str) and "<img" in opt.get("formattedText")
            )
            if not has_text and not has_image:
                errors.append(f"Alternativa {opt.get('id') or i} sem texto nem imagem")
        if not any(opt.get("isCorrect") for opt in options):
            errors.append("Marque pelo menos uma alternativa com [CORRETA]")

    solution = block.get("solution") or {}
    solution_text = (solution.get("text") or "").strip() or None
    formatted_solution = solution.get("html") or None

    number = meta.get("number")
    if number not in (None, ""):
        try:
            number = int(str(number).strip())
        except ValueError:
            warnings.append(f"Número inválido ignorado: {number}")
            number = None
    else:
        number = None

    value = meta.get("value")
    if value not in (None, ""):
        try:
            value = float(str(value).replace(",", ".").strip())
        except ValueError:
            warnings.append(f"Valor inválido ignorado: {value}")
            value = None
    else:
        value = None

    payload: Dict[str, Any] = {
        "text": text if text.strip() else (text or " "),
        "type": "multipleChoice",
        "subjectId": subject_id,
        "grade": grade_id,
        "createdBy": created_by,
        "formattedText": formatted_text,
        "difficulty": difficulty,
        "title": meta.get("title"),
        "description": meta.get("description"),
        "command": meta.get("command"),
        "subtitle": meta.get("subtitle"),
        "solution": solution_text,
        "formattedSolution": formatted_solution,
        "number": number,
        "value": value,
        "options": options,
        "version": 1,
    }
    if skill_id:
        payload["skills"] = [skill_id]

    payload = {k: v for k, v in payload.items() if v is not None}

    resolved = {
        "subjectId": subject_id,
        "subjectName": subject_name,
        "gradeId": grade_id,
        "gradeName": grade_name,
        "difficulty": difficulty,
        "skillId": skill_id,
        "type": "multipleChoice",
        "imagesInEnunciado": enunciado.get("imagesCount") or 0,
        "alternativesCount": len(options),
    }
    return payload, resolved, errors, warnings


def _user_id(current_user: Dict[str, Any]) -> Optional[str]:
    return current_user.get("user_id") or current_user.get("id")


def _scope_for_user(current_user: Dict[str, Any]) -> Tuple[str, Optional[str], Optional[str]]:
    user_role = current_user.get("role")
    user_city_id = current_user.get("tenant_id") or current_user.get("city_id")
    if user_role == "admin":
        return "GLOBAL", None, None
    if user_role == "tecadm":
        return "CITY", user_city_id, None
    return "PRIVATE", None, _user_id(current_user)


def _create_question_from_payload(payload: Dict[str, Any], current_user: Dict[str, Any]) -> Question:
    """Reutiliza a mesma lógica de create_question (scope + pipeline de imagens)."""
    from app.routes.question_routes import (
        _apply_question_images_pipeline,
        _validate_multiple_choice_options,
    )

    if payload.get("type") == "multipleChoice":
        ok, err = _validate_multiple_choice_options(payload.get("options"))
        if not ok:
            raise ValueError(err)
        if not any(alt.get("isCorrect") for alt in payload.get("options") or []):
            raise ValueError("At least one alternative must be marked as correct")

    skills_input = payload.get("skills")
    skill_value = None
    if skills_input:
        if isinstance(skills_input, list):
            skill_value = skills_input[0] if skills_input else None
        else:
            skill_value = skills_input

    scope_type, owner_city_id, owner_user_id = _scope_for_user(current_user)

    question = Question(
        number=payload.get("number"),
        text=payload.get("text"),
        formatted_text=payload.get("formattedText"),
        secondstatement=payload.get("secondStatement"),
        images=[],
        subject_id=payload.get("subjectId"),
        title=payload.get("title"),
        description=payload.get("description"),
        command=payload.get("command"),
        subtitle=payload.get("subtitle"),
        alternatives=payload.get("options"),
        skill=skill_value,
        grade_level=payload.get("grade"),
        difficulty_level=payload.get("difficulty"),
        correct_answer=payload.get("solution"),
        formatted_solution=payload.get("formattedSolution"),
        question_type=payload.get("type"),
        value=payload.get("value"),
        topics=None,
        version=payload.get("version", 1),
        created_by=payload.get("createdBy"),
        last_modified_by=payload.get("lastModifiedBy") or payload.get("createdBy"),
        education_stage_id=None,
        scope_type=scope_type,
        owner_city_id=owner_city_id,
        owner_user_id=owner_user_id,
    )
    db.session.add(question)
    db.session.flush()  # obtém id antes do pipeline de imagens
    _apply_question_images_pipeline(question)
    return question


def _preview_item(block: Dict[str, Any], payload: Dict[str, Any], resolved: Dict[str, Any], errors: List[str], warnings: List[str]) -> Dict[str, Any]:
    preview_payload = dict(payload)
    if "formattedText" in preview_payload:
        preview_payload["formattedText"] = _sanitize_html_for_preview(preview_payload.get("formattedText"))
    if "formattedSolution" in preview_payload:
        preview_payload["formattedSolution"] = _sanitize_html_for_preview(
            preview_payload.get("formattedSolution")
        )
    if "options" in preview_payload and isinstance(preview_payload["options"], list):
        preview_payload["options"] = [
            _sanitize_option_for_preview(opt) if isinstance(opt, dict) else opt
            for opt in preview_payload["options"]
        ]

    return {
        "index": block["index"],
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "resolved": resolved,
        "payload": preview_payload,
    }


def _apply_form_context_to_defaults(defaults: Dict[str, Any], form_ctx: Dict[str, Any]) -> Dict[str, Any]:
    merged = {
        **defaults,
        "grade": form_ctx["gradeId"],
        "gradeId": form_ctx["gradeId"],
        "defaultSubjectId": form_ctx.get("defaultSubjectId"),
        "allowedSubjectIds": form_ctx.get("allowedSubjectIds"),
    }
    # subjectId do form só como default (não força em todas as questões)
    if form_ctx.get("defaultSubjectId"):
        merged["subjectId"] = form_ctx["defaultSubjectId"]
    elif form_ctx.get("subjectId"):
        merged["subjectId"] = form_ctx["subjectId"]
    else:
        merged.pop("subjectId", None)
    merged.pop("difficulty", None)
    merged.pop("type", None)
    return merged


def prepare_docx_questions(
    file_storage,
    *,
    current_user: Dict[str, Any],
    defaults: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Lê o DOCX, resolve metadados e devolve itens validados sem gravar.

    Retorno:
      form, items, prepared_by_index, summary parcial
    """
    defaults = defaults or {}
    created_by = _user_id(current_user)
    if not created_by:
        raise ValueError("Usuário autenticado sem id")

    form_ctx = validate_import_defaults(defaults)
    defaults = _apply_form_context_to_defaults(defaults, form_ctx)

    filename = getattr(file_storage, "filename", "") or ""
    if not filename.lower().endswith(".docx"):
        raise ValueError("Envie um arquivo .docx")

    raw = file_storage.read()
    if not raw:
        raise ValueError("Arquivo vazio")
    if len(raw) > MAX_DOCX_BYTES:
        raise ValueError(f"Arquivo excede o limite de {MAX_DOCX_BYTES // (1024 * 1024)} MB")

    from io import BytesIO

    blocks = parse_questions_docx(BytesIO(raw))
    items: List[Dict[str, Any]] = []
    prepared_by_index: Dict[int, Dict[str, Any]] = {}

    for block in blocks:
        payload, resolved, errors, warnings = _build_payload(block, defaults, created_by)
        item = _preview_item(block, payload, resolved, errors, warnings)
        items.append(item)
        prepared_by_index[block["index"]] = {
            "block": block,
            "payload": payload,
            "resolved": resolved,
            "errors": errors,
            "warnings": warnings,
            "item": item,
        }

    valid_count = sum(1 for i in items if i["valid"])
    return {
        "form": form_ctx,
        "items": items,
        "prepared_by_index": prepared_by_index,
        "summary": {
            "total": len(items),
            "valid": valid_count,
            "invalid": len(items) - valid_count,
        },
        "created_by": created_by,
    }


def import_questions_from_docx(
    file_storage,
    *,
    current_user: Dict[str, Any],
    commit: bool = False,
    defaults: Optional[Dict[str, Any]] = None,
    indexes: Optional[List[int]] = None,
) -> Dict[str, Any]:
    """
    Parseia o DOCX, valida e opcionalmente cria questões de múltipla escolha.

    defaults: grade (obrigatório); subjectId (opcional default);
              subjectIds (opcional, lista permitida).
    Disciplina e dificuldade vêm por questão no DOCX.

    indexes (só no commit):
      - None → cria todas as questões válidas
      - [1, 3, 5] → cria apenas esses índices (do preview), se válidos
    """
    if indexes is not None:
        if not isinstance(indexes, list):
            raise ValueError("indexes deve ser uma lista de inteiros")
        if len(indexes) == 0:
            raise ValueError(
                "indexes está vazio. Envie pelo menos um índice do preview "
                "(ex.: indexes=1,3) ou omita o campo para importar todas as válidas."
            )
        for idx in indexes:
            if not isinstance(idx, int) or idx < 1:
                raise ValueError("indexes deve conter apenas inteiros >= 1")

    prepared_pack = prepare_docx_questions(
        file_storage,
        current_user=current_user,
        defaults=defaults,
    )
    form_ctx = prepared_pack["form"]
    items = prepared_pack["items"]
    by_index = prepared_pack["prepared_by_index"]
    valid_count = prepared_pack["summary"]["valid"]
    invalid_count = prepared_pack["summary"]["invalid"]

    empty_summary = {
        "total": 0,
        "valid": 0,
        "invalid": 0,
        "created": 0,
        "failed": 0,
        "skipped": 0,
        "selectedIndexes": indexes,
    }
    if not items:
        return {
            "mode": "commit" if commit else "preview",
            "form": form_ctx,
            "summary": empty_summary,
            "questions": [],
            "created": [],
            "failed": [],
            "skipped": [],
            "message": "Nenhuma questão encontrada. Use os marcadores === QUESTÃO === e === FIM ===.",
        }

    created: List[Dict[str, Any]] = []
    failed: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []

    if not commit:
        return {
            "mode": "preview",
            "form": form_ctx,
            "summary": {
                "total": len(items),
                "valid": valid_count,
                "invalid": invalid_count,
                "created": 0,
                "failed": 0,
                "skipped": 0,
                "selectedIndexes": None,
            },
            "questions": items,
            "created": [],
            "failed": [],
            "skipped": [],
        }

    selected_set = set(indexes) if indexes is not None else None

    if selected_set is not None:
        for missing_idx in sorted(selected_set - set(by_index.keys())):
            failed.append(
                {
                    "index": missing_idx,
                    "errors": [f"Índice {missing_idx} não existe no arquivo (preview)"],
                    "warnings": [],
                }
            )

    try:
        for idx, entry in sorted(by_index.items(), key=lambda x: x[0]):
            errors = entry["errors"]
            warnings = entry["warnings"]
            payload = entry["payload"]

            if selected_set is not None and idx not in selected_set:
                skipped.append(
                    {
                        "index": idx,
                        "reason": "not_selected",
                        "valid": len(errors) == 0,
                    }
                )
                continue

            if errors:
                failed.append(
                    {
                        "index": idx,
                        "errors": errors,
                        "warnings": warnings,
                    }
                )
                continue

            try:
                question = _create_question_from_payload(payload, current_user)
                created.append(
                    {
                        "index": idx,
                        "id": question.id,
                        "type": question.question_type,
                        "subjectId": question.subject_id,
                        "warnings": warnings,
                    }
                )
            except Exception as exc:
                logger.exception("Falha ao criar questão index=%s", idx)
                failed.append(
                    {
                        "index": idx,
                        "errors": [str(exc)],
                        "warnings": warnings,
                    }
                )

        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return {
        "mode": "commit",
        "form": form_ctx,
        "summary": {
            "total": len(items),
            "valid": valid_count,
            "invalid": invalid_count,
            "created": len(created),
            "failed": len(failed),
            "skipped": len(skipped),
            "selectedIndexes": indexes,
        },
        "questions": items,
        "created": created,
        "failed": failed,
        "skipped": skipped,
    }
