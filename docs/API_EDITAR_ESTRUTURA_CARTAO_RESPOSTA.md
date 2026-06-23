# API: Editar Estrutura do Cartão Resposta

## Endpoint

```
PATCH /answer-sheets/gabarito/{gabarito_id}/structure
```

## Descrição

Permite editar a estrutura do cartão resposta: quantidade de questões, configuração de blocos e habilidades por questão.

## Regras de Negócio

### ❌ Bloqueio de Edição

**Não é possível editar** se o cartão já possui correções registradas.

**Response (422 Unprocessable Entity):**
```json
{
  "error": "Este cartão resposta não pode ser editado porque já existem correções registradas. Editar agora poderia causar inconsistências nos resultados já calculados. Para fazer alterações, crie um novo cartão resposta.",
  "reason": "has_corrections",
  "corrections_count": 15
}
```

### ✅ Edição com Aviso

**É possível editar** se o cartão foi gerado mas não corrigido. O sistema retorna um aviso de que os PDFs devem ser regenerados.

**Response (200 OK):**
```json
{
  "success": true,
  "gabarito_id": "uuid-do-gabarito",
  "message": "Estrutura do cartão resposta atualizada com sucesso",
  "warning": "Atenção: os cartões em PDF já gerados não refletem as alterações. É necessário gerar os cartões novamente para que as mudanças apareçam nos documentos impressos.",
  "changes": {
    "num_questions": {
      "old": 20,
      "new": 30
    },
    "blocks_count": {
      "old": 2,
      "new": 3
    },
    "skills_updated": true
  }
}
```

### ✅ Edição Livre

**É possível editar** sem avisos se o cartão foi apenas criado mas nunca gerado.

**Response (200 OK):**
```json
{
  "success": true,
  "gabarito_id": "uuid-do-gabarito",
  "message": "Estrutura do cartão resposta atualizada com sucesso",
  "changes": {
    "num_questions": {
      "old": 20,
      "new": 30
    }
  }
}
```

## Request

### Headers

```
Authorization: Bearer {jwt_token}
Content-Type: application/json
X-City-Context: {city_id}
```

### Permissões

Requer role: `admin`, `professor`, `coordenador`, `diretor` ou `tecadm`

### Body (JSON)

**Todos os campos são opcionais.** Envie apenas os campos que deseja alterar.

```json
{
  "num_questions": 30,
  "blocks_config": {
    "blocks": [
      {
        "block_id": 1,
        "subject_id": "uuid-da-disciplina",
        "subject_name": "Matemática",
        "start_question": 1,
        "end_question": 15,
        "questions_count": 15
      },
      {
        "block_id": 2,
        "subject_id": "uuid-da-disciplina-2",
        "subject_name": "Português",
        "start_question": 16,
        "end_question": 30,
        "questions_count": 15
      }
    ]
  },
  "question_skills": {
    "1": ["EF05MA01", "uuid-habilidade"],
    "2": ["EF05LP02"],
    "3": ["uuid-habilidade-3"]
  },
  "questions_options": {
    "1": ["A", "B", "C", "D"],
    "2": ["A", "B", "C"]
  }
}
```

### Campos do Body

#### `num_questions` (integer, opcional)
- Nova quantidade de questões do cartão
- Mínimo: 1
- Máximo: 104
- Se alterado, as respostas corretas (`correct_answers`) são ajustadas automaticamente:
  - Questões removidas: descartadas
  - Questões novas: recebem valor padrão "A"

#### `blocks_config` (object, opcional)
- Nova configuração de blocos do cartão
- **Validações:**
  - Máximo de 4 blocos
  - Cada bloco deve ter `subject_id` (obrigatório)
  - Máximo de 26 questões por bloco
  - A soma das questões dos blocos deve ser igual a `num_questions`
  - As questões devem ser sequenciais (1, 2, 3...)

##### Estrutura de `blocks_config.blocks[]`:
```json
{
  "block_id": 1,                        // ID do bloco (1-4)
  "subject_id": "uuid-da-disciplina",   // UUID da disciplina (obrigatório)
  "subject_name": "Matemática",         // Nome da disciplina (opcional, será resolvido do banco)
  "start_question": 1,                  // Primeira questão do bloco
  "end_question": 15,                   // Última questão do bloco
  "questions_count": 15                 // Quantidade de questões no bloco
}
```

