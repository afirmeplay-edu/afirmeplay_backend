# Mapeamento do relatório PDF (`report_organized.html`) para o frontend

Documento de referência para reproduzir o layout e os textos do relatório gerado por WeasyPrint.  
**Fonte de verdade do template:** `app/templates/report_organized.html`.

**Convenções:**

- Texto **fixo** = literal no template (pode copiar para i18n).
- **`{{ variavel }}`** = conteúdo dinâmico vindo do payload (JSON do relatório).
- **`[condição]`** = ramo do template; implementar conforme `metadados.scope_type` e flags derivadas.

---

## Legenda rápida de variáveis (payload típico)

| Variável | Origem comum |
|----------|----------------|
| `{{ avaliacao.titulo }}` | `avaliacao.titulo` |
| `{{ avaliacao.disciplinas }}` | lista de strings |
| `{{ avaliacao.series_label }}` / `{{ avaliacao.series }}` | série(s) |
| `{{ avaliacao.serie }}` | série única (capa), opcional |
| `{{ metadados.municipio }}`, `{{ metadados.uf }}` | escopo |
| `{{ metadados.escola }}` | escopo escola |
| `{{ metadados.ano }}` | ano numérico do relatório |
| `{{ metadados.data_geracao }}` | string data/hora geração |
| `{{ metadados.scope_type }}` | `"school"` \| `"city"` \| `"all"` \| `"teacher"` \| `"overall"` (normalizar no app) |
| `{{ metadados.logo }}` | URL ou vazio |
| `{{ default_logo }}` | base64 PNG (fallback) |
| `{{ total_alunos }}` | `por_turma`, `por_escola`, `total_geral` |
| `{{ niveis_aprendizagem }}` | dict por disciplina + `GERAL` |
| `{{ proficiencia.por_disciplina }}` | ver nota abaixo |
| `{{ nota_geral.por_disciplina }}` | idem |
| `{{ acertos_por_habilidade }}` | por disciplina + `GERAL` |
| `{{ analise_ia }}` | textos de IA (opcional) |

**Flags úteis (derivadas no template):**

- `is_school_scope` = `metadados.scope_type === 'school'`
- `is_class_scope` = escola **e** (metadados tem `turma` **ou** só uma linha em `total_alunos.por_turma`)
- `serie_geral_label` = rótulo da linha consolidada (ex.: `"9º ANO GERAL"` ou `"MUNICIPAL GERAL"`)

---

## Estilo global (resumo para UI)

| Elemento | Valor (referência CSS) |
|----------|-------------------------|
| Página | A4, margem **1 cm** |
| Corpo | `font-size` 11pt, `line-height` 1.6, cor texto `#1e293b` |
| Fonte | `ReportFont` / Arial (no PDF); no web: Inter / system sans |
| Rodapé (páginas após a capa no PDF) | 8pt, cor `#9ca3af` |
| Rodapé esquerda (fixo) | `AfirmePlay: Sistema de Ensino e Avaliação` |
| Rodapé centro (fixo + página) | `Página {n}` |
| Rodapé direita | `Gerado em {{ metadados.data_geracao }}` |
| Título de seção `h2` | 12pt, bold, `#1e293b`, margem vertical |
| Tabela `.data-table` thead | fundo `#6b21a8`, texto branco |
| Caixa de análise `.analysis-section` | fundo `#f8fafc`, borda esquerda `#6366f1` |

**Quebras de página (comportamento PDF):** `.cover-page` força nova página depois; `.data-section` usa `page-break-after: always` (cada bloco grande “empurra” o próximo conteúdo). No frontend use `break-after: page` só se quiser imitar impressão.

---

## Página 1 — Capa (`.cover-page`)

**Layout:** coluna flex, conteúdo centralizado horizontalmente; três faixas verticais (topo / meio / rodapé). `min-height` full view; padding **40px 60px**. Fundo branco. **Após a capa:** quebra de página.

### Topo (`.cover-top-section`)

| Item | Texto / conteúdo | Dinâmico |
|------|------------------|----------|
| Logo | Imagem ou fallback | `{{ metadados.logo }}` → senão `{{ default_logo }}` → senão texto fixo abaixo |
| Fallback logo (texto) | **AfirmePlay** (quebra de linha) **PLAY** | fixo |
| Município | — | `{{ metadados.municipio }}{{ " - " + metadados.uf se metadados.uf }}` (linha opcional; se não houver município, bloco omitido) |
| Secretaria (fixo) | **SECRETARIA MUNICIPAL DE EDUCAÇÃO** | fixo (`margin-top: 5px` no template) |

