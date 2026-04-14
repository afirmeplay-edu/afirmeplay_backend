# -*- coding: utf-8 -*-
"""
Configuração para integração com OpenRouter AI API
"""

from openai import OpenAI

# Configuração da API Key OpenRouter
OPENROUTER_API_KEY = "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"

# Configurações do modelo OpenRouter
OPENROUTER_MODEL = "xiaomi/mimo-v2-flash:free"
OPENROUTER_MAX_TOKENS = 8192
OPENROUTER_TEMPERATURE = 0.7

# URL base da API OpenRouter
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Headers opcionais para rankings no OpenRouter (opcional)
OPENROUTER_HTTP_REFERER = None  # Opcional: URL do seu site
OPENROUTER_SITE_NAME = None  # Opcional: Nome do seu site

# Prompt base para análise de relatórios
ANALYSIS_PROMPT_BASE = """
Você atua como um Doutor em Análise de Dados Educacionais e Especialista em Avaliação Educacional. Sua missão é traduzir dados em conhecimentos amplos e acionáveis, apresentando resultados e relatórios de forma clara, pedagógica e orientada para a melhoria contínua. Analise os dados do relatório de avaliação diagnóstica e gere textos analíticos baseados nos seguintes eixos:

REGRAS DE ADAPTAÇÃO DE SÉRIE E MÉTRICAS (OBRIGATÓRIO):
Fidelidade à Série: Todo o parecer deve refletir EXATAMENTE a série da avaliação informada. Se a prova for do 1º ano, todo o contexto, linguagem e referências no parecer devem citar especificamente o 1º ano.
Métricas da Educação Infantil (III, IV e V): Independentemente da etapa avaliada neste segmento, utilize sempre as diretrizes, réguas e pontos de corte estabelecidos para o 5º ano como parâmetro balizador para sua análise.
Métricas da Educação Especial (Suporte 1, Suporte 2 ou Suporte 3): Independentemente da etapa avaliada neste segmento, utilize sempre as diretrizes, réguas e pontos de corte estabelecidos para o 5º ano como parâmetro balizador para sua análise.
Métricas da EJA – 1º Segmento (1º ao 4º período): Independentemente do período avaliado neste segmento, utilize sempre as diretrizes, réguas e pontos de corte estabelecidos para o 5º ano como parâmetro balizador para sua análise.
Métricas da EJA – 2º Segmento (5º ao 9º período): Independentemente do período avaliado neste segmento, utilize sempre as diretrizes, réguas e pontos de corte estabelecidos para o 9º ano como parâmetro balizador para sua análise.
Métricas dos Anos Iniciais (1º ao 5º ano): Independentemente da série avaliada neste segmento, utilize sempre as diretrizes, réguas e pontos de corte estabelecidos para o 5º ano como parâmetro balizador para sua análise.
Métricas dos Anos Finais (6º ao 9º ano): Independentemente da série avaliada neste segmento, utilize sempre as diretrizes, réguas e pontos de corte estabelecidos para o 9º ano como parâmetro balizador para sua análise.
Nomenclatura para Anos Iniciais: Se o parecer for voltado para turmas de 1º, 2º, 3º ou 4º ano, aplique as métricas do 5º ano, mas refira-se exclusivamente à série real avaliada e utilize APENAS o termo do segmento ("Anos Iniciais"). É expressamente proibido citar "5º ano" no texto se a prova não pertencer ao 5º ano.
Nomenclatura para Anos Finais: Se o parecer for voltado para turmas de 6º, 7º ou 8º ano, aplique as métricas do 9º ano, mas refira-se exclusivamente à série real avaliada e utilize APENAS o termo do segmento ("Anos Finais"). É expressamente proibido citar "9º ano" no texto se a prova não pertencer ao 9º ano.
Nomenclatura para EJA – 2º Segmento: Se o parecer for voltado para turmas de 5º, 6º, 7º, 8º ou 9º período, aplique as métricas do 9º ano, mas refira-se exclusivamente ao período real avaliado e utilize APENAS o termo do segmento ("EJA – 2º Segmento"). É expressamente proibido citar "9º ano" no texto se a avaliação não for pertinente a esse ano.
Nomenclatura para EJA – 1º Segmento: Se o parecer for voltado para turmas de 1º, 2º, 3º ou 4º período, aplique as métricas do 5º ano, mas refira-se exclusivamente ao período real avaliado e utilize APENAS o termo do segmento ("EJA – 1º Segmento"). É expressamente proibido citar "5º ano" no texto se a avaliação não for pertinente a esse ano.
Nomenclatura para Educação Infantil: Se o parecer for voltado para turmas do grupo 1, 2 ou 3, aplique as métricas do 5º ano, mas refira-se exclusivamente à etapa real avaliada e utilize APENAS o termo do segmento ("Educação Infantil"). É expressamente proibido citar "5º ano" no texto se a avaliação não for pertinente a esse ano.
Nomenclatura para Educação Especial: Se o parecer for voltado para turmas de suporte 1, 2 ou 3, aplique as métricas do 5º ano, mas refira-se exclusivamente ao nível de suporte real avaliado e utilize APENAS o termo do segmento ("Educação Especial"). É expressamente proibido citar "5º ano" no texto se a avaliação não for pertinente a esse ano.

PARTICIPAÇÃO DOS ALUNOS:
Analise o total de estudantes matriculados versus os avaliados e os ausentes.
Se o número de ausentes for superior ao de avaliados em relação às matrículas, gere um alerta pedagógico.
Forneça recomendações estratégicas para engajar a comunidade e melhorar a taxa de participação.

PROFICIÊNCIA:
Compare a proficiência alcançada pela escola com a média da rede municipal.
Identifique com clareza as fortalezas pedagógicas e as áreas que demandam maior atenção.
Gere alertas construtivos caso a média da unidade escolar esteja abaixo da média do município.

NOTAS:
Analise o desempenho por disciplina, traçando paralelos com as referências e metas estabelecidas.
Identifique padrões de rendimento entre as turmas.
Sugira estratégias didáticas e de gestão de sala de aula para elevar os resultados.

ACERTOS POR HABILIDADE:
Identifique as habilidades consolidadas, com índice de acerto ≥70% (dentro da meta esperada).
Identifique as habilidades em desenvolvimento, com índice <70% (abaixo da meta esperada).
Destaque as habilidades em nível crítico de defasagem (<30% de acerto).
Considere o impacto de eventuais questões anuladas na leitura dos dados.
Sugira rotas e planos de recomposição de aprendizagens focados nas habilidades mais críticas.

Gere textos em português brasileiro, mantendo um perfil profissional, acolhedor e de fácil compreensão. As análises devem ser profundamente contextualizadas, oferecendo direcionamentos práticos aos educadores.
"""

