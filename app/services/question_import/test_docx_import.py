# -*- coding: utf-8 -*-
"""
Cria avaliação online (Test) + questões do DOCX de forma atômica.

Escopo: type AVALIACAO|SIMULADO, evaluation_mode=virtual apenas.
Se qualquer índice selecionado for inválido, não cria nada.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app import db
from app.models.school import School
from app.models.test import Test
from app.models.testQuestion import TestQuestion
from app.services.question_import.importer import (
    _create_question_from_payload,
    prepare_docx_questions,
)
from app.utils.municipality_availability import (
    municipality_availability_payload,
    resolve_availability_for_create,
)
from app.utils.uuid_helpers import ensure_uuid_list, uuid_list_to_str

logger = logging.getLogger(__name__)

ALLOWED_TEST_TYPES = ("AVALIACAO", "SIMULADO")
ALLOWED_EVALUATION_MODE = "virtual"


class TestDocxImportError(Exception):
    """Erro de validação com payload estruturado para o frontend."""

    def __init__(self, message: str, payload: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.payload = payload or {}


def _parse_json_field(raw: Any, field_name: str) -> Any:
    if raw in (None, ""):
        return None
    if isinstance(raw, (dict, list)):
        return raw
    text = str(raw).strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise TestDocxImportError(
            f"Campo '{field_name}' deve ser JSON válido",
            {"field": field_name, "value": text[:200]},
        ) from exc


def parse_test_fields_from_form(form) -> Dict[str, Any]:
    """Extrai campos da avaliação do multipart (strings ou JSON)."""
    data: Dict[str, Any] = {}

    simple_keys = (
        "title",
        "description",
        "intructions",
        "type",
        "model",
        "course",
        "created_by",
        "createdBy",
        "subject",
        "grade",
        "grade_id",
        "max_score",
        "time_limit",
        "end_time",
        "duration",
        "evaluation_mode",
        "subjectId",  # disciplina das questões / também pode preencher subject
    )

    for key in simple_keys:
        value = form.get(key)
        if value not in (None, ""):
            data[key] = value.strip() if isinstance(value, str) else value

    for key in ("subjects", "subjects_info", "municipalities", "schools", "classes"):
        raw = form.get(key)
        if raw not in (None, ""):
            data[key] = _parse_json_field(raw, key)

    if "created_by" not in data and data.get("createdBy"):
        data["created_by"] = data["createdBy"]

    if data.get("max_score") not in (None, ""):
        try:
            data["max_score"] = float(str(data["max_score"]).replace(",", "."))
        except ValueError as exc:
            raise TestDocxImportError("max_score deve ser numérico") from exc

    if data.get("duration") not in (None, ""):
        try:
            data["duration"] = int(data["duration"])
        except (TypeError, ValueError) as exc:
            raise TestDocxImportError("duration deve ser um inteiro (minutos)") from exc

    return data


def _validate_test_payload(data: Dict[str, Any], current_user: Dict[str, Any]) -> Tuple[Dict[str, Any], Any, Any]:
    required = ["title", "type", "model", "course", "created_by"]
    missing = [f for f in required if not data.get(f)]
    if missing:
        raise TestDocxImportError(
            "Campos obrigatórios da avaliação ausentes: " + ", ".join(missing),
            {"missing": missing},
        )

    test_type = str(data["type"]).strip().upper()
    if test_type not in ALLOWED_TEST_TYPES:
        raise TestDocxImportError(
            f"type inválido: {data['type']!r}. Aceitos: {', '.join(ALLOWED_TEST_TYPES)}"
        )
    data["type"] = test_type

    evaluation_mode = (data.get("evaluation_mode") or ALLOWED_EVALUATION_MODE).strip().lower()
    if evaluation_mode != ALLOWED_EVALUATION_MODE:
        raise TestDocxImportError(
            "Este importador cria apenas avaliação online (evaluation_mode=virtual). "
            "Cartão-resposta e subjetiva não são suportados."
        )
    data["evaluation_mode"] = ALLOWED_EVALUATION_MODE

    if data.get("duration") is not None:
        if int(data["duration"]) <= 0:
            raise TestDocxImportError("duration deve ser maior que zero")

    if test_type == "SIMULADO":
        subjects_info = data.get("subjects_info") or data.get("subjects")
        if not subjects_info:
            raise TestDocxImportError(
                "subjects_info (ou subjects) é obrigatório para SIMULADO"
            )
        data["subjects_info"] = subjects_info
    elif test_type == "AVALIACAO":
        has_subject = bool(data.get("subject") or data.get("subjectId"))
        has_subjects = (
            isinstance(data.get("subjects"), list) and len(data.get("subjects")) > 0
        )
        if not has_subject and not has_subjects:
            raise TestDocxImportError(
                "subject (ou subjects) é obrigatório para AVALIACAO"
            )
        if not data.get("subject") and data.get("subjectId"):
            data["subject"] = data["subjectId"]

    available_to_municipality, available_from, availability_err = resolve_availability_for_create(
        data, current_user
    )
    if availability_err:
        raise TestDocxImportError(availability_err)

    # escolas
    if data.get("schools"):
        school_ids = data["schools"] if isinstance(data["schools"], list) else [data["schools"]]
        existing = School.query.filter(School.id.in_(school_ids)).all()
        if len(existing) != len(school_ids):
            raise TestDocxImportError("Uma ou mais escolas não foram encontradas")

    # turmas → deriva schools
    if data.get("classes"):
        from app.models.studentClass import Class as ClassModel

        if isinstance(data["classes"], list):
            class_ids = [
                c.get("id") if isinstance(c, dict) else c for c in data["classes"]
            ]
        else:
            class_ids = [data["classes"]]

        class_ids_uuids = ensure_uuid_list(class_ids)
        existing_classes = ClassModel.query.filter(ClassModel.id.in_(class_ids_uuids)).all()
        if len(existing_classes) != len(class_ids_uuids):
            raise TestDocxImportError("Uma ou mais turmas não foram encontradas")

        school_ids_from_classes = list({c.school_id for c in existing_classes})
        data["schools"] = uuid_list_to_str(school_ids_from_classes) if school_ids_from_classes else []
        data["classes"] = uuid_list_to_str(class_ids_uuids)

    return data, available_to_municipality, available_from


def _resolve_selected_indexes(
    indexes: Optional[List[int]],
    prepared_by_index: Dict[int, Dict[str, Any]],
) -> List[int]:
    available = sorted(prepared_by_index.keys())
    if not available:
        raise TestDocxImportError(
            "Nenhuma questão encontrada no arquivo. Use os marcadores === QUESTÃO === e === FIM ===."
        )

    if indexes is None:
        selected = available
    else:
        if len(indexes) == 0:
            raise TestDocxImportError(
                "indexes está vazio. Selecione ao menos uma questão do preview."
            )
        selected = list(indexes)

    # validação all-or-nothing dos selecionados
    problems: List[Dict[str, Any]] = []
    for idx in selected:
        entry = prepared_by_index.get(idx)
        if entry is None:
            problems.append(
                {
                    "index": idx,
                    "valid": False,
                    "errors": [f"Índice {idx} não existe no arquivo (preview)"],
                    "warnings": [],
                }
            )
            continue
        if entry["errors"]:
            problems.append(
                {
                    "index": idx,
                    "valid": False,
                    "errors": entry["errors"],
                    "warnings": entry["warnings"],
                }
            )

    if problems:
        raise TestDocxImportError(
            "Não foi possível criar a avaliação: uma ou mais questões selecionadas "
            "estão inválidas. Ajuste no Word, remova do arquivo ou desmarque no preview.",
            {
                "failed": problems,
                "selectedIndexes": selected,
            },
        )

    return selected


def create_test_with_docx(
    file_storage,
    *,
    current_user: Dict[str, Any],
    test_data: Dict[str, Any],
    question_defaults: Dict[str, Any],
    indexes: Optional[List[int]] = None,
) -> Dict[str, Any]:
    """
    Valida DOCX + metadados da avaliação e cria Test + Questions + TestQuestion
    em uma única transação. Em qualquer falha: rollback total.
    """
    test_data, available_to_municipality, available_from = _validate_test_payload(
        dict(test_data), current_user
    )

    # série das questões: form ou herdada da avaliação
    # disciplina: por questão no DOCX; subjectId/subjectIds do form são default/whitelist
    q_defaults = dict(question_defaults or {})
    if not q_defaults.get("grade") and not q_defaults.get("gradeId"):
        q_defaults["grade"] = test_data.get("grade") or test_data.get("grade_id")
    if not q_defaults.get("subjectId") and test_data.get("subject"):
        q_defaults["subjectId"] = test_data.get("subject")
    if not q_defaults.get("subjectIds") and test_data.get("subjectId"):
        # subjectId avulso no test_data também entra na whitelist se já houver lista? skip
        pass

    prepared = prepare_docx_questions(
        file_storage,
        current_user=current_user,
        defaults=q_defaults,
    )

    selected = _resolve_selected_indexes(indexes, prepared["prepared_by_index"])

    try:
        nova_avaliacao = Test(
            title=test_data.get("title"),
            description=test_data.get("description"),
            type=test_data.get("type"),
            subject=test_data.get("subject") if test_data.get("subject") else None,
            grade_id=test_data.get("grade") or test_data.get("grade_id"),
            intructions=test_data.get("intructions"),
            max_score=test_data.get("max_score"),
            time_limit=(
                datetime.fromisoformat(test_data["time_limit"])
                if test_data.get("time_limit")
                else None
            ),
            end_time=(
                datetime.fromisoformat(test_data["end_time"])
                if test_data.get("end_time")
                else None
            ),
            duration=test_data.get("duration"),
            evaluation_mode=ALLOWED_EVALUATION_MODE,
            created_by=test_data.get("created_by"),
            municipalities=test_data.get("municipalities"),
            schools=test_data.get("schools"),
            classes=test_data.get("classes"),
            course=test_data.get("course"),
            model=test_data.get("model"),
            subjects_info=test_data.get("subjects") or test_data.get("subjects_info"),
            status="pendente",
            available_to_municipality=available_to_municipality,
            available_from=available_from,
        )
        db.session.add(nova_avaliacao)
        db.session.flush()

        created: List[Dict[str, Any]] = []
        for order, idx in enumerate(selected, start=1):
            entry = prepared["prepared_by_index"][idx]
            question = _create_question_from_payload(entry["payload"], current_user)
            # number na prova = ordem
            if question.number is None:
                question.number = order

            db.session.add(
                TestQuestion(
                    test_id=nova_avaliacao.id,
                    question_id=question.id,
                    order=order,
                )
            )
            created.append(
                {
                    "index": idx,
                    "id": question.id,
                    "order": order,
                    "type": question.question_type,
                    "subjectId": question.subject_id,
                    "difficulty": entry["resolved"].get("difficulty"),
                    "warnings": entry["warnings"],
                }
            )

        db.session.commit()
    except TestDocxImportError:
        db.session.rollback()
        raise
    except ValueError as exc:
        db.session.rollback()
        raise TestDocxImportError(str(exc)) from exc
    except Exception:
        db.session.rollback()
        raise

    return {
        "message": "Avaliação criada com questões importadas do DOCX",
        "id": nova_avaliacao.id,
        "evaluation_mode": nova_avaliacao.evaluation_mode,
        "type": nova_avaliacao.type,
        "form": prepared["form"],
        "summary": {
            "totalInFile": prepared["summary"]["total"],
            "selected": len(selected),
            "created": len(created),
            "selectedIndexes": selected,
        },
        "created": created,
        "questionsPreview": prepared["items"],
        **municipality_availability_payload(nova_avaliacao),
    }


def parse_indexes_arg(form, args=None) -> Optional[List[int]]:
    """Compatível com indexes / indexes[] do multipart."""
    from app.services.question_import.importer import parse_indexes_from_request

    return parse_indexes_from_request(form, args)
