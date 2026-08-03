# Fonte da verdade: nota, proficiência, médias e classificações

Este arquivo é o **ponto de consulta** para auditar se um valor exibido no sistema (nota, proficiência, classificação, médias agregadas) está **coerente com as regras implementadas no código**.

**Autoridade absoluta:** `app/services/evaluation_calculator.py` (`EvaluationCalculator`).  
Se este documento divergir do código, **prevalece o código**.

**Outros arquivos no repositório** (`documentacao_calculos_avaliacoes.md`, `docs/CALCULOS_AVALIACOES.md`, etc.) podem estar desatualizados ou usar exemplos simplificados — use este documento + o código para validação.

---

## 1. Proficiência (valor numérico por aluno / por disciplina)

### 1.1 Fórmula base

Implementação: `EvaluationCalculator.calculate_proficiency`.

```
proficiência = (acertos / total_de_questões) × proficiência_máxima
```

- `total_de_questões`: questões **consideradas no cálculo** (na avaliação online costuma ser o respondido; no cartão, por bloco/disciplina conforme o fluxo).
- Resultado limitado ao máximo da célula `(nível_do_curso, tipo_disciplina)` e arredondado (2 casas) conforme o serviço.

### 1.2 Proficiência máxima (`MAX_PROFICIENCY_CONFIG`)

| Nível do curso (`course_name` inferido) | Matemática | Outras |
|----------------------------------------|------------|--------|
| Educação Infantil, Anos Iniciais, Educação Especial, EJA | 375 | 350 |
| Anos Finais, Ensino Médio | 425 | 400 |

Detecção do nível: `EvaluationCalculator._determine_course_level` (palavras-chave em `course_name`: infantil, iniciais, finais, médio, eja, especial, etc.). Padrão se não reconhecer: **Anos Iniciais**.

### 1.3 Exemplo auditável

- Curso: Anos Iniciais, disciplina **Outras**, máximo **350**.
- 8 acertos em 10 questões válidas:  
  `proficiência = (8/10) × 350 = 280` → classificação por faixa de **Outras / Anos Iniciais** (ver §3).

---

## 2. Nota (0 a 10)

### 2.1 Cálculo “simples” (`use_simple_calculation=True`)

```
nota = (acertos / total_questões) × 10
```

### 2.2 Cálculo “complexo” (a partir da proficiência)

```
nota = ((proficiência - base) / divisor) × 10
```

`base` e `divisor` vêm de `GRADE_CALCULATION_CONFIG` em `evaluation_calculator.py` (tabela completa no próprio arquivo). Exemplos:

| Nível | Disciplina | base | divisor |
|-------|------------|------|---------|
| Anos Iniciais / EI / Especial / EJA | Outras | 49 | 275 |
| Anos Iniciais / EI / Especial / EJA | Matemática | 60 | 262 |
| Anos Finais / Ensino Médio | Todas (na config) | 100 | 300 |

Nota final limitada entre **0** e **10** (e arredondada conforme utilitário do projeto).

---

## 3. Classificação textual (Abaixo do Básico, Básico, Adequado, Avançado)

### 3.1 Função central

`EvaluationCalculator.determine_classification(proficiency, course_name, subject_name, has_matematica=None)`

- Percorre faixas `(min, max, classificação)` **inclusivas** (`min <= proficiência <= max`).
- Se nenhuma faixa casar, retorna **"Abaixo do Básico"**.

### 3.2 Por disciplina nomeada (ex.: "Matemática", "Língua Portuguesa")

Usa `CLASSIFICATION_CONFIG` com `(CourseLevel, MATEMATICA | OUTRAS)` conforme o nome da disciplina (`matemática`/`matematica` → Matemática).

Faixas **exatas** estão no dicionário `CLASSIFICATION_CONFIG` no arquivo Python (trechos resumidos abaixo — **validar sempre no código**).

**Outras disciplinas — Anos Iniciais / EI / Especial / EJA**

| Proficiência | Classificação |
|--------------|----------------|
| 0 – 149 | Abaixo do Básico |
| 150 – 199 | Básico |
| 200 – 249 | Adequado |
| 250 – 350 | Avançado |

**Matemática — mesmo grupo de cursos**

| Proficiência | Classificação |
|--------------|----------------|
| 0 – 174 | Abaixo do Básico |
| 175 – 224 | Básico |
| 225 – 274 | Adequado |
| 275 – 375 | Avançado |

**Outras — Anos Finais / Ensino Médio**

| Proficiência | Classificação |
|--------------|----------------|
| 0 – 199 | Abaixo do Básico |
| 200 – 274,99 | Básico |
| 275 – 324,99 | Adequado |
| 325 – 400 | Avançado |

**Matemática — Anos Finais / Ensino Médio**

| Proficiência | Classificação |
|--------------|----------------|
| 0 – 224,99 | Abaixo do Básico |
| 225 – 299,99 | Básico |
| 300 – 349,99 | Adequado |
| 350 – 425 | Avançado |

