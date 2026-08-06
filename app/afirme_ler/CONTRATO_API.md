# Afirme Ler — Contrato de API (Frontend)

Base path: `/afirme-reading`

Todas as rotas exigem:

| Requisito | Detalhe |
|-----------|---------|
| Auth | Header `Authorization: Bearer <JWT>` |
| Feature | Entitlement `afirme_reading` (sem feature → bloqueio do decorator) |
| Content-Type | `application/json` em POST/PATCH |

Campos JSON aceitam **camelCase** (preferido no frontend) e, em vários pontos, **snake_case** como alias.

Erros padrão:

```json
{ "error": "mensagem" }
```

| Status | Quando |
|--------|--------|
| 400 | Validação (`ValueError`) |
| 401 | Usuário não encontrado / JWT inválido |
| 403 | Sem permissão / sem contexto de cidade (avaliações) / sem feature |
| 404 | Recurso não encontrado (`LookupError`) |
| 500 | Erro interno / banco |

---

## 0. Login (front Afirme Ler — sem subdomínio municipal)

Hosts de **produto** (não são município): `afirme-ler.afirmeplay.com.br`, `afirme-ler.afirmeplay.com`, `localhost:3000`.

Nesses hosts o backend **não** exige `jaru.afirmeplay...`. O município vem no login.

### `POST /login/`

**Preferido — headers** (igual mobile):

```http
POST /login/
Content-Type: application/json
X-City-Slug: jaru
```

```json
{
  "registration": "professor@email.com",
  "password": "senha"
}
```

**Alternativa — body:**

```json
{
  "registration": "professor@email.com",
  "password": "senha",
  "citySlug": "jaru"
}
```

(`cityId` / `city_id` também aceitos.)

Prioridade de resolução: `X-City-ID` → `X-City-Slug` → body `cityId`/`citySlug` → subdomínio municipal clássico (se houver).

**Não-admin:** deve pertencer ao município informado (`usuario.city_id`).  
**Admin:** pode logar sem município; nas rotas tenant (`/guided-sessions`, `/schools`, etc.) envie `X-City-Slug` depois.

**Response `200` (trecho):**

```json
{
  "mensagem": "Login bem-sucedido.",
  "token": "eyJ...",
  "user": {
    "id": "...",
    "role": "professor",
    "tenant_id": "9a2f95ed-9f70-4863-a5f1-1b6c6c262b0d",
    "city_id": "9a2f95ed-9f70-4863-a5f1-1b6c6c262b0d",
    "city_slug": "jaru",
    "plan_code": "plus",
    "entitlements": { "plan_code": "plus", "features": ["...", "afirme_reading"] }
  }
}
```

Após o login, o JWT já carrega o município — requests autenticadas de professor/tecadm **não** precisam de subdomínio. Admin continua mandando `X-City-Slug` nas rotas tenant.

---

## Papéis

| Grupo | Roles | Uso |
|-------|-------|-----|
| Cadastro | `admin`, `tecadm`, `professor`, `coordenador`, `diretor` | Textos, listas, questões, CRUD de avaliação, apply |
| Aplicação | Cadastro + `aplicador` | Listar/obter avaliações e sessões; start, fluency, answers, submit, absent |

---

## Escopo de catálogo (textos e word-lists)

Resolvido automaticamente no create (não envie `scopeType`):

| Role | `scopeType` |
|------|-------------|
| `admin` | `GLOBAL` |
| `tecadm` | `CITY` (município do usuário) |
| `professor` / `coordenador` / `diretor` | `PRIVATE` (dono = usuário) |

Visibilidade na listagem: GLOBAL + CITY do município atual + PRIVATE do usuário.

Edição/exclusão: `admin` pode tudo; conteúdo GLOBAL só `admin`; CITY só `tecadm` do município; PRIVATE só o dono.

---

## Enums

### `difficultyLevel` (textos)

`VERY_EASY` | `EASY` | `MEDIUM` | `HARD` | `VERY_HARD`

### `kind` (listas de palavras)