#### `question_skills` (object, opcional)
- Mapa de habilidades por questão
- Chave: número da questão (string)
- Valor: array de códigos ou UUIDs de habilidades
- O sistema aceita tanto códigos (ex: "EF05MA01") quanto UUIDs
- Habilidades inexistentes são ignoradas

**Exemplo:**
```json
{
  "1": ["EF05MA01", "EF05MA02"],
  "2": ["uuid-da-habilidade"],
  "3": ["EF05LP01"]
}
```

#### `questions_options` (object, opcional)
- Alternativas customizadas por questão
- Chave: número da questão (string)
- Valor: array de alternativas (mínimo 2)
- Padrão se não informado: `["A", "B", "C", "D"]`

**Exemplo:**
```json
{
  "1": ["A", "B", "C", "D"],
  "2": ["A", "B", "C"],
  "3": ["A", "B"]
}
```

## Response

### Success (200 OK)

```json
{
  "success": true,
  "gabarito_id": "uuid-do-gabarito",
  "message": "Estrutura do cartão resposta atualizada com sucesso",
  "warning": "Atenção: os cartões em PDF já gerados não refletem as alterações. É necessário gerar os cartões novamente para que as mudanças apareçam nos documentos impressos.",
  "changes": {
    "num_questions": {
      "old": 20,
      "new": 30
    },
    "blocks_count": {
      "old": 2,
      "new": 3
    },
    "skills_updated": true
  }
}
```

#### Campos da Response:

- **`success`** (boolean): Sempre `true` em caso de sucesso
- **`gabarito_id`** (string): UUID do gabarito editado
- **`message`** (string): Mensagem de sucesso
- **`warning`** (string, opcional): Aviso sobre PDFs desatualizados (aparece apenas se o cartão já foi gerado)
- **`changes`** (object, opcional): Resumo das alterações realizadas

### Bloqueado por Correções (422 Unprocessable Entity)

```json
{
  "error": "Este cartão resposta não pode ser editado porque já existem correções registradas. Editar agora poderia causar inconsistências nos resultados já calculados. Para fazer alterações, crie um novo cartão resposta.",
  "reason": "has_corrections",
  "corrections_count": 15
}
```

### Erro de Validação (400 Bad Request)

```json
{
  "error": "Bloco 1 (Matemática): máximo de 26 questões por bloco. Você definiu 30."
}
```

**Exemplos de erros de validação:**
- "num_questions deve ser maior que 0"
- "Máximo de 104 questões permitidas"
- "Máximo de 4 blocos permitidos. Você enviou 5 blocos."
- "Bloco 2: 'subject_id' é obrigatório (disciplina do bloco)."
- "Soma das questões dos blocos (35) difere do total informado (30)."

### Sem Permissão (403 Forbidden)

```json
{
  "error": "Você não tem permissão para editar este gabarito"
}
```

### Não Encontrado (404 Not Found)

```json
{
  "error": "Gabarito não encontrado"
}
```

## Fluxo de Uso no Frontend

### 1. Verificar se o Cartão Pode Ser Editado

Antes de mostrar a interface de edição, verifique o estado do cartão:

```javascript
// Buscar detalhes do gabarito
const response = await fetch(`/answer-sheets/gabarito/${gabaritoId}`, {
  headers: {
    'Authorization': `Bearer ${token}`,
    'X-City-Context': cityId
  }
});

const gabarito = await response.json();

// Verificar se tem correções (consultar endpoint de resultados)
const resultsResponse = await fetch(`/answer-sheets/results?gabarito_id=${gabaritoId}&page=1&per_page=1`, {
  headers: {
    'Authorization': `Bearer ${token}`,
    'X-City-Context': cityId
  }
});

const resultsData = await resultsResponse.json();
const hasCorrections = resultsData.total > 0;

if (hasCorrections) {
  // Bloquear edição e mostrar mensagem
  showWarning("Este cartão não pode ser editado porque já possui correções.");
} else {
  // Permitir edição
  enableEditForm();
}
```

### 2. Editar a Estrutura