**Cores (capa):** título município típico `#6b21a8`; secretaria `#6b7280` (uppercase no CSS).

### Meio (`.cover-middle-section`)

| Item | Texto | Dinâmico |
|------|-------|----------|
| Título principal (`.cover-title`, ~36pt bold, uppercase visual) | fallback | `{{ avaliacao.titulo }}` ou **`AVALIAÇÃO DIAGNÓSTICA`** |
| Séries (opcional, `.cover-series`, roxo) | — | `avaliacao.series_label` → senão `metadados.series_label` → senão `join(avaliacao.series)` → senão `join(metadados.series)` |
| Disciplinas (opcional, `.cover-disciplinas`) | — | `join(avaliacao.disciplinas, ", ")` |

### Rodapé (`.cover-bottom-section` — card com borda)

| Label (fixo) | Valor |
|----------------|--------|
| **ESCOLA:** | `{{ metadados.escola }}` — só se `scope_type === 'school'` e existir escola |
| **MUNICÍPIO:** | `{{ metadados.municipio }}` — se `scope_type` em `['city','all']` e existir município |
| **SÉRIE:** | `{{ avaliacao.serie or metadados.serie or '9º Ano' }}` — se houver `avaliacao.serie` ou `metadados.serie` |

---

## Bloco textual — 1. APRESENTAÇÃO (`<section class="section">`)

**Título fixo:** `1. APRESENTAÇÃO`

Parágrafo inicial — **três variantes** (escolher pela mesma regra do backend):

### Variante A — escopo escola (`is_school_scope`)

Texto montado:

```
Este relatório apresenta os resultados do {{ avaliacao.titulo }} referentes {{ turmas_text }} do ano de {{ metadados.ano }} na {{ metadados.escola or 'ESCOLA' }}. Foram avaliados {{ total_alunos.total_geral.avaliados }} alunos, o que corresponde a {{ percentual }}% do total de estudantes contemplados.
```

Onde `turmas_text` = **`às turmas {{ series_label }}`** se existir `series_label`, senão **`às turmas avaliadas`**.

(`series_label` no template = `avaliacao.series_label or metadados.series_label` apenas quando escopo escola.)

### Variante B — escopo cidade (`metadados.scope_type === 'city'`)

```
Este relatório apresenta os resultados consolidados do {{ avaliacao.titulo }} referentes à rede municipal de ensino de {{ metadados.municipio or 'MUNICÍPIO' }} no ano de {{ metadados.ano }}. Foram avaliados {{ total_alunos.total_geral.avaliados }} alunos em {{ total_alunos.por_escola.length }} escolas, o que corresponde a {{ percentual }}% do total de estudantes da rede.
```

### Variante C — demais (ex.: `all` / geral)

```
Este relatório apresenta os resultados consolidados do {{ avaliacao.titulo }} para todas as turmas avaliadas no ano de {{ metadados.ano }}. Foram avaliados {{ total_alunos.total_geral.avaliados }} alunos, o que corresponde a {{ percentual }}% do total de estudantes participantes.
```

**Parágrafos fixos seguintes:**

- `Para a análise, utilizamos:`
- Lista com marcadores (square):
  - `Frequência absoluta (número de alunos)`
  - `Frequência relativa (percentual)`
  - `Média aritmética simples`

```
As competências avaliadas foram {{ disciplinas_texto }}, com dados apresentados por turma, por série e consolidado para toda a rede. Gráficos nominais por aluno e rendimento de cada turma estão disponíveis na Plataforma AfirmePlay, nas respectivas unidades de ensino.
```

`disciplinas_texto` = `join(avaliacao.disciplinas, " e ")` **ou**, se vazio, fixo: **`Língua Portuguesa e Matemática`**.

```
A escala de cores das médias variou do vermelho (0) ao verde (10). Para identificar descritores/habilidades com índice de erro superior a 40%, registramos esses itens em destaque vermelho, sinalizando prioridades de intervenção pedagógica.
```

**Alinhamento:** `text-align: justify` (classe `.justified`).

---

## Bloco textual — 2. CONSIDERAÇÕES GERAIS

**Título fixo:** `2. CONSIDERAÇÕES GERAIS`

**Parágrafos fixos:**

1. `Antes de olharmos os resultados é importante nos atentarmos que cada escola tem suas especificidades, assim como cada turma. Existem resultados que só serão explicados considerando estas especificidades.`

