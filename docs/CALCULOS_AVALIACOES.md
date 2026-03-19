# 📊 Documentação: Cálculos de Avaliações

## Visão Geral

Este documento explica como funcionam os cálculos de notas, proficiências e classificações no sistema de avaliações, e como esses dados devem se comportar em todo o sistema.

## Princípio Fundamental: "Calcular Uma Vez, Usar Sempre"

**REGRA DE OURO**: Uma vez que um valor é calculado e salvo no banco de dados, ele **NUNCA** deve ser recalculado. O mesmo valor deve ser retornado em todos os lugares do sistema.

### Exemplo:
- Se um aluno tirou nota `7.35` em Matemática, esse valor deve aparecer como `7.35` em:
  - Listagem de resultados (`/evaluation-results/avaliacoes`)
  - Relatórios por município (`/reports/dados-json`)
  - Relatórios por escola
  - Análises estatísticas
  - Exportações CSV/PDF
  - **TODOS OS LUGARES**

## Estrutura de Dados

### 1. Tabela `evaluation_results`

Cada registro representa o resultado de **um aluno** em **uma avaliação**.

#### Campos Principais:

```sql
CREATE TABLE evaluation_results (
    id VARCHAR PRIMARY KEY,
    test_id VARCHAR NOT NULL,
    student_id VARCHAR NOT NULL,
    
    -- Dados gerais (média de todas as disciplinas)
    grade DECIMAL(5,2),              -- Nota geral (0-10)
    proficiency DECIMAL(5,2),        -- Proficiência geral (0-100)
    classification VARCHAR,          -- Classificação geral (ex: "Básico")
    accuracy_rate DECIMAL(5,2),      -- Taxa de acerto geral (%)
    
    -- Dados por disciplina (JSONB)
    subject_results JSONB,           -- Resultados específicos de cada disciplina
    
    -- Metadados
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

#### Estrutura do campo `subject_results` (JSONB):

```json
{
  "Matemática": {
    "grade": 5.50,
    "proficiency": 45.00,
    "classification": "Abaixo do Básico",
    "answered_questions": 10
  },
  "Português": {
    "grade": 9.20,
    "proficiency": 85.00,
    "classification": "Avançado",
    "answered_questions": 10
  }
}
```

## Fluxo de Cálculo

### 1. Quando o Aluno Finaliza a Avaliação

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. Aluno submete respostas                                      │
│    → Salvas na tabela student_answers                           │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ 2. EvaluationResultService.calculate_and_save_result()          │
│    → Calcula nota, proficiência e classificação                 │
│    → Para cada disciplina E para o geral                        │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ 3. Salva no banco de dados (evaluation_results)                 │
│    → grade, proficiency, classification (geral)                 │
│    → subject_results (JSONB com dados por disciplina)           │
└─────────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────────┐
│ 4. Dados prontos para uso                                       │
│    → Todas as rotas devem LER esses dados                       │
│    → NUNCA recalcular                                           │
└─────────────────────────────────────────────────────────────────┘
```

### 2. Fórmulas de Cálculo

Implementadas em `app/services/evaluation_calculator.py`:

#### a) Proficiência

```python
proficiency = (correct_answers / total_questions) * 100
```

**Exemplo**: 8 acertos em 10 questões = `(8/10) * 100 = 80.00%`

#### b) Nota (Grade)

```python
grade = (proficiency / 100) * 10
```

**Exemplo**: Proficiência de 80% = `(80/100) * 10 = 8.00`

#### c) Classificação

Baseada na proficiência, varia por curso e disciplina:

| Proficiência | Classificação        |
|--------------|----------------------|
| 0-24%        | Abaixo do Básico     |
| 25-49%       | Básico               |
| 50-74%       | Adequado             |
| 75-100%      | Avançado             |

**Nota**: Os intervalos podem variar dependendo do curso e disciplina (configurado no `EvaluationCalculator`).

### 3. Arredondamento Padronizado

**SEMPRE** usar a função `round_to_two_decimals()` de `app/utils/decimal_helpers.py`:

```python
from app.utils.decimal_helpers import round_to_two_decimals

nota = round_to_two_decimals(7.567)  # Retorna: 7.57
proficiencia = round_to_two_decimals(82.3)  # Retorna: 82.30
```

**Regra**: Todos os valores numéricos (nota, proficiência, taxa de acerto) devem ter **exatamente 2 casas decimais**.

## Uso dos Dados Calculados

### ✅ CORRETO: Ler do Banco de Dados

