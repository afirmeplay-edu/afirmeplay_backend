# -*- coding: utf-8 -*-
"""
Mapeamento EJA: períodos equivalem aos anos regulares para fins de habilidades.

Regra: 1º período = 1º ano, 2º período = 2º ano, ..., 9º período = 9º ano.
Quando a grade for de EJA (etapa "EJA") e o nome for "Nº Período", as skills
devem ser buscadas pela grade do "Nº Ano" correspondente.
"""
from typing import Optional
import re

from app.models.grades import Grade
from app.models.educationStage import EducationStage
from app.utils.uuid_helpers import ensure_uuid


# Nomes possíveis para cada ano (1-9) usados na busca da grade equivalente
ANO_NAME_PATTERNS = [
    (n, [f"{n}º Ano", f"{n}º ano", f"{n}° Ano", f"{n}° ano"])
    for n in range(1, 10)
]

# Regex para extrair número do período no nome da grade: "1º Período", "2º período", etc.
PERIODO_PATTERN = re.compile(r"(\d)\s*[º°]\s*[Pp]er[ií]odo", re.IGNORECASE)


def _is_eja_stage(education_stage: Optional[EducationStage]) -> bool:
    """Verifica se a etapa de ensino é EJA."""
    if not education_stage or not education_stage.name:
        return False
    return "eja" in (education_stage.name or "").lower()


def _extract_period_number(grade_name: Optional[str]) -> Optional[int]:
    """
    Extrai o número do período do nome da grade (1-9).
    Ex.: "1º Período" -> 1, "2º período" -> 2.
    """
    if not grade_name or not grade_name.strip():
        return None
    m = PERIODO_PATTERN.search(grade_name.strip())
    if not m:
        return None
    n = int(m.group(1))
    return n if 1 <= n <= 9 else None


def _find_grade_by_ano_number(ano_number: int):
    """
    Busca a grade correspondente ao "Nº Ano" (qualquer etapa).
    Retorna o primeiro registro cujo nome coincida com um dos padrões do ano.
    """
    if ano_number < 1 or ano_number > 9:
        return None
    patterns = next((pats for n, pats in ANO_NAME_PATTERNS if n == ano_number), None)
    if not patterns:
        return None
    for name in patterns:
        grade = Grade.query.filter(Grade.name == name).first()
        if grade:
            return grade
    # Fallback: ilike para variações de acento/espaço
    for name in patterns:
        grade = Grade.query.filter(Grade.name.ilike(name)).first()
        if grade:
            return grade
    return None


def get_effective_grade_id_for_skills(grade_id: Optional[str]):
    """
    Retorna o grade_id a ser usado para buscar habilidades (skills).

    Se a grade for de EJA e for um período (1º a 9º), retorna o id da grade
    do ano correspondente (1º ano a 9º ano). Caso contrário, retorna o
    grade_id original.

    Args:
        grade_id: UUID da grade (pode ser string ou None).

    Returns:
        UUID da grade efetiva para consulta de skills, ou o próprio grade_id
        se não houver mapeamento EJA.
    """
    if not grade_id:
        return grade_id
    grade_uuid = ensure_uuid(grade_id)
    if not grade_uuid:
        return grade_id

    grade = Grade.query.get(grade_uuid)
    if not grade:
        return grade_id

    stage = getattr(grade, "education_stage", None)
    if not stage and grade.education_stage_id:
        stage = EducationStage.query.get(grade.education_stage_id)

    if not _is_eja_stage(stage):
        return grade_id

    period_num = _extract_period_number(grade.name)
    if period_num is None:
        return grade_id

    equivalent_grade = _find_grade_by_ano_number(period_num)
    if equivalent_grade:
        return str(equivalent_grade.id)
    return grade_id
