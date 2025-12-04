# -*- coding: utf-8 -*-
"""
Configuração para integração com OpenAI API e Google Gemini API
"""

import os
from openai import OpenAI

# Configuração da API Key OpenAI
OPENAI_API_KEY = "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"

# Configuração da API Key Gemini
GEMINI_API_KEY = "AIzaSyDcwxjngnTvZb8Xe4BDno6dQlBJRsExliE"

# Escolher qual API usar (pode ser configurado via variável de ambiente)
# Por padrão, usar Gemini se a chave estiver disponível
USE_GEMINI_ENV = os.getenv("USE_GEMINI", "").lower()
if USE_GEMINI_ENV:
    USE_GEMINI = USE_GEMINI_ENV == "true"
elif GEMINI_API_KEY:
    USE_GEMINI = True  # Usar Gemini por padrão se a chave estiver disponível
else:
    USE_GEMINI = False  # Usar OpenAI se não houver chave do Gemini

# Configurações do modelo OpenAI
OPENAI_MODEL = "gemini-1.5-flash"  # Modelo mais econômico e eficiente
OPENAI_MAX_TOKENS = 6000  # Aumentado para acomodar todas as análises em uma única chamada
OPENAI_TEMPERATURE = 0.7

# Configurações do modelo Gemini
GEMINI_MODEL = "gemini-2.5-pro"  # Modelo mais rápido e econômico
# GEMINI_MODEL = "gemini-1.5-pro"  # Modelo mais poderoso, mas mais lento
GEMINI_MAX_TOKENS = 8192  # Limite do Gemini Flash
GEMINI_TEMPERATURE = 0.7

# Inicializar cliente OpenAI
def get_openai_client():
    """Retorna cliente OpenAI configurado"""
    return OpenAI(api_key=OPENAI_API_KEY)

# Inicializar cliente Gemini
def get_gemini_client():
    """Retorna cliente Gemini configurado"""
    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        return genai.GenerativeModel(GEMINI_MODEL)
    except ImportError:
        raise ImportError("google-generativeai não está instalado. Execute: pip install google-generativeai")
    except Exception as e:
        raise Exception(f"Erro ao configurar Gemini: {str(e)}")

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

# Tabela de Classificação de Participação
# Esta tabela foca no diagnóstico (o que o número significa) e na confiabilidade dos dados (o quanto podemos confiar nesse resultado).
PARTICIPATION_CLASSIFICATION_TABLE = """
Classificação	Faixa (Percentual)	Diagnóstico (O que significa?)	Nível de Confiabilidade dos Dados
Ideal (Todos Incluídos)	95% - 100%	Engajamento total. A escola demonstrou uma mobilização exemplar, garantindo que a voz de (quase) todos os alunos fosse ouvida.	Altíssima. O resultado é um espelho fiel da realidade da escola/rede.
Alto Engajamento	90% - 94,9%	Meta superada. Um resultado excelente que mostra um forte compromisso da comunidade escolar. Supera a meta técnica do SAEB com folga.	Muito Alta. Os dados são robustos e representam a realidade com grande precisão.
Meta Atingida (Padrão SAEB)	80% - 89,9%	Trabalho concluído. A escola cumpriu o requisito técnico mínimo (80%) do SAEB. Os dados são oficialmente válidos para análise.	Alta. Os dados são confiáveis e podem ser usados para o planejamento pedagógico.
Atenção (Meta Não Atingida)	70% - 79,9%	Quase lá, mas inválido. Faltou pouco para a meta. Indica que 2 a 3 de cada 10 alunos ficaram de fora, o que acende um alerta.	Baixa. Os dados não são oficialmente válidos pelo SAEB e podem não representar a média real da escola.
Crítico (Não Representativo)	50% - 69,9%	Falha na mobilização. Uma parcela muito grande dos alunos (até metade) não participou. O diagnóstico da escola está comprometido.	Muito Baixa. Os dados não são representativos e podem levar a conclusões erradas.
Inválido (Falha Grave)	Abaixo de 50%	Processo falhou. A avaliação não pode ser considerada. Os dados coletados são estatisticamente irrelevantes e devem ser descartados.	Nula. Os dados são inúteis para diagnóstico.
"""