`PALAVRAS` | `POUCO_COMUNS`

### `assessmentType` (avaliações)

`fluencia` | `compreensao` | `completa`

### `status` (avaliação)

`rascunho` | `agendada` | `em_andamento` | `concluida` | `cancelada`

### `status` (sessão)

`pendente` | `em_andamento` | `finalizada` | `ausente`

---

## 1. Listas de palavras (`/word-lists`)

Roles: cadastro.

### `POST /afirme-reading/word-lists` → `201`

```json
{
  "name": "Lista 1º ano",
  "kind": "PALAVRAS",
  "items": ["casa", "bola", "mesa"],
  "description": "opcional",
  "isDefault": false,
  "active": true
}
```

- `name` obrigatório
- `kind` default `PALAVRAS`
- `items`: array de strings **ou** string com palavras separadas por `,` `;` ou quebra de linha
- `isDefault: true` remove o default anterior do mesmo `kind` + escopo

**Response** — objeto `WordList`:

```json
{
  "id": "uuid",
  "name": "Lista 1º ano",
  "kind": "PALAVRAS",
  "items": ["casa", "bola", "mesa"],
  "description": null,
  "isDefault": false,
  "active": true,
  "scopeType": "PRIVATE",
  "createdAt": "2026-08-06T12:00:00",
  "updatedAt": "2026-08-06T12:00:00"
}
```

### `GET /afirme-reading/word-lists` → `200`

Query: `kind`, `active` (`true`/`false`/`1`/`0`).

Response: `WordList[]` (ordenadas: default primeiro, depois mais recentes).

### `GET /afirme-reading/word-lists/:id` → `200`

### `PATCH /afirme-reading/word-lists/:id` → `200`

Body parcial: `name`, `kind`, `items`, `description`, `isDefault`, `active`.

### `DELETE /afirme-reading/word-lists/:id` → `200`

```json
{ "message": "Lista excluída com sucesso." }
```

---

## 2. Textos de leitura (`/texts`)

Roles: cadastro.

### `POST /afirme-reading/texts` → `201`

```json
{
  "title": "A lebre e a tartaruga",
  "content": "Texto completo...",
  "gradeId": "uuid-da-serie",
  "difficultyLevel": "EASY",
  "targetSkills": ["fluência", "vocabulário"],
  "source": "opcional",
  "isCalibrated": false
}
```

Obrigatórios: `title`, `content`, `gradeId`, `difficultyLevel`.

**Response** — `ReadingText` com `questions: []`:

```json
{
  "id": "uuid",
  "title": "A lebre e a tartaruga",
  "content": "Texto completo...",
  "gradeId": "uuid",
  "grade": { "id": "uuid", "name": "1º Ano" },
  "difficultyLevel": "EASY",
  "targetSkills": ["fluência", "vocabulário"],
  "source": null,
  "isCalibrated": false,
  "scopeType": "PRIVATE",
  "questions": [],
  "createdAt": "...",
  "updatedAt": "..."
}
```

### `GET /afirme-reading/texts` → `200`

Query:

| Param | Descrição |
|-------|-----------|
| `gradeId` | Filtra série |
| `difficultyLevel` | Filtra dificuldade |
| `isCalibrated` | `true` / `false` |
| `orderBy` | `title` (default), `difficulty`, `grade` |

Response: `ReadingText[]` **sem** `questions`.

### `GET /afirme-reading/texts/:id` → `200`

Inclui `questions`.

### `PATCH /afirme-reading/texts/:id` → `200`

Body parcial: `title`, `content`, `gradeId`, `difficultyLevel`, `targetSkills`, `source`, `isCalibrated`.

### `DELETE /afirme-reading/texts/:id` → `200`

Falha se houver avaliações de leitura vinculadas.

```json
{ "message": "Texto excluído com sucesso." }
```

---

## 3. Questões de compreensão (`/texts/:textId/questions`)

Roles: cadastro. Exige permissão de escrita no texto pai.

### `POST /afirme-reading/texts/:textId/questions` → `201`

