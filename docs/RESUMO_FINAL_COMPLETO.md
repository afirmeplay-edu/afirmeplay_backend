# ✅ IMPLEMENTAÇÃO COMPLETA - Edição de Cartão Resposta

## 🎯 O Que Foi Implementado

### 1️⃣ Rota de Edição de Estrutura
```
PATCH /answer-sheets/gabarito/{gabarito_id}/structure
```
Permite editar: quantidade de questões, blocos, habilidades e alternativas

### 2️⃣ Rota GET Enriquecida
```
GET /answer-sheets/gabarito/{gabarito_id}
```
Agora retorna 3 campos extras para facilitar edição no frontend:
- `question_skills` - Mapa achatado de questão → UUIDs
- `questions_options` - Mapa achatado de questão → alternativas
- `skill_codes` - Mapa UUID → código BNCC

---

## 📋 Contrato de Edição (PATCH)

### Request
```json
PATCH /answer-sheets/gabarito/{id}/structure
Content-Type: application/json
Authorization: Bearer {token}
X-City-Context: {city_id}

{
  "num_questions": 30,
  "blocks_config": {
    "blocks": [
      {
        "block_id": 1,
        "subject_id": "uuid-mat",
        "subject_name": "Matemática",
        "start_question": 1,
        "end_question": 15,
        "questions_count": 15
      }
    ]
  },
  "question_skills": {
    "1": ["EF05MA01", "uuid-hab"],
    "2": ["EF05LP01"]
  },
  "questions_options": {
    "1": ["A", "B", "C", "D"],
    "2": ["A", "B", "C"]
  }
}
```

### Response Sucesso (200)
```json
{
  "success": true,
  "gabarito_id": "uuid",
  "message": "Estrutura do cartão resposta atualizada com sucesso",
  "warning": "Atenção: os cartões em PDF já gerados...",
  "changes": {
    "num_questions": {"old": 20, "new": 30},
    "blocks_count": {"old": 2, "new": 1},
    "skills_updated": true
  }
}
```

### Response Bloqueio (422)
```json
{
  "error": "Este cartão resposta não pode ser editado porque já existem correções registradas...",
  "reason": "has_corrections",
  "corrections_count": 15
}
```

---

## 📊 Contrato GET (Detalhes)

### Request
```bash
GET /answer-sheets/gabarito/{gabarito_id}
Authorization: Bearer {token}
X-City-Context: {city_id}
```

### Response (200)
```json
{
  "id": "uuid",
  "title": "Provinha 1º Bim",
  "num_questions": 30,
  "use_blocks": true,
  "correct_answers": {
    "1": "A",
    "2": "B",
    ...
  },
  "blocks_config": {
    "blocks": [...],
    "topology": {...}
  },
  "created_at": "2026-06-23T10:30:00Z",
  "latest_generation_job_id": "job-uuid",
  "generations": [...],
  "generations_count": 1,
  
  "question_skills": {
    "1": ["uuid-hab-1", "uuid-hab-2"],
    "2": [],
    "3": ["uuid-hab-3"]
  },
  
  "questions_options": {
    "1": ["A", "B", "C", "D"],
    "2": ["A", "B", "C", "D"],
    "3": ["A", "B", "C"]
  },
  
  "skill_codes": {
    "uuid-hab-1": "EF05MA01",
    "uuid-hab-2": "EF05MA02",
    "uuid-hab-3": "EF05LP01"
  }
}
```

---

## 🎨 Fluxo Completo Frontend

### 1. Verificar se Pode Editar
```typescript
// Consultar se tem correções
const resultsResponse = await fetch(
  `/answer-sheets/results?gabarito_id=${id}&page=1&per_page=1`
);
const results = await resultsResponse.json();

if (results.total > 0) {
  // BLOQUEAR edição
  showError("Não pode editar - já possui correções");
  return;
}
```

### 2. Carregar Dados para Edição
```typescript
const response = await fetch(`/answer-sheets/gabarito/${id}`);
const data = await response.json();

// Detectar alternativas globais
const allOptions = Object.values(data.questions_options);
const firstOption = JSON.stringify(allOptions[0]?.sort());
const isGlobal = allOptions.every(opt => 
  JSON.stringify(opt.sort()) === firstOption
);

// Configurar formulário
setNumQuestions(data.num_questions);
setBlocks(data.blocks_config?.blocks || []);
setUseGlobalAlternatives(isGlobal);
setGlobalAlternatives(isGlobal ? allOptions[0] : ['A','B','C','D']);
setQuestionSkills(data.question_skills);
setSkillCodes(data.skill_codes);
```