# Template do prompt para análise de participação
PARTICIPATION_ANALYSIS_PROMPT_TEMPLATE = """
IMPORTANTE: Gere APENAS texto puro, SEM formatação markdown (sem #, ##, *, **, etc). Use apenas parágrafos normais e títulos em maiúsculas seguidos de dois pontos.

Gere um PARECER TÉCNICO DE PARTICIPAÇÃO humanizado e formatado para o relatório PDF, seguindo exatamente este formato:

PARECER TÉCNICO DE PARTICIPAÇÃO: [Entidade] ([Avaliação])
[Aqui comece o primeiro parágrafo mencionando a participação geral e os dados básicos. Use os números específicos fornecidos.]

Classificação: [Nome da Classificação]
[Segundo parágrafo explicando o que essa classificação significa em termos de engajamento e confiabilidade dos dados. Explique se podemos confiar nas médias de proficiência.]

Destaques e Recomendações:
[Mencione os destaques formatados como frases completas. Se não houver destaques, não mencione destaques.]
[Mencione as recomendações práticas focadas nos pontos de atenção, especialmente alunos faltosos. Use formato de parágrafo ou lista com bullets simples (•).]

DADOS DO RELATÓRIO:
- Entidade: [Entidade: Ex. Escola Municipal X / 5º Ano Geral]
- Avaliação: [Avaliação: Ex: Avaliação Diagnóstica 2025.1]
- Total de Alunos Matriculados: [Nº]
- Total de Alunos Avaliados: [Nº]
- Total de Faltosos: [Nº]
- Taxa de Participação Geral: [__]%
- Destaque(s) por Turma: [Ex: 5º A - M: 95% (21/22)]
- Ponto(s) de Atenção por Turma: [Ex: 5º B - M: 91% (21/23) com 2 faltosos]

TABELA DE CLASSIFICAÇÃO (USE ESTA PARA CLASSIFICAR):
{PARTICIPATION_CLASSIFICATION_TABLE}

INSTRUÇÕES IMPORTANTES:
1. Use a tabela acima para classificar a taxa de participação de [__]% e mencione a classificação encontrada no texto.
2. Escreva um texto fluido e humanizado, SEM usar markdown (#, ##, *, **, etc). Use parágrafos normais.
3. USE QUEBRAS DE LINHA DUPLAS (\n\n) para separar parágrafos diferentes.
4. USE QUEBRAS DE LINHA SIMPLES (\n) antes de títulos ou seções importantes (como "Destaques e Recomendações:").
5. Seja específico com os números fornecidos (mencione exatamente a taxa, quantidade de alunos, etc).
6. Explique claramente a confiabilidade dos dados e se podemos confiar nas médias de proficiência.
7. Inclua recomendações práticas e acionáveis focadas nos pontos de atenção.
8. O texto deve ser formatado para impressão em PDF, então use parágrafos bem estruturados e títulos em maiúsculas seguidos de dois pontos.
"""

