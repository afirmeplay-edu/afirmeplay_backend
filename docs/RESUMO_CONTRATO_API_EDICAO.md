# Resumo: Contrato API Edição de Cartão Resposta

## Endpoint Principal

```
PATCH /answer-sheets/gabarito/{gabarito_id}/structure
```

## O Que Pode Ser Editado

✅ **Quantidade de questões** (`num_questions`)  
✅ **Configuração de blocos** (`blocks_config`)  
✅ **Habilidades por questão** (`question_skills`)  
✅ **Alternativas customizadas** (`questions_options`)

## Regras de Bloqueio

| Estado do Cartão | Pode Editar? | Comportamento |
|-----------------|--------------|---------------|
| **Com correções** | ❌ NÃO | Retorna erro 422 com mensagem amigável |
| **Gerado mas não corrigido** | ✅ SIM | Retorna sucesso 200 **com aviso** de regenerar PDFs |
| **Apenas criado** | ✅ SIM | Retorna sucesso 200 sem avisos |

## Request Mínimo

```bash
PATCH /answer-sheets/gabarito/{id}/structure
Content-Type: application/json
Authorization: Bearer {token}
X-City-Context: {city_id}

{
  "num_questions": 30
}
```

## Request Completo

```json
{
  "num_questions": 30,
  "blocks_config": {
    "blocks": [
      {
        "block_id": 1,
        "subject_id": "uuid-disciplina",
        "subject_name": "Matemática",
        "start_question": 1,
        "end_question": 15,
        "questions_count": 15
      }
    ]
  },
  "question_skills": {
    "1": ["EF05MA01", "uuid-habilidade"],
    "2": ["EF05LP02"]
  },
  "questions_options": {
    "1": ["A", "B", "C", "D"],
    "2": ["A", "B", "C"]
  }
}
```

## Response de Sucesso (200)

```json
{
  "success": true,
  "gabarito_id": "uuid",
  "message": "Estrutura do cartão resposta atualizada com sucesso",
  "warning": "Atenção: os cartões em PDF já gerados...",
  "changes": {
    "num_questions": {"old": 20, "new": 30},
    "blocks_count": {"old": 2, "new": 3},
    "skills_updated": true
  }
}
```

## Response de Bloqueio (422)

```json
{
  "error": "Este cartão resposta não pode ser editado porque já existem correções registradas. Para fazer alterações, crie um novo cartão resposta.",
  "reason": "has_corrections",
  "corrections_count": 15
}
```

## Validações Principais

| Campo | Validação |
|-------|-----------|
| `num_questions` | Mínimo: 1, Máximo: 104 |
| Blocos | Máximo: 4 blocos |
| Questões por bloco | Máximo: 26 questões |
| `subject_id` | Obrigatório por bloco |
| Soma de questões | Deve bater com `num_questions` |
| Sequência | Questões devem ser sequenciais (1, 2, 3...) |

## O Que o Backend Faz Automaticamente

1. ✅ Valida consistência entre blocos e questões
2. ✅ Regenera coordenadas (ROI das bolhas)
3. ✅ Regenera topologia completa
4. ✅ Resolve códigos de habilidades (EF05MA01 → UUID)
5. ✅ Resolve nomes de disciplinas se não enviados
6. ✅ Ajusta `correct_answers` se questões mudaram
7. ✅ Invalida templates de blocos (força regeneração)
8. ✅ Detecta se tem correções (bloqueio)
9. ✅ Detecta se foi gerado (aviso)

## Fluxo Frontend Recomendado

```javascript
// 1. Antes de mostrar formulário de edição
const canEdit = await checkIfCanEdit(gabaritoId);
if (!canEdit) {
  showError("Não pode editar - já tem correções");
  return;
}

// 2. Enviar edição
const response = await editStructure(gabaritoId, payload);

// 3. Tratar resposta
if (response.ok) {
  showSuccess(response.message);
  
  if (response.warning) {
    // Mostrar modal com aviso de regenerar PDFs
    showRegenerationWarning();
  }
} else if (response.status === 422) {
  // Bloqueado por correções
  showError(response.error);
}
```

## Diferença Entre Rotas de Edição

| Rota | Edita | Recalcula Correções? |
|------|-------|---------------------|
| `PATCH /gabarito/{id}/structure` | Estrutura (questões, blocos, habilidades) | ❌ NÃO |
| `PATCH /gabaritos/{id}` | Apenas respostas corretas | ✅ SIM (automático) |

## Status Codes

- `200` - Sucesso (com ou sem warning)
- `400` - Erro de validação
- `401` - Não autenticado
- `403` - Sem permissão
- `404` - Gabarito não encontrado
- `422` - Bloqueado por correções
- `500` - Erro interno
