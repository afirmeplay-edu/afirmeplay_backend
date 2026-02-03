# -*- coding: utf-8 -*-
"""
Constantes de competições: níveis e mapeamento com etapas de ensino.
"""

# Níveis permitidos: 1 e 2
COMPETITION_LEVEL_VALID = (1, 2)

# Rótulos para exibição (frontend / API)
LEVEL_OPTIONS = [
    {
        "value": 1,
        "label": "Educação Infantil, Anos Iniciais, Educação Especial, EJA",
    },
    {
        "value": 2,
        "label": "Anos Finais e Ensino Médio",
    },
]

# Nomes de etapas de ensino (education_stage.name) que pertencem a cada nível.
# Usado para filtrar "competições disponíveis" por aluno (Etapa 3).
LEVEL_1_STAGE_NAMES = (
    "Educação Infantil",
    "Anos Iniciais",
    "Educação Especial",
    "EJA",
)
LEVEL_2_STAGE_NAMES = (
    "Anos Finais",
    "Ensino Médio",
)

# Mapeamento nível -> tuple de nomes (para uso em serviços)
STAGE_NAMES_BY_LEVEL = {
    1: LEVEL_1_STAGE_NAMES,
    2: LEVEL_2_STAGE_NAMES,
}


def is_valid_level(level):
    """Retorna True se level for 1 ou 2."""
    return level in COMPETITION_LEVEL_VALID


def student_grade_matches_level(education_stage_name, competition_level):
    """
    Verifica se o nome da etapa de ensino do aluno corresponde ao nível da competição.
    education_stage_name: str (ex.: grade.education_stage.name)
    competition_level: int (1 ou 2)
    """
    if education_stage_name is None or competition_level not in STAGE_NAMES_BY_LEVEL:
        return False
    name = (education_stage_name or "").strip()
    return name in STAGE_NAMES_BY_LEVEL[competition_level]
