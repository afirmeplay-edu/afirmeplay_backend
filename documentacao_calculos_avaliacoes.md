# Documentação dos Cálculos de Avaliações - InnovaPlay

## Visão Geral

Este documento detalha como são realizados os cálculos de notas e proficiência no sistema InnovaPlay, incluindo fórmulas, configurações e exemplos práticos.

## 1. Processo de Cálculo das Respostas

### 1.1 Contagem de Acertos
- O sistema busca todas as respostas do aluno (`StudentAnswer`) para o teste
- Para cada resposta, verifica se está correta comparando com `question.correct_answer`
- **Questões de múltipla escolha**: compara `answer.answer` com `question.correct_answer` (case-insensitive)
- **Outros tipos de questão**: compara diretamente as strings
- Conta o total de acertos (`correct_answers`)

### 1.2 Total de Questões
- Usa o número de questões **respondidas pelo aluno** (`total_answered` do `StudentAnswer`)
- **Importante**: Não usa o total de questões da avaliação, mas sim quantas o aluno efetivamente respondeu

## 2. Cálculo da Proficiência

### 2.1 Fórmula
```
Proficiência = (Acertos / Total de Questões Respondidas) × Proficiência Máxima
```

### 2.2 Proficiências Máximas por Nível e Disciplina

| Nível de Ensino | Matemática | Outras Disciplinas |
|----------------|------------|-------------------|
| Educação Infantil | 375 | 350 |
| Anos Iniciais | 375 | 350 |
| Educação Especial | 375 | 350 |
| EJA | 375 | 350 |
| Anos Finais | 425 | 400 |
| Ensino Médio | 425 | 400 |

### 2.3 Exemplo de Cálculo
- Aluno do 5º ano (Anos Iniciais) em Matemática
- Acertos: 8 de 10 questões respondidas
- Proficiência: (8/10) × 375 = **300**

## 3. Cálculo da Nota

### 3.1 Métodos de Cálculo

O sistema oferece dois métodos:

#### a) Cálculo Simples
```
Nota = (Acertos / Total de Questões) × 10
```

#### b) Cálculo Complexo (baseado na proficiência)
```
Nota = ((Proficiência - Base) / Divisor) × 10
```

### 3.2 Configurações por Nível e Disciplina

| Nível | Disciplina | Base | Divisor |
|-------|------------|------|---------|
| Educação Infantil/Anos Iniciais/EJA | Matemática | 60 | 262 |
| Educação Infantil/Anos Iniciais/EJA | Outras | 49 | 275 |
| Anos Finais/Ensino Médio | Todas | 100 | 300 |

### 3.3 Exemplo de Cálculo
- Aluno do 5º ano (Anos Iniciais) em Matemática
- Proficiência: 300
- Nota: ((300 - 60) / 262) × 10 = **9.16**

## 4. Classificação por Faixas de Proficiência

### 4.1 Outras Disciplinas (Educação Infantil/Anos Iniciais/EJA)
- **Abaixo do Básico**: 0-149
- **Básico**: 150-199
- **Adequado**: 200-249
- **Avançado**: 250-350

### 4.2 Matemática (Educação Infantil/Anos Iniciais/EJA)
- **Abaixo do Básico**: 0-174
- **Básico**: 175-224
- **Adequado**: 225-274
- **Avançado**: 275-375

### 4.3 Outras Disciplinas (Anos Finais/Ensino Médio)
- **Abaixo do Básico**: 0-199
- **Básico**: 200-274.99
- **Adequado**: 275-324.99
- **Avançado**: 325-400

### 4.4 Matemática (Anos Finais/Ensino Médio)
- **Abaixo do Básico**: 0-224.99
- **Básico**: 225-299.99
- **Adequado**: 300-349.99
- **Avançado**: 350-425

### 4.5 Classificação GERAL (Educação Infantil/Anos Iniciais/EJA)
**IMPORTANTE**: Para a classificação geral dos alunos, o sistema usa faixas específicas:
- **Abaixo do Básico**: 0-162
- **Básico**: 163-212
- **Adequado**: 213-262
- **Avançado**: 263-375

### 4.6 Classificação GERAL (Anos Finais/Ensino Médio)
**IMPORTANTE**: Para a classificação geral dos alunos, o sistema usa faixas específicas:
- **Abaixo do Básico**: 0-212.49
- **Básico**: 212.50-289.99
- **Adequado**: 290-339.99
- **Avançado**: 340-425

## 5. Identificação do Nível e Disciplina

### 5.1 Nível do Curso
O sistema analisa o campo `test.course` ou `test.course_name` e identifica palavras-chave:
- "infantil" → Educação Infantil
- "iniciais" → Anos Iniciais
- "finais" → Anos Finais
- "médio" ou "medio" → Ensino Médio
- "eja" → EJA
- "especial" → Educação Especial

