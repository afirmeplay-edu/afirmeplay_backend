# Changelog - Sistema de Cálculos Consistentes

**Data:** 18/03/2026  
**Objetivo:** Garantir que dados calculados (nota, proficiência, classificação) sejam consistentes em todos os lugares do sistema.

## 🎯 Problema Identificado

Anteriormente, os cálculos de nota, proficiência e classificação eram realizados em múltiplos locais:
- Cálculo inicial salvava na tabela `evaluation_results`
- Tabela detalhada por disciplina **recalculava** os dados
- Dados gerais **recalculavam** médias
- Estatísticas agregadas **recalculavam** valores

**Resultado:** Valores podiam divergir devido a:
- Arredondamentos diferentes
- Lógica de classificação inconsistente
- Recálculos com base em dados diferentes

**Exemplo do problema:**
- Cálculo inicial: `2.50`
- Recálculo 1: `2.49`
- Recálculo 2: `2.51`

## ✅ Solução Implementada (SIMPLIFICADA)

### 1. Campo JSON na Tabela Existente

Adicionado campo `subject_results` (JSONB) à tabela `evaluation_results`:
- Armazena resultados por disciplina em formato JSON
- Evita criar nova tabela e manter relacionamentos complexos
- Formato: `{"subject_id": {"grade": 2.5, "proficiency": 250.0, ...}}`

**Migration:** `migrations/versions/20260318_add_subject_results_json_to_evaluation_results.py`

### 2. Função de Arredondamento Padronizada

Criado módulo utilitário para arredondamento consistente:
- `round_to_two_decimals(value)` - ÚNICA função para arredondamento
- Todas as notas, proficiências e percentuais usam 2 casas decimais

**Localização:** `app/utils/decimal_helpers.py`

### 3. Atualização do Serviço de Cálculo

`evaluation_result_service.py` agora:
- Calcula resultados por disciplina
- Salva no campo JSON `subject_results` da tabela `evaluation_results`
- Usa `round_to_two_decimals` em todos os cálculos

**Localização:** `app/services/evaluation_result_service.py`

### 4. Eliminação de Recálculos

#### Tabela Detalhada por Disciplina
- **Antes:** Recalculava nota/proficiência por disciplina
- **Depois:** Busca dados salvos do campo JSON `subject_results`

**Localização:** `app/routes/evaluation_results_routes.py` (linha ~1420)

#### Dados Gerais dos Alunos
- **Antes:** Recalculava médias e classificações
- **Depois:** Usa dados pré-calculados do JSON e apenas calcula média aritmética

**Localização:** `app/routes/evaluation_results_routes.py` (função `_calcular_dados_gerais_alunos`)

#### Estatísticas por Disciplina
- **Antes:** Recalculava para cada aluno
- **Depois:** Busca dados salvos do campo JSON `subject_results`

**Localização:** `app/services/evaluation_result_service.py` (função `get_subject_detailed_statistics`)

### 5. Script de Migração Multi-Tenancy

Criado script para adicionar campo JSON em todos os schemas de cidades:

**Localização:** `scripts/add_subject_results_field_to_all_cities.py`

**Nota:** O sistema usa multi-tenancy com schema por cidade (city_xxx), então não podemos usar migrations do Alembic. O script adiciona o campo `subject_results` em todos os schemas automaticamente.

## 📊 Fluxo Atual

```
1. Aluno responde avaliação
   ↓
2. Sistema calcula (evaluation_result_service.py):
   - Proficiência por disciplina (arredondado 2 casas)
   - Nota por disciplina (arredondado 2 casas)
   - Classificação por disciplina
   ↓
3. Salva em evaluation_results:
   - Campos principais: grade, proficiency, classification
   - Campo JSON subject_results: {subject_id: {grade, proficiency, classification, ...}}
   ↓
4. TODOS os relatórios e análises usam dados salvos
   - Tabela detalhada: busca subject_results do JSON
   - Dados gerais: busca subject_results do JSON + calcula média
   - Estatísticas: busca subject_results do JSON
```

## 🔒 Garantias

1. **Cálculo único:** Feito apenas uma vez no `evaluation_result_service.py`
2. **Arredondamento consistente:** Sempre 2 casas decimais via `round_to_two_decimals`
3. **Dados imutáveis:** Após cálculo, dados não são recalculados
4. **Fonte da verdade:** Tabelas `evaluation_results` e `subject_evaluation_results`

## 📝 Exemplo

Se o cálculo inicial resulta em `2.5`:
- Tabela detalhada mostra: `2.5`
- Dados gerais mostram: `2.5`
- Estatísticas mostram: `2.5`
- Análises mostram: `2.5`

**SEMPRE 2.5 EM TODOS OS LUGARES!**

## 🚀 Como Aplicar

1. Executar script para adicionar campo em todos os schemas:
   ```bash
   python scripts/add_subject_results_field_to_all_cities.py
   ```

2. Recalcular avaliações existentes (opcional):
   ```bash
   # Endpoint: POST /evaluation-results/<test_id>/recalcular-avaliacao
   ```

3. Novos cálculos serão automaticamente salvos no campo JSON

## ⚠️ Notas Importantes

- **Fallback:** Se dados não existirem em `subject_evaluation_results`, sistema recalcula e loga warning
- **Performance:** Índices criados para otimizar consultas
- **Compatibilidade:** Sistema continua funcionando com avaliações antigas

## 📁 Arquivos Modificados

1. **Novos:**
   - `app/utils/decimal_helpers.py` - Função padronizada de arredondamento
   - `scripts/add_subject_results_field_to_all_cities.py` - Script para adicionar campo em todos os schemas
   - `CHANGELOG_CALCULOS_CONSISTENTES.md` - Este arquivo

2. **Modificados:**
   - `app/models/evaluationResult.py` - Adicionado campo `subject_results` (JSONB)
   - `app/services/evaluation_calculator.py` - Usa `round_to_two_decimals`
   - `app/services/evaluation_result_service.py` - Salva resultados por disciplina no JSON
   - `app/routes/evaluation_results_routes.py` - Usa dados salvos ao invés de recalcular

## 🎉 Resultado Final

✅ Dados calculados são consistentes em 100% dos lugares  
✅ Arredondamento padronizado para 2 casas decimais  
✅ Eliminados recálculos desnecessários  
✅ Performance melhorada (menos cálculos)  
✅ Código mais limpo e manutenível  