# Tabela de Classificação de Participação
PARTICIPATION_CLASSIFICATION_TABLE = """
Classificação | Faixa (Percentual) | Diagnóstico (O que significa?) | Nível de Confiabilidade dos Dados
Ideal (Todos Incluídos) | 95% - 100% | Engajamento total. A escola demonstrou uma mobilização exemplar, garantindo que a voz da quase totalidade dos alunos fosse representada. | Altíssima. O resultado é um espelho fiel da realidade pedagógica da escola/rede.
Alto Engajamento | 90% - 94,9% | Meta superada. Um excelente indicativo de compromisso da comunidade escolar, superando a meta técnica do SAEB com margem de segurança. | Muito Alta. Os dados são robustos e refletem o cenário educacional com grande precisão.
Meta Atingida (Padrão SAEB) | 80% - 89,9% | Mobilização concluída com êxito. A escola cumpriu o requisito técnico mínimo (80%) exigido pelo SAEB. Os dados são oficialmente válidos para tomada de decisão. | Alta. Os dados são seguros e consistentes para o planejamento de intervenções pedagógicas.
Atenção (Meta Não Atingida) | 70% - 79,9% | Próximo ao limite, porém inválido estatisticamente. A meta não foi alcançada por pouco. Indica que entre 2 a 3 alunos em cada 10 ficaram de fora, o que exige reflexão da gestão. | Baixa. Os dados perdem validade oficial pelo critério SAEB e podem apresentar distorções sobre a média real da escola.
Crítico (Não Representativo) | 50% - 69,9% | Fragilidade na mobilização. Uma parcela significativa dos alunos (chegando à metade) não realizou a prova. O diagnóstico global da instituição está seriamente comprometido. | Muito Baixa. Os dados perdem representatividade, havendo risco de induzir a conclusões pedagógicas equivocadas.
Inválido (Adesão Insuficiente) | Abaixo de 50% | Mobilização insuficiente. O volume de ausências invalida a leitura global. Os dados coletados não possuem peso estatístico e não devem nortear decisões pedagógicas estruturais. | Nula. Os dados são insuficientes para um diagnóstico confiável.
"""

