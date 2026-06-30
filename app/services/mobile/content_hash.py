import hashlib
import json
from typing import Any, Dict, List


def compute_test_content_version(test_dict: Dict[str, Any], questions_payload: List[Dict[str, Any]]) -> str:
    """
    SHA-256 hex minúsculo do canone JSON (ordenado) da prova + questões na ordem do teste.
    """
    payload = {
        "test": test_dict,
        "questions": questions_payload,
    }
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def compute_form_content_version(form_payload: Dict[str, Any]) -> str:
    """
    SHA-256 hex do canone JSON do formulário socioeconômico + questões.
    """
    canonical = {
        "form_id": form_payload.get("form_id"),
        "title": form_payload.get("title"),
        "description": form_payload.get("description"),
        "form_type": form_payload.get("form_type"),
        "instructions": form_payload.get("instructions"),
        "deadline": form_payload.get("deadline"),
        "questions": form_payload.get("questions") or [],
    }
    raw = json.dumps(canonical, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def question_to_canon(q) -> Dict[str, Any]:
    """Serializa Question ORM para dict estável (sem relações)."""
    return {
        "id": q.id,
        "question_id": q.id,
        "number": q.number,
        "text": q.text,
        "formatted_text": q.formatted_text,
        "secondstatement": q.secondstatement,
        "images": q.images,
        "alternatives": q.alternatives,
        "command": q.command,
        "subtitle": q.subtitle,
        "question_type": q.question_type,
        "correct_answer": q.correct_answer,
        "value": q.value,
        "topics": q.topics,
        "version": q.version,
    }
