# -*- coding: utf-8 -*-
"""
Configuração para integração com OpenAI API
"""

import os
from openai import OpenAI

# Configuração da API Key
OPENAI_API_KEY = "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"

# Configurações do modelo
OPENAI_MODEL = "gpt-4o-mini"  # Modelo mais econômico e eficiente
OPENAI_MAX_TOKENS = 2000
OPENAI_TEMPERATURE = 0.7

# Inicializar cliente OpenAI
def get_openai_client():
    """Retorna cliente OpenAI configurado"""
    return OpenAI(api_key=OPENAI_API_KEY)

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
    "model": OPENAI_MODEL
}