```javascript
const payload = {
  num_questions: 30,
  blocks_config: {
    blocks: [
      {
        block_id: 1,
        subject_id: "uuid-matematica",
        subject_name: "Matemática",
        start_question: 1,
        end_question: 15,
        questions_count: 15
      },
      {
        block_id: 2,
        subject_id: "uuid-portugues",
        subject_name: "Português",
        start_question: 16,
        end_question: 30,
        questions_count: 15
      }
    ]
  },
  question_skills: {
    "1": ["EF05MA01", "EF05MA02"],
    "2": ["EF05LP01"]
  }
};

const response = await fetch(`/answer-sheets/gabarito/${gabaritoId}/structure`, {
  method: 'PATCH',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json',
    'X-City-Context': cityId
  },
  body: JSON.stringify(payload)
});

const result = await response.json();

if (response.ok) {
  showSuccess(result.message);
  
  // Exibir aviso se presente
  if (result.warning) {
    showWarning(result.warning);
  }
  
  // Atualizar interface com as mudanças
  console.log("Alterações:", result.changes);
  
} else if (response.status === 422) {
  // Bloqueado por correções
  showError(result.error);
  
} else {
  // Erro de validação ou outro erro
  showError(result.error);
}
```

### 3. Tratamento de Avisos

```javascript
if (result.warning) {
  // Mostrar modal ou toast informativo
  showModal({
    title: "Edição realizada com sucesso!",
    message: result.warning,
    type: "warning",
    actions: [
      {
        label: "Gerar PDFs agora",
        onClick: () => navigateToGeneration(gabaritoId)
      },
      {
        label: "Entendido",
        onClick: () => closeModal()
      }
    ]
  });
}
```

## Diferença Entre as Rotas de Edição

### PATCH `/gabarito/{id}/structure` (NOVA)
- Edita: `num_questions`, `blocks_config`, `question_skills`, `questions_options`
- Regenera: coordenadas, topologia, templates
- Ajusta automaticamente: `correct_answers` (se `num_questions` mudou)
- **Não dispara recálculo de correções**

### PATCH `/gabaritos/{id}` (EXISTENTE)
- Edita: **apenas** `correct_answers` (respostas corretas)
- **Dispara recálculo automático** de todos os resultados existentes
- Retorna job de recálculo assíncrono

## Exemplos de Uso Comum

### Exemplo 1: Alterar apenas a quantidade de questões

```json
PATCH /answer-sheets/gabarito/{id}/structure
{
  "num_questions": 40
}
```

### Exemplo 2: Alterar blocos e quantidade

```json
PATCH /answer-sheets/gabarito/{id}/structure
{
  "num_questions": 52,
  "blocks_config": {
    "blocks": [
      {
        "block_id": 1,
        "subject_id": "uuid-matematica",
        "subject_name": "Matemática",
        "start_question": 1,
        "end_question": 26,
        "questions_count": 26
      },
      {
        "block_id": 2,
        "subject_id": "uuid-portugues",
        "subject_name": "Português",
        "start_question": 27,
        "end_question": 52,
        "questions_count": 26
      }
    ]
  }
}
```

### Exemplo 3: Adicionar/Atualizar habilidades

```json
PATCH /answer-sheets/gabarito/{id}/structure
{
  "question_skills": {
    "1": ["EF05MA01"],
    "2": ["EF05MA02", "EF05MA03"],
    "5": ["EF05LP01"]
  }
}
```

### Exemplo 4: Customizar alternativas de questões específicas

```json
PATCH /answer-sheets/gabarito/{id}/structure
{
  "questions_options": {
    "1": ["A", "B", "C", "D", "E"],
    "2": ["A", "B"],
    "10": ["A", "B", "C"]
  }
}
```

## Notas Importantes

1. **Edição parcial**: Você pode enviar apenas os campos que deseja alterar
2. **Validação automática**: O sistema valida a consistência entre blocos e questões
3. **Resolução de habilidades**: Aceita tanto códigos (`EF05MA01`) quanto UUIDs
4. **Resolução de disciplinas**: Se `subject_name` não for enviado, o sistema busca no banco
5. **Ajuste de respostas corretas**: Se `num_questions` mudar, as respostas são ajustadas automaticamente
6. **Invalidação de templates**: Os templates de blocos são invalidados e precisam ser regenerados
7. **Regeneração necessária**: Se o cartão já foi gerado, é necessário gerar novamente para obter PDFs atualizados

## Status Codes

| Código | Descrição |
|--------|-----------|
| 200 | Edição realizada com sucesso |
| 400 | Erro de validação (dados inválidos) |
| 401 | Não autenticado |
| 403 | Sem permissão para editar |
| 404 | Gabarito não encontrado |
| 422 | Bloqueado por correções existentes |
| 500 | Erro interno do servidor |
