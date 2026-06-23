# Exemplos de Teste da API - Editar Estrutura do Cartão Resposta

## Pré-requisitos

```bash
# Variáveis de ambiente
export JWT_TOKEN="seu-token-jwt-aqui"
export CITY_ID="uuid-da-cidade"
export GABARITO_ID="uuid-do-gabarito"
export API_URL="http://localhost:5000"
```

## Cenário 1: Alterar Apenas Quantidade de Questões

### Request
```bash
curl -X PATCH "${API_URL}/answer-sheets/gabarito/${GABARITO_ID}/structure" \
  -H "Authorization: Bearer ${JWT_TOKEN}" \
  -H "Content-Type: application/json" \
  -H "X-City-Context: ${CITY_ID}" \
  -d '{
    "num_questions": 40
  }'
```

### Response Esperada (200 OK - Cartão não gerado)
```json
{
  "success": true,
  "gabarito_id": "uuid-do-gabarito",
  "message": "Estrutura do cartão resposta atualizada com sucesso",
  "changes": {
    "num_questions": {
      "old": 20,
      "new": 40
    }
  }
}
```

### Response Esperada (200 OK - Cartão já gerado)
```json
{
  "success": true,
  "gabarito_id": "uuid-do-gabarito",
  "message": "Estrutura do cartão resposta atualizada com sucesso",
  "warning": "Atenção: os cartões em PDF já gerados não refletem as alterações. É necessário gerar os cartões novamente para que as mudanças apareçam nos documentos impressos.",
  "changes": {
    "num_questions": {
      "old": 20,
      "new": 40
    }
  }
}
```

---

## Cenário 2: Alterar Configuração de Blocos

### Request
```bash
curl -X PATCH "${API_URL}/answer-sheets/gabarito/${GABARITO_ID}/structure" \
  -H "Authorization: Bearer ${JWT_TOKEN}" \
  -H "Content-Type: application/json" \
  -H "X-City-Context: ${CITY_ID}" \
  -d '{
    "num_questions": 52,
    "blocks_config": {
      "blocks": [
        {
          "block_id": 1,
          "subject_id": "123e4567-e89b-12d3-a456-426614174001",
          "subject_name": "Matemática",
          "start_question": 1,
          "end_question": 26,
          "questions_count": 26
        },
        {
          "block_id": 2,
          "subject_id": "123e4567-e89b-12d3-a456-426614174002",
          "subject_name": "Português",
          "start_question": 27,
          "end_question": 52,
          "questions_count": 26
        }
      ]
    }
  }'
```

### Response Esperada (200 OK)
```json
{
  "success": true,
  "gabarito_id": "uuid-do-gabarito",
  "message": "Estrutura do cartão resposta atualizada com sucesso",
  "changes": {
    "num_questions": {
      "old": 20,
      "new": 52
    },
    "blocks_count": {
      "old": 1,
      "new": 2
    }
  }
}
```

---

## Cenário 3: Adicionar Habilidades às Questões

### Request
```bash
curl -X PATCH "${API_URL}/answer-sheets/gabarito/${GABARITO_ID}/structure" \
  -H "Authorization: Bearer ${JWT_TOKEN}" \
  -H "Content-Type: application/json" \
  -H "X-City-Context: ${CITY_ID}" \
  -d '{
    "question_skills": {
      "1": ["EF05MA01", "EF05MA02"],
      "2": ["EF05LP01"],
      "3": ["123e4567-e89b-12d3-a456-426614174010"]
    }
  }'
```

### Response Esperada (200 OK)
```json
{
  "success": true,
  "gabarito_id": "uuid-do-gabarito",
  "message": "Estrutura do cartão resposta atualizada com sucesso",
  "changes": {
    "skills_updated": true
  }
}
```

---

## Cenário 4: Edição Completa (Questões + Blocos + Habilidades)