```python
# Buscar resultado salvo
resultado = EvaluationResult.query.get(result_id)

# Usar valores salvos
nota_geral = resultado.grade
proficiencia_geral = resultado.proficiency
classificacao_geral = resultado.classification

# Usar valores por disciplina
if resultado.subject_results:
    matematica = resultado.subject_results.get('Matemática', {})
    nota_matematica = matematica.get('grade')
    classificacao_matematica = matematica.get('classification')
```

### ❌ ERRADO: Recalcular

```python
# NÃO FAZER ISSO!
nota_recalculada = (acertos / total_questoes) * 10
```

## Rotas e Suas Responsabilidades

### 1. `/evaluation-results/avaliacoes` (Listagem)

**Arquivo**: `app/routes/evaluation_results_routes.py`

**Responsabilidade**: Retornar lista de resultados de avaliações

**Comportamento**:
- Busca `EvaluationResult` do banco
- Extrai `subject_results` (JSONB)
- Retorna dados **sem recalcular**

### 2. `/reports/dados-json/<evaluation_id>` (Relatório Analítico)

**Arquivo**: `app/report_analysis/routes.py` → chama → `app/routes/report_routes.py`

**Responsabilidade**: Gerar relatório agregado por escola/município

**Comportamento**:
- Busca todos os `EvaluationResult` da avaliação
- Agrupa por escola/turma
- Para estatísticas **por disciplina**, deve usar `subject_results[disciplina]['classification']`
- Para estatísticas **gerais**, deve usar `classification` (campo direto)

### 3. Funções de Agregação

#### a) `_calcular_niveis_aprendizagem_por_municipio()`

**Localização**: `app/routes/report_routes.py` (linha ~3552)

**Propósito**: Agregar classificações por escola e disciplina para relatórios municipais

**Como deve funcionar**:

```python
# 1. Criar mapeamento nome -> UUID
disciplina_nome_para_uuid = {}
for question in test.questions:
    if question.subject_id:
        subject = Subject.query.get(question.subject_id)
        if subject:
            disciplina_nome_para_uuid[subject.name] = str(subject.id)

# 2. Usar UUID para buscar em subject_results
for disciplina in ['Matemática', 'Português', ...]:
    subject_uuid = disciplina_nome_para_uuid.get(disciplina)
    for escola in escolas:
        for resultado in resultados_da_escola:
            # ✅ CORRETO: Buscar usando UUID da disciplina
            subject_data = resultado.subject_results.get(subject_uuid)
            if subject_data:
                classificacao = subject_data['classification']
            
            # ❌ ERRADO: Buscar usando nome da disciplina
            # subject_data = resultado.subject_results.get(disciplina)
            
            # ❌ ERRADO: Usar classificação geral
            # classificacao = resultado.classification
```

#### b) `_calcular_estatisticas_consolidadas_por_escopo()`

**Localização**: `app/routes/evaluation_results_routes.py` (linha ~6396)

**Propósito**: Calcular estatísticas gerais consolidadas

**Como deve funcionar**:

```python
for resultado in resultados:
    classificacao = resultado.classification.lower()  # ✅ Usa classificação GERAL
    
    # Ordem de verificação: mais específico primeiro
    if 'abaixo' in classificacao:
        distribuicao['abaixo_do_basico'] += 1
    elif 'básico' in classificacao or 'basico' in classificacao:
        distribuicao['basico'] += 1
    elif 'adequado' in classificacao:
        distribuicao['adequado'] += 1
    elif 'avançado' in classificacao or 'avancado' in classificacao:
        distribuicao['avancado'] += 1
```

**⚠️ ATENÇÃO**: A ordem dos `if/elif` é crítica! Verificar "abaixo" ANTES de "básico" evita que "Básico" seja incorretamente contado como "Abaixo do Básico".

## Erros Comuns e Como Evitar

### Erro 1: Usar Classificação Geral para Disciplinas Específicas

**Problema**:
```python
# ❌ ERRADO
for disciplina in disciplinas:
    classificacao = resultado.classification  # Classificação GERAL
```

**Solução**:
```python
# ✅ CORRETO
for disciplina in disciplinas:
    classificacao = resultado.subject_results[disciplina]['classification']
```

### Erro 2: Ordem Incorreta de Verificação de Strings

**Problema**:
```python
# ❌ ERRADO: "Básico" contém "básico", então será contado em ambos
if 'abaixo' in classificacao or 'básico' in classificacao:
    abaixo_do_basico += 1
elif 'básico' in classificacao:
    basico += 1
```

**Solução**:
```python
# ✅ CORRETO: Verificar mais específico primeiro
if 'abaixo' in classificacao:
    abaixo_do_basico += 1
elif 'básico' in classificacao or 'basico' in classificacao:
    basico += 1
```

### Erro 3: Recalcular ao Invés de Ler