```json
{
  "statement": "O que a tartaruga fez?",
  "options": ["Correu", "Andou devagar", "Voou", "Nadou"],
  "correctOption": 1,
  "descriptor": "Identificar informação explícita"
}
```

- `statement`, `descriptor` obrigatórios
- `options`: ≥ 2 alternativas
- `correctOption`: índice 0-based (pode ser `null`)

**Response** — `ReadingQuestion`:

```json
{
  "id": "uuid",
  "readingTextId": "uuid",
  "statement": "...",
  "options": ["Correu", "Andou devagar", "Voou", "Nadou"],
  "correctOption": 1,
  "descriptor": "...",
  "createdAt": "...",
  "updatedAt": "..."
}
```

### `POST /afirme-reading/texts/:textId/questions/bulk` → `201`

Body: **array** de objetos no mesmo formato da criação unitária.

```json
[
  { "statement": "...", "options": ["A", "B"], "correctOption": 0, "descriptor": "..." }
]
```

### `GET /afirme-reading/texts/:textId/questions` → `200`

`ReadingQuestion[]` (ordem de criação).

### `GET /afirme-reading/texts/:textId/questions/:questionId` → `200`

### `PATCH /afirme-reading/texts/:textId/questions/:questionId` → `200`

Body parcial: `statement`, `descriptor`, `options`, `correctOption`.

### `DELETE /afirme-reading/texts/:textId/questions/:questionId` → `200`

Falha se já houver respostas de alunos vinculadas.

```json
{ "message": "Questão excluída com sucesso." }
```

---

## 4. Avaliações (`/evaluations`)

**Contexto de município obrigatório** (`@requires_city_context`):

- Header `X-City-ID` ou `X-City-Slug`, ou subdomínio da cidade
- Admin sem cidade → `403`

Dados em schema **tenant** (por município).

### `POST /afirme-reading/evaluations` → `201` (cadastro)

```json
{
  "title": "Diagnóstico 1º bimestre",
  "description": "opcional",
  "readingTextId": "uuid",
  "wordsWordListId": "uuid",
  "uncommonWordListId": "uuid",
  "gradeId": "uuid",
  "classIds": [],
  "schoolIds": [],
  "assessmentType": "completa",
  "timezone": "America/Sao_Paulo"
}
```

Regras:

- `title`, `readingTextId` obrigatórios
- `assessmentType` default `completa`
- Para `fluencia` ou `completa`: `wordsWordListId` obrigatório
- Status inicial: `rascunho`
- Texto e listas devem estar **visíveis** ao usuário

**Response** — `ReadingEvaluation`:

```json
{
  "id": "uuid",
  "title": "Diagnóstico 1º bimestre",
  "description": null,
  "readingTextId": "uuid",
  "wordsWordListId": "uuid",
  "uncommonWordListId": "uuid",
  "gradeId": "uuid",
  "grade": { "id": "uuid", "name": "1º Ano" },
  "classIds": [],
  "schoolIds": [],
  "assessmentType": "completa",
  "status": "rascunho",
  "applicationStart": null,
  "applicationEnd": null,
  "timezone": "America/Sao_Paulo",
  "createdAt": "...",
  "updatedAt": "..."
}
```

### `GET /afirme-reading/evaluations` → `200` (aplicação)

Query: `status`, `assessmentType`.

### `GET /afirme-reading/evaluations/:id` → `200` (aplicação)

Query: `includeSessions=true` → inclui `sessions: Session[]` (sem answers).

### `PATCH /afirme-reading/evaluations/:id` → `200` (cadastro)

Body parcial: `title`, `description`, `readingTextId`, `wordsWordListId`, `uncommonWordListId`, `assessmentType`, `gradeId`, `classIds`, `schoolIds`, `applicationStart`, `applicationEnd`, `timezone`, `status`.

Datas: ISO-8601 (`2026-08-06T08:00:00` ou com `Z`).

Bloqueado se status `concluida` ou `cancelada`.

### `DELETE /afirme-reading/evaluations/:id` → `200` (cadastro)

