# -*- coding: utf-8 -*-
"""
Avalia o requisito de desempenho de um item da loja, reusando os services existentes.
Não persiste elegibilidade: calcula no momento da compra/listagem.
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from app.services.competition_student_ranking_service import (
    CompetitionStudentRankingService,
    RANK_BANDS,
)
from app.services.achievement_service import get_conquistas, MEDAL_ORDER
from app.routes.student_grades_routes import _get_student_general_stats
from app.store.constants import (
    COMPETITION_BAND_NAMES,
    EVAL_CLASSIFICATIONS,
    MEDAL_LABELS,
    MEDAL_NAMES,
    REQUIREMENT_TYPE_ACHIEVEMENT,
    REQUIREMENT_TYPE_COMPETITION_BAND,
    REQUIREMENT_TYPE_EVAL_CLASSIFICATION,
    REQUIREMENT_TYPE_EVAL_MIN_GRADE,
    REQUIREMENT_TYPES,
    achievement_catalog,
)


RequirementResult = Tuple[bool, str]


def validate_requirement(raw) -> Optional[Dict[str, Any]]:
    """
    Valida e normaliza o JSON de requisito.
    None / {} / string vazia → None (item sem requisito).
    Levanta ValueError se o tipo ou os parâmetros forem inválidos.
    """
    if raw is None or raw == '' or raw == {}:
        return None
    if not isinstance(raw, dict):
        raise ValueError("requirement deve ser um objeto JSON ou nulo.")
    req_type = str(raw.get('type') or '').strip()
    if req_type not in REQUIREMENT_TYPES:
        raise ValueError(
            "Tipo de requisito inválido. Use: "
            + ", ".join(REQUIREMENT_TYPES)
        )
    if req_type == REQUIREMENT_TYPE_COMPETITION_BAND:
        min_band = str(raw.get('min_band') or '').strip()
        if min_band not in COMPETITION_BAND_NAMES:
            raise ValueError(
                "min_band inválido. Use uma das faixas: "
                + ", ".join(COMPETITION_BAND_NAMES)
            )
        return {'type': req_type, 'min_band': min_band}
    if req_type == REQUIREMENT_TYPE_EVAL_MIN_GRADE:
        try:
            min_grade = float(raw.get('min_grade'))
        except (TypeError, ValueError):
            raise ValueError("min_grade deve ser um número.")
        if min_grade < 0 or min_grade > 10:
            raise ValueError("min_grade deve estar entre 0 e 10.")
        return {'type': req_type, 'min_grade': min_grade}
    if req_type == REQUIREMENT_TYPE_EVAL_CLASSIFICATION:
        min_cls = str(raw.get('min_classification') or '').strip()
        if min_cls not in EVAL_CLASSIFICATIONS:
            raise ValueError(
                "min_classification inválido. Use: "
                + ", ".join(EVAL_CLASSIFICATIONS)
            )
        return {'type': req_type, 'min_classification': min_cls}
    # achievement
    achievement_id = str(raw.get('id') or raw.get('achievement_id') or '').strip()
    medal = str(raw.get('medal') or raw.get('medalha') or '').strip().lower()
    known_ids = {item['id'] for item in achievement_catalog()}
    if achievement_id not in known_ids:
        raise ValueError("id de conquista inválido.")
    if medal not in MEDAL_NAMES:
        raise ValueError("medal inválida. Use: " + ", ".join(MEDAL_NAMES))
    return {'type': req_type, 'id': achievement_id, 'medal': medal}


def missing_reason(requirement: Optional[Dict[str, Any]]) -> str:
    """Texto amigável do que falta para desbloquear (usado na vitrine)."""
    if not requirement or not isinstance(requirement, dict):
        return ""
    req_type = requirement.get('type')
    if req_type == REQUIREMENT_TYPE_COMPETITION_BAND:
        band = requirement.get('min_band') or 'a faixa exigida'
        return f"Alcance a faixa {band} para desbloquear"
    if req_type == REQUIREMENT_TYPE_EVAL_MIN_GRADE:
        grade = requirement.get('min_grade')
        grade_txt = _format_grade(grade)
        return f"Alcance média {grade_txt} nas avaliações para desbloquear"
    if req_type == REQUIREMENT_TYPE_EVAL_CLASSIFICATION:
        cls = requirement.get('min_classification') or 'a classificação exigida'
        return f"Alcance a classificação {cls} para desbloquear"
    if req_type == REQUIREMENT_TYPE_ACHIEVEMENT:
        nome = _achievement_name(requirement.get('id'))
        medal_label = MEDAL_LABELS.get(requirement.get('medal'), requirement.get('medal') or 'a medalha')
        return f"Conquiste {nome} no nível {medal_label} para desbloquear"
    return "Atenda ao requisito de desempenho para desbloquear"


def build_snapshot(student_id: str) -> Dict[str, Any]:
    """Lê uma vez os dados de competição/avaliação/conquistas para vários itens da listagem."""
    rank = CompetitionStudentRankingService.get_student_competition_rank_classification(student_id)
    stats = _get_student_general_stats(student_id) or {}
    conquistas_result = get_conquistas(student_id, redeemed_keys=[]) or {}
    medals = {}
    names = {}
    for item in conquistas_result.get('conquistas') or []:
        cid = item.get('id')
        if not cid:
            continue
        medals[cid] = item.get('medalha_atual')
        names[cid] = item.get('nome') or cid
    return {
        'band': (rank or {}).get('band') or COMPETITION_BAND_NAMES[0],
        'general_grade': float(stats.get('general_grade') or 0.0),
        'general_classification': stats.get('general_classification') or 'Sem avaliações',
        'medals': medals,
        'achievement_names': names,
    }


def check_requirement(
    student_id: str,
    requirement: Optional[Dict[str, Any]],
    snapshot: Optional[Dict[str, Any]] = None,
) -> RequirementResult:
    """
    Retorna (met, reason).
    Sem requisito → (True, "").
    Tipo desconhecido → (True, "") para não travar o catálogo.
    """
    if not requirement:
        return True, ""
    req_type = requirement.get('type')
    if req_type not in REQUIREMENT_TYPES:
        return True, ""
    snap = snapshot if snapshot is not None else build_snapshot(student_id)
    reason = missing_reason(requirement)

    if req_type == REQUIREMENT_TYPE_COMPETITION_BAND:
        student_idx = _band_index(snap.get('band'))
        required_idx = _band_index(requirement.get('min_band'))
        if required_idx < 0:
            return True, ""
        if student_idx >= required_idx:
            return True, ""
        return False, reason

    if req_type == REQUIREMENT_TYPE_EVAL_MIN_GRADE:
        try:
            min_grade = float(requirement.get('min_grade'))
        except (TypeError, ValueError):
            return True, ""
        if float(snap.get('general_grade') or 0.0) >= min_grade:
            return True, ""
        return False, reason

    if req_type == REQUIREMENT_TYPE_EVAL_CLASSIFICATION:
        student_idx = _classification_index(snap.get('general_classification'))
        required_idx = _classification_index(requirement.get('min_classification'))
        if required_idx < 0:
            return True, ""
        if student_idx >= required_idx:
            return True, ""
        return False, reason

    # achievement: medalha atual >= nível pedido (ouro conta como bronze/prata)
    achievement_id = requirement.get('id')
    required_medal = requirement.get('medal')
    current_medal = (snap.get('medals') or {}).get(achievement_id)
    if _medal_index(current_medal) >= _medal_index(required_medal) and _medal_index(required_medal) >= 0:
        return True, ""
    return False, reason


def get_requirement_options() -> Dict[str, Any]:
    """Opções para o formulário admin (não duplica enums no frontend)."""
    return {
        'types': list(REQUIREMENT_TYPES),
        'competition_bands': [{'value': name, 'label': name} for name in COMPETITION_BAND_NAMES],
        'eval_classifications': [{'value': name, 'label': name} for name in EVAL_CLASSIFICATIONS],
        'medals': [{'value': name, 'label': MEDAL_LABELS.get(name, name)} for name in MEDAL_NAMES],
        'achievements': achievement_catalog(),
    }


def _band_index(name) -> int:
    names = [band.name for band in RANK_BANDS]
    try:
        return names.index(name)
    except (ValueError, TypeError):
        return -1


def _classification_index(name) -> int:
    try:
        return EVAL_CLASSIFICATIONS.index(name)
    except (ValueError, TypeError):
        return -1


def _medal_index(name) -> int:
    try:
        return MEDAL_ORDER.index(name)
    except (ValueError, TypeError):
        return -1


def _format_grade(value) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if number == int(number):
        return str(int(number))
    return str(number).replace('.', ',')


def _achievement_name(achievement_id) -> str:
    for item in achievement_catalog():
        if item['id'] == achievement_id:
            return item['nome']
    return achievement_id or 'a conquista'
