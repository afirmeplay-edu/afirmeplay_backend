# -*- coding: utf-8 -*-
"""
Funções puras do mapa de questões: tipo, letra da alternativa, taxas.

Média de acertos = total de acertos / (alunos × questões) × 100.
Cada aluno pesa igual. Sem média ponderada por escola/turma e sem média hierárquica.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Sequence

from app.utils.decimal_helpers import round_to_two_decimals

LETTERS = ["A", "B", "C", "D", "E", "F", "G", "H"]
LETTER_SET = set(LETTERS)

DISCURSIVE_TYPES = {
    "essay",
    "discursive",
    "dissertativa",
    "discursiva",
    "aberta",
    "open",
    "open_ended",
}

OBJECTIVE_TYPES = {
    "multiple_choice",
    "multiplechoice",
    "objetiva",
    "multipla_escolha",
    "múltipla_escolha",
}

_OPTION_INDEX_RE = re.compile(r"^option[-_]?(\d+)$", re.IGNORECASE)


def normalize_question_type(raw: Any) -> str:
    return (str(raw or "").strip().lower().replace("-", "_").replace(" ", "_"))


def is_discursive_question(question_type: Any) -> bool:
    return normalize_question_type(question_type) in DISCURSIVE_TYPES


def parse_alternatives(raw: Any) -> List[Any]:
    if not raw:
        return []
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (TypeError, ValueError, json.JSONDecodeError):
            return []
    if isinstance(raw, list):
        return raw
    return []


def is_objective_question(question_type: Any, alternatives: Any = None) -> bool:
    """Discursiva fica de fora. Objetiva explícita ou com alternativas entra."""
    if is_discursive_question(question_type):
        return False
    qt = normalize_question_type(question_type)
    if qt in OBJECTIVE_TYPES:
        return True
    return bool(parse_alternatives(alternatives))


def letters_for_alternatives(alternatives: Any, default_n: int = 4) -> List[str]:
    alts = parse_alternatives(alternatives)
    n = len(alts) if alts else default_n
    n = min(max(n, 1), len(LETTERS))
    return LETTERS[:n]


def letters_for_answer_sheet(gabarito_letters: Sequence[str], marked_letters: Sequence[str]) -> List[str]:
    seen = {str(x).strip().upper() for x in list(gabarito_letters) + list(marked_letters) if x}
    seen &= LETTER_SET
    ordered = [L for L in LETTERS if L in seen]
    return ordered or LETTERS[:4]


def answer_to_letter(raw: Any, alternatives: Any = None) -> Optional[str]:
    """
    Converte resposta do aluno / gabarito para A–H.
    Aceita letra, id da opção, texto da alternativa ou option-N.
    """
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None

    upper = s.upper()
    if upper in LETTER_SET:
        return upper

    alts = parse_alternatives(alternatives)
    for idx, alt in enumerate(alts):
        if idx >= len(LETTERS):
            break
        letter = LETTERS[idx]
        if isinstance(alt, dict):
            alt_id = str(alt.get("id") or "").strip()
            alt_text = str(alt.get("text") or alt.get("answer") or "").strip()
            if alt_id and s == alt_id:
                return letter
            if alt_text and s.lower() == alt_text.lower():
                return letter
        elif isinstance(alt, str) and s.lower() == alt.strip().lower():
            return letter

    match = _OPTION_INDEX_RE.match(s)
    if match:
        n = int(match.group(1))
        if alts:
            if 0 <= n < len(alts):
                return LETTERS[n]
            if 1 <= n <= len(alts):
                return LETTERS[n - 1]
        else:
            if 0 <= n < len(LETTERS):
                return LETTERS[n]
            if 1 <= n <= len(LETTERS):
                return LETTERS[n - 1]
    return None


def gabarito_letter(correct_answer: Any, alternatives: Any = None) -> Optional[str]:
    letter = answer_to_letter(correct_answer, alternatives)
    if letter:
        return letter
    alts = parse_alternatives(alternatives)
    for idx, alt in enumerate(alts):
        if idx >= len(LETTERS):
            break
        if isinstance(alt, dict) and (alt.get("isCorrect") or alt.get("is_correct")):
            return LETTERS[idx]
    return None


def percentual(parte: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round_to_two_decimals(100.0 * parte / total)


def media_acertos_percentual(total_acertos: int, n_alunos: int, n_questoes: int) -> float:
    """Percentual simples: acertos / (alunos × questões). Sem ponderação."""
    if n_alunos <= 0 or n_questoes <= 0:
        return 0.0
    return round_to_two_decimals(100.0 * total_acertos / (n_alunos * n_questoes))


def build_marcacoes(
    mark_counts: Dict[str, int],
    letters: Sequence[str],
    n_alunos: int,
) -> List[Dict[str, Any]]:
    ordered = list(letters)
    extra = [k for k in mark_counts.keys() if k not in ordered and k != "sem_resposta"]
    extra.sort()
    ordered.extend(extra)
    ordered.append("sem_resposta")

    rows: List[Dict[str, Any]] = []
    for key in ordered:
        alunos = int(mark_counts.get(key, 0))
        rows.append(
            {
                "alternativa": key,
                "alunos": alunos,
                "percentual": percentual(alunos, n_alunos),
            }
        )
    return rows


def empty_payload(
    estado: str,
    municipio_id: str,
    avaliacao_id: str,
    escola_ids: Optional[Sequence[str]] = None,
    serie_ids: Optional[Sequence[str]] = None,
    turma_ids: Optional[Sequence[str]] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "escopo": {
            "estado": estado,
            "municipio_id": str(municipio_id),
            "avaliacao_id": str(avaliacao_id),
            "escolas": list(escola_ids or []),
            "series": list(serie_ids or []),
            "turmas": [str(t) for t in (turma_ids or [])],
        },
        "avaliacao": {"id": str(avaliacao_id), "nome": "", "disciplinas": []},
        "metricas": {
            "total_alunos_realizaram": 0,
            "media_acertos_percentual": 0.0,
            "total_questoes": 0,
        },
        "por_disciplina": [],
    }
    if extra:
        payload.update(extra)
    return payload


def build_question_row(
    *,
    numero: int,
    disciplina: str,
    disciplina_id: Optional[str],
    habilidade: str,
    gabarito: Optional[str],
    letters: Sequence[str],
    mark_counts: Dict[str, int],
    acertaram: int,
    n_alunos: int,
    question_id: Optional[str] = None,
) -> Dict[str, Any]:
    row: Dict[str, Any] = {
        "numero": numero,
        "disciplina": disciplina,
        "disciplina_id": disciplina_id,
        "habilidade": habilidade or "N/A",
        "gabarito": gabarito or "",
        "taxa_acertos": {
            "acertaram": acertaram,
            "total": n_alunos,
            "percentual": percentual(acertaram, n_alunos),
        },
        "marcacoes": build_marcacoes(mark_counts, letters, n_alunos),
    }
    # Prova digital: ID para o frontend buscar enunciado/alternativas (GET /questions/batch).
    # Cartão-resposta não envia este campo (não há enunciado no gabarito).
    if question_id:
        row["question_id"] = str(question_id)
    return row