### 3.3 Classificação **GERAL** (`subject_name == "GERAL"`)

Usada na média geral do aluno, no **nível de classificação agregado** (`nivel_classificacao` nas respostas JSON do cartão) e onde o código passa `"GERAL"`.

1. **`has_matematica` informado (`True` ou `False`)**  
   Usa as **mesmas faixas** de `CLASSIFICATION_CONFIG` para `(course_level, MATEMATICA)` ou `(course_level, OUTRAS)`, conforme `has_matematica`.  
   No cartão, `has_matematica` costuma vir dos blocos do gabarito (ex.: `infer_has_matematica_from_blocks_config` / `course_name_and_has_matematica_for_gabarito` em `proficiency_by_subject.py`).

2. **`has_matematica is None` (legado)**  
   Faixas **fixas alternativas** dentro de `determine_classification` (Anos Finais/Médio vs demais) — ver linhas do `if subject_name.upper() == "GERAL"` e `else` em `evaluation_calculator.py`.

### 3.4 Exemplo auditável (escola ou aluno com média 197)

- Se a regra aplicável for **Anos Iniciais + Outras** (GERAL com `has_matematica=False`): faixa **150 – 199** → **Básico**.
- Proficiência **197** está nesse intervalo → classificação **"Básico"** está correta segundo `CLASSIFICATION_CONFIG`.

---

## 4. Onde os valores são persistidos e agregados

### 4.1 Avaliação online (prova digital)

| Conceito | Tabela / campo | Observação |
|----------|----------------|------------|
| Resultado por aluno | `evaluation_results`: `grade`, `proficiency`, `classification` | Geral |
| Por disciplina | `evaluation_results.subject_results` (JSON) | `grade`, `proficiency`, `classification` por chave de disciplina |

Agregações (município, escola, distribuição): leitura desses campos em `evaluation_results_routes.py` e serviços — **contagem de classificação** costuma usar o texto de `classification` por aluno (regras de substring documentadas nas rotas).

### 4.2 Cartão-resposta (OMR)

| Conceito | Tabela / campo |
|----------|----------------|
| Resultado por aluno | `answer_sheet_results`: `grade`, `proficiency`, `classification`, `proficiency_by_subject` (JSON) |
| Colocação histórica | `school_id_snapshot` / `class_id_snapshot` / `grade_id_snapshot` (igual `evaluation_results`) |

- **Média geral do aluno** na tabela detalhada: média das notas/proficiências por disciplina conforme `_calcular_dados_gerais_alunos_cartao` em `answer_sheet_routes.py`.
- **Estatísticas gerais / por escola / por disciplina**: médias e distribuições a partir dos registros deduplicados por aluno (`_dedupe_answer_sheet_results_latest_per_student`), com roster = alunos atuais **∪** snapshots (`app/services/answer_sheet_result_snapshot.py`).

### 4.3 Nível de classificação (cartão, lista municipal)

Em `answer-sheets/opcoes-filtros-results` e agregações correlatas, campo **`nivel_classificacao`**:

1. Média aritmética das proficiências dos **participantes** da escola (mesmo escopo de turmas do gabarito).
2. `EvaluationCalculator.determine_classification(média, course_name_do_gabarito, "GERAL", has_matematica=...)`.

Ou seja: para auditar, use a **média** exibida (`media_proficiencia`) + curso + `has_matematica` e compare com a tabela do §3.3.

### 4.4 Município (consolidado)

- **Médias** (`media_nota_geral`, `media_proficiencia_geral`): agregação hierárquica via `hierarchical_mean_grade_and_proficiency` — a proficiência é a média hierárquica; a **nota geral** é `calculate_grade(média_proficiência)`, não a média das notas dos alunos.
- **Distribuição** (`distribuicao_classificacao_geral`): contagem de alunos em cada faixa usando o campo `classification` de cada resultado (regra por substring no código), alinhada ao evaluation quando aplicável.

---

## 5. Checklist rápido de auditoria

1. Identificar **fonte**: avaliação online (`evaluation_results`) ou cartão (`answer_sheet_results`).
2. Confirmar **curso** (`course_name` / série do teste ou `grade_name` do gabarito) e se a classificação é **por disciplina** ou **GERAL** (`has_matematica` se for GERAL no cartão).
3. Ler **proficiência** (ou média) numérica usada na tela.
4. Abrir `CLASSIFICATION_CONFIG` + ramo **GERAL** em `determine_classification` e localizar o intervalo que contém o valor.
5. Comparar com o rótulo exibido (**Abaixo do Básico**, **Básico**, **Adequado**, **Avançado**).

---

## 6. Referências de código (atualizar se renomear arquivos)

