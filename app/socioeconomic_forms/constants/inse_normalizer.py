# -*- coding: utf-8 -*-
"""
Camada de normalização para o cálculo INSE.

Transforma respostas brutas (qualquer numeração q8/q9/q12/q13/q14 e textos variados)
em um formato canônico. O cálculo de pontos consome apenas esse formato,
sem depender de IDs de pergunta nem do texto exato da opção.
"""

from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Mapas de chaves: múltiplas numerações (formulários antigos vs novos)
# ---------------------------------------------------------------------------

ESCOLARIDADE_MAE_KEYS = ["q9", "q8"]
ESCOLARIDADE_PAI_KEYS = ["q10", "q9"]

# Bens (quantidade): conceito -> lista de chaves possíveis [q13a ou q12a, ...]
BENS_MAP = {
    "geladeira": ["q13a", "q12a"],
    "computador": ["q13b", "q12b"],
    "quartos": ["q13c", "q12c"],
    "televisao": ["q13d", "q12d"],
    "banheiro": ["q13e", "q12e"],
    "carro": ["q13f", "q12f"],
    "celular": ["q13g", "q12g"],
}

# Serviços (sim/não): conceito -> lista de chaves possíveis [q14a ou q13a, ...]
SERVICOS_MAP = {
    "tv_internet": ["q14a", "q13a"],
    "wifi": ["q14b", "q13b"],
    "quarto_so_seu": ["q14c", "q13c"],
    "mesa_estudar": ["q14d", "q13d"],
    "microondas": ["q14e", "q13e"],
    "aspirador": ["q14f", "q13f"],
    "maquina_lavar": ["q14g", "q13g"],
    "freezer": ["q14h", "q13h"],
    "garagem": ["q14i", "q13i"],
}

# ---------------------------------------------------------------------------
# Aliases semânticos: texto da opção -> conceito estável
# ---------------------------------------------------------------------------

ESCOLARIDADE_ALIAS = {
    "fundamental_incompleto": [
        "Não completou o 5º ano",
        "Não completou a 4ª série",
        "Não completou a 4ª série ou o 5º ano do Ensino Fundamental",
    ],
    "fundamental_ate_4": [
        "Ensino Fundamental, até a 4ª série ou o 5º ano",
    ],
    "fundamental_completo": [
        "Ensino Fundamental completo",
    ],
    "medio_completo": [
        "Ensino Médio completo",
    ],
    "superior_completo": [
        "Ensino Superior completo (faculdade ou graduação)",
        "Ensino Superior completo",
    ],
    "nao_sei": [
        "Não sei",
    ],
}

# Quantidade (bens): texto da opção -> valor canônico "0" | "1" | "2" | "3+"
BENS_OPCAO_ALIAS = {
    "0": ["Nenhum", "0"],
    "1": ["1"],
    "2": ["2"],
    "3+": ["3 ou mais", "3 ou mais"],
}

# Sim/Não: texto -> booleano (True = Sim)
SIM_NAO_ALIAS = {
    True: ["Sim", "sim", "Sím", "sím"],
    False: ["Não", "Nao", "não", "nao", "Nao"],
}


def _first_value(responses: Dict[str, Any], keys: List[str]) -> Optional[str]:
    """Retorna o valor da primeira chave que existir em responses (strip)."""
    for k in keys:
        v = responses.get(k)
        if v is not None and str(v).strip() != "":
            return str(v).strip()
    return None


def normalizar_escolaridade(texto: Optional[str]) -> str:
    """
    Mapeia texto livre da opção de escolaridade para conceito semântico estável.
    Retorna 'desconhecido' se não houver alias.
    """
    if not texto or not str(texto).strip():
        return "desconhecido"
    t = str(texto).strip()
    for key, aliases in ESCOLARIDADE_ALIAS.items():
        for alias in aliases:
            if alias.strip() == t:
                return key
    logger.warning("INSE: escolaridade não reconhecida (adicione alias se necessário): %r", t)
    return "desconhecido"


def normalizar_quantidade_bens(texto: Optional[str]) -> str:
    """Mapeia texto da opção de quantidade (bens) para valor canônico 0, 1, 2, 3+."""
    if not texto or str(texto).strip() == "":
        return "0"
    t = str(texto).strip()
    for canonical, aliases in BENS_OPCAO_ALIAS.items():
        if t in aliases:
            return canonical
    if t in ("1", "2"):
        return t
    if "3" in t or "ou mais" in t.lower():
        return "3+"
    return "0"


def normalizar_sim_nao(texto: Optional[str]) -> Optional[bool]:
    """Mapeia texto Sim/Não para booleano. Retorna None se não reconhecido."""
    if not texto or str(texto).strip() == "":
        return None
    t = str(texto).strip()
    for valor, aliases in SIM_NAO_ALIAS.items():
        if t in aliases:
            return valor
    return None


def normalizar_respostas(responses: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transforma respostas brutas (form_responses.responses) em formato canônico.
    O cálculo do INSE consome apenas esse retorno.

    Formato canônico:
    - mae_escolaridade: str (conceito semântico)
    - pai_escolaridade: str (conceito semântico)
    - bens: dict item -> "0"|"1"|"2"|"3+"
    - servicos: dict item -> True|False
    """
    if not responses:
        return {
            "mae_escolaridade": "desconhecido",
            "pai_escolaridade": "desconhecido",
            "bens": {k: "0" for k in BENS_MAP},
            "servicos": {k: False for k in SERVICOS_MAP},
        }

    # Regra especial: quando q10 está ausente ou vazio e existem q8 e q9 -> mãe = q8, pai = q9
    q10_val = (responses.get("q10") or "").strip()
    q8_val = _first_value(responses, ["q8"])
    q9_val = _first_value(responses, ["q9"])
    if not q10_val and q8_val and q9_val:
        mae_escolaridade = normalizar_escolaridade(q8_val)
        pai_escolaridade = normalizar_escolaridade(q9_val)
    else:
        texto_mae = _first_value(responses, ESCOLARIDADE_MAE_KEYS)
        texto_pai = _first_value(responses, ESCOLARIDADE_PAI_KEYS)
        mae_escolaridade = normalizar_escolaridade(texto_mae)
        pai_escolaridade = normalizar_escolaridade(texto_pai)

    bens = {}
    for item, keys in BENS_MAP.items():
        raw = _first_value(responses, keys)
        bens[item] = normalizar_quantidade_bens(raw)

    servicos = {}
    for item, keys in SERVICOS_MAP.items():
        raw = _first_value(responses, keys)
        val = normalizar_sim_nao(raw)
        servicos[item] = val if val is not None else False

    return {
        "mae_escolaridade": mae_escolaridade,
        "pai_escolaridade": pai_escolaridade,
        "bens": bens,
        "servicos": servicos,
    }