**Problema**:
```python
# ❌ ERRADO
proficiencia = (acertos / total) * 100
nota = (proficiencia / 100) * 10
```

**Solução**:
```python
# ✅ CORRETO
proficiencia = resultado.proficiency
nota = resultado.grade
```

### Erro 4: Duplicação de Contagem

**Problema**: Contar o mesmo aluno múltiplas vezes devido a lógica `or` incorreta

**Exemplo do Bug**:
```python
# Se classificacao = "Básico"
if 'abaixo' in classificacao or 'básico' in classificacao:  # True! ('básico' in 'Básico')
    abaixo_do_basico += 1  # ❌ Conta aqui
elif 'básico' in classificacao:  # True também!
    basico += 1  # ❌ E conta aqui também! (duplicação)
```

**Solução**: Usar `if/elif` correto e verificar mais específico primeiro.

## Checklist de Implementação

Ao trabalhar com cálculos de avaliações, sempre verificar:

- [ ] Estou lendo `subject_results` para dados por disciplina?
- [ ] Estou usando `classification` (geral) apenas para estatísticas gerais?
- [ ] Estou usando `round_to_two_decimals()` para arredondamento?
- [ ] A ordem dos `if/elif` está correta (mais específico primeiro)?
- [ ] Não estou recalculando valores que já existem no banco?
- [ ] Estou usando o campo correto (geral vs. disciplina específica)?

## Arquivos Importantes

### Cálculo e Salvamento:
- `app/services/evaluation_calculator.py` - Fórmulas de cálculo
- `app/services/evaluation_result_service.py` - Salva resultados no banco
- `app/utils/decimal_helpers.py` - Funções de arredondamento

### Exibição e Agregação:
- `app/routes/evaluation_results_routes.py` - Listagem de resultados
- `app/routes/report_routes.py` - Relatórios agregados
- `app/report_analysis/tasks.py` - Processamento assíncrono de relatórios

### Modelos:
- `app/models/evaluationResult.py` - Modelo da tabela `evaluation_results`

## Exemplo Completo: Aluno com Múltiplas Disciplinas

### Dados Salvos no Banco:

```json
{
  "id": "abc123",
  "test_id": "avaliacao-001",
  "student_id": "aluno-001",
  
  "grade": 7.35,
  "proficiency": 73.50,
  "classification": "Adequado",
  "accuracy_rate": 73.50,
  
  "subject_results": {
    "Matemática": {
      "grade": 5.50,
      "proficiency": 55.00,
      "classification": "Adequado",
      "answered_questions": 10
    },
    "Português": {
      "grade": 9.20,
      "proficiency": 92.00,
      "classification": "Avançado",
      "answered_questions": 10
    }
  }
}
```

### Como Usar em Relatórios:

#### Relatório Geral (todas as disciplinas juntas):
```python
classificacao_geral = resultado.classification  # "Adequado"
```

#### Relatório por Disciplina (Matemática):
```python
matematica = resultado.subject_results['Matemática']
classificacao_matematica = matematica['classification']  # "Adequado"
nota_matematica = matematica['grade']  # 5.50
```

#### Relatório por Disciplina (Português):
```python
portugues = resultado.subject_results['Português']
classificacao_portugues = portugues['classification']  # "Avançado"
nota_portugues = portugues['grade']  # 9.20
```

## Agregação de Estatísticas

### Estatísticas Gerais (Todas as Disciplinas)

**Função**: `_calcular_estatisticas_consolidadas_por_escopo()`

**Usa**: `resultado.classification` (campo direto)

**Exemplo**:
```python
distribuicao = {
    'abaixo_do_basico': 0,
    'basico': 0,
    'adequado': 0,
    'avancado': 0
}

for resultado in resultados:
    classificacao = resultado.classification.lower()
    
    if 'abaixo' in classificacao:
        distribuicao['abaixo_do_basico'] += 1
    elif 'básico' in classificacao or 'basico' in classificacao:
        distribuicao['basico'] += 1
    elif 'adequado' in classificacao:
        distribuicao['adequado'] += 1
    elif 'avançado' in classificacao or 'avancado' in classificacao:
        distribuicao['avancado'] += 1
```

### Estatísticas por Disciplina

**Função**: `_calcular_niveis_aprendizagem_por_municipio()`

**Usa**: `resultado.subject_results[disciplina]['classification']`

