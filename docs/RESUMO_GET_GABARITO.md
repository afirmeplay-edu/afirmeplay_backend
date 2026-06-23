# ✅ RESUMO: GET Gabarito com Dados para Edição

## Endpoint

```
GET /answer-sheets/gabarito/{gabarito_id}
```

## O Que Foi Adicionado

✅ **3 novos campos** na resposta para facilitar edição no frontend:

```typescript
{
  // ... campos existentes
  
  // NOVOS CAMPOS ⬇️
  "question_skills": {           // Mapa: questão → UUIDs de habilidades
    "1": ["uuid-hab-1", "uuid-hab-2"],
    "2": [],
    "3": ["uuid-hab-3"]
  },
  
  "questions_options": {         // Mapa: questão → alternativas
    "1": ["A", "B", "C", "D"],
    "2": ["A", "B", "C"],
    "3": ["A", "B", "C", "D"]
  },
  
  "skill_codes": {               // Mapa: UUID → código BNCC
    "uuid-hab-1": "EF05MA01",
    "uuid-hab-2": "EF05MA02",
    "uuid-hab-3": "EF05LP01"
  }
}
```

---

## Interface TypeScript

```typescript
interface GabaritoDetailResponse {
  id: string;
  title?: string;
  num_questions: number;
  use_blocks: boolean;
  correct_answers: Record<string, string | null>;
  blocks_config?: BlocksConfig;
  created_at?: string;
  latest_generation_job_id?: string;
  generations: Generation[];
  generations_count: number;
  
  // ⬇️ NOVOS CAMPOS
  question_skills: Record<string, string[]>;      // questão → UUIDs
  questions_options: Record<string, string[]>;    // questão → alternativas
  skill_codes: Record<string, string>;            // UUID → código BNCC
}
```

---

## Exemplo Completo

### Request

```bash
GET /answer-sheets/gabarito/123e4567-e89b-12d3-a456-426614174000
Authorization: Bearer {token}
X-City-Context: {city_id}
```

### Response

```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "title": "Provinha 1º Bimestre",
  "num_questions": 30,
  "use_blocks": true,
  "correct_answers": {
    "1": "A",
    "2": "B",
    ...
  },
  "blocks_config": {
    "blocks": [
      {
        "block_id": 1,
        "subject_id": "mat-uuid",
        "subject_name": "Matemática",
        "start_question": 1,
        "end_question": 15,
        "questions_count": 15
      },
      {
        "block_id": 2,
        "subject_id": "port-uuid",
        "subject_name": "Português",
        "start_question": 16,
        "end_question": 30,
        "questions_count": 15
      }
    ],
    "topology": { ... }
  },
  "created_at": "2026-06-23T10:30:00.000Z",
  "latest_generation_job_id": "job-uuid-123",
  "generations": [...],
  "generations_count": 1,
  
  "question_skills": {
    "1": ["ef05ma01-uuid", "ef05ma02-uuid"],
    "2": ["ef05ma03-uuid"],
    "3": [],
    "4": ["ef05ma04-uuid"],
    ...
    "16": ["ef05lp01-uuid"],
    "17": [],
    ...
    "30": ["ef05lp02-uuid"]
  },
  
  "questions_options": {
    "1": ["A", "B", "C", "D"],
    "2": ["A", "B", "C", "D"],
    ...
    "30": ["A", "B", "C", "D"]
  },
  
  "skill_codes": {
    "ef05ma01-uuid": "EF05MA01",
    "ef05ma02-uuid": "EF05MA02",
    "ef05ma03-uuid": "EF05MA03",
    "ef05ma04-uuid": "EF05MA04",
    "ef05lp01-uuid": "EF05LP01",
    "ef05lp02-uuid": "EF05LP02"
  }
}
```

---

## Como Usar no Frontend

### 1️⃣ Detectar Modo de Alternativas

```typescript
function detectAlternativesMode(data: GabaritoDetailResponse) {
  const allOptions = Object.values(data.questions_options);
  const firstOption = JSON.stringify([...allOptions[0]].sort());
  const allSame = allOptions.every(opt => 
    JSON.stringify([...opt].sort()) === firstOption
  );
  
  return {
    useGlobalAlternatives: allSame,
    globalAlternatives: allSame ? allOptions[0] : ['A', 'B', 'C', 'D'],
    questionOptions: allSame ? {} : data.questions_options
  };
}
```

**Resultado:**