### Request
```bash
curl -X PATCH "${API_URL}/answer-sheets/gabarito/${GABARITO_ID}/structure" \
  -H "Authorization: Bearer ${JWT_TOKEN}" \
  -H "Content-Type: application/json" \
  -H "X-City-Context: ${CITY_ID}" \
  -d '{
    "num_questions": 30,
    "blocks_config": {
      "blocks": [
        {
          "block_id": 1,
          "subject_id": "123e4567-e89b-12d3-a456-426614174001",
          "subject_name": "Matemática",
          "start_question": 1,
          "end_question": 15,
          "questions_count": 15
        },
        {
          "block_id": 2,
          "subject_id": "123e4567-e89b-12d3-a456-426614174002",
          "subject_name": "Português",
          "start_question": 16,
          "end_question": 30,
          "questions_count": 15
        }
      ]
    },
    "question_skills": {
      "1": ["EF05MA01"],
      "2": ["EF05MA02"],
      "16": ["EF05LP01"],
      "17": ["EF05LP02"]
    },
    "questions_options": {
      "1": ["A", "B", "C", "D", "E"],
      "2": ["A", "B", "C"]
    }
  }'
```

### Response Esperada (200 OK)
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
      "old": 1,
      "new": 2
    },
    "skills_updated": true
  }
}
```

---

## Cenário 5: Erro - Cartão com Correções (Bloqueado)

### Request
```bash
curl -X PATCH "${API_URL}/answer-sheets/gabarito/${GABARITO_ID}/structure" \
  -H "Authorization: Bearer ${JWT_TOKEN}" \
  -H "Content-Type: application/json" \
  -H "X-City-Context: ${CITY_ID}" \
  -d '{
    "num_questions": 40
  }'
```

### Response Esperada (422 Unprocessable Entity)
```json
{
  "error": "Este cartão resposta não pode ser editado porque já existem correções registradas. Editar agora poderia causar inconsistências nos resultados já calculados. Para fazer alterações, crie um novo cartão resposta.",
  "reason": "has_corrections",
  "corrections_count": 15
}
```

---

## Cenário 6: Erro - Validação de Blocos

### Request (Blocos com soma incorreta)
```bash
curl -X PATCH "${API_URL}/answer-sheets/gabarito/${GABARITO_ID}/structure" \
  -H "Authorization: Bearer ${JWT_TOKEN}" \
  -H "Content-Type: application/json" \
  -H "X-City-Context: ${CITY_ID}" \
  -d '{
    "num_questions": 30,
    "blocks_config": {
      "blocks": [
        {
          "block_id": 1,
          "subject_id": "123e4567-e89b-12d3-a456-426614174001",
          "subject_name": "Matemática",
          "start_question": 1,
          "end_question": 20,
          "questions_count": 20
        }
      ]
    }
  }'
```

### Response Esperada (400 Bad Request)
```json
{
  "error": "Soma das questões dos blocos (20) difere do total informado (30)."
}
```

---

## Cenário 7: Erro - Excesso de Questões por Bloco

### Request
```bash
curl -X PATCH "${API_URL}/answer-sheets/gabarito/${GABARITO_ID}/structure" \
  -H "Authorization: Bearer ${JWT_TOKEN}" \
  -H "Content-Type: application/json" \
  -H "X-City-Context: ${CITY_ID}" \
  -d '{
    "num_questions": 30,
    "blocks_config": {
      "blocks": [
        {
          "block_id": 1,
          "subject_id": "123e4567-e89b-12d3-a456-426614174001",
          "subject_name": "Matemática",
          "start_question": 1,
          "end_question": 30,
          "questions_count": 30
        }
      ]
    }
  }'
```

### Response Esperada (400 Bad Request)
```json
{
  "error": "Bloco 1 (Matemática): máximo de 26 questões por bloco. Você definiu 30."
}
```

---

## Cenário 8: Erro - Excesso de Blocos

### Request
```bash
curl -X PATCH "${API_URL}/answer-sheets/gabarito/${GABARITO_ID}/structure" \
  -H "Authorization: Bearer ${JWT_TOKEN}" \
  -H "Content-Type: application/json" \
  -H "X-City-Context: ${CITY_ID}" \
  -d '{
    "num_questions": 100,
    "blocks_config": {
      "blocks": [
        {
          "block_id": 1,
          "subject_id": "uuid-1",
          "start_question": 1,
          "end_question": 20,
          "questions_count": 20
        },
        {
          "block_id": 2,
          "subject_id": "uuid-2",
          "start_question": 21,
          "end_question": 40,
          "questions_count": 20
        },
        {
          "block_id": 3,
          "subject_id": "uuid-3",
          "start_question": 41,
          "end_question": 60,
          "questions_count": 20
        },
        {
          "block_id": 4,
          "subject_id": "uuid-4",
          "start_question": 61,
          "end_question": 80,
          "questions_count": 20
        },
        {
          "block_id": 5,
          "subject_id": "uuid-5",
          "start_question": 81,
          "end_question": 100,
          "questions_count": 20
        }
      ]
    }
  }'