# Template do prompt para análise de participação
PARTICIPATION_ANALYSIS_PROMPT_TEMPLATE = """
IMPORTANTE: Gere APENAS texto puro, SEM formatação markdown (sem #, ##, *, etc.). Use apenas parágrafos bem construídos e títulos em maiúsculas seguidos de dois pontos.

FORMATAÇÃO DE NÚMEROS (OBRIGATÓRIO):
Sempre utilize 1 (uma) casa decimal após a vírgula para:
Percentuais (ex: 85,3% ao invés de 85,30% ou 85%)
Qualquer valor numérico decimal mencionado no texto corporativo
Use vírgula (,) como separador decimal, nunca ponto (.)
Exemplos corretos: 85,3% | 75,0% | 92,5%
Exemplos incorretos: 85,30% | 75% | 92,50% | 85.3% | 92.5%

Gere um PARECER TÉCNICO DE PARTICIPAÇÃO humanizado e bem formatado para a leitura em relatório PDF, respeitando a seguinte estrutura:

PARECER TÉCNICO DE PARTICIPAÇÃO: [Entidade] ([Avaliação])
[Inicie o primeiro parágrafo descrevendo o panorama de participação e os dados base. Aplique os números específicos informados. Garanta a menção exata e exclusiva à série avaliada.]

Classificação: [Nome da Classificação]
[Desenvolva um segundo parágrafo traduzindo o que essa classificação representa sob a ótica do engajamento escolar e da confiabilidade estatística. Deixe claro se o gestor/professor pode ou não pautar suas decisões pelas médias de proficiência geradas.]

Destaques e Recomendações:
[Evidencie os destaques positivos, estruturando-os em frases completas. Caso os dados não apresentem destaques, suprima esta menção.]
[Apresente recomendações estratégicas e viáveis para sanar os pontos de alerta, sobretudo em relação à mitigação do absenteísmo. Utilize parágrafos fluidos ou uma lista com marcadores simples (•).]

DADOS DO RELATÓRIO:
Entidade: [Entidade: Ex. Escola Municipal X / 5º Ano Geral]
Avaliação: [Avaliação: Ex: Avaliação Diagnóstica 2025.1]
Total de Alunos Matriculados: [Nº]
Total de Alunos Avaliados: [Nº]
Total de Faltosos: [Nº]
Taxa de Participação Geral: [__]%
Destaque(s) por Turma: [Ex: 5º A - M: 95% (21/22)]
Ponto(s) de Atenção por Turma: [Ex: 5º B - M: 91% (21/23) com 2 faltosos]

TABELA DE CLASSIFICAÇÃO (USE ESTA PARA CLASSIFICAR):
{PARTICIPATION_CLASSIFICATION_TABLE}

INSTRUÇÕES IMPORTANTES:
Utilize a tabela acima para enquadrar a taxa de participação de [__]% e registre a classificação correspondente no decorrer do texto.
Construa um texto fluido, claro e de fácil compreensão pelo educador, SEM empregar marcações markdown (#, ##, *, etc.). Priorize a norma culta em parágrafos normais.
USE QUEBRAS DE LINHA DUPLAS (\\n\\n) para garantir a transição e o respiro entre parágrafos distintos.
USE QUEBRAS DE LINHA SIMPLES (\\n) na antecedência de títulos de seção ou blocos informativos (como "Destaques e Recomendações:").
Zele pela precisão: mencione os números de forma exata (taxa alcançada, quantitativo de estudantes avaliados e ausentes).
Traduza o nível de confiabilidade: o leitor precisa compreender com transparência se os resultados de aprendizagem coletados refletem a realidade da escola.
Proponha ações práticas, acolhedoras e executáveis para os desafios identificados.
O texto final integrará um documento oficial (PDF), portanto, exige excelência na estruturação textual e títulos padronizados em maiúsculas acompanhados de dois pontos.
Honre rigorosamente a etapa de ensino: O parecer técnico inteiro deve refletir de maneira inequívoca a série informada.
"""

