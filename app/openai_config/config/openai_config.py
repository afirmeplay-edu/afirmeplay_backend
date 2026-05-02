# -*- coding: utf-8 -*-
"""
Espelho / legado de prompts para análise (sem chaves no código).
Credenciais OpenAI, se usadas no futuro, devem vir apenas do ambiente.
"""

import os

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_MAX_TOKENS = int(os.getenv("OPENAI_MAX_TOKENS", "2000"))
OPENAI_TEMPERATURE = float(os.getenv("OPENAI_TEMPERATURE", "0.7"))

# Prompt base para análise de relatórios
ANALYSIS_PROMPT_BASE = """
Você é um especialista em educação e análise de dados educacionais. 
Analise os dados do relatório de avaliação diagnóstica e gere textos analíticos 
baseados nos seguintes pontos:

1. PARTICIPAÇÃO DOS ALUNOS:
   - Analise o total de matriculados vs avaliados vs faltosos
   - Se faltosos > avaliados em relação aos matriculados, gere um alerta
   - Forneça recomendações para melhorar a participação

2. PROFICIÊNCIA:
   - Compare a proficiência da escola com a média municipal
   - Identifique pontos fortes e áreas de melhoria
   - Gere alertas se a média da escola < média municipal

3. NOTAS:
   - Analise notas por disciplina e compare com referências
   - Identifique padrões de desempenho
   - Sugira estratégias de melhoria

4. ACERTOS POR HABILIDADE:
   - Identifique habilidades com ≥70% (dentro da meta)
   - Identifique habilidades com <70% (abaixo da meta)
   - Destaque habilidades críticas (<30%)
   - Considere questões anuladas na análise
   - Sugira planos de recuperação específicos

Gere textos em português brasileiro, profissionais mas acessíveis, 
com análises contextualizadas e recomendações práticas.
"""

# Configurações de contexto
CONTEXT_SETTINGS = {
    "max_tokens": OPENAI_MAX_TOKENS,
    "temperature": OPENAI_TEMPERATURE,
    "model": OPENAI_MODEL,
}
