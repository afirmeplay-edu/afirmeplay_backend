"""
Catálogo de features por plano municipal.

BASIC_FEATURES: tudo que o produto oferece hoje (plano basic).
PLUS_ONLY_FEATURES: módulos exclusivos do plus — preencher ao lançar cada um.
"""

from typing import FrozenSet, List

from .plans import DEFAULT_PLAN_CODE, PLAN_PLUS, normalize_plan_code

# --- Features do plano basic (produto atual) --------------------------------

BASIC_FEATURES: FrozenSet[str] = frozenset({
    "evaluations",
    "questions",
    "students",
    "schools",
    "classes",
    "users",
    "reports",
    "evaluation_results",
    "report_analysis",
    "play_tv",
    "plantao_online",
    "certificates",
    "balance",
    "competitions",
    "ideb_meta",
    "store",
    "socioeconomic_forms",
    "physical_tests",
    "games",
    "calendar",
    "dashboard",
    "ranking",
    "answer_sheet",
    "monitoring",
    "saved_ata",
    "folha_rascunho",
    "lista_frequencia",
    "city_branding",
    "filters",
})

# Exclusivas do plus — vazio até novos módulos serem cadastrados aqui.
PLUS_ONLY_FEATURES: FrozenSet[str] = frozenset()

ALL_KNOWN_FEATURES: FrozenSet[str] = BASIC_FEATURES | PLUS_ONLY_FEATURES


def is_known_feature(feature: str) -> bool:
    return feature in ALL_KNOWN_FEATURES


def features_for_plan(plan_code: str) -> FrozenSet[str]:
    code = normalize_plan_code(plan_code)
    if code == PLAN_PLUS:
        return BASIC_FEATURES | PLUS_ONLY_FEATURES
    return BASIC_FEATURES


def plan_includes_feature(plan_code: str, feature: str) -> bool:
    if not is_known_feature(feature):
        return False
    return feature in features_for_plan(plan_code)


def sorted_feature_list(features: FrozenSet[str]) -> List[str]:
    return sorted(features)


def build_entitlements_payload(plan_code: str) -> dict:
    """Contrato estável para frontend (login, /city, /persist-user)."""
    code = normalize_plan_code(plan_code)
    return {
        "plan_code": code,
        "features": sorted_feature_list(features_for_plan(code)),
        "plus_only_features": sorted_feature_list(PLUS_ONLY_FEATURES),
    }