Bloqueado se status `em_andamento`.

```json
{ "message": "Avaliação excluída com sucesso." }
```

### `POST /afirme-reading/evaluations/:id/apply` → `200` (cadastro)

Aplica a turmas e cria sessões por aluno.

```json
{
  "classIds": ["uuid-turma-1", "uuid-turma-2"],
  "applicationStart": "2026-08-10T08:00:00",
  "applicationEnd": "2026-08-20T18:00:00"
}
```

- Se omitir `classIds`, usa os da avaliação
- Pelo menos uma turma obrigatória
- Status da avaliação → `agendada`
- Sessões novas: `pendente`; alunos já com sessão são ignorados (`sessionsSkipped`)

**Response:**

```json
{
  "evaluationId": "uuid",
  "status": "agendada",
  "sessionsCreated": 28,
  "sessionsSkipped": 2,
  "totalStudents": 30
}
```

---

## 5. Sessões de aplicação

Roles: aplicação. Contexto de município obrigatório.

Fluxo sugerido no frontend:

1. `GET .../sessions` — lista alunos/sessões
2. `POST .../sessions/:id/start` — inicia
3. `PATCH .../fluency` e/ou `POST .../comprehension-answers` — salva progresso
4. `POST .../submit` — finaliza  
   ou `POST .../absent` — marca ausência

### `GET /afirme-reading/evaluations/:evaluationId/sessions` → `200`

`Session[]` (com `studentName` quando disponível).

### `GET /afirme-reading/evaluations/:evaluationId/sessions/:sessionId` → `200`

Inclui `answers`.

**Shape `Session`:**

```json
{
  "id": "uuid",
  "readingEvaluationId": "uuid",
  "studentId": "uuid",
  "studentName": "Maria Silva",
  "classId": "uuid",
  "status": "pendente",
  "fluencyData": null,
  "comprehensionCorrectCount": null,
  "comprehensionTotal": null,
  "comprehensionScore": null,
  "startedAt": null,
  "submittedAt": null,
  "appliedBy": null,
  "createdAt": "...",
  "updatedAt": "...",
  "answers": [
    {
      "id": "uuid",
      "sessionId": "uuid",
      "readingTextQuestionId": "uuid",
      "selectedOption": 1,
      "isCorrect": true,
      "createdAt": "..."
    }
  ]
}
```

(`answers` só no GET da sessão e após salvar compreensão / submit.)

### `POST .../sessions/:sessionId/start` → `200`

- Avaliação deve estar `agendada` ou `em_andamento`
- Sessão não pode estar `finalizada` / `ausente`
- Sessão → `em_andamento`; se avaliação era `agendada` → `em_andamento`
- Preenche `startedAt` e `appliedBy`

### `PATCH .../sessions/:sessionId/fluency` → `200`

Só se `assessmentType` ∈ `fluencia` | `completa`.

```json
{
  "fluencyData": {
    "wordsCorrect": 40,
    "wordsTotal": 50,
    "timeSeconds": 60,
    "ppm": 80,
    "errors": []
  }
}
```

Também aceita o objeto de fluência **direto no root** (sem wrapper).

`fluencyData` é JSON livre (o backend persiste o objeto; o frontend define a estrutura CAEd).

Sessão deve estar `em_andamento` ou `pendente` (neste caso promove para `em_andamento`).

### `POST .../sessions/:sessionId/comprehension-answers` → `200`

Só se `assessmentType` ∈ `compreensao` | `completa`.

```json
{
  "answers": [
    { "readingTextQuestionId": "uuid", "selectedOption": 1 },
    { "readingTextQuestionId": "uuid", "selectedOption": 0 }
  ]
}
```

Ou body = array direto de respostas.

- Upsert por questão (atualiza se já existir)
- Recalcula `comprehensionCorrectCount`, `comprehensionTotal`, `comprehensionScore` (0–100)
- Response inclui `answers`

### `POST .../sessions/:sessionId/submit` → `200`