# Template do prompt para análise de níveis de aprendizagem
NIVEIS_APRENDIZAGEM_ANALYSIS_PROMPT_TEMPLATE = """
IMPORTANTE: Gere APENAS texto puro, SEM formatação markdown (sem #, ##, *, **, etc). Use apenas parágrafos normais e títulos em maiúsculas seguidos de dois pontos.

Gere um PARECER TÉCNICO DE NÍVEIS DE APRENDIZAGEM humanizado e formatado para o relatório PDF, seguindo exatamente este formato:

PARECER TÉCNICO: NÍVEIS DE APRENDIZAGEM EM [DISCIPLINA] ([Avaliação])
[Aqui comece o primeiro parágrafo explicando o que são os Níveis de Aprendizagem e sua importância como diagnóstico pedagógico. Em seguida, explique os 4 níveis usando as definições do INEP, deixando claro que "Adequado" é a meta esperada.]

Diagnóstico e Meta ([Disciplina] - [Série/Ano])
[Segundo parágrafo apresentando os dados da avaliação e a análise do gargalo: percentual que não atingiu a meta vs percentual que atingiu a meta, com detalhamento por nível]

Conclusão: [Conclusão diagnosticando onde está o maior desafio (gargalo) para esta disciplina]

DADOS DO RELATÓRIO:
- Disciplina: [PREENCHER DISCIPLINA: ex: Matemática / Língua Portuguesa]
- Avaliação: [AVALIAÇÃO: ex: Avaliação Diagnóstica 2025.1]
- Total de alunos avaliados: [Nº]
- Abaixo do Básico: [Nº] alunos ([__]%)
- Básico: [Nº] alunos ([__]%)
- Adequado: [Nº] alunos ([__]%)
- Avançado: [Nº] alunos ([__]%)

DEFINIÇÕES DOS NÍVEIS (INEP - "Descritores de Padrões de Desempenho - 2025"):
1. Abaixo do Básico: Indica um desempenho "aquém do esperado", com "significativo comprometimento" das habilidades. Esses alunos têm a "trajetória académica seriamente comprometida" e necessitam de "intervenções emergenciais".
2. Básico: Indica um domínio parcial e insuficiente das habilidades. O aluno não consolidou as competências essenciais para a série e precisa de apoio para recompor a aprendizagem.
3. Adequado (A Meta): Indica o "desempenho esperado". O aluno demonstra ter "desenvolvido as habilidades previstas" e possui "condições adequadas à continuidade" de sua trajetória.
4. Avançado: Indica um "desempenho superior àquele esperado". O aluno domina "habilidades mais complexas" e necessita de "atividades mais desafiadoras".

INSTRUÇÕES IMPORTANTES:
1. Inicie explicando o que são os Níveis de Aprendizagem e defina cada um dos 4 níveis usando as definições acima.
2. Calcule e apresente claramente:
   - O percentual total de alunos que NÃO ATINGIRAM A META (soma de Abaixo do Básico + Básico)
   - O percentual total de alunos que ATINGIRAM A META (soma de Adequado + Avançado)
   - Detalhe cada nível com números específicos (ex: "42% (19 alunos) estão no nível Abaixo do Básico")
3. Escreva um texto fluido e humanizado, SEM usar markdown (#, ##, *, **, etc). Use parágrafos normais.
4. USE QUEBRAS DE LINHA DUPLAS (\n\n) para separar parágrafos diferentes.
5. USE QUEBRAS DE LINHA SIMPLES (\n) antes de títulos ou seções importantes.
6. A conclusão deve apontar claramente onde está o maior desafio (gargalo) para esta disciplina.
7. Use um tom profissional e técnico, baseado nas diretrizes do INEP/SAEB, mas mantenha a humanização.
8. O texto deve ser formatado para impressão em PDF, então use parágrafos bem estruturados e títulos em maiúsculas seguidos de dois pontos.
"""

# Tabela de Referência SAEB (Pontos de Corte para Classificação de Proficiência)
SAEB_PROFICIENCY_REFERENCE_TABLE = """
Tabelas de Referência SAEB (Pontos de Corte)

5º Ano:
Língua Portuguesa:
- Avançado: 275 ou mais
- Adequado (Meta): 225 a < 275
- Básico: 175 a < 225
- Abaixo do Básico: Menos de 175

Matemática:
- Avançado: 300 ou mais
- Adequado (Meta): 250 a < 300
- Básico: 200 a < 250
- Abaixo do Básico: Menos de 200

9º Ano:
Língua Portuguesa:
- Avançado: 350 ou mais
- Adequado (Meta): 300 a < 350
- Básico: 250 a < 300
- Abaixo do Básico: Menos de 250

Matemática:
- Avançado: 375 ou mais
- Adequado (Meta): 325 a < 375
- Básico: 275 a < 325
- Abaixo do Básico: Menos de 275
"""

