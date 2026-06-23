# Contrato API: GET Gabarito com Dados para Edição

## Endpoint

```
GET /answer-sheets/gabarito/{gabarito_id}
```

## Headers

```json
{
  "Authorization": "Bearer {jwt_token}",
  "X-City-Context": "{city_id}"
}
```

## Response Completa (200 OK)

### Estrutura TypeScript

```typescript
interface GabaritoDetailResponse {
  id: string;
  test_id?: string;
  class_id?: string;
  title?: string;
  num_questions: number;
  use_blocks: boolean;
  correct_answers: Record<string, string | null>;
  created_at?: string;
  latest_generation_job_id?: string;
  generations: Generation[];
  generations_count: number;
  
  // Configuração completa (estrutura aninhada)
  blocks_config?: {
    use_blocks: boolean;
    num_blocks: number;
    questions_per_block: number;
    separate_by_subject: boolean;
    blocks?: Array<{
      block_id: number;
      subject_id: string;
      subject_name: string;
      start_question: number;
      end_question: number;
      questions_count: number;
    }>;
    topology?: {
      blocks: Array<{
        block_id: number;
        subject_id?: string;
        subject_name?: string;
        questions: Array<{
          q: number;
          alternatives: string[];
          skills?: string[];
        }>;
      }>;
    };
  };
  
  // ⬇️ NOVOS CAMPOS - Mapas achatados para facilitar edição
  question_skills: Record<string, string[]>;      // questão → UUIDs de habilidades
  questions_options: Record<string, string[]>;    // questão → alternativas
  skill_codes: Record<string, string>;            // UUID → código BNCC
}
```

---

## Exemplo 1: Cartão Simples (Sem Blocos)

### Request

```bash
GET /answer-sheets/gabarito/123e4567-e89b-12d3-a456-426614174000
Authorization: Bearer eyJhbGc...
X-City-Context: city-uuid
```

### Response

```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "title": "Avaliação 1º Bimestre",
  "num_questions": 10,
  "use_blocks": false,
  "correct_answers": {
    "1": "A",
    "2": "B",
    "3": "C",
    "4": "D",
    "5": "A",
    "6": "B",
    "7": "C",
    "8": "D",
    "9": "A",
    "10": "B"
  },
  "created_at": "2026-06-23T10:30:00.000Z",
  "latest_generation_job_id": null,
  "generations": [],
  "generations_count": 0,
  
  "blocks_config": {
    "use_blocks": false,
    "num_blocks": 1,
    "questions_per_block": 10,
    "separate_by_subject": false,
    "topology": {
      "blocks": [
        {
          "block_id": 1,
          "questions": [
            {
              "q": 1,
              "alternatives": ["A", "B", "C", "D"],
              "skills": ["hab-uuid-1", "hab-uuid-2"]
            },
            {
              "q": 2,
              "alternatives": ["A", "B", "C", "D"],
              "skills": []
            },
            {
              "q": 3,
              "alternatives": ["A", "B", "C"],
              "skills": ["hab-uuid-3"]
            }
            // ... questões 4-10
          ]
        }
      ]
    }
  },
  
  "question_skills": {
    "1": ["hab-uuid-1", "hab-uuid-2"],
    "2": [],
    "3": ["hab-uuid-3"],
    "4": [],
    "5": [],
    "6": [],
    "7": [],
    "8": [],
    "9": [],
    "10": []
  },
  
  "questions_options": {
    "1": ["A", "B", "C", "D"],
    "2": ["A", "B", "C", "D"],
    "3": ["A", "B", "C"],
    "4": ["A", "B", "C", "D"],
    "5": ["A", "B", "C", "D"],
    "6": ["A", "B", "C", "D"],
    "7": ["A", "B", "C", "D"],
    "8": ["A", "B", "C", "D"],
    "9": ["A", "B", "C", "D"],
    "10": ["A", "B", "C", "D"]
  },
  
  "skill_codes": {
    "hab-uuid-1": "EF05MA01",
    "hab-uuid-2": "EF05MA02",
    "hab-uuid-3": "EF05LP01"
  }
}
```

