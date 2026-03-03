# -*- coding: utf-8 -*-
"""
Tabela de pontuação INSE e faixas de nível (formulário aluno-velho).
Baseado nas questões q9, q10 (escolaridade) e q13, q14 (bens/serviços).
"""

# Escolaridade mãe (q9) e pai (q10) - opção de resposta -> pontos
ESCOLARIDADE_PONTOS = {
    "Não completou a 4ª série ou o 5º ano do Ensino Fundamental": 1,
    "Ensino Fundamental, até a 4ª série ou o 5º ano": 2,
    "Ensino Fundamental completo": 4,
    "Ensino Médio completo": 7,
    "Ensino Superior completo (faculdade ou graduação)": 10,
    "Não sei": 0,
}

# Q13 (quantidade de bens) - por subquestão: opção -> pontos
# q13a Geladeira, q13b Computador, q13c Quartos, q13d Televisão, q13e Banheiro, q13f Carro, q13g Celular
Q13_PONTOS = {
    "q13a": {"Nenhum": 0, "1": 3, "2": 4, "3 ou mais": 5},
    "q13b": {"Nenhum": 1, "1": 4, "2": 6, "3 ou mais": 8},
    "q13c": {"Nenhum": 0, "1": 2, "2": 4, "3 ou mais": 6},
    "q13d": {"Nenhum": 0, "1": 2, "2": 3, "3 ou mais": 4},
    "q13e": {"Nenhum": 0, "1": 3, "2": 5, "3 ou mais": 7},
    "q13f": {"Nenhum": 1, "1": 5, "2": 8, "3 ou mais": 10},
    "q13g": {"Nenhum": 0, "1": 2, "2": 3, "3 ou mais": 4},
}

# Q14 (Sim/Não) - por subquestão: opção -> pontos
Q14_PONTOS = {
    "q14a": {"Não": 1, "Sim": 3},   # TV por internet
    "q14b": {"Não": 1, "Sim": 5},   # Rede wi-fi
    "q14c": {"Não": 1, "Sim": 4},   # Um quarto só seu
    "q14d": {"Não": 1, "Sim": 2},   # Mesa para estudar
    "q14e": {"Não": 1, "Sim": 3},   # Forno de micro-ondas
    "q14f": {"Não": 1, "Sim": 2},   # Aspirador de pó
    "q14g": {"Não": 1, "Sim": 4},   # Máquina de lavar roupa
    "q14h": {"Não": 1, "Sim": 3},   # Freezer
    "q14i": {"Não": 1, "Sim": 4},   # Garagem
}

# Chaves das respostas usadas no INSE (template aluno-velho)
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