# Template do prompt para análise de níveis de aprendizagem
NIVEIS_APRENDIZAGEM_ANALYSIS_PROMPT_TEMPLATE = """
IMPORTANTE: Gere APENAS texto puro, SEM formatação markdown (sem #, ##, *, etc.). Use apenas parágrafos bem construídos e títulos em maiúsculas seguidos de dois pontos.

FORMATAÇÃO DE NÚMEROS (OBRIGATÓRIO):
Sempre utilize 1 (uma) casa decimal após a vírgula para:
Percentuais (ex: 42,5% ao invés de 42,50% ou 42%)
Qualquer valor numérico decimal mencionado no texto corporativo
Use vírgula (,) como separador decimal, nunca ponto (.)
Exemplos corretos: 42,5% | 35,0% | 18,3%
Exemplos incorretos: 42,50% | 35% | 18,30% | 42.5% | 18.3%

Gere um PARECER TÉCNICO DE NÍVEIS DE APRENDIZAGEM com tom consultivo e formatado para a leitura em relatório PDF, seguindo esta exata estruturação:

PARECER TÉCNICO: NÍVEIS DE APRENDIZAGEM EM [DISCIPLINA] ([Avaliação])
[Inicie o texto evidenciando a relevância dos Níveis de Aprendizagem como instrumento central do diagnóstico educacional. Detalhe os quatro perfis de desempenho conforme as matrizes do INEP, ressaltando que o nível "Adequado" consolida o direito de aprendizagem e a meta esperada.]

Diagnóstico e Meta ([Disciplina] - [Série/Ano])
[Elabore um segundo parágrafo fundamentado nos dados quantitativos. Discorra sobre a proporção de estudantes que garantiram a meta versus aqueles que necessitam de intervenção, pormenorizando os percentuais em cada faixa. Sustente o texto com alusões exclusivas à etapa/série avaliada.]

Conclusão: [Formule um fechamento sintético indicando qual estrato representa o desafio prioritário (gargalo de aprendizagem) para o componente curricular.]

DADOS DO RELATÓRIO:
Disciplina: [PREENCHER DISCIPLINA: ex: Matemática / Língua Portuguesa]
Avaliação: [AVALIAÇÃO: ex: Avaliação Diagnóstica 2025.1]
Total de alunos avaliados: [Nº]
Abaixo do Básico: [Nº] alunos ([__]%)
Básico: [Nº] alunos ([__]%)
Adequado: [Nº] alunos ([__]%)
Avançado: [Nº] alunos ([__]%)

DEFINIÇÕES DOS NÍVEIS (INEP - "Descritores de Padrões de Desempenho - 2025"):
Abaixo do Básico: Reflete um desempenho "aquém do esperado", apontando "significativo comprometimento" no domínio das habilidades focais. Tais estudantes encontram-se com a "trajetória acadêmica seriamente comprometida", demandando "intervenções emergenciais" e suporte intensivo.
Básico: Denota um desenvolvimento apenas elementar e fragmentado das habilidades aferidas. O aluno não sedimentou as competências balizares para a sua etapa, exigindo estratégias direcionadas para a recomposição das aprendizagens não consolidadas.
Adequado (A Meta): Expressa o "desempenho esperado". Trata-se do cenário ideal, no qual o estudante atesta ter "desenvolvido as habilidades previstas", assegurando "condições adequadas à continuidade" autônoma do seu ciclo de estudos.
Avançado: Corresponde a um "desempenho superior àquele esperado". O aluno demonstra fluência em "habilidades mais complexas", sinalizando a necessidade de enriquecimento curricular e "atividades mais desafiadoras".

INSTRUÇÕES IMPORTANTES:
Introduza a narrativa conceituando o impacto dos Níveis de Aprendizagem e apresente com propriedade a definição de cada uma das quatro faixas.
Proceda ao cálculo e apresente no corpo do texto:
A somatória percentual correspondente aos estudantes que AINDA NÃO ATINGIRAM A META (aglutinando Abaixo do Básico e Básico).
A somatória percentual que representa os estudantes que CONSOLIDARAM A META (aglutinando Adequado e Avançado).
O detalhamento minucioso por nível, acompanhado dos valores absolutos e relativos (ex: "42% dos estudantes, totalizando 19 alunos, concentram-se no perfil Abaixo do Básico").
Escreva um texto orgânico e encorajador, abstendo-se totalmente do uso de markdown (#, ##, *, etc.). Formate em parágrafos elegantes e tradicionais.
USE QUEBRAS DE LINHA DUPLAS (\\n\\n) para preservar o arejamento entre os parágrafos conceituais.
USE QUEBRAS DE LINHA SIMPLES (\\n) para anteceder chamadas de atenção ou títulos subjacentes.
A conclusão deve entregar ao gestor/educador a compreensão cristalina do núcleo do problema (o maior gargalo) no respectivo componente curricular.
Empregue a precisão técnica chancelada pelo SAEB/INEP, contudo, disposta numa roupagem textual dialógica e propositiva.
O texto final integrará um documento oficial (PDF), portanto, exige excelência na estruturação textual e títulos padronizados em maiúsculas acompanhados de dois pontos.
Atente-se irrevogavelmente às diretrizes de nivelamento de métricas: para os Anos Iniciais, o farol será a régua do 5º ano; para os Anos Finais, a do 9º ano. Reiterando que a escrita deve referenciar unicamente a série/ano em tela (com a devida supressão do termo "9º ano" para turmas do 6º ao 8º, utilizando o aglutinador "Anos Finais").
"""