---

## Exemplo 2: Cartão com Blocos por Disciplina

### Request

```bash
GET /answer-sheets/gabarito/456e7890-e89b-12d3-a456-426614174001
Authorization: Bearer eyJhbGc...
X-City-Context: city-uuid
```

### Response

```json
{
  "id": "456e7890-e89b-12d3-a456-426614174001",
  "title": "Provinha Brasil - 2º Bimestre",
  "num_questions": 30,
  "use_blocks": true,
  "correct_answers": {
    "1": "A",
    "2": "B",
    // ... 3-30
  },
  "created_at": "2026-06-20T14:20:00.000Z",
  "latest_generation_job_id": "job-uuid-123",
  "generations": [
    {
      "job_id": "job-uuid-123",
      "created_at": "2026-06-20T14:30:00.000Z",
      "total_students_generated": 150,
      "classes_generated": 5
    }
  ],
  "generations_count": 1,
  
  "blocks_config": {
    "use_blocks": true,
    "num_blocks": 2,
    "questions_per_block": 15,
    "separate_by_subject": true,
    "blocks": [
      {
        "block_id": 1,
        "subject_id": "mat-uuid-001",
        "subject_name": "Matemática",
        "start_question": 1,
        "end_question": 15,
        "questions_count": 15
      },
      {
        "block_id": 2,
        "subject_id": "port-uuid-002",
        "subject_name": "Língua Portuguesa",
        "start_question": 16,
        "end_question": 30,
        "questions_count": 15
      }
    ],
    "topology": {
      "blocks": [
        {
          "block_id": 1,
          "subject_id": "mat-uuid-001",
          "subject_name": "Matemática",
          "questions": [
            {
              "q": 1,
              "alternatives": ["A", "B", "C", "D"],
              "skills": ["ef05ma01-uuid", "ef05ma02-uuid"]
            },
            {
              "q": 2,
              "alternatives": ["A", "B", "C", "D"],
              "skills": ["ef05ma03-uuid"]
            }
            // ... questões 3-15
          ]
        },
        {
          "block_id": 2,
          "subject_id": "port-uuid-002",
          "subject_name": "Língua Portuguesa",
          "questions": [
            {
              "q": 16,
              "alternatives": ["A", "B", "C", "D"],
              "skills": ["ef05lp01-uuid"]
            }
            // ... questões 17-30
          ]
        }
      ]
    }
  },
  
  "question_skills": {
    "1": ["ef05ma01-uuid", "ef05ma02-uuid"],
    "2": ["ef05ma03-uuid"],
    "3": [],
    "4": ["ef05ma04-uuid"],
    // ... 5-15 (Matemática)
    "16": ["ef05lp01-uuid"],
    "17": ["ef05lp02-uuid"],
    "18": [],
    // ... 19-30 (Português)
  },
  
  "questions_options": {
    "1": ["A", "B", "C", "D"],
    "2": ["A", "B", "C", "D"],
    "3": ["A", "B", "C", "D"],
    // ... todas com 4 alternativas (padrão global)
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

## Exemplo 3: Alternativas Customizadas por Questão

### Response (trecho relevante)

```json
{
  "num_questions": 5,
  
  "questions_options": {
    "1": ["A", "B", "C", "D", "E"],  // 5 alternativas
    "2": ["A", "B", "C"],            // 3 alternativas
    "3": ["A", "B"],                 // 2 alternativas
    "4": ["A", "B", "C", "D"],       // 4 alternativas (padrão)
    "5": ["A", "B", "C", "D"]
  }
}
```

---

## Como Usar no Frontend

### 1. Detectar Modo de Alternativas (Global vs Individual)

```typescript
interface GabaritoDetailResponse {
  // ... outros campos
  questions_options: Record<string, string[]>;
}

