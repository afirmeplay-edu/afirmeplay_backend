# -*- coding: utf-8 -*-
"""Helpers puros do boletim do aluno."""
from __future__ import annotations

from typing import Any, Dict, Optional

from app.mapa_questoes.helpers import percentual
from app.utils.decimal_helpers import round_to_two_decimals

DEFAULT_PER_PAGE = 20
MAX_PER_PAGE = 100


def parse_pagination(
    page_raw: Any,
    per_page_raw: Any,
    default_per_page: int = DEFAULT_PER_PAGE,
    max_per_page: int = MAX_PER_PAGE,
) -> tuple:
    try:
        page = int(page_raw if page_raw not in (None, "") else 1)
    except (TypeError, ValueError):
        page = 1
    try:
        per_page = int(per_page_raw if per_page_raw not in (None, "") else default_per_page)
    except (TypeError, ValueError):
        per_page = default_per_page
    return max(page, 1), min(max(per_page, 1), max_per_page)


def pagination_meta(total: int, page: int, per_page: int) -> Dict[str, int]:
    if per_page <= 0 or total <= 0:
        total_pages = 0
    else:
        total_pages = (total + per_page - 1) // per_page
    return {
        "page": page,
        "per_page": per_page,
        "total": int(total),
        "total_pages": total_pages,
    }


def parse_aluno_param(raw_ids: list) -> Optional[str]:
    """
    None = todos os alunos (paginado).
    str = um aluno específico.
    """
    cleaned = [str(x).strip() for x in (raw_ids or []) if str(x).strip()]
    cleaned = [x for x in cleaned if x.lower() not in ("all", "todos", "todas")]
    if not cleaned:
        return None
    if len(cleaned) > 1:
        raise ValueError("Informe no máximo um aluno (ou omita para todos)")
    return cleaned[0]


def build_questao_boletim(
    *,
    numero: int,
    habilidade: str,
    resposta: Optional[str],
    gabarito: Optional[str],
    acertou: bool,
    respondeu: bool,
) -> Dict[str, Any]:
    return {
        "numero": numero,
        "habilidade": habilidade or "N/A",
        "resposta": resposta,
        "gabarito": gabarito or "",
        "acertou": bool(acertou),
        "respondeu": bool(respondeu),
    }


def build_cards(
    acertou: int,
    total: int,
    nota: Any,
    proficiencia: Any,
    nivel: Any,
) -> Dict[str, Any]:
    return {
        "acertos_totais": {
            "acertou": int(acertou),
            "total": int(total),
            "percentual": percentual(int(acertou), int(total)),
        },
        "nota": round_to_two_decimals(float(nota or 0)),
        "proficiencia": round_to_two_decimals(float(proficiencia or 0)),
        "nivel": nivel,
    }


def build_disciplina_cards_parcial(acertou: int, total: int) -> Dict[str, Any]:
    """Card por disciplina sem nota/proficiência/nível pré-calculados."""
    return {
        "acertos_totais": {
            "acertou": int(acertou),
            "total": int(total),
            "percentual": percentual(int(acertou), int(total)),
        },
        "nota": None,
        "proficiencia": None,
        "nivel": None,
    }


def build_disciplina_cards_computed(
    acertou: int,
    total: int,
    *,
    course_name: str,
    subject_name: str,
    use_simple_calculation: bool = False,
) -> Dict[str, Any]:
    """
    Calcula nota/proficiência/nível da disciplina com o mesmo EvaluationCalculator
    usado na gravação de subject_results / proficiency_by_subject.
    """
    from app.services.evaluation_calculator import EvaluationCalculator

    result = EvaluationCalculator.calculate_complete_evaluation(
        correct_answers=int(acertou),
        total_questions=int(total),
        course_name=course_name or "Anos Iniciais",
        subject_name=subject_name or "Outras",
        use_simple_calculation=use_simple_calculation,
    )
    return build_cards(
        acertou,
        total,
        result["grade"],
        result["proficiency"],
        result["classification"],
    )


def attach_disciplina_cards(
    bloco: Dict[str, Any],
    subject_data: Optional[Dict[str, Any]],
    *,
    course_name: Optional[str] = None,
    use_simple_calculation: bool = False,
) -> None:
    """
    Preenche bloco['cards'] a partir do JSON por disciplina (subject_results /
    proficiency_by_subject). Se o JSON estiver ausente (resultados antigos /
    sem subjects_info na gravação), calcula na hora para o frontend não receber null.
    """
    questoes = bloco.get("questoes") or []
    acertou_local = sum(1 for q in questoes if q.get("acertou"))
    total_local = len(questoes)
    if subject_data:
        bloco["cards"] = build_cards(
            subject_data["correct_answers"],
            subject_data["total_questions"],
            subject_data["grade"],
            subject_data["proficiency"],
            subject_data["classification"],
        )
        return

    subject_name = bloco.get("disciplina") or "Outras"
    if total_local > 0:
        bloco["cards"] = build_disciplina_cards_computed(
            acertou_local,
            total_local,
            course_name=course_name or "Anos Iniciais",
            subject_name=subject_name,
            use_simple_calculation=use_simple_calculation,
        )
    else:
        bloco["cards"] = build_disciplina_cards_parcial(acertou_local, total_local)


def empty_boletim_payload(
    estado: str,
    municipio_id: str,
    avaliacao_id: str,
    escola_ids=None,
    serie_ids=None,
    turma_ids=None,
    aluno_id: Optional[str] = None,
    page: int = 1,
    per_page: int = DEFAULT_PER_PAGE,
) -> Dict[str, Any]:
    return {
        "escopo": {
            "estado": estado,
            "municipio_id": str(municipio_id),
            "avaliacao_id": str(avaliacao_id),
            "escolas": list(escola_ids or []),
            "series": list(serie_ids or []),
            "turmas": [str(t) for t in (turma_ids or [])],
            "aluno_id": aluno_id,
        },
        "avaliacao": {"id": str(avaliacao_id), "nome": ""},
        "paginacao": pagination_meta(0, page, per_page),
        "boletins": [],
    }
