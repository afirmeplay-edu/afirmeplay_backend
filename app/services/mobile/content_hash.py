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


def question_to_canon(q) -> Dict[str, Any]:
    """Serializa Question ORM para dict estável (sem relações)."""
    return {
        "id": q.id,
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