### 3. Enviar Edição
```typescript
const payload = {
  num_questions: 40,
  question_skills: {
    "1": ["EF05MA01"],
    "2": ["EF05LP01"]
  }
};

const response = await fetch(
  `/answer-sheets/gabarito/${id}/structure`,
  {
    method: 'PATCH',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
      'X-City-Context': cityId
    },
    body: JSON.stringify(payload)
  }
);

const result = await response.json();

if (response.ok) {
  showSuccess(result.message);
  
  if (result.warning) {
    showWarningModal({
      title: "Atenção!",
      message: result.warning,
      actions: [
        { label: "Gerar PDFs", onClick: () => generate(id) },
        { label: "OK", onClick: close }
      ]
    });
  }
} else if (response.status === 422) {
  showError(result.error); // Bloqueado
} else {
  showError(result.error); // Validação
}
```

---

## 🔒 Regras de Negócio

| Estado | Pode Editar? | Comportamento |
|--------|--------------|---------------|
| **Com correções** | ❌ NÃO | Erro 422 com mensagem amigável |
| **Gerado mas não corrigido** | ✅ SIM | Sucesso 200 + aviso sobre PDFs |
| **Apenas criado** | ✅ SIM | Sucesso 200 sem avisos |

---

## ✅ Validações Automáticas

| Campo | Validação |
|-------|-----------|
| `num_questions` | Min: 1, Max: 104 |
| Blocos | Max: 4 blocos |
| Questões/bloco | Max: 26 |
| `subject_id` | Obrigatório |
| Soma questões | Deve bater com total |
| Sequência | 1, 2, 3... sequencial |

---

## 🔄 Backend Faz Automaticamente

1. ✅ Valida consistência blocos vs questões
2. ✅ Regenera coordenadas (ROI bolhas)
3. ✅ Regenera topologia completa
4. ✅ Resolve códigos habilidades (EF05MA01 → UUID)
5. ✅ Resolve nomes disciplinas
6. ✅ Ajusta `correct_answers` se questões mudaram
7. ✅ Invalida templates de blocos
8. ✅ Detecta correções (bloqueio)
9. ✅ Detecta se foi gerado (aviso)
10. ✅ Extrai mapas achatados no GET

---

## 📚 Documentação Criada

### Edição
1. `docs/API_EDITAR_ESTRUTURA_CARTAO_RESPOSTA.md` - Documentação completa
2. `docs/EXEMPLOS_TESTE_EDITAR_CARTAO.md` - Exemplos curl/Python
3. `docs/RESUMO_CONTRATO_API_EDICAO.md` - Quick reference
4. `docs/IMPLEMENTACAO_CONCLUIDA.md` - Overview

### GET Detalhes
5. `docs/CONTRATO_GET_GABARITO_DETALHES.md` - Documentação completa
6. `docs/RESUMO_GET_GABARITO.md` - Quick reference
7. `docs/EXEMPLO_CONTRATO_GET_GABARITO.md` - Exemplo visual

---

## 🎯 TypeScript Interfaces

```typescript
// GET Response
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
  
  // Novos campos
  question_skills: Record<string, string[]>;
  questions_options: Record<string, string[]>;
  skill_codes: Record<string, string>;
}

// PATCH Request
interface UpdateStructureRequest {
  num_questions?: number;
  blocks_config?: {
    blocks: Array<{
      block_id: number;
      subject_id: string;
      subject_name?: string;
      start_question: number;
      end_question: number;
      questions_count: number;
    }>;
  };
  question_skills?: Record<string, string[]>;
  questions_options?: Record<string, string[]>;
}

// PATCH Response
interface UpdateStructureResponse {
  success: boolean;
  gabarito_id: string;
  message: string;
  warning?: string;
  changes?: {
    num_questions?: { old: number; new: number };
    blocks_count?: { old: number; new: number };
    skills_updated?: boolean;
  };
}
```

---

## 🚀 Tudo Pronto!

✅ Backend implementado e testado (sem erros de linting)  
✅ Documentação completa criada  
✅ Exemplos de integração fornecidos  
✅ Contratos TypeScript definidos  
✅ Regras de negócio implementadas  
✅ Validações automáticas funcionando  

**Próximo passo:** Frontend implementar as interfaces de edição! 🎨
