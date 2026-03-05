# -*- coding: utf-8 -*-
"""
Tabela de pontuação INSE e faixas de nível.

O cálculo deve consumir apenas o formato canônico (saída de inse_normalizer).
As tabelas abaixo são por conceito semântico; não dependem de ID de pergunta
nem do texto exato da opção.
"""

from typing import Dict, Any, Tuple, Optional

# ---------------------------------------------------------------------------
# Pontuação canônica: conceito semântico -> pontos
# (consumido após normalizar_respostas)
# ---------------------------------------------------------------------------

# Escolaridade: conceito retornado por normalizar_escolaridade -> pontos
ESCOLARIDADE_PONTOS_CANONICO = {
    "fundamental_incompleto": 1,
    "fundamental_ate_4": 2,
    "fundamental_completo": 4,
    "medio_completo": 7,
    "superior_completo": 10,
    "nao_sei": 0,
    "desconhecido": 0,
}

# Bens: item -> valor canônico "0"|"1"|"2"|"3+" -> pontos (ordem: geladeira..celular)
BENS_PONTOS_CANONICO = {
    "geladeira": {"0": 0, "1": 3, "2": 4, "3+": 5},
    "computador": {"0": 1, "1": 4, "2": 6, "3+": 8},
    "quartos": {"0": 0, "1": 2, "2": 4, "3+": 6},
    "televisao": {"0": 0, "1": 2, "2": 3, "3+": 4},
    "banheiro": {"0": 0, "1": 3, "2": 5, "3+": 7},
    "carro": {"0": 1, "1": 5, "2": 8, "3+": 10},
    "celular": {"0": 0, "1": 2, "2": 3, "3+": 4},
}

# Serviços: item -> bool (True=Sim) -> pontos
SERVICOS_PONTOS_CANONICO = {
    "tv_internet": {False: 1, True: 3},
    "wifi": {False: 1, True: 5},
    "quarto_so_seu": {False: 1, True: 4},
    "mesa_estudar": {False: 1, True: 2},
    "microondas": {False: 1, True: 3},
    "aspirador": {False: 1, True: 2},
    "maquina_lavar": {False: 1, True: 4},
    "freezer": {False: 1, True: 3},
    "garagem": {False: 1, True: 4},
}

# ---------------------------------------------------------------------------
# Legado (mantido para referência; uso via normalização + canônico)
# ---------------------------------------------------------------------------

ESCOLARIDADE_PONTOS = {
    "Não completou a 4ª série ou o 5º ano do Ensino Fundamental": 1,
    "Ensino Fundamental, até a 4ª série ou o 5º ano": 2,
    "Ensino Fundamental completo": 4,
    "Ensino Médio completo": 7,
    "Ensino Superior completo (faculdade ou graduação)": 10,
    "Não sei": 0,
}

Q13_PONTOS = {
    "q13a": {"Nenhum": 0, "1": 3, "2": 4, "3 ou mais": 5},
    "q13b": {"Nenhum": 1, "1": 4, "2": 6, "3 ou mais": 8},
    "q13c": {"Nenhum": 0, "1": 2, "2": 4, "3 ou mais": 6},
    "q13d": {"Nenhum": 0, "1": 2, "2": 3, "3 ou mais": 4},
    "q13e": {"Nenhum": 0, "1": 3, "2": 5, "3 ou mais": 7},
    "q13f": {"Nenhum": 1, "1": 5, "2": 8, "3 ou mais": 10},
    "q13g": {"Nenhum": 0, "1": 2, "2": 3, "3 ou mais": 4},
}

Q14_PONTOS = {
    "q14a": {"Não": 1, "Sim": 3},
    "q14b": {"Não": 1, "Sim": 5},
    "q14c": {"Não": 1, "Sim": 4},
    "q14d": {"Não": 1, "Sim": 2},
    "q14e": {"Não": 1, "Sim": 3},
    "q14f": {"Não": 1, "Sim": 2},
    "q14g": {"Não": 1, "Sim": 4},
    "q14h": {"Não": 1, "Sim": 3},
    "q14i": {"Não": 1, "Sim": 4},
}

INSE_QUESTIONS_ESCOLARIDADE = ["q9", "q10"]
INSE_QUESTIONS_BENS = list(Q13_PONTOS.keys())
INSE_QUESTIONS_SIM_NAO = list(Q14_PONTOS.keys())

# Faixas de pontuação total -> nível INSE (1 a 6)
INSE_FAIXAS = [
    (10, 30, 1, "Muito Baixo"),
    (31, 50, 2, "Baixo"),
    (51, 70, 3, "Médio Baixo"),
    (71, 90, 4, "Médio"),
    (91, 110, 5, "Alto"),
    (111, 9999, 6, "Muito Alto"),
]

NIVEIS_INSE_LABELS = {
    1: "Muito Baixo",
    2: "Baixo",
    3: "Médio Baixo",
    4: "Médio",
    5: "Alto",
    6: "Muito Alto",
}


def calcular_pontos_inse_canonico(normalized: Dict[str, Any]) -> Tuple[int, bool]:
    """
    Calcula pontuação INSE a partir do dict canônico (saída de normalizar_respostas).
    Não depende de IDs de pergunta nem de texto de opção.
    Retorna (pontos_total, sucesso).
    """
    if not normalized:
        return 0, False
    total = 0
    # Escolaridade
    total += ESCOLARIDADE_PONTOS_CANONICO.get(
        normalized.get("mae_escolaridade"), 0
    )
    total += ESCOLARIDADE_PONTOS_CANONICO.get(
        normalized.get("pai_escolaridade"), 0
    )
    # Bens
    bens = normalized.get("bens") or {}
    for item, pontos_map in BENS_PONTOS_CANONICO.items():
        val = bens.get(item, "0")
        total += pontos_map.get(val, 0)
    # Serviços
    servicos = normalized.get("servicos") or {}
    for item, pontos_map in SERVICOS_PONTOS_CANONICO.items():
        val = servicos.get(item, False)
        total += pontos_map.get(val, 0)
    return total, True


def pontuacao_para_nivel_inse(pontos: int) -> Tuple[Optional[int], str]:
    """
    Retorna (número do nível 1-6, label).
    Se pontos for None ou < 10, retorna (None, "Não calculado").
    """
    if pontos is None or pontos < 10:
        return None, "Não calculado"
    for min_p, max_p, nivel, label in INSE_FAIXAS:
        if min_p <= pontos <= max_p:
            return nivel, label
    return 6, NIVEIS_INSE_LABELS.get(6, "Muito Alto")