Finaliza sessão (`finalizada` + `submittedAt`).  
Se não restar sessão `pendente`/`em_andamento`, avaliação → `concluida`.  
Idempotente se já `finalizada`.

### `POST .../sessions/:sessionId/absent` → `200`

Marca `ausente` + `submittedAt`. Bloqueado se já `finalizada`.

---

## Fluxo de produto (resumo)

```
[Catálogo GLOBAL/CITY/PRIVATE]
  Textos + Questões
  Word lists (PALAVRAS / POUCO_COMUNS)
        │
        ▼
[Tenant] Avaliação (rascunho)
        │  POST /apply
        ▼
  agendada + N sessões pendentes
        │  start → fluency / comprehension → submit|absent
        ▼
  em_andamento → concluida (quando todas as sessões encerram)
```

Fluxo paralelo — **Leitura Guiada** (não usa `/evaluations`):

```
GET /texts + GET /students/...
  → grava áudio + correção no frontend
  → POST /guided-sessions (métricas + answers)
  → POST /guided-sessions/:id/audio
  → GET /guided-sessions/:id  (audioUrl = path autenticado)
  → GET audioUrl com JWT → blob URL no <audio>
```

---

## 6. Leitura Guiada (`/guided-sessions`)

Produto separado da avaliação por turma: **1 aluno + 1 texto + métricas tipadas + áudio**.

Roles: aplicação (`admin`, `tecadm`, `professor`, `coordenador`, `diretor`, `aplicador`).  
Contexto de município obrigatório (`X-City-ID` / slug / subdomínio).  
Feature: `afirme_reading` (plano **plus**).

### Headers comuns (todas as rotas desta seção)

```http
Authorization: Bearer <jwt>
X-City-Slug: jaru
Content-Type: application/json
```

No upload de áudio, use `multipart/form-data` (não defina `Content-Type: application/json`).

### Cálculos no servidor

```
correctWords = max(0, wordsRead - errorsCount)
calculatedAccuracy = round(100 * correctWords / wordsRead, 2)   // se wordsRead > 0
calculatedPlcm     = round(correctWords / (readingTimeSeconds / 60), 2)  // se time > 0
```

Exemplo: `wordsRead=120`, `errorsCount=8`, `readingTimeSeconds=90` → `calculatedAccuracy=93.33`, `calculatedPlcm=74.67`.

`prosodyLevel`: inteiro **1–5**.

---

### Exemplo completo (copy-paste frontend)

#### 1) Criar sessão (após correção do professor)

```http
POST /afirme-reading/guided-sessions
Authorization: Bearer eyJ...
X-City-Slug: jaru
Content-Type: application/json
```

```json
{
  "studentId": "7e2e3d21-c0a2-42dc-983b-2d70b199bb1b",
  "readingTextId": "9190dbbc-1f81-4458-83cd-e0e445f679bd",
  "wordsRead": 120,
  "readingTimeSeconds": 90,
  "errorsCount": 8,
  "prosodyLevel": 3,
  "answers": [
    {
      "readingTextQuestionId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "selectedOption": 1
    },
    {
      "readingTextQuestionId": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
      "selectedOption": 0
    }
  ]
}
```

**Response `201`:**

```json
{
  "id": "fffbcff5-2d61-411a-8b67-90118cdc4060",
  "studentId": "7e2e3d21-c0a2-42dc-983b-2d70b199bb1b",
  "studentName": "Maria Silva",
  "classId": "3f8a1c2b-1111-2222-3333-444444444444",
  "readingTextId": "9190dbbc-1f81-4458-83cd-e0e445f679bd",
  "wordsRead": 120,
  "readingTimeSeconds": 90,
  "errorsCount": 8,
  "prosodyLevel": 3,
  "status": "finalizada",
  "calculatedPlcm": 74.67,
  "calculatedAccuracy": 93.33,
  "comprehensionCorrectCount": 1,
  "comprehensionTotal": 2,
  "comprehensionScore": 50.0,
  "audioUrl": null,
  "audioMimeType": null,
  "audioSizeBytes": null,
  "hasAudio": false,
  "appliedBy": "user-uuid-do-jwt",
  "submittedAt": "2026-08-06T14:10:42.123456",
  "createdAt": "2026-08-06T14:10:42.123456",
  "updatedAt": "2026-08-06T14:10:42.123456",
  "answers": [
    {
      "id": "ans-1",
      "sessionId": "fffbcff5-2d61-411a-8b67-90118cdc4060",
      "readingTextQuestionId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "selectedOption": 1,
      "isCorrect": true,
      "createdAt": "2026-08-06T14:10:42.123456"
    },
    {
      "id": "ans-2",
      "sessionId": "fffbcff5-2d61-411a-8b67-90118cdc4060",
      "readingTextQuestionId": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
      "selectedOption": 0,
      "isCorrect": false,
      "createdAt": "2026-08-06T14:10:42.123456"
    }
  ]
}
```