**Exemplo**:
```python
for disciplina in ['Matemática', 'Português']:
    distribuicao = {
        'abaixo_do_basico': 0,
        'basico': 0,
        'adequado': 0,
        'avancado': 0
    }
    
    for resultado in resultados:
        # ✅ CORRETO: Buscar classificação específica da disciplina
        if resultado.subject_results and disciplina in resultado.subject_results:
            subject_data = resultado.subject_results[disciplina]
            classificacao = subject_data['classification'].lower()
            
            if 'abaixo' in classificacao:
                distribuicao['abaixo_do_basico'] += 1
            elif 'básico' in classificacao or 'basico' in classificacao:
                distribuicao['basico'] += 1
            elif 'adequado' in classificacao:
                distribuicao['adequado'] += 1
            elif 'avançado' in classificacao or 'avancado' in classificacao:
                distribuicao['avancado'] += 1
```

## Recalculação de Resultados

### Quando Recalcular?

Recalcular **APENAS** quando:
1. O gabarito da avaliação foi alterado
2. Questões foram adicionadas/removidas
3. Houve erro no cálculo original
4. Administrador solicita explicitamente

### Como Recalcular?

**Endpoint**: `POST /evaluation-results/result/<result_id>/recalculate`

**Parâmetros**:
```json
{
  "city_id": "0f93f076-c274-4515-98df-302bbf7e9b15"
}
```

**O que faz**:
1. Busca o `EvaluationResult` existente
2. Recalcula todos os valores (geral + por disciplina)
3. **Sobrescreve** os valores no banco
4. Retorna os novos valores

## Multi-Tenancy (Schemas por Cidade)

### Estrutura:
```
Database: innovaplay
├── Schema: city_0f93f076-c274-4515-98df-302bbf7e9b15
│   ├── evaluation_results
│   ├── students
│   └── ...
├── Schema: city_abc123...
│   ├── evaluation_results
│   └── ...
└── Schema: public (compartilhado)
    ├── cities
    ├── users
    └── ...
```

### Importante:
- Sempre definir `search_path` antes de queries: `set_search_path(city_id_to_schema_name(city_id))`
- Passar `city_id` em todas as operações que envolvem dados de avaliação

## Debugging

### Script de Debug:

```bash
python debug_evaluation.py
```

**O que mostra**:
- Dados gerais do `EvaluationResult`
- Dados por disciplina do `subject_results` (JSONB)
- Permite verificar se os valores salvos estão corretos

### Comparação de Rotas:

```bash
python test_statistics.py
```

**O que faz**:
- Compara `/evaluation-results/avaliacoes` com `/reports/dados-json`
- Mostra divergências de classificação
- Útil para identificar bugs de agregação

## Histórico de Correções

### Correção 1: Lógica de Classificação Geral (18/03/2026)
**Problema**: "Básico" sendo contado como "Abaixo do Básico"
**Causa**: Condição `if 'abaixo' in classificacao or 'básico' in classificacao:`
**Solução**: Separar verificações e verificar "abaixo" primeiro

### Correção 2: Classificação por Disciplina em Relatórios (18/03/2026)
**Problema**: Relatório municipal usando classificação geral para todas as disciplinas
**Causa**: `_calcular_niveis_aprendizagem_por_municipio()` usava `r.classification` ao invés de `r.subject_results[disciplina]['classification']`
**Solução**: Modificar para buscar classificação específica do JSONB `subject_results`

### Correção 3: Mapeamento Nome → UUID da Disciplina (18/03/2026)
**Problema**: Código retornando zeros para todas as classificações por disciplina
**Causa**: O `subject_results` é salvo com **UUID da disciplina como chave**, mas o código estava buscando usando **nome da disciplina**
**Exemplo do problema**:
```python
# Salvo no banco:
{
  "44f3421e-ca84-4fe5-a449-a3d9bfa3db3d": {  // ← UUID
    "subject_name": "Matemática",
    "classification": "Abaixo do Básico"
  }
}

# Código tentava buscar:
subject_data = r.subject_results.get("Matemática")  // ← Nome (ERRADO!)
```
**Solução**: Criar mapeamento `disciplina_nome_para_uuid` e usar UUID para buscar em `subject_results`

## Manutenção

### Ao Adicionar Nova Funcionalidade:

1. **Sempre ler do banco**, nunca recalcular
2. **Usar `subject_results`** para dados por disciplina
3. **Usar campos diretos** (`grade`, `proficiency`, `classification`) para dados gerais
4. **Aplicar `round_to_two_decimals()`** se precisar fazer alguma média/agregação
5. **Testar com `debug_evaluation.py`** para verificar dados salvos
6. **Comparar com `test_statistics.py`** para verificar consistência entre rotas

### Ao Corrigir Bugs:

1. Identificar se o problema é no **cálculo** ou na **agregação**
2. Verificar se está usando o campo correto (geral vs. disciplina)
3. Verificar ordem dos `if/elif` para evitar duplicação
4. Testar com dados reais usando os scripts de debug

---

**Última atualização**: 18/03/2026
**Versão**: 2.0