| Cenário | `useGlobalAlternatives` | Ação |
|---------|------------------------|------|
| Todas iguais: `["A","B","C","D"]` | `true` | Marcar checkbox "usar global" |
| Diferentes: Q1=3, Q2=4, Q3=2 alt. | `false` | Carregar individualmente |

---

### 2️⃣ Mostrar Habilidades com Códigos

```typescript
function renderQuestionSkills(
  questionNum: string, 
  data: GabaritoDetailResponse
) {
  const skillUuids = data.question_skills[questionNum] || [];
  
  if (skillUuids.length === 0) {
    return <span>❌ Sem habilidades</span>;
  }
  
  const codes = skillUuids.map(uuid => data.skill_codes[uuid]).join(', ');
  return (
    <span>✅ {skillUuids.length} habilidade(s): {codes}</span>
  );
}

// Exemplo de uso
renderQuestionSkills("1", data);
// Resultado: "✅ 2 habilidade(s): EF05MA01, EF05MA02"
```

---

### 3️⃣ Carregar Estado Inicial do Form

```typescript
async function loadGabaritoForEdit(gabaritoId: string) {
  const response = await fetch(
    `/answer-sheets/gabarito/${gabaritoId}`,
    {
      headers: {
        'Authorization': `Bearer ${token}`,
        'X-City-Context': cityId
      }
    }
  );
  
  const data: GabaritoDetailResponse = await response.json();
  
  // Detectar modo de alternativas
  const altMode = detectAlternativesMode(data);
  
  // Configurar estado do formulário
  setNumQuestions(data.num_questions);
  setBlocks(data.blocks_config?.blocks || []);
  setUseGlobalAlternatives(altMode.useGlobalAlternatives);
  setGlobalAlternatives(altMode.globalAlternatives);
  setQuestionOptions(altMode.questionOptions);
  setQuestionSkills(data.question_skills);
  setSkillCodes(data.skill_codes);
}
```

---

## Casos de Uso Principais

### ✅ Caso 1: Alternativas Globais

```json
{
  "questions_options": {
    "1": ["A", "B", "C", "D"],
    "2": ["A", "B", "C", "D"],
    "3": ["A", "B", "C", "D"]
  }
}
```

**Frontend:**
- ✅ Marcar checkbox "usar as mesmas alternativas"
- ✅ Marcar: A, B, C, D

---

### ❌ Caso 2: Alternativas Individuais

```json
{
  "questions_options": {
    "1": ["A", "B", "C"],        // 3 alternativas
    "2": ["A", "B", "C", "D"],   // 4 alternativas
    "3": ["A", "B"]              // 2 alternativas
  }
}
```

**Frontend:**
- ❌ Desmarcar checkbox "usar as mesmas alternativas"
- Mostrar botão "Configurar" para cada questão

---

### 📝 Caso 3: Habilidades

```json
{
  "question_skills": {
    "1": ["uuid-1", "uuid-2"],
    "2": [],
    "3": ["uuid-3"]
  },
  "skill_codes": {
    "uuid-1": "EF05MA01",
    "uuid-2": "EF05MA02",
    "uuid-3": "EF05LP01"
  }
}
```

**Frontend exibe:**
- Q1: ✅ 2 habilidades (EF05MA01, EF05MA02)
- Q2: ❌ Sem habilidades
- Q3: ✅ 1 habilidade (EF05LP01)

---

## Benefícios

| Antes | Depois |
|-------|--------|
| Navegar `topology.blocks[].questions[]` | Ler `question_skills` diretamente |
| Iterar blocos e questões manualmente | Mapa já achatado |
| Consultar API de habilidades | Códigos já em `skill_codes` |
| Complexidade: O(n*m) + N chamadas API | Complexidade: O(1), sem chamadas extras |

---

## Padrões

| Campo | Valor Padrão |
|-------|--------------|
| `questions_options[n]` | `["A", "B", "C", "D"]` (4 alternativas) |
| `question_skills[n]` | `[]` (sem habilidades) |
| `skill_codes` | `{}` (vazio se nenhuma habilidade) |

---

## Status Codes

| Código | Descrição |
|--------|-----------|
| 200 | ✅ Sucesso |
| 401 | ❌ Não autenticado |
| 403 | ❌ Sem permissão |
| 404 | ❌ Gabarito não encontrado |
| 500 | ❌ Erro interno |

---

## Documentação Completa

Ver: `docs/CONTRATO_GET_GABARITO_DETALHES.md`