function detectAlternativesMode(data: GabaritoDetailResponse) {
  const allOptions = Object.values(data.questions_options);
  
  // Verificar se todas as questões têm as mesmas alternativas
  const firstOption = JSON.stringify([...allOptions[0]].sort());
  const allSame = allOptions.every(opt => 
    JSON.stringify([...opt].sort()) === firstOption
  );
  
  if (allSame && allOptions.length > 0) {
    // Modo GLOBAL
    return {
      useGlobalAlternatives: true,
      globalAlternatives: allOptions[0],
      questionOptions: {}
    };
  } else {
    // Modo INDIVIDUAL
    return {
      useGlobalAlternatives: false,
      globalAlternatives: ['A', 'B', 'C', 'D'],
      questionOptions: data.questions_options
    };
  }
}

// Uso
const response = await fetch(`/answer-sheets/gabarito/${gabaritoId}`);
const data = await response.json();
const alternativesMode = detectAlternativesMode(data);

console.log(alternativesMode);
// Cenário 1 (todas iguais):
// { useGlobalAlternatives: true, globalAlternatives: ["A", "B", "C", "D"], questionOptions: {} }

// Cenário 2 (diferentes):
// { useGlobalAlternatives: false, globalAlternatives: ["A", "B", "C", "D"], questionOptions: {...} }
```

### 2. Carregar Habilidades com Códigos BNCC

```typescript
function loadQuestionSkills(data: GabaritoDetailResponse) {
  const questionSkillsWithCodes: Record<string, Array<{uuid: string, code: string}>> = {};
  
  for (const [questionNum, skillUuids] of Object.entries(data.question_skills)) {
    questionSkillsWithCodes[questionNum] = skillUuids.map(uuid => ({
      uuid,
      code: data.skill_codes[uuid] || 'N/A'
    }));
  }
  
  return questionSkillsWithCodes;
}

// Uso
const skillsData = loadQuestionSkills(data);
console.log(skillsData["1"]);
// [
//   { uuid: "hab-uuid-1", code: "EF05MA01" },
//   { uuid: "hab-uuid-2", code: "EF05MA02" }
// ]
```

### 3. Interface de Edição - Estado Inicial

```typescript
import { useState, useEffect } from 'react';

