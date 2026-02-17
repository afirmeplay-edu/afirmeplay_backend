# -*- coding: utf-8 -*-
"""
Constantes de competições: níveis e mapeamento com etapas de ensino.
"""

# Níveis permitidos: 1 e 2
COMPETITION_LEVEL_VALID = (1, 2)

# Escopos aceitos na criação/edição de competições (sem série)
# global = competição aberta para todos (torneios automáticos Afirmeplay)
SCOPE_OPTIONS = ('individual', 'turma', 'escola', 'municipio', 'estado', 'global')

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


def is_valid_scope(scope):
    """Retorna True se scope for um dos SCOPE_OPTIONS."""
    return scope is not None and (scope or '').strip().lower() in SCOPE_OPTIONS


def validate_scope_and_filter(scope, scope_filter):
    """
    Valida scope e scope_filter para criação/edição de competição.
    Levanta ValueError se scope não estiver em SCOPE_OPTIONS ou se, para escopo
    não-individual, scope_filter não contiver a chave esperada com ao menos um item.
    """
    scope = (scope or 'individual').strip().lower()
    if scope not in SCOPE_OPTIONS:
        raise ValueError(
            f"Escopo deve ser um dos: {', '.join(SCOPE_OPTIONS)}"
        )
    # individual e global não exigem scope_filter
    if scope in ('individual', 'global'):
        return
    sf = scope_filter or {}
    if scope == 'municipio':
        ids = sf.get('municipality_ids') or sf.get('city_ids')
        if not ids or (isinstance(ids, (list, tuple)) and len(ids) == 0):
            raise ValueError(
                "Para escopo 'municipio' informe city_ids ou municipality_ids em scope_filter com ao menos um item"
            )
        return
    if scope == 'estado':
        val = sf.get('state_names') or sf.get('state')
        if val is None or (isinstance(val, (list, tuple)) and len(val) == 0):
            raise ValueError(
                "Para escopo 'estado' informe state_names ou state em scope_filter com ao menos um item"
            )
        return
    key_expected = {'turma': 'class_ids', 'escola': 'school_ids'}.get(scope)
    if key_expected:
        ids = sf.get(key_expected)
        if not ids or (isinstance(ids, (list, tuple)) and len(ids) == 0):
            raise ValueError(
                f"Para escopo '{scope}' informe scope_filter.{key_expected} com ao menos um item"
            )