### 5.2 Tipo de Disciplina
- Verifica se o nome da disciplina contém "matemática" ou "matematica"
- **Se sim**: trata como Matemática
- **Se não**: trata como Outras Disciplinas

## 6. Mapeamento de Questões para Disciplinas

### 6.1 Questões com Habilidade (Skill)
- Cada questão pode ter um campo `skill` que referencia uma habilidade específica
- A habilidade (`Skill`) possui um `subject_id` que aponta para a disciplina
- Mapeamento: `Question.skill → Skill.subject_id → Subject.name`

### 6.2 Questões sem Habilidade
- Questões sem skill são mapeadas para a disciplina principal da avaliação
- Usa o campo `test.subject_rel.name` (disciplina principal do teste)

## 7. Limitações e Validações

- **Proficiência**: Limitada ao valor máximo da configuração
- **Nota**: Limitada entre 0 e 10
- **Divisão por zero**: Se total de questões = 0, retorna 0
- **Arredondamento**: Todos os valores são arredondados para 2 casas decimais

## 8. Exemplos Práticos Completos

### 8.1 Exemplo 1: Aluno do 5º ano em Matemática
- **Dados**: 8 acertos de 10 questões respondidas
- **Nível**: Anos Iniciais
- **Disciplina**: Matemática
- **Cálculos**:
  - Proficiência: (8/10) × 375 = 300
  - Nota: ((300 - 60) / 262) × 10 = 9.16
  - Classificação: Avançado (300 está entre 275-375)

### 8.2 Exemplo 2: Aluno do 9º ano em Português
- **Dados**: 15 acertos de 20 questões respondidas
- **Nível**: Anos Finais
- **Disciplina**: Outras (Português)
- **Cálculos**:
  - Proficiência: (15/20) × 400 = 300
  - Nota: ((300 - 100) / 300) × 10 = 6.67
  - Classificação por disciplina: Adequado (300 está entre 275-324.99)
  - **Classificação GERAL**: Adequado (300 está entre 290-339.99) - usa faixas específicas

### 8.3 Exemplo 3: Aluno do 3º ano do Ensino Médio em Matemática
- **Dados**: 18 acertos de 25 questões respondidas
- **Nível**: Ensino Médio
- **Disciplina**: Matemática
- **Cálculos**:
  - Proficiência: (18/25) × 425 = 306
  - Nota: ((306 - 100) / 300) × 10 = 6.87
  - Classificação por disciplina: Adequado (306 está entre 300-349.99)
  - **Classificação GERAL**: Adequado (306 está entre 290-339.99) - usa faixas específicas

### 8.4 Exemplo 4: Aluno do 1º Médio com Proficiência 106.25
- **Dados**: Proficiência geral: 106.25
- **Nível**: Ensino Médio
- **Classificação GERAL**: **Abaixo do Básico** (106.25 está entre 0-212.49)
- **Nota**: Esta correção resolve o problema identificado onde alunos com proficiência baixa estavam sendo classificados incorretamente como "Básico"

### 8.5 Exemplo 5: Aluno do 5º ano com Proficiência 200
- **Dados**: Proficiência geral: 200
- **Nível**: Anos Iniciais
- **Classificação GERAL**: **Abaixo do Básico** (200 está entre 0-162) - usa faixas específicas

## 9. Cálculos por Disciplina

### 9.1 Agrupamento
- As respostas dos alunos são agrupadas por disciplina
- Cada disciplina é calculada separadamente

### 9.2 Níveis de Agregação
- **Por Aluno**: Resultado individual por disciplina
- **Por Turma**: Média da turma por disciplina
- **Por Escola**: Média da escola por disciplina
- **Por Município**: Média municipal por disciplina

## 10. Tratamento de Casos Especiais

- **Disciplina Geral**: Questões sem disciplina específica são agrupadas como "Disciplina Geral"
- **Múltiplas Disciplinas**: Uma avaliação pode conter questões de diferentes disciplinas
- **Fallback**: Se não conseguir identificar a disciplina, usa configurações padrão

## 11. Arquivos de Código Relevantes

- **Calculadora Principal**: `app/services/evaluation_calculator.py`
- **Agregador de Estatísticas**: `app/services/evaluation_aggregator.py`
- **Serviço de Resultados**: `app/services/evaluation_result_service.py`
- **Rotas de Relatórios**: `app/routes/report_routes.py`

## 12. Configurações Técnicas

### 12.1 Estrutura de Dados
```python
# Exemplo de resultado calculado
{
    "proficiency": 300.0,
    "grade": 9.16,
    "classification": "Avançado",
    "correct_answers": 8,
    "total_questions": 10,
    "accuracy_rate": 80.0
}
```

### 12.2 Validações de Entrada
- `correct_answers`: deve ser inteiro >= 0
- `total_questions`: deve ser inteiro > 0
- `course_name`: string não vazia
- `subject_name`: string não vazia

---

**Data de Criação**: 2024
**Versão**: 1.0
**Sistema**: InnovaPlay Backend