function EditGabaritoForm({ gabaritoId }: { gabaritoId: string }) {
  const [numQuestions, setNumQuestions] = useState(0);
  const [blocks, setBlocks] = useState<Block[]>([]);
  const [useGlobalAlternatives, setUseGlobalAlternatives] = useState(true);
  const [globalAlternatives, setGlobalAlternatives] = useState<string[]>([]);
  const [questionOptions, setQuestionOptions] = useState<Record<string, string[]>>({});
  const [questionSkills, setQuestionSkills] = useState<Record<string, string[]>>({});
  const [skillCodes, setSkillCodes] = useState<Record<string, string>>({});
  
  useEffect(() => {
    loadGabarito();
  }, [gabaritoId]);
  
  async function loadGabarito() {
    const response = await fetch(`/answer-sheets/gabarito/${gabaritoId}`, {
      headers: {
        'Authorization': `Bearer ${token}`,
        'X-City-Context': cityId
      }
    });
    
    const data: GabaritoDetailResponse = await response.json();
    
    // Carregar dados básicos
    setNumQuestions(data.num_questions);
    setBlocks(data.blocks_config?.blocks || []);
    
    // Detectar modo de alternativas
    const alternativesMode = detectAlternativesMode(data);
    setUseGlobalAlternatives(alternativesMode.useGlobalAlternatives);
    setGlobalAlternatives(alternativesMode.globalAlternatives);
    setQuestionOptions(alternativesMode.questionOptions);
    
    // Carregar habilidades
    setQuestionSkills(data.question_skills);
    setSkillCodes(data.skill_codes);
  }
  
  return (
    <form>
      <h2>Editar Cartão Resposta</h2>
      
      {/* Quantidade de questões */}
      <input 
        type="number" 
        value={numQuestions}
        onChange={(e) => setNumQuestions(Number(e.target.value))}
      />
      
      {/* Alternativas */}
      <label>
        <input 
          type="checkbox"
          checked={useGlobalAlternatives}
          onChange={(e) => setUseGlobalAlternatives(e.target.checked)}
        />
        Usar as mesmas alternativas em todas as questões
      </label>
      
      {useGlobalAlternatives && (
        <div>
          {['A', 'B', 'C', 'D', 'E'].map(alt => (
            <label key={alt}>
              <input 
                type="checkbox"
                checked={globalAlternatives.includes(alt)}
                onChange={(e) => {
                  if (e.target.checked) {
                    setGlobalAlternatives([...globalAlternatives, alt]);
                  } else {
                    setGlobalAlternatives(globalAlternatives.filter(a => a !== alt));
                  }
                }}
              />
              {alt}
            </label>
          ))}
        </div>
      )}
      
      {/* Habilidades por questão */}
      <div>
        <h3>Habilidades</h3>
        {Object.entries(questionSkills).map(([qNum, skillUuids]) => (
          <div key={qNum}>
            <strong>Q{qNum}:</strong> {
              skillUuids.length > 0 
                ? skillUuids.map(uuid => skillCodes[uuid]).join(', ')
                : 'Sem habilidades'
            }
          </div>
        ))}
      </div>
    </form>
  );
}
```

---

## Casos de Uso

### ✅ Caso 1: Todas alternativas iguais (A, B, C, D)

```json
{
  "questions_options": {
    "1": ["A", "B", "C", "D"],
    "2": ["A", "B", "C", "D"],
    "3": ["A", "B", "C", "D"]
  }
}
```

**Frontend deve marcar:**
- ✅ `useGlobalAlternatives = true`
- ✅ `globalAlternatives = ["A", "B", "C", "D"]`

---

### ❌ Caso 2: Alternativas diferentes

```json
{
  "questions_options": {
    "1": ["A", "B", "C"],
    "2": ["A", "B", "C", "D"],
    "3": ["A", "B"]
  }
}
```

**Frontend deve marcar:**
- ❌ `useGlobalAlternatives = false`
- Carregar individualmente: Q1 → 3 alternativas, Q2 → 4, Q3 → 2

---

### 📝 Caso 3: Questões com habilidades

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
- Q1: ✅ **2 habilidades** (EF05MA01, EF05MA02)
- Q2: ❌ Sem habilidades
- Q3: ✅ **1 habilidade** (EF05LP01)

---

## Benefícios dos Novos Campos

| Campo | Benefício |
|-------|-----------|
| `question_skills` | Acesso direto às habilidades por questão (não precisa navegar topology) |
| `questions_options` | Detectar facilmente se usa alternativas globais ou individuais |
| `skill_codes` | Mostrar códigos BNCC sem consultar API de habilidades |

---

## Comparação: Antes vs Depois

### ❌ ANTES (sem novos campos)

```typescript
// Frontend precisava:
1. Navegar blocks_config.topology.blocks[]
2. Iterar questions[] de cada bloco
3. Consultar API de habilidades para obter códigos BNCC
4. Montar mapas manualmente

// Complexidade: O(n*m) + chamadas extras de API
```

### ✅ DEPOIS (com novos campos)

```typescript
// Frontend apenas:
1. Ler question_skills (já achatado)
2. Ler questions_options (já achatado)
3. Ler skill_codes (já com códigos BNCC)

// Complexidade: O(1) + sem chamadas extras
```

---

## Status Codes

| Código | Descrição |
|--------|-----------|
| 200 | Sucesso - gabarito encontrado |
| 401 | Não autenticado |
| 403 | Sem permissão para acessar |
| 404 | Gabarito não encontrado |
| 500 | Erro interno do servidor |