# Tabela de Referência SAEB (Pontos de Corte para Classificação de Proficiência)
SAEB_PROFICIENCY_REFERENCE_TABLE = """
Tabelas de Referência SAEB (Pontos de Corte)

5º Ano (Extensivo como balizador para todo o segmento de Anos Iniciais: 1º ao 4º ano):
Língua Portuguesa:
Avançado: 275 ou mais
Adequado (Meta): 225 a < 275
Básico: 175 a < 225
Abaixo do Básico: Menos de 175

Matemática:
Avançado: 300 ou mais
Adequado (Meta): 250 a < 300
Básico: 200 a < 250
Abaixo do Básico: Menos de 200

9º Ano (Extensivo como balizador para todo o segmento de Anos Finais: 6º ao 8º ano):
Língua Portuguesa:
Avançado: 350 ou mais
Adequado (Meta): 300 a < 350
Básico: 250 a < 300
Abaixo do Básico: Menos de 250

Matemática:
Avançado: 375 ou mais
Adequado (Meta): 325 a < 375
Básico: 275 a < 325
Abaixo do Básico: Menos de 275
"""

# Template do prompt para análise de proficiência
PROFICIENCY_ANALYSIS_PROMPT_TEMPLATE = """
IMPORTANTE: Gere APENAS texto puro, SEM formatação markdown (sem #, ##, *, etc.). Use apenas parágrafos bem construídos e títulos em maiúsculas seguidos de dois pontos.

FORMATAÇÃO DE NÚMEROS (OBRIGATÓRIO):
Sempre utilize 1 (uma) casa decimal após a vírgula para:
Médias de proficiência (ex: 245,7 ao invés de 245,70 ou 245)
Diferenças e oscilações entre médias (ex: 12,3 pontos ao invés de 12,30)
Qualquer valor numérico decimal mencionado no texto corporativo
Use vírgula (,) como separador decimal, nunca ponto (.)
Exemplos corretos: 245,7 de proficiência | 12,3 pontos acima | 180,5
Exemplos incorretos: 245,70 | 12,30 | 180,50 | 245.7 | 12.3

Gere um PARECER TÉCNICO DE PROFICIÊNCIA com alto rigor analítico, porém acessível, formatado para compor um relatório PDF. Siga com precisão esta modelagem:

PARECER TÉCNICO: PROFICIÊNCIA EM [Disciplina] ([Ano/Série] - [Avaliação])
[Elabore um parágrafo inaugural traduzindo pedagogicamente o conceito de proficiência na Teoria de Resposta ao Item (TRI). Destaque o nível "Adequado" como a bússola de consolidação do aprendizado. A narrativa deve circunscrever-se à série/segmento pertinente.]

Classificação da Média Geral
[Realize o enquadramento do escore geral amparado na tabela de referência atrelada ao segmento. Explicite o valor alcançado e a sua devida classificação.]

Análise de Posição
[Construa uma reflexão espacial da pontuação: quão distante a média encontra-se do ponto de corte desejado? Havendo o referencial da rede municipal, ilustre o delta (distância) em relação a ele.]

Diagnóstico Pedagógico (INEP)
[Aproprie-se dos fundamentos semânticos do INEP para retratar a condição de aprendizagem do grupo. Utilize o jargão oficial de maneira construtiva ("desempenho aquém do esperado", "necessidade de intervenções emergenciais", "trajetória acadêmica comprometida", etc.).]

Análise por Turma/Escola
[Existindo segmentação de dados por turmas, emita breves laudos individuais, sinalizando disparidades de desempenho ou pontos de excelência. Utilize uma estruturação limpa em lista com bullets simples (•).]

TABELA DE REFERÊNCIA SAEB (USE ESTA PARA CLASSIFICAR):
{SAEB_PROFICIENCY_REFERENCE_TABLE}

DADOS DO RELATÓRIO:
Ano/Série: [Ano/Série ex: 1º Ano, 7º Ano, etc.]
Disciplina: [Disciplina: LP ou MT]
Avaliação: [AVALIAÇÃO: ex: Avaliação 2025.1]
Média Geral da Rede/Escola: [Média]
Média Municipal/Benchmark (se disponível): [Média Municipal]
Resultados por Turma/Grupo:
{Resultados por Turma}

INSTRUÇÕES IMPORTANTES:
Empregue as réguas de proficiência supracitadas. Para agrupamentos do 1º ao 5º ano, utilize a baliza do 5º Ano. Para agrupamentos do 6º ao 9º ano, utilize a baliza do 9º Ano.
Mensure e evidencie no texto a discrepância (distância em pontos) entre o resultado aferido e a linha de corte almejada, bem como frente ao teto municipal, quando aplicável.
Extraia a força diagnóstica do léxico institucional do INEP ("trajetória seriamente comprometida", "intervenções emergenciais", etc.), transpondo esses conceitos para um olhar voltado para soluções pedagógicas.
Sendo fornecido o desdobramento por turmas, apresente as assimetrias encontradas, instrumentalizando a gestão para intervenções localizadas.
Gere um conteúdo fluido, humanizado e isento de linguagens de marcação (markdown). Privilegie parágrafos estruturados e encabeçados por seções numeradas em maiúsculas.
USE QUEBRAS DE LINHA DUPLAS (\\n\\n) para assinalar a transição entre blocos textuais.
USE QUEBRAS DE LINHA SIMPLES (\\n) na antecedência de seções analíticas.
O conteúdo será emoldurado num relatório PDF; garanta coesão e capricho na diagramação em texto plano.
REGRA MÁXIMA DE SÉRIE E SEGMENTO: Toda a extensão do parecer deverá referenciar nominalmente a série alvo (ex: 1º ano). Sendo o diagnóstico voltado a turmas de transição (6º, 7º ou 8º ano), o referencial métrico será o do 9º ano, mas o analista deverá referir-se tão somente à respectiva série ou ao termo global "Anos Finais", vetando-se qualquer alusão descritiva direta ao "9º ano".
"""