#### 2) Enviar áudio (Blob `audio/webm` do MediaRecorder)

```http
POST /afirme-reading/guided-sessions/fffbcff5-2d61-411a-8b67-90118cdc4060/audio
Authorization: Bearer eyJ...
X-City-Slug: jaru
```

Campo do form: **`audio`** (alias aceito: `file`).

```ts
const form = new FormData();
form.append("audio", blob, "leitura.webm"); // blob.type ≈ "audio/webm" | "video/webm"

const res = await fetch(
  `${API}/afirme-reading/guided-sessions/${sessionId}/audio`,
  {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "X-City-Slug": "jaru",
      // NÃO setar Content-Type — o browser define o boundary do multipart
    },
    body: form,
  }
);
const session = await res.json();
// session.hasAudio === true
// session.audioUrl === "http://localhost:5000/afirme-reading/guided-sessions/{id}/audio"
```

**Response `200`** (mesmo shape, com áudio):

```json
{
  "id": "fffbcff5-2d61-411a-8b67-90118cdc4060",
  "studentId": "7e2e3d21-c0a2-42dc-983b-2d70b199bb1b",
  "studentName": "Maria Silva",
  "status": "finalizada",
  "calculatedPlcm": 74.67,
  "calculatedAccuracy": 93.33,
  "hasAudio": true,
  "audioUrl": "http://localhost:5000/afirme-reading/guided-sessions/fffbcff5-2d61-411a-8b67-90118cdc4060/audio",
  "audioMimeType": "audio/webm",
  "audioSizeBytes": 245760
}
```

#### 3) Ouvir áudio no player (JWT obrigatório)

`audioUrl` **não** funciona como `src` anônimo em `<audio>`. Faça fetch autenticado:

```ts
async function playGuidedAudio(audioUrl: string, token: string, citySlug: string) {
  const res = await fetch(audioUrl, {
    headers: {
      Authorization: `Bearer ${token}`,
      "X-City-Slug": citySlug,
    },
  });
  if (!res.ok) throw new Error("Falha ao baixar áudio");
  const blob = await res.blob();
  const objectUrl = URL.createObjectURL(blob);
  // <audio src={objectUrl} controls />
  // URL.revokeObjectURL(objectUrl) no unmount
  return objectUrl;
}
```

#### 4) Listar / obter / excluir

```http
GET /afirme-reading/guided-sessions?studentId=7e2e3d21-c0a2-42dc-983b-2d70b199bb1b&limit=50
GET /afirme-reading/guided-sessions/fffbcff5-2d61-411a-8b67-90118cdc4060
DELETE /afirme-reading/guided-sessions/fffbcff5-2d61-411a-8b67-90118cdc4060
```

`DELETE` → `{ "message": "Sessão de leitura guiada excluída com sucesso." }`

---

### Referência rápida das rotas

| Método | Path | Body | Status |
|--------|------|------|--------|
| POST | `/guided-sessions` | JSON métricas + `answers?` | `201` |
| GET | `/guided-sessions` | query `studentId`, `readingTextId`, `status`, `limit` | `200` array |
| GET | `/guided-sessions/:id` | — | `200` + `answers` |
| POST | `/guided-sessions/:id/audio` | multipart `audio` ou `file` | `200` |
| GET | `/guided-sessions/:id/audio` | — (bytes) | `200` stream |
| DELETE | `/guided-sessions/:id` | — | `200` |