2. `As turmas são únicas e, portanto, a observação das necessidades de cada turma deve ser analisada através do sistema.`

---

## Seção dados — Participação (`.data-section`)

**Título fixo:** `1. PARTICIPAÇÃO DA REDE NO PROCESSO DE AVALIAÇÃO DIAGNÓSTICA`

**Subtítulo da tabela (thead linha 1, colspan 5):**  
`TOTAL DE ALUNOS QUE REALIZARAM A AVALIAÇÃO DIAGNÓSTICA`

**Cabeçalhos colunas:**

- Coluna 1: se escola → **`SÉRIE/TURNO`**; senão → **`ESCOLA`**
- **`MATRICULADOS`**, **`AVALIADOS`**, **`PERCENTUAL`**, **`FALTOSOS`**

**Corpo:** linhas de `{{ total_alunos.por_turma }}` (escola) ou `{{ total_alunos.por_escola }}` (município/geral).

**Linha de total (th):** exibida se existir `total_alunos.total_geral` **e** **não** for `is_class_scope`. Primeira célula = `{{ serie_geral_label }}` (ex. `MUNICIPAL GERAL` ou `{{ séries }} GERAL`).

---

## Parecer — Participação (`.analysis-section`, após a tabela)

**Título fixo:** `PARECER TÉCNICO DE PARTICIPAÇÃO`

- Se existir `analise_ia.participacao`: renderizar HTML formatado a partir do texto da IA (`formatar_texto_ia` no backend).
- **Senão**, parágrafo padrão longo (resumo): informa avaliados, %, matriculados, faltosos, recomenda investigar ausências e reposição — valores de `{{ total_alunos.total_geral }}` e menção a `serie_geral_label` quando diferente de `MUNICIPAL GERAL`.

**Fallback sem IA** (com `total_alunos.total_geral`), texto base (partes dinâmicas entre `{{ }}`):

- Começa com: `A escola avaliou` **{{ avaliados }}** `alunos`
- Se `serie_geral_label` existe e ≠ `MUNICIPAL GERAL`: insere `{{ serie_geral_label sem sufixo ' GERAL', em minúsculas }}` + `, o que representa`
- Senão: `avaliados, o que representa`
- Continua: `{{ percentual }}%` `do total de` **{{ matriculados }}** `alunos matriculados. Registrou-se um total de` **{{ faltosos }}** `alunos faltosos. A taxa de participação de` **{{ percentual }}%** `é boa, indicando um bom engajamento geral. Contudo, a ausência de` **{{ faltosos }}** `alunos é um número considerável. Recomenda-se a investigação das causas dessas ausências, um contato proativo com as famílias para elevar a participação em futuras avaliações e o planejamento de uma reposição diagnóstica para os alunos faltosos, visando obter um panorama mais completo da aprendizagem na série.`

Se não houver `total_alunos.total_geral`: texto fixo **`Análise de participação não disponível no momento.`**

---

## Seção dados — Níveis de aprendizagem (repete por `disc` em `niveis_aprendizagem`)

Para cada par `(disc, bloco)`:

**Título (dinâmico):**

```
NÍVEIS DE APRENDIZAGEM POR {{ rótulo_escopo }} – {{ avaliacao.titulo }} {{ disc_nome_exibido }}
```

- `rótulo_escopo`: se escola e **uma turma** → `TURMA`; se escola e várias → `TURMA/GERAL`; senão → `ESCOLA/GERAL`.
- `disc_nome_exibido`: nome da chave; se `GERAL` → rótulo `GERAL`; se contiver português/portugues → `PORTUGUÊS`; matemática → `MATEMÁTICA`; senão uppercase da chave.

**Tabela:** colunas fixas  
`ABAIXO DO BÁSICO`, `BÁSICO`, `ADEQUADO`, `AVANÇADO` (classes de cor no thead: vermelho, laranja, verde claro, verde escuro).

- Linhas: `bloco.por_turma` (escola) ou `bloco.por_escola` (outros), com campos `abaixo_do_basico`, `basico`, `adequado`, `avancado` (+ `turma` ou `escola`).
- Linha consolidada: se `(bloco.geral || bloco.total_geral)` e **não** `is_class_scope`: célula 1 = `serie_geral_label`, demais = totais do bloco.

**Gráfico de barras (se existir `dados_gerais` com `total`):** título com `disc_nome` e total de alunos; quatro barras (Abaixo, Básico, Adequado, Avançado) com altura proporcional ao % dentro do total da disciplina.

