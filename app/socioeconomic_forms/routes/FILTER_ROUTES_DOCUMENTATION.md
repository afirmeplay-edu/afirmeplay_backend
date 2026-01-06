# Documentação das Rotas de Filtros para Formulários Socioeconômicos

## Visão Geral

Todas as rotas estão disponíveis em `/forms/` e funcionam **sem necessidade de avaliação**, diferentemente das rotas de `evaluation-results`.

**Base URL:** `/forms`

**Autenticação:** Todas as rotas requerem JWT token no header `Authorization: Bearer <token>`

**Permissões:** Requer role: `admin`, `tecadm`, `diretor`, `coordenador` ou `professor`

---

## 1. Rota Unificada - GET /forms/filter-options

### Descrição
Retorna opções hierárquicas de filtros seguindo a hierarquia: **Estado → Município → Escola → Série → Turma**

### Endpoint
```
GET /forms/filter-options
```

### Query Parameters (todos opcionais)
- `estado` (string): Nome do estado (ex: "SP", "AL")
- `municipio` (string): ID do município (UUID)
- `escola` (string): ID da escola (UUID)
- `serie` (string): ID da série (UUID)
- `turma` (string): ID da turma (UUID)

### Comportamento
- **Sem parâmetros**: Retorna apenas estados
- **Com `estado`**: Retorna estados + municípios do estado
- **Com `estado` + `municipio`**: Retorna estados + municípios + escolas do município
- **Com `estado` + `municipio` + `escola`**: Retorna estados + municípios + escolas + séries da escola
- **Com `estado` + `municipio` + `escola` + `serie`**: Retorna estados + municípios + escolas + séries + turmas da série

### Exemplo 1: Buscar apenas estados
**Request:**
```
GET /forms/filter-options
Authorization: Bearer <token>
```

**Response (200 OK):**
```json
{
  "estados": [
    {
      "id": "SP",
      "nome": "SP",
      "name": "SP"
    },
    {
      "id": "AL",
      "nome": "AL",
      "name": "AL"
    }
  ],
  "avaliacoes": []
}
```

### Exemplo 2: Buscar municípios de um estado
**Request:**
```
GET /forms/filter-options?estado=AL
Authorization: Bearer <token>
```

**Response (200 OK):**
```json
{
  "estados": [
    {
      "id": "SP",
      "nome": "SP",
      "name": "SP"
    },
    {
      "id": "AL",
      "nome": "AL",
      "name": "AL"
    }
  ],
  "municipios": [
    {
      "id": "f252f786-cac5-439f-b0b1-8e3e558f2636",
      "nome": "Maceió",
      "name": "Maceió",
      "estado_id": "AL"
    },
    {
      "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "nome": "Arapiraca",
      "name": "Arapiraca",
      "estado_id": "AL"
    }
  ],
  "avaliacoes": []
}
```

### Exemplo 3: Buscar escolas de um município
**Request:**
```
GET /forms/filter-options?estado=AL&municipio=f252f786-cac5-439f-b0b1-8e3e558f2636
Authorization: Bearer <token>
```

**Response (200 OK):**
```json
{
  "estados": [...],
  "municipios": [...],
  "escolas": [
    {
      "id": "escola-uuid-1",
      "nome": "Escola Municipal X",
      "name": "Escola Municipal X",
      "city_id": "f252f786-cac5-439f-b0b1-8e3e558f2636",
      "municipio_id": "f252f786-cac5-439f-b0b1-8e3e558f2636",
      "address": "Rua X, 123",
      "domain": "escola.com.br"
    },
    {
      "id": "escola-uuid-2",
      "nome": "Escola Estadual Y",
      "name": "Escola Estadual Y",
      "city_id": "f252f786-cac5-439f-b0b1-8e3e558f2636",
      "municipio_id": "f252f786-cac5-439f-b0b1-8e3e558f2636",
      "address": "Av. Y, 456",
      "domain": null
    }
  ],
  "avaliacoes": []
}
```

### Exemplo 4: Buscar séries de uma escola
**Request:**
```
GET /forms/filter-options?estado=AL&municipio=f252f786-cac5-439f-b0b1-8e3e558f2636&escola=escola-uuid-1
Authorization: Bearer <token>
```

**Response (200 OK):**
```json
{
  "estados": [...],
  "municipios": [...],
  "escolas": [...],
  "series": [
    {
      "id": "grade-uuid-1",
      "nome": "1º Ano",
      "name": "1º Ano",
      "education_stage_id": "614b7d10-b758-42ec-a04e-86f78dc7740a",
      "educationStageId": "614b7d10-b758-42ec-a04e-86f78dc7740a"
    },
    {
      "id": "grade-uuid-2",
      "nome": "2º Ano",
      "name": "2º Ano",
      "education_stage_id": "614b7d10-b758-42ec-a04e-86f78dc7740a",
      "educationStageId": "614b7d10-b758-42ec-a04e-86f78dc7740a"
    }
  ],
  "avaliacoes": []
}
```