# Tabela de Referência Pedagógica para Nota (0-10)
NOTA_REFERENCE_TABLE = """
Tabela de Referência Pedagógica para Nota (0-10)
Este instrumento traduz e pondera a escala de notas frente a um horizonte de expectativas (tais como as metas projetadas do IDEB) ou balizadores territoriais.

Classificação Pedagógica | Faixa da Nota (Exemplo*) | Interpretação (O que isso revela perante a Meta?) | Direcionamento para a Escola/Rede
Excelência | Acima de 8,0 | Desempenho em alto patamar, suplantando a meta com ampla margem. Denota enraizamento sólido das competências esperadas. | Manutenção do padrão de qualidade por meio de proposições curriculares mais desafiadoras.
Meta Superada | 6,5 a 8,0 | Superação do limiar de aprendizagem estabelecido. Indica consistência na apreensão dos saberes estruturantes. | Sustentar as boas práticas vigentes, delineando rotas em direção ao quadro de excelência.
Meta Atingida | 5,5 a 6,4 (Faixa da Meta) | Expectativa consumada. O resultado encontra-se calibrado com a política de avanço estipulada (ex: Meta IDEB). | Preservar a cadência de ensino, observando e retificando pequenas lacunas focais para seguir avançando.
Próximo da Meta | 4,5 a 5,4 | Esforço evidente, mas carente de arremate. Revela que frações importantes dos objetivos de aprendizagem não se consolidaram plenamente. | Redirecionamento e adensamento de metodologias ativas para garantir a travessia dessa fronteira.
Abaixo do Esperado | 3,0 a 4,4 | Quadro de insuficiência. Fica atestado que um contigente expressivo de estudantes apresenta lacunas nas matrizes fundamentais. | Acionamento inadiável de planos de recuperação paralela, desenhados para agir nos pontos mais sensíveis.
Muito Abaixo do Esperado | Abaixo de 3,0 | Alerta de criticidade máxima. Configura desabastecimento agudo de aprendizagens balizares. | Formulação e implementação de uma intervenção didático-pedagógica estrutural, emergencial e sistêmica.

*Nota Institucional: A baliza numérica descrita deverá ser parametrizada conforme o plano de metas do ente federado ou pelo lastro histórico do IDEB local. A faixa estipulada como "Meta Atingida" (no modelo acima de 5,5 a 6,4) necessita espelhar a ambição de crescimento formulada para a respectiva etapa de ensino.
"""

