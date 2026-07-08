# -*- coding: utf-8 -*-
"""
Cálculo INSE contínuo (INSE x Avaliação).

O cálculo consome apenas o formato canônico (saída de inse_normalizer), sem
dependência de IDs de pergunta:
- escolaridade da mãe e do pai (âncora)
- bens por quantidade (Q12 no modelo)
- itens de presença (sim/não) (Q13 no modelo)
"""

from typing import Dict, Any, Tuple, Optional

ESCOLARIDADE_SCORE_CANONICO = {
    # "Nunca estudou" é tratado como equivalente a "não completou 4º/5º".
    "nunca_estudou": -0.9,
    "fundamental_incompleto": -0.9,  # nao_completou_5
    "fundamental_ate_4": -0.5,  # completou_5_nao_9
    "fundamental_completo": -0.1,  # completou_9_nao_medio
    "medio_completo": 0.4,  # completou_medio_nao_superior
    "superior_completo": 1.1,  # completou_superior
    "nao_sei": -0.2,
    "desconhecido": -0.2,
}

# Q12: score base por categoria de quantidade.
Q12_QUANTIDADE_SCORE = {
    "0": -0.4,
    "1": 0.0,
    "2": 0.25,
    "3+": 0.5,
}

# Pesos por item de quantidade (Q12 no modelo novo).
Q12_WEIGHTS = {
    "geladeira": 0.6,
    "computador": 0.9,
    "quartos": 0.5,
    "televisao": 0.4,
    "banheiro": 0.7,
    "carro": 0.9,
    "celular": 0.5,
}

# Pesos por item sim/não (Q13 no modelo novo).
Q13_WEIGHTS = {
    "tv_internet": 0.25,
    "wifi": 0.30,
    # Regra definida: repetir o peso da questão anterior (wifi).
    "quarto_so_seu": 0.30,
    "mesa_estudar": 0.20,
    "microondas": 0.25,
    "aspirador": 0.35,
    "maquina_lavar": 0.25,
    "freezer": 0.30,
    "garagem": 0.30,
}

# Pesos globais da combinação linear.
PESO_ANCORA = 0.9
PESO_BENS_Q12 = 0.55
PESO_BENS_Q13 = 0.45

# Parâmetros da transformação para escala INSE.
INSE_TRANSFORM_OFFSET = 0.149337
INSE_TRANSFORM_SCALE = 0.973668
INSE_BASE = 5.0

# Faixas de classificação por valor de INSE (níveis I a VIII).
INSE_FAIXAS = [
    (3.0, 1, "Nível I"),
    (4.0, 2, "Nível II"),
    (4.5, 3, "Nível III"),
    (5.0, 4, "Nível IV"),
    (5.5, 5, "Nível V"),
    (6.0, 6, "Nível VI"),
    (7.0, 7, "Nível VII"),
]

NIVEIS_INSE_LABELS = {
    1: "Nível I",
    2: "Nível II",
    3: "Nível III",
    4: "Nível IV",
    5: "Nível V",
    6: "Nível VI",
    7: "Nível VII",
    8: "Nível VIII",
}


def _clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(max_value, value))


def calcular_inse_canonico(normalized: Dict[str, Any]) -> Tuple[float, bool, float]:
    """
    Calcula INSE contínuo a partir do dict canônico.
    Retorna (inse, sucesso, theta_clamp).
    """
    if not normalized:
        return 0.0, False, 0.0

    esc_mae = ESCOLARIDADE_SCORE_CANONICO.get(normalized.get("mae_escolaridade"), -0.2)
    esc_pai = ESCOLARIDADE_SCORE_CANONICO.get(normalized.get("pai_escolaridade"), -0.2)
    ancora = (esc_mae + esc_pai) / 2.0

    bens_q12 = 0.0
    bens = normalized.get("bens") or {}
    for item, peso in Q12_WEIGHTS.items():
        categoria = bens.get(item, "0")
        bens_q12 += Q12_QUANTIDADE_SCORE.get(categoria, -0.4) * peso

    bens_q13 = 0.0
    servicos = normalized.get("servicos") or {}
    for item, peso in Q13_WEIGHTS.items():
        valor = bool(servicos.get(item, False))
        bens_q13 += (1.0 if valor else -0.5) * peso

    theta = _clamp(
        (ancora * PESO_ANCORA) + (bens_q12 * PESO_BENS_Q12) + (bens_q13 * PESO_BENS_Q13),
        -3.0,
        3.0,
    )
    inse = ((theta - INSE_TRANSFORM_OFFSET) / INSE_TRANSFORM_SCALE) + INSE_BASE
    return inse, True, theta


def pontuacao_para_nivel_inse(inse: Optional[float]) -> Tuple[Optional[int], str]:
    """
    Retorna (número do nível 1-8, label) a partir do INSE contínuo.
    """
    if inse is None:
        return None, "Não calculado"
    for limite_superior, nivel, label in INSE_FAIXAS:
        if inse < limite_superior:
            return nivel, label
    return 8, NIVEIS_INSE_LABELS[8]


def calcular_pontos_inse_canonico(normalized: Dict[str, Any]) -> Tuple[float, bool]:
    """
    Compatibilidade: retorna o valor contínuo de INSE no formato antigo (valor, sucesso).
    """
    inse, ok, _theta = calcular_inse_canonico(normalized)
    return inse, ok