### Exemplo 5: Buscar turmas de uma série
**Request:**
```
GET /forms/filter-options?estado=AL&municipio=f252f786-cac5-439f-b0b1-8e3e558f2636&escola=escola-uuid-1&serie=grade-uuid-1
Authorization: Bearer <token>
```

**Response (200 OK):**
```json
{
  "estados": [...],
  "municipios": [...],
  "escolas": [...],
  "series": [...],
  "turmas": [
    {
      "id": "class-uuid-1",
      "nome": "Turma A",
      "name": "Turma A",
      "grade_id": "grade-uuid-1",
      "school_id": "escola-uuid-1"
    },
    {
      "id": "class-uuid-2",
      "nome": "Turma B",
      "name": "Turma B",
      "grade_id": "grade-uuid-1",
      "school_id": "escola-uuid-1"
    }
  ],
  "avaliacoes": []
}
```

---

## 2. Rota Direta - GET /forms/schools/city/:cityId

### Descrição
Busca todas as escolas de um município específico.

### Endpoint
```
GET /forms/schools/city/:cityId
```

### Path Parameters
- `cityId` (string, obrigatório): ID do município (UUID)

### Exemplo
**Request:**
```
GET /forms/schools/city/f252f786-cac5-439f-b0b1-8e3e558f2636
Authorization: Bearer <token>
```

**Response (200 OK):**
```json
[
  {
    "id": "escola-uuid-1",
    "nome": "Escola Municipal X",
    "name": "Escola Municipal X",
    "city_id": "f252f786-cac5-439f-b0b1-8e3e558f2636",
    "municipio_id": "f252f786-cac5-439f-b0b1-8e3e558f2636",
    "address": "Rua X, 123",
    "domain": "escola.com.br"
  },
  {
    "id": "escola-uuid-2",
    "nome": "Escola Estadual Y",
    "name": "Escola Estadual Y",
    "city_id": "f252f786-cac5-439f-b0b1-8e3e558f2636",
    "municipio_id": "f252f786-cac5-439f-b0b1-8e3e558f2636",
    "address": "Av. Y, 456",
    "domain": null
  }
]
```

**Response quando não há escolas (200 OK):**
```json
[]
```

---

## 3. Rota Direta - GET /forms/grades/school/:schoolId

### Descrição
Busca todas as séries que têm turmas em uma escola específica.

### Endpoint
```
GET /forms/grades/school/:schoolId
```

### Path Parameters
- `schoolId` (string, obrigatório): ID da escola (UUID)

### Exemplo
**Request:**
```
GET /forms/grades/school/escola-uuid-1
Authorization: Bearer <token>
```

**Response (200 OK):**
```json
[
  {
    "id": "grade-uuid-1",
    "nome": "1º Ano",
    "name": "1º Ano",
    "education_stage_id": "614b7d10-b758-42ec-a04e-86f78dc7740a",
    "educationStageId": "614b7d10-b758-42ec-a04e-86f78dc7740a"
  },
  {
    "id": "grade-uuid-2",
    "nome": "2º Ano",
    "name": "2º Ano",
    "education_stage_id": "614b7d10-b758-42ec-a04e-86f78dc7740a",
    "educationStageId": "614b7d10-b758-42ec-a04e-86f78dc7740a"
  },
  {
    "id": "grade-uuid-3",
    "nome": "6º Ano",
    "name": "6º Ano",
    "education_stage_id": "c78fcd8e-00a1-485d-8c03-70bcf59e3025",
    "educationStageId": "c78fcd8e-00a1-485d-8c03-70bcf59e3025"
  }
]
```

**Response quando não há séries (200 OK):**
```json
[]
```

---

## 4. Rota Direta - GET /forms/classes/grade/:gradeId

### Descrição
Busca todas as turmas de uma série específica. Opcionalmente pode filtrar por escola via query parameter.

### Endpoint
```
GET /forms/classes/grade/:gradeId
```

### Path Parameters
- `gradeId` (string, obrigatório): ID da série (UUID)

### Query Parameters (opcional)
- `escola` (string): ID da escola (UUID) - se fornecido, filtra turmas da série apenas naquela escola

### Exemplo 1: Buscar todas as turmas da série
**Request:**
```
GET /forms/classes/grade/grade-uuid-1
Authorization: Bearer <token>
```

**Response (200 OK):**
```json
[
  {
    "id": "class-uuid-1",
    "nome": "Turma A",
    "name": "Turma A",
    "grade_id": "grade-uuid-1",
    "school_id": "escola-uuid-1"
  },
  {
    "id": "class-uuid-2",
    "nome": "Turma B",
    "name": "Turma B",
    "grade_id": "grade-uuid-1",
    "school_id": "escola-uuid-1"
  },
  {
    "id": "class-uuid-3",
    "nome": "Turma A",
    "name": "Turma A",
    "grade_id": "grade-uuid-1",
    "school_id": "escola-uuid-2"
  }
]
```