### Campos do POST create

| Campo | Tipo | Obrigatório | Notas |
|-------|------|-------------|-------|
| `studentId` | string UUID | sim | Aluno do tenant |
| `readingTextId` | string UUID | sim | Texto visível ao usuário |
| `wordsRead` | int ≥ 0 | sim | Total de palavras |
| `readingTimeSeconds` | int ≥ 0 | sim | Duração da gravação |
| `errorsCount` | int ≥ 0 | não (default 0) | ≤ `wordsRead` |
| `prosodyLevel` | int 1–5 | sim | Escala de prosódia |
| `answers` | array | não | `{ readingTextQuestionId, selectedOption }` 0-based |

### Shape `GuidedSession` (response)

| Campo | Tipo | Notas |
|-------|------|-------|
| `id` | string | |
| `studentId` / `studentName` | string | |
| `classId` | string ou null | Snapshot da turma do aluno |
| `readingTextId` | string | |
| `wordsRead` / `readingTimeSeconds` / `errorsCount` | number | |
| `prosodyLevel` | number | 1–5 |
| `status` | `em_andamento` ou `finalizada` | MVP create → `finalizada` |
| `calculatedPlcm` / `calculatedAccuracy` | number ou null | Calculados no servidor |
| `comprehensionCorrectCount` / `comprehensionTotal` / `comprehensionScore` | number ou null | Se enviou `answers` |
| `audioUrl` | string ou null | Path autenticado GET |
| `audioMimeType` / `audioSizeBytes` | string / number ou null | |
| `hasAudio` | boolean | |
| `appliedBy` | string | User do JWT |
| `submittedAt` / `createdAt` / `updatedAt` | ISO string | |
| `answers` | array | Só no GET `/:id` e no POST create |

### Áudio — regras

| Regra | Valor |
|-------|--------|
| MIME | `audio/webm`, `audio/ogg`, `audio/mp4`, `audio/mpeg`, `audio/wav`, `video/webm` |
| Tamanho máx | 40 MB (`AFIRME_READING_MAX_AUDIO_MB`) |
| Storage | MinIO bucket `afirme-reading-audio` |
| Reenvio | Substitui áudio anterior (best-effort delete) |

### Erros comuns

```json
{ "error": "studentId é obrigatório." }
```

```json
{ "error": "prosodyLevel deve ser um inteiro entre 1 e 5." }
```

```json
{ "error": "errorsCount não pode ser maior que wordsRead." }
```

```json
{ "error": "Aluno não encontrado." }
```

```json
{ "error": "Campo multipart 'audio' (ou 'file') é obrigatório." }
```

```json
{ "error": "Áudio excede o tamanho máximo permitido (40 MB)." }
```

```json
{ "error": "Sessão de leitura guiada não encontrada." }
```

```json
{ "error": "Sessão sem áudio." }
```

### Listagens auxiliares (já existentes)

- Textos: `GET /afirme-reading/texts`, `GET /afirme-reading/texts/:id` (com `questions`)
- Alunos: `GET /students/school/:schoolId`, `GET /students/classes/:classId`, etc.

---

## Checklist rápido para o frontend

1. JWT + feature `afirme_reading`
2. Em `/evaluations*` e `/guided-sessions*`: sempre enviar `X-City-ID` (ou slug/subdomínio)
3. Preferir camelCase nos bodies
4. Montar catálogo (`texts`, `word-lists`) antes de criar avaliação por turma
5. `apply` com `classIds` antes de abrir tela de aplicação CAEd
6. Persistência de fluência CAEd = objeto livre em `fluencyData`
7. Compreensão: índices 0-based alinhados a `options` / `correctOption`
8. Leitura guiada: `POST /guided-sessions` (JSON) → `POST .../audio` (Blob webm) → playback via `GET audioUrl` com JWT (fetch + blob URL)