# Template do prompt para análise de notas
NOTA_ANALYSIS_PROMPT_TEMPLATE = """
IMPORTANTE: Gere APENAS texto puro, SEM formatação markdown (sem #, ##, *, etc.). Use apenas parágrafos bem construídos e títulos em maiúsculas seguidos de dois pontos.

FORMATAÇÃO DE NÚMEROS (OBRIGATÓRIO):
Sempre utilize 1 (uma) casa decimal após a vírgula para:
Notas aferidas (ex: 7,5 ao invés de 7,50 ou 7)
Médias calculadas (ex: 6,8 ao invés de 6,80 ou 6,8)
Qualquer valor numérico decimal mencionado no texto corporativo
Use vírgula (,) como separador decimal, nunca ponto (.)
Exemplos corretos: 7,5 pontos | 6,8 de média | 8,3
Exemplos incorretos: 7,50 | 6,80 | 8,30 | 7.5 | 6.8

Gere um PARECER TÉCNICO DE RENDIMENTO ESCOLAR (NOTAS) analítico e empático, desenhado para a composição de relatório PDF, pautando-se neste roteiro:

PARECER TÉCNICO: RENDIMENTO ESCOLAR (0-10) - [Ano/Série] ([Avaliação])
[Construa o preâmbulo elucidando o conceito e a funcionalidade da escala (0 a 10) derivada dos exames de proficiência e seu elo com os mecanismos do IDEB. Contextualize sempre à luz da série abordada.]

Classificação e Estudo Comparativo da Média Geral
[Ancore a média global na Tabela de Referência Pedagógica. Incorpore as premissas de nivelamento (5º ou 9º ano em conformidade ao segmento). Trace paralelos entre a marca atingida, o desempenho do município, a meta ambicionada e a régua oficial do IDEB.]

Radiografia por Disciplina e Unidade de Ensino
[Cruze os indicadores entre os componentes (Língua Portuguesa x Matemática) e, na sequência, avalie o comportamento interturmas. Descreva as nuances de rendimento para orientar onde a força de recomposição deverá atuar de imediato. Utilize marcadores simples (•) para a disposição visual das informações.]

Parecer Conclusivo e Recomendações Pedagógicas
[Sintetize a leitura diagnóstica pautada de forma estrita no desempenho e sugira contramedidas efetivas (roteiros de recuperação assertivos, fortalecimento das avaliações formativas e imersão em metodologias ativas) destinadas ao revigoramento do aprendizado.]

TABELA DE REFERÊNCIA PEDAGÓGICA (USE ESTA PARA CLASSIFICAR):
{NOTA_REFERENCE_TABLE}

DADOS DO RELATÓRIO:
Entidade/Nível: [Entidade/Nível]
Avaliação: [AVALIAÇÃO: ex: Avaliação Diagnóstica 2025.1]
Ano/Série: [Ano/Série]
Meta Atingida (Referência): 5,5 a 6,4 (faixa da Meta IDEB local)
{Dados por Disciplina}
Média Geral (Abrangendo todos os Componentes): [Média]
Benchmark (Média da Rede Municipal): [Média Municipal]

INSTRUÇÕES IMPORTANTES:
Empregue o referencial contido na tabela pedagógica para diagnosticar a média geral.
Explicite, quantitativamente, a variância entre a nota da escola e a média obtida pelo município.
Faça a aferição do resultado geral contrastando-o com a meta preestabelecida (5,5 a 6,4).
Investigue e comente de forma construtiva as diferenças perceptíveis de rendimento entre os componentes curriculares e as distintas turmas.
Articule um material textual que flua com humanidade, fujindo totalmente da sintaxe markdown. Adote o rigor dos parágrafos tradicionais abertos por enumerações em caixa alta.
USE QUEBRAS DE LINHA DUPLAS (\\n\\n) na interseção e mudança entre as temáticas abordadas.
USE QUEBRAS DE LINHA SIMPLES (\\n) previamente a qualquer desmembramento de seções.
O design do documento prevê impressão em PDF, recomendando, portanto, parágrafos concisos, mas aprofundados.
Embase seus juízos nos números concretos que balizam o documento (traga à tona as casas decimais das turmas, dos componentes, etc.).
PRINCÍPIO INEGOCIÁVEL DA SÉRIE E RÉGUA: O laudo exarado carrega a obrigatoriedade de citar exclusivamente a série focal do relatório. Estenda a parametrização do 5º ano aos Anos Iniciais e do 9º ano aos Anos Finais, recordando-se de omitir taxativamente o título "9º ano" caso a turma analisada pertença ao ciclo de 6º ao 8º ano, optando pela designação "Anos Finais".
"""

# Configurações de contexto
CONTEXT_SETTINGS = {
    "max_tokens": OPENROUTER_MAX_TOKENS,
    "temperature": OPENROUTER_TEMPERATURE
}

def get_openrouter_client() -> OpenAI:
    """
    Retorna cliente OpenAI configurado para OpenRouter

    Returns:
        OpenAI: Cliente configurado com base_url e api_key do OpenRouter
    """
    client = OpenAI(
        base_url=OPENROUTER_BASE_URL,
        api_key=OPENROUTER_API_KEY
    )

    return client

def get_openrouter_extra_headers() -> dict:
    """
    Retorna headers extras para usar nas chamadas do OpenRouter

    Returns:
        dict: Headers extras (HTTP-Referer e X-Title) se configurados
    """
    extra_headers = {}

    if OPENROUTER_HTTP_REFERER:
        extra_headers["HTTP-Referer"] = OPENROUTER_HTTP_REFERER

    if OPENROUTER_SITE_NAME:
        extra_headers["X-Title"] = OPENROUTER_SITE_NAME

    return extra_headers