### Exemplo 2: Buscar turmas da série em uma escola específica
**Request:**
```
GET /forms/classes/grade/grade-uuid-1?escola=escola-uuid-1
Authorization: Bearer <token>
```

**Response (200 OK):**
```json
[
  {
    "id": "class-uuid-1",
    "nome": "Turma A",
    "name": "Turma A",
    "grade_id": "grade-uuid-1",
    "school_id": "escola-uuid-1"
  },
  {
    "id": "class-uuid-2",
    "nome": "Turma B",
    "name": "Turma B",
    "grade_id": "grade-uuid-1",
    "school_id": "escola-uuid-1"
  }
]
```

**Response quando não há turmas (200 OK):**
```json
[]
```

---

## 5. Rota Direta - GET /forms/grades/:gradeId

### Descrição
Busca informações detalhadas de uma série específica por ID, incluindo `education_stage_id` necessário para determinar o tipo de formulário.

### Endpoint
```
GET /forms/grades/:gradeId
```

### Path Parameters
- `gradeId` (string, obrigatório): ID da série (UUID)

### Exemplo
**Request:**
```
GET /forms/grades/grade-uuid-1
Authorization: Bearer <token>
```

**Response (200 OK):**
```json
{
  "id": "grade-uuid-1",
  "name": "1º Ano",
  "nome": "1º Ano",
  "education_stage_id": "614b7d10-b758-42ec-a04e-86f78dc7740a",
  "educationStageId": "614b7d10-b758-42ec-a04e-86f78dc7740a",
  "education_stage": {
    "id": "614b7d10-b758-42ec-a04e-86f78dc7740a",
    "name": "Anos Iniciais",
    "nome": "Anos Iniciais"
  }
}
```

**Response quando série não encontrada (404 Not Found):**
```json
{
  "error": "Série não encontrada"
}
```

---

## Resumo das Rotas

| Rota | Método | Descrição | Parâmetros |
|------|--------|-----------|------------|
| `/forms/filter-options` | GET | Rota unificada hierárquica | Query: estado, municipio, escola, serie, turma |
| `/forms/schools/city/:cityId` | GET | Escolas por município | Path: cityId |
| `/forms/grades/school/:schoolId` | GET | Séries por escola | Path: schoolId |
| `/forms/classes/grade/:gradeId` | GET | Turmas por série | Path: gradeId, Query: escola (opcional) |
| `/forms/grades/:gradeId` | GET | Informações da série | Path: gradeId |

---

## Observações Importantes

1. **Sem avaliação**: Todas as rotas funcionam sem necessidade de avaliação, diferentemente de `/evaluation-results/opcoes-filtros`

2. **Arrays vazios**: Quando não há resultados, as rotas retornam `[]` (array vazio) com status 200, **não** erro 404

3. **Permissões**: As rotas respeitam as permissões do usuário:
   - **Admin**: Vê tudo
   - **Tecadm**: Vê apenas seu município
   - **Diretor/Coordenador**: Vê apenas sua escola
   - **Professor**: Vê apenas escolas onde está vinculado

4. **Campos duplicados**: Todos os objetos retornam tanto `nome` quanto `name` para compatibilidade

5. **education_stage_id**: Sempre retornado nas séries para permitir determinação do tipo de formulário no frontend

6. **Validação de hierarquia**: O backend valida que:
   - Município pertence ao estado
   - Escola pertence ao município
   - Série tem turmas na escola
   - Turma pertence à série e escola

---

## Exemplos de Uso no Frontend

### Fluxo completo de seleção hierárquica:

1. **Buscar estados:**
   ```
   GET /forms/filter-options
   → Retorna: { estados: [...] }
   ```

2. **Usuário seleciona estado "AL":**
   ```
   GET /forms/filter-options?estado=AL
   → Retorna: { estados: [...], municipios: [...] }
   ```

3. **Usuário seleciona município:**
   ```
   GET /forms/filter-options?estado=AL&municipio=uuid-municipio
   → Retorna: { estados: [...], municipios: [...], escolas: [...] }
   ```

4. **Usuário seleciona escola:**
   ```
   GET /forms/filter-options?estado=AL&municipio=uuid-municipio&escola=uuid-escola
   → Retorna: { estados: [...], municipios: [...], escolas: [...], series: [...] }
   ```

5. **Usuário seleciona série:**
   ```
   GET /forms/filter-options?estado=AL&municipio=uuid-municipio&escola=uuid-escola&serie=uuid-serie
   → Retorna: { estados: [...], municipios: [...], escolas: [...], series: [...], turmas: [...] }
   ```

### Uso de rotas diretas (fallback):

Se a rota unificada não atender, pode usar as rotas diretas:

```
GET /forms/schools/city/uuid-municipio
GET /forms/grades/school/uuid-escola
GET /forms/classes/grade/uuid-serie?escola=uuid-escola
GET /forms/grades/uuid-serie
```