# Template do prompt para análise de proficiência
PROFICIENCY_ANALYSIS_PROMPT_TEMPLATE = """
IMPORTANTE: Gere APENAS texto puro, SEM formatação markdown (sem #, ##, *, **, etc). Use apenas parágrafos normais e títulos em maiúsculas seguidos de dois pontos.

Gere um PARECER TÉCNICO DE PROFICIÊNCIA humanizado e formatado para o relatório PDF, seguindo exatamente este formato:

PARECER TÉCNICO: PROFICIÊNCIA EM [Disciplina] ([Ano/Série] - [Avaliação])
[Primeiro parágrafo explicando o que é proficiência na escala TRI e mencionando que a meta é o nível "Adequado"]

1. Classificação da Média Geral
[Aqui classifique a média geral de acordo com a tabela de referência e mencione o valor e a classificação encontrada]

2. Análise de Posição
[Aqui descreva onde a média se encontra em relação aos pontos de corte. Se houver benchmark municipal, mencione a distância até ele.]

3. Diagnóstico Pedagógico (INEP)
[Aqui use as definições oficiais do INEP para descrever o que essa classificação significa em termos de aprendizagem, mencionando "desempenho aquém do esperado", "significativo comprometimento", "intervenções emergenciais", etc.]

4. Análise por Turma/Escola
[Se houver dados por turma ou por escola, classifique cada uma individualmente e aponte as disparidades. Use formato de lista com bullets simples (•).]

TABELA DE REFERÊNCIA SAEB (USE ESTA PARA CLASSIFICAR):
{SAEB_PROFICIENCY_REFERENCE_TABLE}

DADOS DO RELATÓRIO:
- Ano/Série: [Ano/Série: 5º Ano ou 9º Ano]
- Disciplina: [Disciplina: LP ou MT]
- Avaliação: [AVALIAÇÃO: ex: Avaliação 2025.1]
- Média Geral da Rede/Escola: [Média]
- Média Municipal/Benchmark (se disponível): [Média Municipal]
- Resultados por Turma/Grupo:
{Resultados por Turma}

INSTRUÇÕES IMPORTANTES:
1. Use a tabela de referência acima para classificar a média geral de acordo com o ano/série e disciplina.
2. Calcule e mencione a distância da média até os pontos de corte relevantes e até a média municipal (se disponível).
3. Use as definições oficiais do INEP para o diagnóstico pedagógico ("desempenho aquém do esperado", "significativo comprometimento", "intervenções emergenciais", "trajetória acadêmica seriamente comprometida", etc.).
4. Se houver dados por turma, classifique cada uma e aponte disparidades.
5. Escreva um texto fluido e humanizado, SEM usar markdown. Use apenas parágrafos normais e títulos numerados em maiúsculas.
6. USE QUEBRAS DE LINHA DUPLAS (\n\n) para separar parágrafos diferentes.
7. USE QUEBRAS DE LINHA SIMPLES (\n) antes de títulos ou seções importantes.
8. O texto deve ser formatado para impressão em PDF, então use parágrafos bem estruturados.
"""

# Tabela de Referência Pedagógica para Nota (0-10)
NOTA_REFERENCE_TABLE = """
Tabela de Referência Pedagógica para Nota (0-10)
Esta tabela classifica a nota com base em sua posição relativa a uma meta (como a meta do IDEB para a rede/escola) ou a um benchmark nacional/municipal.

Classificação Pedagógica	Faixa da Nota (Exemplo*)	Interpretação (O que significa em relação à Meta?)	Implicação para a Rede/Escola
Excelência	Acima de 8,0	Supera a meta com folga. Demonstra um domínio muito sólido das aprendizagens esperadas.	Foco em desafios avançados e manutenção do alto desempenho.
Meta Superada	6,5 a 8,0	Atingiu e ultrapassou a meta. Indica bom domínio das aprendizagens essenciais.	Consolidar o bom trabalho e buscar a excelência.
Meta Atingida	5,5 a 6,4 (Faixa da Meta)	Alcançou o esperado. O desempenho está alinhado com a meta estabelecida (ex: meta IDEB).	Manter o foco, identificar pontos de melhoria para progredir.
Próximo da Meta	4,5 a 5,4	Ainda não atingiu, mas está perto. Indica que parte significativa das aprendizagens precisa ser consolidada.	Intensificar esforços e estratégias para alcançar a meta.
Abaixo do Esperado	3,0 a 4,4	Desempenho insuficiente. Uma parcela considerável dos alunos não domina as habilidades essenciais.	Requer atenção e planejamento de recuperação focado.
Muito Abaixo do Esperado	Abaixo de 3,0	Nível crítico. Indica grandes defasagens na aprendizagem.	Necessidade de intervenção pedagógica urgente e abrangente.

*Nota Importante: A faixa numérica exata para cada classificação deve ser ajustada com base nas metas específicas da sua rede ou nos resultados históricos do SAEB/IDEB para sua localidade. A faixa "Meta Atingida" (5,5-6,4 neste exemplo) deve circundar a meta oficial do IDEB para o ano/ciclo correspondente.
"""