| Tema | Arquivo |
|------|---------|
| Fórmulas e faixas | `app/services/evaluation_calculator.py` |
| Cartão: por disciplina / curso do gabarito | `app/services/cartao_resposta/proficiency_by_subject.py`, `course_name_resolver.py` |
| Rotas agregadas cartão | `app/routes/answer_sheet_routes.py` |
| Rotas agregadas avaliação online | `app/routes/evaluation_results_routes.py`, `app/services/evaluation_result_service.py` |
| Médias hierárquicas (peso igual) | `app/utils/school_equal_weight_means.py` |
| Ranking (auditar conformidade) | `app/services/ranking_report_service.py`, `app/services/dashboard_service.py` |

---

## 7. REGRA OBRIGATÓRIA — médias agregadas (nota e proficiência)

### 7.1 Proibido

**NÃO EXISTE média ponderada neste sistema.**

Proibido em qualquer endpoint, serviço, ranking, dashboard ou relatório:

- ponderar médias pelo número de alunos (`sum(media × n) / sum(n)`);
- usar `SQL AVG(grade)` / `SQL AVG(proficiency)` agrupado acima do nível **turma** para representar escola, série ou município;
- implementar “média geral dos alunos” quando o nível de exibição for escola ou superior.

### 7.2 Obrigatório — média hierárquica com peso igual + nota via proficiência

Implementação canônica: `app/utils/school_equal_weight_means.py` → `hierarchical_mean_grade_and_proficiency(results, target_level, course_name=...)`.

| Nível exibido | Regra da **proficiência** |
|---------------|---------------------------|
| Turma | Média aritmética das proficiências dos alunos da turma |
| Série | Média das médias das turmas (peso igual por turma) |
| Escola | Média das médias das séries (peso igual por série) |
| Município | Média das médias das escolas (peso igual por escola) |

**Nota agregada (canônico):** `media_nota = calculate_grade(media_proficiencia_agregada)` (`aggregated_grade_from_proficiency`).  
**Não** usar a média das notas individuais dos alunos (clipping em 0 distorce a média das notas vs. a nota da média de proficiência).

Nota do **aluno** continua sendo `calculate_grade(proficiência_do_aluno)` na correção.

**Referência correta:** `GET /evaluation-results/avaliacoes` — `_calcular_estatisticas_grupo` + `hierarchical_mean_grade_and_proficiency`.

**Exemplo auditável (Pedro Ribeiro, 3 turmas na mesma série):**

| Turma | Alunos | Proficiência média (turma) |
|-------|--------|----------------------------|
| A | 6 | … |
| B | 5 | … |
| C | 19 | … |

- ❌ Média ponderada / `AVG` de todos os alunos
- ✅ Média hierárquica da **proficiência** (escola = média das 3 turmas), depois `calculate_grade` uma vez

Rotas de ranking devem usar a mesma regra (agregar proficiência → derivar nota; ver `RankingReportService` + `aggregated_grade_from_proficiency`).

---

## 8. REGRA OBRIGATÓRIA — participação / comparecimento

### 8.1 Fórmula canônica

```
percentual_participacao = round(100 * avaliados / matriculados, 2)
```

(se `matriculados == 0` → `0` ou nulo conforme o endpoint)

| Conceito | Significado |
|----------|-------------|
| **Matriculados** | Universo previsto no escopo (turmas da aplicação / destinatários / ClassTest ∪ snapshots, conforme o domínio) |
| **Avaliados / participantes** | Quem tem resultado oficial no escopo (`EvaluationResult` ou `AnswerSheetResult`; no socioeconômico: quem respondeu) |

### 8.2 Proibido para participação

- Média das taxas de participação das escolas ou séries (peso igual) como “participação geral”
- Qualquer consolidação que faça média de percentuais de unidades em vez de `soma(avaliados) / soma(matriculados)`

Isso **não** conflita com §7: média hierárquica vale para **nota e proficiência**; participação é **contagem / ratio**.

### 8.3 Referências corretas

| Domínio | Onde |
|---------|------|
| Avaliação online | `evaluation_results_routes` → `percentual_comparecimento` |
| Cartão (KPI / agregados) | `answer_sheet_routes` → `_calcular_estatisticas_consolidadas_cartao` |
| Relatório de participação | `app/participation_report/` |
| Socioeconômico INSE | `inse_saeb_service` → `porcentagem_participacao` |
| Consolidado (frequência) | `consolidated_report_service._build_participation_matriz` |

### 8.4 Exemplo (mesmo gabarito, 4 escolas)

| Escola | Matriculados | Avaliados | Taxa da escola |
|--------|--------------|-----------|----------------|
| A | 51 | 44 | 86,27% |
| B | 10 | 9 | 90,00% |
| C | 18 | 16 | 88,89% |
| D | 17 | 14 | 82,35% |
| **Total** | **96** | **83** | |

- ✅ Canônico: `83/96 = 86,46%`
- ❌ Errado (média das taxas): `(86,27+90+88,89+82,35)/4 = 86,88%`

---

*Última revisão: §8 — participação canônica = ratio avaliados/matriculados; §7 permanece para nota/proficiência.*