**Parecer opcional:** se `analise_ia.niveis_aprendizagem[disc]`: título  
`PARECER TÉCNICO: NÍVEIS DE APRENDIZAGEM EM {{ disc_nome }} ({{ avaliacao.titulo }})`.

---

## Seção dados — Proficiência (uma seção, se `proficiencia.por_disciplina`)

**Título:**  
`PROFICIÊNCIA POR {{ TURMA | TURMA/GERAL | ESCOLA/GERAL }} – {{ avaliacao.titulo }}`

**Tabela interna (thead):**

- Linha 1 título mesclado: varia entre  
  `PROFICIÊNCIA POR TURMA` / `TURMA/GERAL` / `ESCOLA/GERAL` + ` – {{ avaliacao.titulo }}`
- Linha 2: `SÉRIE/TURNO` ou `ESCOLA` | **`LÍNGUA PORTUGUESA`** | **`MATEMÁTICA`** | **`MÉDIA`** | **`MÉDIA MUNICIPAL`**

**Corpo:** o template **resolve** as chaves de disciplina cujo nome parece português ou matemática e preenche as colunas; média municipal em célula com rowspan.

**Gráfico:** barras LP, Mat, Média geral, Média municipal (rótulos fixos nos eixos).

**Pareceres opcionais:** para cada entrada em `analise_ia.proficiencia` com chave ≠ `GERAL`:  
`PARECER TÉCNICO: PROFICIÊNCIA EM {{ disc_prof }} ({{ avaliacao.titulo }})`

---

## Seção dados — Notas (se `nota_geral.por_disciplina`)

**Título:**  
`NOTA POR {{ TURMA | TURMA/GERAL | ESCOLA/GERAL }} – {{ avaliacao.titulo }}`

Estrutura análoga à proficiência; colunas numéricas 0–10; gráfico com três barras principais (LP, Mat, Média Geral) — **sem** barra “Média municipal” no mesmo gráfico de notas (apenas 3 barras no template).

**Parecer opcional:**  
`PARECER TÉCNICO: NOTA (0-10) - {{ avaliacao.titulo }}` se `analise_ia.notas`.

---

## Seção dados — Acertos por habilidade (se `acertos_por_habilidade`)

**Título fixo:** `Acertos por Habilidade`

Para cada disciplina (exceto chave `GERAL` no loop principal):

- Título curso disciplina (`PORTUGUÊS` / `MATEMÁTICA` / nome upper).
- **Grade horizontal:** lotes de 10 questões; linhas: número da questão, código da habilidade, % (verde se ≥ 70%, vermelho se &lt; 70%).
- **Legenda fixa:** `≥ 70%` (verde), `< 70%` (vermelho).
- **Tabela vertical** colunas: `Questão`, `Código`, `Descrição`, `Acertos`, `Total`, `%`, `Classificação`  
  Classificação por faixa de %: ≤50% → **Revisar e Reavaliar**; ≤80% → **Reavaliar**; senão → **Concluído**.

**Parecer opcional por disciplina:**  
`PARECER PEDAGÓGICO: ACERTOS POR HABILIDADE EM {{ disc_nome }} ({{ avaliacao.titulo }})`

**Opcional GERAL:**  
`PARECER PEDAGÓGICO: ACERTOS POR HABILIDADE EM GERAL (TODAS AS DISCIPLINAS) ({{ avaliacao.titulo }})`

---

## Seção final — Conclusão (`.data-section`)

**Título fixo:** `3. CONCLUSÃO E RECOMENDAÇÃO`

**Texto fixo:**

```
Esta seção sintetiza os principais achados do relatório e apresenta recomendações práticas para intervenção pedagógica com base nos resultados observados nas turmas e no consolidado geral.
```

---

## Observações para o frontend

1. **Ordem das chaves em `niveis_aprendizagem`:** no backend recente (cartão-resposta), disciplinas podem vir antes de `GERAL`; no PDF a ordem do objeto importa para a ordem das seções.
2. **Proficiência/Notas:** o layout atual assume **duas colunas nomeadas** LP e Mat; outras disciplinas no payload não ganham coluna extra nesse template.
3. **Paginação:** número de páginas **não** é fixo; depende de quantidade de disciplinas, linhas de tabela, questões e tamanho dos textos de IA.
4. **`report_entity_type`:** não aparece no HTML; use só para escolher API no cliente.

---

*Gerado como mapa de conteúdo alinhado ao template `report_organized.html`.*