# Template do prompt para análise de notas
NOTA_ANALYSIS_PROMPT_TEMPLATE = """
IMPORTANTE: Gere APENAS texto puro, SEM formatação markdown (sem #, ##, *, **, etc). Use apenas parágrafos normais e títulos em maiúsculas seguidos de dois pontos.

Gere um PARECER TÉCNICO DE NOTA humanizado e formatado para o relatório PDF, seguindo exatamente este formato:

PARECER TÉCNICO: NOTA (0-10) - [Ano/Série] ([Avaliação])
[Primeiro parágrafo explicando brevemente o que é a Nota (escala 0-10 derivada da proficiência, usada no IDEB)]

1. Classificação e Comparação (Média Geral)
[Aqui classifique a média geral usando a tabela de referência. Compare com a média municipal, com a meta e com o IDEB oficial se disponível.]

2. Análise por Disciplina e Turma
[Aqui compare o desempenho entre disciplinas (LP vs MT) e entre turmas. Aponte disparidades e onde o reforço é mais necessário. Use formato de lista com bullets simples (•) se necessário.]

3. Conclusão e Recomendação
[Baseado apenas na análise das notas, sumarize o diagnóstico e recomende ações gerais (aulas de recuperação, avaliações formativas, metodologias ativas) para elevar o rendimento.]

TABELA DE REFERÊNCIA PEDAGÓGICA (USE ESTA PARA CLASSIFICAR):
{NOTA_REFERENCE_TABLE}

DADOS DO RELATÓRIO:
- Entidade/Nível: [Entidade/Nível]
- Avaliação: [AVALIAÇÃO: ex: Avaliação Diagnóstica 2025.1]
- Ano/Série: [Ano/Série]
- Meta Atingida (Referência): 5,5 a 6,4 (faixa da Meta IDEB)
{Dados por Disciplina}
- Média Geral (Todas as Disciplinas): [Média]
- Benchmark (Média Municipal): [Média Municipal]

INSTRUÇÕES IMPORTANTES:
1. Use a tabela de referência acima para classificar a média geral.
2. Compare a média geral com a média municipal e indique a diferença.
3. Compare a média geral com a meta estabelecida (5,5 a 6,4).
4. Analise disparidades entre disciplinas e entre turmas.
5. Escreva um texto fluido e humanizado, SEM usar markdown. Use apenas parágrafos normais e títulos numerados em maiúsculas.
6. USE QUEBRAS DE LINHA DUPLAS (\n\n) para separar parágrafos diferentes.
7. USE QUEBRAS DE LINHA SIMPLES (\n) antes de títulos ou seções importantes.
8. O texto deve ser formatado para impressão em PDF, então use parágrafos bem estruturados.
9. Seja específico com os números fornecidos (mencione exatamente as notas de cada turma, disciplina, etc).
"""

# Configurações de contexto (compatível com ambas as APIs)
CONTEXT_SETTINGS = {
    "max_tokens": GEMINI_MAX_TOKENS if USE_GEMINI else OPENAI_MAX_TOKENS,
    "temperature": GEMINI_TEMPERATURE if USE_GEMINI else OPENAI_TEMPERATURE,
    "model": GEMINI_MODEL if USE_GEMINI else OPENAI_MODEL,
    "use_gemini": USE_GEMINI
}