```

### Response Esperada (400 Bad Request)
```json
{
  "error": "Máximo de 4 blocos permitidos. Você enviou 5 blocos."
}
```

---

## Cenário 9: Verificar Estado Antes de Editar

### 1. Buscar detalhes do gabarito
```bash
curl -X GET "${API_URL}/answer-sheets/gabarito/${GABARITO_ID}" \
  -H "Authorization: Bearer ${JWT_TOKEN}" \
  -H "X-City-Context: ${CITY_ID}"
```

### 2. Verificar se tem correções
```bash
curl -X GET "${API_URL}/answer-sheets/results?gabarito_id=${GABARITO_ID}&page=1&per_page=1" \
  -H "Authorization: Bearer ${JWT_TOKEN}" \
  -H "X-City-Context: ${CITY_ID}"
```

### 3. Decidir se permite edição
```javascript
// Pseudo-código
if (resultsData.total > 0) {
  // Bloquear edição no frontend
  console.log("Cartão não pode ser editado - tem correções");
} else if (gabarito.latest_generation_job_id) {
  // Permitir edição com aviso
  console.log("Cartão pode ser editado - mas precisa regenerar PDFs");
} else {
  // Edição livre
  console.log("Cartão pode ser editado livremente");
}
```

---

## Script de Teste Completo (Python)

```python
import requests
import json

# Configuração
API_URL = "http://localhost:5000"
JWT_TOKEN = "seu-token-aqui"
CITY_ID = "uuid-da-cidade"
GABARITO_ID = "uuid-do-gabarito"

headers = {
    "Authorization": f"Bearer {JWT_TOKEN}",
    "Content-Type": "application/json",
    "X-City-Context": CITY_ID
}

# Teste 1: Alterar quantidade de questões
print("Teste 1: Alterar quantidade de questões")
payload = {
    "num_questions": 40
}
response = requests.patch(
    f"{API_URL}/answer-sheets/gabarito/{GABARITO_ID}/structure",
    headers=headers,
    json=payload
)
print(f"Status: {response.status_code}")
print(f"Response: {json.dumps(response.json(), indent=2)}\n")

# Teste 2: Adicionar habilidades
print("Teste 2: Adicionar habilidades")
payload = {
    "question_skills": {
        "1": ["EF05MA01"],
        "2": ["EF05MA02"]
    }
}
response = requests.patch(
    f"{API_URL}/answer-sheets/gabarito/{GABARITO_ID}/structure",
    headers=headers,
    json=payload
)
print(f"Status: {response.status_code}")
print(f"Response: {json.dumps(response.json(), indent=2)}\n")

# Teste 3: Verificar se tem correções (deve bloquear)
print("Teste 3: Verificar bloqueio por correções")
# Primeiro, verificar se tem resultados
results_response = requests.get(
    f"{API_URL}/answer-sheets/results",
    headers=headers,
    params={"gabarito_id": GABARITO_ID, "page": 1, "per_page": 1}
)
results_data = results_response.json()
print(f"Tem correções: {results_data.get('total', 0) > 0}")
```

---

## Notas de Teste

1. **Ambiente de Desenvolvimento**: Teste primeiro em ambiente de desenvolvimento
2. **Backup**: Sempre faça backup do banco antes de testar edições
3. **Validação**: Verifique se as coordenadas foram regeneradas corretamente
4. **PDFs**: Teste a geração de PDFs após editar a estrutura
5. **Correção**: Teste a correção de cartões após editar habilidades
