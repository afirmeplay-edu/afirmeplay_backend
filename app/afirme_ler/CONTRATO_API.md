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
| 409 | Aluno já tem aplicação `finalizada` nesta avaliação (`POST /fluency-sessions`) |
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
| Cadastro e aplicação | `admin`, `tecadm`, `professor`, `coordenador`, `diretor`, `aplicador` | Textos, listas, questões, CRUD de avaliação e realização (`/fluency-sessions`) |

`aplicador` tem o **mesmo** acesso de professor / coordenador / diretor neste módulo.

### Permissões da avaliação (instrumento)

| Ação | Criador | Admin / Tecadm | Demais |
|------|---------|----------------|--------|
| Listar / visualizar | as próprias | todas do município | só as que criou |
| Editar | sim | só se for o criador | só as que criou |
| Excluir | sim | todas do município | só as que criou |
| Aplicar (`/fluency-sessions`) | sim | só as que **eles** criaram | só as que criou |

---

## Escopo de catálogo (textos e word-lists)

Resolvido automaticamente no create (não envie `scopeType`):

| Role | `scopeType` |
|------|-------------|
| `admin` | `GLOBAL` |
| `tecadm` | `CITY` (município do usuário) |
| `professor` / `coordenador` / `diretor` / `aplicador` | `PRIVATE` (dono = usuário) |

Visibilidade na listagem: GLOBAL + CITY do município atual + PRIVATE do usuário.

Edição/exclusão: `admin` pode tudo; conteúdo GLOBAL só `admin`; CITY só `tecadm` do município; PRIVATE só o dono.

---

## Enums

### `difficultyLevel` (textos)

`VERY_EASY` | `EASY` | `MEDIUM` | `HARD` | `VERY_HARD`

### `kind` (listas de palavras)

`PALAVRAS_CONHECIDAS` | `POUCO_COMUNS`

(`PALAVRAS` ainda é aceito como alias e gravado como `PALAVRAS_CONHECIDAS`.)

### `evaluationKind` (avaliações)

`entrada` | `formativa` | `saida`

| Valor | Rótulo |
|-------|--------|
| `entrada` | Avaliação de Entrada |
| `formativa` | Avaliação Formativa |
| `saida` | Avaliação de Saída |

Toda avaliação é de **fluência leitora** (Q1 conhecidas + Q2 pouco comuns + Q3 texto + compreensão). Não existe mais `assessmentType` no contrato.

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
  "kind": "PALAVRAS_CONHECIDAS",
  "gradeId": "uuid-da-serie",
  "items": ["casa", "bola", "mesa"],
  "description": "opcional",
  "isDefault": false,
  "active": true
}
```

- `name` e `gradeId` obrigatórios
- `kind` default `PALAVRAS_CONHECIDAS`
- `items`: array de strings **ou** string com palavras separadas por `,` `;` ou quebra de linha
- `isDefault: true` remove o default anterior do mesmo `kind` + série + escopo

**Response** — objeto `WordList`:

```json
{
  "id": "uuid",
  "name": "Lista 1º ano",
  "kind": "PALAVRAS_CONHECIDAS",
  "gradeId": "uuid-da-serie",
  "grade": { "id": "uuid-da-serie", "name": "1º Ano" },
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

Query: `kind`, `active` (`true`/`false`/`1`/`0`), `gradeId` ou `gradeIds` (CSV).

Com `gradeId` / `gradeIds`: só listas **dessa(s) série(s)**. Listas sem série (`gradeId` nulo) **não** entram nesse filtro.

Response: `WordList[]` (ordenadas: default primeiro, depois mais recentes).

### `GET /afirme-reading/word-lists/:id` → `200`

### `PATCH /afirme-reading/word-lists/:id` → `200`

Body parcial: `name`, `kind`, `gradeId`, `items`, `description`, `isDefault`, `active`.

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

`questions` é **opcional**. Ausente, `null` ou `[]` cria o texto sem questões. Se enviado, cada item segue o mesmo contrato de `POST /texts/:textId/questions` (enunciado, alternativas e gabarito obrigatório). Item inválido → `400` e **nada** é persistido.

```json
{
  "title": "A lebre e a tartaruga",
  "content": "Texto completo...",
  "gradeId": "uuid-da-serie",
  "difficultyLevel": "EASY",
  "targetSkills": ["fluência", "vocabulário"],
  "questions": [
    {
      "statement": "O que a tartaruga fez?",
      "options": [
        { "text": "Correu", "isCorrect": false },
        { "text": "Andou devagar", "isCorrect": true },
        { "text": "Voou", "isCorrect": false }
      ],
      "descriptor": "Identificar informação explícita"
    }
  ]
}
```

**Response** — `ReadingText`. Sem `questions` no body → `questions: []`. Com questões → array preenchido (sempre `options` como strings + `correctOption`):

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
  "questions": [
    {
      "id": "uuid",
      "readingTextId": "uuid",
      "statement": "O que a tartaruga fez?",
      "options": ["Correu", "Andou devagar", "Voou"],
      "correctOption": 1,
      "descriptor": "Identificar informação explícita",
      "createdAt": "...",
      "updatedAt": "..."
    }
  ],
  "createdAt": "...",
  "updatedAt": "..."
}
```

### `GET /afirme-reading/texts` → `200`

Query:

| Param | Descrição |
|-------|-----------|
| `gradeId` | Filtra uma série |
| `gradeIds` | Várias séries (CSV, ex. `uuid1,uuid2`) |
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

Formato A — strings + índice da correta:

```json
{
  "statement": "O que a tartaruga fez?",
  "options": ["Correu", "Andou devagar", "Voou", "Nadou"],
  "correctOption": 1,
  "descriptor": "Identificar informação explícita"
}
```

Formato B — objetos com `isCorrect` (igual à avaliação online):

```json
{
  "statement": "O que a tartaruga fez?",
  "options": [
    { "text": "Correu", "isCorrect": false },
    { "text": "Andou devagar", "isCorrect": true },
    { "text": "Voou", "isCorrect": false },
    { "text": "Nadou", "isCorrect": false }
  ],
  "descriptor": "Identificar informação explícita"
}
```

- `statement` obrigatório (alias: `enunciado`)
- `descriptor` obrigatório
- `options`: ≥ 2 alternativas (strings **ou** `{ text, isCorrect }`)
- gabarito **obrigatório**: `correctOption` (índice 0-based) **ou** exatamente uma opção com `isCorrect: true`
- se os dois forem enviados, devem apontar para a mesma alternativa
- persistido sempre como `options: string[]` + `correctOption: number`

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

Mesmo objeto `ReadingQuestion` do POST.

### `PATCH /afirme-reading/texts/:textId/questions/:questionId` → `200`

Body **parcial**. Envie só o que mudou. Campos: `statement` (alias `enunciado`), `descriptor`, `options`, `correctOption`.

Exemplo — só enunciado e descritor:

```json
{
  "statement": "Por que a tartaruga venceu?",
  "descriptor": "Inferir informação implícita"
}
```

Exemplo — alternativas + gabarito (formato A):

```json
{
  "options": ["Porque correu mais", "Porque não desistiu", "Porque voou"],
  "correctOption": 1
}
```

Exemplo — alternativas + gabarito (formato B):

```json
{
  "options": [
    { "text": "Porque correu mais", "isCorrect": false },
    { "text": "Porque não desistiu", "isCorrect": true },
    { "text": "Porque voou", "isCorrect": false }
  ]
}
```

Regras:

- gabarito continua obrigatório se `options` ou `correctOption` forem enviados
- não é possível deixar a correta vazia (`correctOption: null` → `400`)
- resposta: objeto `ReadingQuestion` atualizado (sempre `options: string[]` + `correctOption`)

```json
{
  "id": "uuid-da-questao",
  "readingTextId": "uuid-do-texto",
  "statement": "Por que a tartaruga venceu?",
  "options": ["Porque correu mais", "Porque não desistiu", "Porque voou"],
  "correctOption": 1,
  "descriptor": "Inferir informação implícita",
  "createdAt": "...",
  "updatedAt": "..."
}
```

`PATCH /texts/:id` **não** edita questões. Use esta rota.

### `DELETE /afirme-reading/texts/:textId/questions/:questionId` → `200`

Sem body. Falha com `400` se já houver respostas de alunos vinculadas.

```json
{ "message": "Questão excluída com sucesso." }
```

`404` se a questão não existir ou não pertencer àquele texto.

---

## 4. Avaliações (`/evaluations`)

Instrumento de **fluência leitora**. Criar = escolher tipo + texto + lista conhecidas + lista pouco comuns + escopo. Realizar = `/fluency-sessions` (seção 8). Relatórios consolidados vêm depois; o `submit` da sessão é o save oficial.

**Contexto de município obrigatório** (`@requires_city_context`):

- Header `X-City-ID` ou `X-City-Slug`, ou subdomínio da cidade
- Admin sem cidade → `403`

Dados em schema **tenant** (por município).

### `POST /afirme-reading/evaluations` → `201`

```json
{
  "title": "Diagnóstico 1º bimestre",
  "description": "opcional",
  "evaluationKind": "entrada",
  "readingTextId": "uuid",
  "knownWordListId": "uuid",
  "uncommonWordListId": "uuid",
  "gradeIds": ["uuid-serie-1", "uuid-serie-2"],
  "schoolIds": ["uuid-escola"],
  "classIds": ["uuid-turma-1", "uuid-turma-2"],
  "timezone": "America/Sao_Paulo"
}
```

Regras:

- `title`, `evaluationKind`, `readingTextId` obrigatórios
- `knownWordListId` (alias: `wordsWordListId`) obrigatório — lista `PALAVRAS_CONHECIDAS`
- `uncommonWordListId` obrigatório — lista `POUCO_COMUNS`
- Escopo obrigatório: `gradeIds` (≥1 série) + `schoolIds` (≥1) + `classIds` (≥1)
- `gradeId` (singular) ainda é aceito e vira uma lista de um item
- Turmas devem pertencer às escolas **e** a alguma das séries informadas
- `studentIds` é **opcional** (omitir ou `[]`). A criação **não** exige aluno; o roster da tela de aplicar vem de `GET .../applicants`
- Texto e listas devem estar **visíveis** ao usuário
- Texto e listas devem ter série ∈ `gradeIds` (senão `400`)
- Status inicial: `rascunho`
- `aplicador` pode criar (mesmo grupo de professor)

**Response** — resumo `ReadingEvaluation`:

```json
{
  "id": "uuid",
  "title": "Diagnóstico 1º bimestre",
  "description": null,
  "evaluationKind": "entrada",
  "evaluationKindLabel": "Avaliação de Entrada",
  "readingTextId": "uuid",
  "knownWordListId": "uuid",
  "wordsWordListId": "uuid",
  "uncommonWordListId": "uuid",
  "gradeIds": ["uuid-serie-1", "uuid-serie-2"],
  "grades": [
    { "id": "uuid-serie-1", "name": "1º Ano" },
    { "id": "uuid-serie-2", "name": "2º Ano" }
  ],
  "gradeId": "uuid-serie-1",
  "grade": { "id": "uuid-serie-1", "name": "1º Ano" },
  "classIds": ["uuid-turma-1", "uuid-turma-2"],
  "schoolIds": ["uuid-escola"],
  "studentIds": [],
  "status": "rascunho",
  "createdBy": { "id": "user-uuid", "name": "Maria Professora" },
  "applicationStart": null,
  "applicationEnd": null,
  "timezone": "America/Sao_Paulo",
  "createdAt": "...",
  "updatedAt": "..."
}
```

### `GET /afirme-reading/evaluations` → `200`

Query: `status`, `evaluationKind`.

Admin/tecadm: todas do município. Demais roles: **somente as que criaram**.

### `GET /afirme-reading/evaluations/:id` → `200` (visualizar)

Ficha completa: escopo (escolas, séries, turmas, alunos), texto anexado (com questões) e as duas listas.

Query: `includeSessions=true` → inclui `sessions` das sessões antigas em lote (opcional).

Quem não for criador (nem admin/tecadm) recebe `403`.

**Response (trecho da ficha):**

```json
{
  "id": "uuid",
  "title": "Diagnóstico 1º bimestre",
  "evaluationKind": "entrada",
  "evaluationKindLabel": "Avaliação de Entrada",
  "status": "rascunho",
  "createdBy": { "id": "user-uuid", "name": "Maria Professora" },
  "readingText": {
    "id": "uuid",
    "title": "A lebre e a tartaruga",
    "questions": []
  },
  "knownWordList": {
    "id": "uuid",
    "name": "Lista 1º ano",
    "kind": "PALAVRAS_CONHECIDAS",
    "items": ["casa", "bola"]
  },
  "uncommonWordList": {
    "id": "uuid",
    "name": "Pouco comuns 1º ano",
    "kind": "POUCO_COMUNS",
    "items": ["nave", "cristal"]
  },
  "scope": {
    "grades": [
      { "id": "uuid-serie-1", "name": "1º Ano" },
      { "id": "uuid-serie-2", "name": "2º Ano" }
    ],
    "grade": { "id": "uuid-serie-1", "name": "1º Ano" },
    "schools": [{ "id": "uuid", "name": "EMEF Centro" }],
    "classes": [{ "id": "uuid", "name": "A", "schoolId": "uuid", "gradeId": "uuid" }],
    "students": []
  }
}
```

`scope.students` só lista `studentIds` persistidos na avaliação (em geral vazio). O roster para aplicar é `GET .../applicants`.

### `GET /afirme-reading/evaluations/:id/applicants` → `200`

Tela de aplicar: turmas do escopo com os alunos atuais, e o status da aplicação de cada um.

Só o **criador** (quem pode aplicar). Admin/tecadm vêem só se forem o criador.

Alunos = matrícula atual das turmas (`classIds`) da avaliação, filtrados pelas séries (`gradeIds`) e escolas. Se a avaliação tiver `studentIds` preenchido, restringe a esses alunos.

**Response:**

```json
{
  "evaluationId": "uuid",
  "evaluationTitle": "Diagnóstico 1º bimestre",
  "evaluationKind": "entrada",
  "evaluationKindLabel": "Avaliação de Entrada",
  "gradeIds": ["uuid-serie"],
  "grades": [{ "id": "uuid-serie", "name": "1º Ano" }],
  "grade": { "id": "uuid-serie", "name": "1º Ano" },
  "classes": [
    {
      "id": "uuid-turma-a",
      "name": "A",
      "schoolId": "uuid-escola",
      "schoolName": "EMEF Centro",
      "gradeId": "uuid-serie",
      "students": [
        {
          "id": "uuid-aluno-1",
          "name": "Ana Souza",
          "classId": "uuid-turma-a",
          "schoolId": "uuid-escola",
          "application": null,
          "canStart": true,
          "canContinue": false,
          "canView": false
        },
        {
          "id": "uuid-aluno-2",
          "name": "Bruno Lima",
          "classId": "uuid-turma-a",
          "schoolId": "uuid-escola",
          "application": {
            "sessionId": "uuid-sessao",
            "status": "em_andamento",
            "startedAt": "2026-08-24T11:00:00",
            "submittedAt": null
          },
          "canStart": false,
          "canContinue": true,
          "canView": false
        },
        {
          "id": "uuid-aluno-3",
          "name": "Carla Dias",
          "classId": "uuid-turma-a",
          "schoolId": "uuid-escola",
          "application": {
            "sessionId": "uuid-sessao-ok",
            "status": "finalizada",
            "startedAt": "2026-08-24T09:00:00",
            "submittedAt": "2026-08-24T09:18:00"
          },
          "canStart": false,
          "canContinue": false,
          "canView": true
        }
      ]
    }
  ]
}
```

Como usar no frontend:

| Flag | Ação |
|------|------|
| `canStart` | `POST /fluency-sessions` `{ evaluationId, studentId }` |
| `canContinue` | `GET /fluency-sessions/{sessionId}` e retomar o wizard |
| `canView` | `GET /fluency-sessions/{sessionId}/report` (ou o GET da sessão) |
| `application.status == "ausente"` | `canStart: true` — permite nova sessão |

### `PATCH /afirme-reading/evaluations/:id` → `200`

**Somente o criador.** Body parcial: `title`, `description`, `evaluationKind`, `readingTextId`, `knownWordListId` / `wordsWordListId`, `uncommonWordListId`, `gradeIds` (ou `gradeId`), `classIds`, `schoolIds`, `studentIds`, `applicationStart`, `applicationEnd`, `timezone`, `status`.

Datas: ISO-8601 (`2026-08-06T08:00:00` ou com `Z`).

Bloqueado se status `concluida` ou `cancelada`. Admin/tecadm **não** editam avaliação de terceiro.

### `DELETE /afirme-reading/evaluations/:id` → `200`

Criador **ou** admin/tecadm. Bloqueado se status `em_andamento` ou se já houver aplicações em `/fluency-sessions`.

```json
{ "message": "Avaliação excluída com sucesso." }
```

### `POST /afirme-reading/evaluations/:id/apply` → `200`

Caminho legado (lote por turma). A realização oficial é `POST /fluency-sessions`. Só o criador pode aplicar.

```json
{
  "classIds": ["uuid-turma-1", "uuid-turma-2"],
  "studentIds": ["uuid-aluno"],
  "applicationStart": "2026-08-10T08:00:00",
  "applicationEnd": "2026-08-20T18:00:00"
}
```

- Se omitir `classIds` / `studentIds`, usa os da avaliação
- Informe ao menos uma turma **ou** alunos
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

## 5. Sessões de aplicação (Fluência Leitora)

Roles: aplicação. Contexto de município obrigatório.  
Base: `/afirme-reading/evaluations/:evaluationId/sessions`

### Divisão de responsabilidades

| Responsabilidade | Quem |
|------------------|------|
| STT / microfone / contagem Q1–Q3 | Frontend (Web Speech + override do professor) |
| Envio de contagens + extras | Frontend → `PATCH .../fluency` |
| Cálculo PLCM, precisão, níveis, ICA | **Backend** |
| Gabarito de compreensão | **Backend** |
| Persistência e relatório | **Backend** |

> O front **não** envia só áudio nesta sessão oficial sob `/evaluations`.  
> Para o wizard CAEd ad-hoc com áudio por parte, use `/fluency-sessions` (seção 8).  
> `PATCH .../fluency` agora faz **merge incremental** (partes omitidas são preservadas).

### Rotas da sessão (referência rápida)

| Método | Path | Status | Função |
|--------|------|--------|--------|
| `GET` | `/evaluations/:evaluationId/sessions` | `200` | Lista sessões da avaliação |
| `GET` | `/evaluations/:evaluationId/sessions/:sessionId` | `200` | Detalhe da sessão (+ `answers`) |
| `POST` | `/evaluations/:evaluationId/sessions/:sessionId/start` | `200` | Inicia aplicação |
| `PATCH` | `/evaluations/:evaluationId/sessions/:sessionId/fluency` | `200` | Salva Q1/Q2/Q3; backend calcula métricas |
| `GET` | `/evaluations/:evaluationId/sessions/:sessionId/report` | `200` | Relatório Leiturômetro (PLCM/ICA) |
| `POST` | `/evaluations/:evaluationId/sessions/:sessionId/comprehension-answers` | `200` | Respostas de compreensão + recalcula ICA |
| `POST` | `/evaluations/:evaluationId/sessions/:sessionId/submit` | `200` | Finaliza sessão |
| `POST` | `/evaluations/:evaluationId/sessions/:sessionId/absent` | `200` | Marca ausência |

Fluxo sugerido no frontend:

1. `GET .../sessions` — lista alunos/sessões  
2. `POST .../sessions/:sessionId/start` — inicia  
3. `PATCH .../sessions/:sessionId/fluency` — Q1 / Q2 / Q3  
4. `POST .../sessions/:sessionId/comprehension-answers` — se `completa` e Q3 feito  
5. `GET .../sessions/:sessionId/report` — Leiturômetro  
6. `POST .../sessions/:sessionId/submit` — finaliza  
   ou `POST .../sessions/:sessionId/absent` — ausência  

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
  "calculatedPlcm": null,
  "calculatedAccuracy": null,
  "precisionLevel": null,
  "fluencyLevel": null,
  "icaScore": null,
  "icaBreakdown": null,
  "prosodyLevel": null,
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

### `POST /afirme-reading/evaluations/:evaluationId/sessions/:sessionId/start` → `200`

- Avaliação deve estar `agendada` ou `em_andamento`
- Sessão não pode estar `finalizada` / `ausente`
- Sessão → `em_andamento`; se avaliação era `agendada` → `em_andamento`
- Preenche `startedAt` e `appliedBy`

**Response:** `Session`.

### `PATCH /afirme-reading/evaluations/:evaluationId/sessions/:sessionId/fluency` → `200`

Parte da realização (Q1/Q2/Q3). Sempre disponível na avaliação de fluência leitora.

O backend **calcula** PLCM, precisão, níveis e ICA. O cliente envia contagens por questão (e extras); pode sobrescrever marcações do STT do protótipo.

**Request:**

```http
PATCH /afirme-reading/evaluations/{evaluationId}/sessions/{sessionId}/fluency
Authorization: Bearer <jwt>
X-City-Slug: jaru
Content-Type: application/json
```

```json
{
  "kind": "FLUENCY",
  "caderno": "A",
  "notReadReason": null,
  "prosodyLevel": 3,
  "q1": {
    "wordsRead": 55,
    "errorsCount": 3,
    "readingTimeSeconds": 60,
    "transcript": "opcional",
    "markings": [],
    "overrides": {}
  },
  "q2": {
    "wordsRead": 32,
    "errorsCount": 4,
    "readingTimeSeconds": 60
  },
  "q3": {
    "wordsRead": 120,
    "errorsCount": 8,
    "readingTimeSeconds": 90,
    "transcript": "opcional"
  },
  "extras": {
    "sttProvider": "web-speech",
    "notes": "qualquer detalhe do wizard"
  }
}
```

Também aceita:

- wrapper `{ "fluencyData": { ... } }`
- aliases `lista1`/`lista2`/`texto` no lugar de `q1`/`q2`/`q3`
- payload flat do protótipo (`wordsRead`, `errorsCount`, `readingTimeSeconds`) → mapeado para **q3**

Sessão deve estar `em_andamento` ou `pendente` (neste caso promove para `em_andamento`).

**Response `200` (trecho):**

```json
{
  "id": "session-uuid",
  "status": "em_andamento",
  "calculatedPlcm": 74.67,
  "calculatedAccuracy": 93.33,
  "precisionLevel": "Instrucional",
  "fluencyLevel": "acima",
  "icaScore": null,
  "icaBreakdown": null,
  "prosodyLevel": 3,
  "fluencyData": {
    "kind": "FLUENCY",
    "caderno": "A",
    "prosodyLevel": 3,
    "q1": {
      "wordsRead": 55,
      "errorsCount": 3,
      "readingTimeSeconds": 60,
      "accuracy": 94.55,
      "plcm": 52.0,
      "precisionLevel": "Instrucional",
      "fluencyLevel": "esperado"
    },
    "q2": {
      "wordsRead": 32,
      "errorsCount": 4,
      "readingTimeSeconds": 60,
      "accuracy": 87.5,
      "plcm": 28.0
    },
    "q3": {
      "wordsRead": 120,
      "errorsCount": 8,
      "readingTimeSeconds": 90,
      "accuracy": 93.33,
      "plcm": 74.67
    },
    "extras": { "sttProvider": "web-speech" },
    "metrics": {
      "calculatedPlcm": 74.67,
      "calculatedAccuracy": 93.33,
      "precisionLevel": "Instrucional",
      "fluencyLevel": "acima",
      "icaScore": null,
      "algorithmVersion": "1.0.0",
      "evaluationVersion": "1.0.0"
    }
  }
}
```

- `icaScore` só é preenchido quando existem **q1 + q2 + q3 + compreensão**
- Após `comprehension-answers`, o ICA é recalculado automaticamente

Fórmulas:

```
PLCM = max(0, palavrasLidas - erros) / (tempoSegundos / 60)
Precisão = max(0, palavrasLidas - erros) / palavrasLidas × 100
Nível precisão: >=95 Independente | >=90 Instrucional | <90 Frustração
Fluência 2º ano: PLCM <40 abaixo | 40–60 esperado | >60 acima
Fluência ICA = min(100, PLCM/60 × 100)
ICA = 0,25×Q1 + 0,15×Q2 + 0,30×Q3 + 0,20×Compreensão + 0,10×Fluência
```

Mapeamento protótipo → API:

| Protótipo | Backend |
|-----------|---------|
| `kind: "FLUENCY"` | `kind` no fluencyData da sessão |
| Q1 lista conhecidas | `q1` + lista `PALAVRAS_CONHECIDAS` (`knownWordListId`) |
| Q2 pouco comuns | `q2` + lista `POUCO_COMUNS` (`uncommonWordListId`) |
| Q3 texto | `q3` + `readingTextId` |

### `GET /afirme-reading/evaluations/:evaluationId/sessions/:sessionId/report` → `200`

Relatório consolidado da Fluência Leitora (Leiturômetro).

**Request:**

```http
GET /afirme-reading/evaluations/{evaluationId}/sessions/{sessionId}/report
Authorization: Bearer <jwt>
X-City-Slug: jaru
```

**Response `200`:**

```json
{
  "evaluationId": "eval-uuid",
  "evaluationTitle": "Fluência Leitora — 2º ano",
  "evaluationKind": "entrada",
  "sessionId": "session-uuid",
  "studentId": "uuid-aluno",
  "studentName": "Maria Silva",
  "classId": "uuid-turma",
  "status": "em_andamento",
  "readingTextId": "uuid-texto",
  "wordsWordListId": "uuid-lista-1",
  "uncommonWordListId": "uuid-lista-2",
  "q1": {
    "wordsRead": 55,
    "errorsCount": 3,
    "readingTimeSeconds": 60,
    "accuracy": 94.55,
    "plcm": 52.0,
    "precisionLevel": "Instrucional",
    "fluencyLevel": "esperado"
  },
  "q2": {
    "wordsRead": 32,
    "errorsCount": 4,
    "readingTimeSeconds": 60,
    "accuracy": 87.5,
    "plcm": 28.0
  },
  "q3": {
    "wordsRead": 120,
    "errorsCount": 8,
    "readingTimeSeconds": 90,
    "accuracy": 93.33,
    "plcm": 74.67,
    "precisionLevel": "Instrucional",
    "fluencyLevel": "acima"
  },
  "prosodyLevel": 3,
  "caderno": "A",
  "notReadReason": null,
  "extras": { "sttProvider": "web-speech" },
  "comprehension": {
    "correctCount": 2,
    "total": 3,
    "score": 66.67,
    "answers": []
  },
  "calculatedPlcm": 74.67,
  "calculatedAccuracy": 93.33,
  "precisionLevel": "Instrucional",
  "fluencyLevel": "acima",
  "icaScore": 88.5,
  "icaBreakdown": {
    "icaScore": 88.5,
    "weights": {
      "lista1": 0.25,
      "lista2": 0.15,
      "texto": 0.3,
      "compreensao": 0.2,
      "fluencia": 0.1
    },
    "components": {
      "lista1Accuracy": 94.55,
      "lista2Accuracy": 87.5,
      "textoAccuracy": 93.33,
      "comprehension": 66.67,
      "fluency": 100.0,
      "plcm": 74.67
    }
  },
  "startedAt": "2026-08-10T14:00:00",
  "submittedAt": null
}
```

### `POST /afirme-reading/evaluations/:evaluationId/sessions/:sessionId/comprehension-answers` → `200`

Questões de compreensão do texto. Sempre fazem parte da realização.

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
- Se já houver `fluencyData` com q1/q2/q3, **recalcula `icaScore` / `icaBreakdown`**
- Response: `Session` com `answers`

### `POST /afirme-reading/evaluations/:evaluationId/sessions/:sessionId/submit` → `200`

Finaliza sessão (`finalizada` + `submittedAt`).  
Se não restar sessão `pendente`/`em_andamento`, avaliação → `concluida`.  
Idempotente se já `finalizada`.

**Response:** `Session` (com `answers`).

### `POST /afirme-reading/evaluations/:evaluationId/sessions/:sessionId/absent` → `200`

Marca `ausente` + `submittedAt`. Bloqueado se já `finalizada`.

**Response:** `Session`.

---

## Fluxo de produto (resumo)

```
[Catálogo GLOBAL/CITY/PRIVATE]
  Textos + Questões
  Word lists (PALAVRAS_CONHECIDAS / POUCO_COMUNS)
        │
        ▼
[Tenant] Avaliação (evaluationKind + texto + 2 listas + escola/série/turmas)
        │
        ▼
GET /evaluations/:id/applicants
  (turmas do escopo + alunos atuais + status)
        │
        ▼
POST /fluency-sessions { evaluationId, studentId }
  (só o criador; 201 inicia ou retoma; 409 se já finalizada)
        │  fluency → compreensão → submit
        ▼
  sessão finalizada (save oficial; relatórios depois)
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
2. Em `/evaluations*` e `/fluency-sessions*`: sempre enviar `X-City-ID` (ou slug/subdomínio)
3. Preferir camelCase nos bodies
4. Montar catálogo com `?gradeId=` (ou `gradeIds`): textos e listas `PALAVRAS_CONHECIDAS` / `POUCO_COMUNS` da série
5. Criar avaliação: `evaluationKind` + texto + duas listas + `gradeIds` + `schoolIds` + `classIds` (sem aluno)
6. Tela aplicar: `GET /evaluations/:id/applicants` → flags `canStart` / `canContinue` / `canView`
7. Realizar: `POST /fluency-sessions` `{ evaluationId, studentId }` (só as que você criou)
8. Wizard: `PATCH .../fluency` (Q1/Q2/Q3) → `comprehension-answers` → **`POST .../submit`** (save)
9. Compreensão: índices 0-based alinhados a `options` / `correctOption`
10. Relatórios: `GET /afirme-reading/resultados/filtros`, `GET /resultados`, `GET /resultados/estudantes/:id` (seção 9)
11. Leitura guiada (manual/auto) continua à parte e **não** entra no filtro de tipo pedagógico

---

## 7. Leitura Guiada Automática (`/guided-auto-sessions`)

Mesmo produto da leitura guiada, com **correção automática**. O frontend **não** envia scores.

Roles: aplicação (`admin`, `tecadm`, `professor`, `coordenador`, `diretor`, `aplicador`).  
Contexto de município obrigatório. Feature: `afirme_reading`.

### Fluxo

```
POST /guided-auto-sessions          → cria sessão (ids + snapshot do conteúdo)
POST /guided-auto-sessions/:id/audio  (multipart) → MinIO + fila STT (202)
GET  /guided-auto-sessions/:id        → status (queued|processing|...)
GET  /guided-auto-sessions/:id/result → resultado oficial (só se completed)
GET  /guided-auto-sessions/:id/words  → alinhamento por palavra
```

### `POST /afirme-reading/guided-auto-sessions` → `201`

```json
{
  "studentId": "uuid-aluno",
  "readingTextId": "uuid-texto",
  "wordsWordListId": "uuid-lista-1",
  "uncommonWordListId": "uuid-lista-2",
  "answers": [
    { "readingTextQuestionId": "uuid-q1", "selectedOption": 1 }
  ]
}
```

- Pelo menos um de: `readingTextId`, `wordsWordListId`, `uncommonWordListId`
- **Proibido** enviar: `plcm`, `accuracy`, `ica`, `wordsRead`, `errorsCount`, `score`, etc. → `400`
- Response: status `awaiting_audio`

### `POST /afirme-reading/guided-auto-sessions/:id/audio` → `202`

Multipart:

| Campo | Obrigatório | Notas |
|-------|-------------|-------|
| `audio` ou `file` | sim | webm/ogg/mp4/mpeg/wav |
| `part` | se houver mais de uma parte | `words` \| `uncommon` \| `text` |
| `durationSeconds` | não | hint; STT pode sobrescrever |

Enfileira Celery (`queued` → `processing` → `completed` \| `failed`).  
Se a sessão tiver várias partes (listas + texto), envie um áudio por `part`. A sessão só fica `completed` quando **todas** as partes configuradas forem processadas.

### `GET .../result` → `200` | `409` | `422`

- `409` se ainda não `completed` (body inclui `status`)
- `422` se `failed`
- `200` com métricas oficiais:

```json
{
  "id": "uuid",
  "status": "completed",
  "calculatedPlcm": 74.67,
  "calculatedAccuracy": 93.33,
  "precisionLevel": "Instrucional",
  "fluencyLevel": "acima",
  "comprehensionScore": 50.0,
  "icaScore": 88.5,
  "icaBreakdown": {},
  "partResults": {
    "text": { "accuracy": 93.33, "plcm": 74.67, "transcript": "..." }
  },
  "transcriptRaw": "...",
  "sttProvider": "whisper_api",
  "sttModel": "whisper-1",
  "algorithmVersion": "1.0.0",
  "evaluationVersion": "1.0.0",
  "hasAudio": true,
  "audioUrl": "/afirme-reading/guided-auto-sessions/{id}/audio"
}
```

### Fórmulas (backend)

```
PLCM = max(0, palavrasLidas - erros) / (tempoSegundos / 60)
Precisão = max(0, palavrasLidas - erros) / palavrasLidas × 100
Nível: >=95 Independente | >=90 Instrucional | <90 Frustração
Fluência 2º ano: <40 abaixo | 40–60 esperado | >60 acima
Fluência ICA = min(100, PLCM/60 × 100)
ICA = 0,25×Lista1 + 0,15×Lista2 + 0,30×Texto + 0,20×Compreensão + 0,10×Fluência
```

ICA só é preenchido quando existem as 3 precisões + compreensão + PLCM.

### Env

| Variável | Default | Uso |
|----------|---------|-----|
| `OPENAI_API_KEY` ou `AFIRME_READING_OPENAI_API_KEY` | — | Whisper API |
| `AFIRME_READING_STT_PROVIDER` | `whisper_api` | provider STT |
| `AFIRME_READING_STT_MODEL` | `whisper-1` | modelo |
| `AFIRME_READING_MAX_AUDIO_MB` | `40` | limite upload |

### Provisionamento

Tabelas tenant via `provision_afirme_ler_for_city_schema` / DDL em `app/afirme_ler/ddl.py` (idempotente). Reaplicar nos schemas `city_*` existentes após deploy.

---

## 8. Realizar avaliação (`/fluency-sessions`)

Aplicação da **avaliação já criada**. Texto e listas vêm do instrumento; o cliente **não** escolhe material de novo.

STT / silêncio / Web Speech ficam no **frontend**. O save oficial é `POST .../submit` (recalcula ICA e marca `finalizada`). Relatórios consolidados por `evaluationKind` vêm em entrega posterior.

Só o **criador** da avaliação pode aplicar. Uma aplicação vigente por aluno:

- `em_andamento` → o POST **devolve a sessão existente** (retomar), status `201`
- `finalizada` → `409` com `sessionId` e `status` (não cria outra)
- `ausente` → permite nova sessão

Roles: as mesmas do CRUD. Contexto de município obrigatório.  
Base: `/afirme-reading/fluency-sessions`

### Rotas

| Método | Path | Status | Função |
|--------|------|--------|--------|
| `POST` | `/fluency-sessions` | `201` / `409` | Inicia ou retoma (`em_andamento`); `409` se já `finalizada` |
| `GET` | `/fluency-sessions/:id` | `200` | Detalhe (+ answers) |
| `PATCH` | `/fluency-sessions/:id/fluency` | `200` | Rascunho Q1/Q2/Q3 (**merge incremental**) |
| `POST` | `/fluency-sessions/:id/comprehension-answers` | `200` | Questões do texto + recalcula ICA |
| `POST` | `/fluency-sessions/:id/audio` | `200` | Upload multipart por parte |
| `GET` | `/fluency-sessions/:id/audio?part=` | `200` | Playback (JWT) |
| `GET` | `/fluency-sessions/:id/report` | `200` | Snapshot interno (não é o relatório de produto) |
| `POST` | `/fluency-sessions/:id/submit` | `200` | **Salvar**: recalcula ICA e finaliza |
| `POST` | `/fluency-sessions/:id/absent` | `200` | Ausência |

### `POST /fluency-sessions` → `201`

```json
{
  "evaluationId": "uuid-da-avaliacao",
  "studentId": "uuid-aluno",
  "classId": "uuid",
  "schoolId": "uuid",
  "caderno": "A"
}
```

- `evaluationId` e `studentId` obrigatórios
- Aluno deve estar no escopo: turma ∈ `classIds`, escola ∈ `schoolIds`, série ∈ `gradeIds`. `studentIds` só restringe se estiver preenchido
- `classId` / `schoolId` opcionais (preenchidos pela matrícula do aluno)
- `readingTextId`, `knownWordListId` e `uncommonWordListId` são copiados da avaliação (ignorados se enviados)

**Conflict `409` (já finalizada):**

```json
{
  "error": "Este aluno já possui aplicação finalizada nesta avaliação.",
  "sessionId": "uuid-sessao",
  "status": "finalizada"
}
```

**Response (exemplo):**

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "evaluationId": "uuid-da-avaliacao",
  "evaluationKind": "entrada",
  "studentId": "11111111-1111-1111-1111-111111111111",
  "studentName": "Maria Silva",
  "classId": "22222222-2222-2222-3333-444444444444",
  "schoolId": "33333333-3333-3333-3333-333333333333",
  "readingTextId": "44444444-4444-4444-4444-444444444444",
  "knownWordListId": "55555555-5555-5555-5555-555555555555",
  "wordsWordListId": "55555555-5555-5555-5555-555555555555",
  "uncommonWordListId": "66666666-6666-6666-6666-666666666666",
  "caderno": "A",
  "status": "em_andamento",
  "fluencyData": {
    "kind": "FLUENCY",
    "caderno": "A",
    "q1": null,
    "q2": null,
    "q3": null,
    "extras": {}
  },
  "partAudios": {},
  "hasAudio": false,
  "audioUrls": {},
  "calculatedPlcm": null,
  "calculatedAccuracy": null,
  "precisionLevel": null,
  "fluencyLevel": null,
  "icaScore": null,
  "icaBreakdown": null,
  "prosodyLevel": null,
  "comprehensionCorrectCount": null,
  "comprehensionTotal": null,
  "comprehensionScore": null,
  "startedAt": "2026-08-12T13:40:00",
  "submittedAt": null,
  "appliedBy": "user-uuid",
  "createdAt": "2026-08-12T13:40:00",
  "updatedAt": "2026-08-12T13:40:00",
  "answers": []
}
```

### `PATCH .../fluency` — merge incremental

Partes **omitidas** são preservadas. Enviar só `q1` não apaga `q2`/`q3` já salvos.  
`"q2": null` remove Q2.

Enums:

- `WordStatus`: `nao_leu` | `acertou` | `inventou` | `silabou` | `soletrou` | `errou`
- `NotReadReason`: `nao_se_aplica` | `recusou` | `nao_consegue` | `nao_sabe`
- `source` (marking): `ia` | `manual` | `timeout`

Se `skipped: true` (ou `notReadReason` ≠ `nao_se_aplica`): aceita markings vazios / zeros.

O mesmo merge incremental vale para `PATCH /evaluations/:id/sessions/:sid/fluency`.

### `POST .../audio` (multipart)

Fields: `part` = `q1` | `q2` | `q3` | `mic_test`, `audio` = blob webm/ogg.

```json
{
  "part": "q1",
  "audioUrl": "/afirme-reading/fluency-sessions/.../audio?part=q1",
  "audioMimeType": "audio/webm",
  "audioSizeBytes": 245760,
  "hasAudio": true
}
```

### ICA com skip + Leiturômetro

Pesos base: Q1 0,25 · Q2 0,15 · Q3 0,30 · Comp 0,20 · Fluência 0,10.

Partes skipped são **excluídas** e os pesos restantes **renormalizados**. Se Q3 for skipped, o componente Fluência (PLCM) também sai.

Leiturômetro (`leiturimetroLevel` 1–6) a partir do ICA:

| ICA | Nível |
|-----|-------|
| ≤ 20 | 1 |
| ≤ 40 | 2 |
| ≤ 55 | 3 |
| ≤ 70 | 4 |
| ≤ 85 | 5 |
| > 85 | 6 |

`POST .../submit` é o **salvar** da realização: recalcula ICA e marca `finalizada`.

### `GET .../report` (exemplo)

```json
{
  "sessionId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "studentId": "11111111-1111-1111-1111-111111111111",
  "studentName": "Maria Silva",
  "classId": "22222222-2222-2222-2222-222222222222",
  "schoolId": "33333333-3333-3333-3333-333333333333",
  "status": "finalizada",
  "readingTextId": "44444444-4444-4444-4444-444444444444",
  "wordsWordListId": "55555555-5555-5555-5555-555555555555",
  "uncommonWordListId": "66666666-6666-6666-6666-666666666666",
  "caderno": "A",
  "q1": {
    "wordsRead": 42,
    "lastWordPosition": 42,
    "errorsCount": 3,
    "readingTimeSeconds": 60,
    "skipped": false,
    "notReadReason": null,
    "transcript": "casa bola...",
    "markings": [
      { "index": 0, "word": "casa", "status": "acertou", "source": "manual" }
    ],
    "accuracy": 92.86,
    "plcm": 39.0,
    "hasAudio": true,
    "audioUrl": "/afirme-reading/fluency-sessions/.../audio?part=q1"
  },
  "q2": {
    "wordsRead": 0,
    "lastWordPosition": 0,
    "errorsCount": 0,
    "readingTimeSeconds": 0,
    "skipped": true,
    "notReadReason": "recusou",
    "markings": [],
    "accuracy": null,
    "plcm": null,
    "hasAudio": false
  },
  "q3": {
    "wordsRead": 90,
    "totalWords": 117,
    "errorsCount": 6,
    "unreadAfterEnd": 27,
    "readingTimeSeconds": 60,
    "skipped": false,
    "obeyedSensePauses": true,
    "lines": [
      { "lineIndex": 0, "text": "SOFIA E MARTIN...", "wrongWordsCount": 1 }
    ],
    "accuracy": 93.33,
    "plcm": 84.0,
    "hasAudio": true,
    "audioUrl": "/afirme-reading/fluency-sessions/.../audio?part=q3"
  },
  "micTest": { "hasAudio": true, "audioUrl": ".../audio?part=mic_test" },
  "prosodyLevel": 3,
  "comprehension": {
    "correctCount": 2,
    "total": 3,
    "score": 66.67,
    "answers": []
  },
  "calculatedPlcm": 84.0,
  "calculatedAccuracy": 93.33,
  "precisionLevel": "Instrucional",
  "fluencyLevel": "acima",
  "icaScore": 88.12,
  "leiturimetroLevel": 6,
  "icaBreakdown": {
    "icaScore": 88.12,
    "leiturimetroLevel": 6,
    "skippedParts": ["lista2"],
    "weights": {
      "lista1": 0.25,
      "lista2": 0.15,
      "texto": 0.3,
      "compreensao": 0.2,
      "fluencia": 0.1
    },
    "weightsUsed": {
      "lista1": 0.2941,
      "texto": 0.3529,
      "compreensao": 0.2353,
      "fluencia": 0.1176
    },
    "components": {
      "lista1Accuracy": 92.86,
      "lista2Accuracy": null,
      "textoAccuracy": 93.33,
      "comprehension": 66.67,
      "fluency": 100.0,
      "plcm": 84.0
    }
  },
  "startedAt": "2026-08-12T13:40:00",
  "submittedAt": "2026-08-12T13:55:00"
}
```

---

## 9. Resultados da fluência leitora (`/resultados`)

Três GETs. Os números são **da avaliação** (`avaliacaoId`). O backend aplica recorte geo **dentro** do escopo dela e calcula com `FluencyScoring`. O front não agrega.

Auth / feature / município: iguais ao restante do módulo.

Cálculo: só `status === "presente"` entra em perfil e IFL. Participação = `avaliados / previstos × 100`.  
IFL = Σ (% do nível × peso) / 100. Pesos: PL1 0 · PL2 1 · PL3 2,5 · PL4 4 · LI 6 · LF 10.  
LF: mais de 65 palavras corretas no **texto** e precisão ≥ 90%. PPM ≥ 60 é só taxa de velocidade.

Cascata dos selects: `ano` → `edicao` → **`avaliacaoId`** → escola / série / turma.

### `GET /afirme-reading/resultados/filtros` → `200`

```json
{
  "anos": [2026],
  "edicoes": [
    { "id": "entrada", "label": "Avaliação de Entrada" },
    { "id": "formativa", "label": "Avaliação Formativa" },
    { "id": "saida", "label": "Avaliação de Saída" }
  ],
  "avaliacoes": [
    {
      "id": "uuid-da-avaliacao",
      "titulo": "Diagnóstico 1º bimestre",
      "ano": 2026,
      "edicao": "formativa",
      "edicaoLabel": "Avaliação Formativa",
      "status": "em_andamento",
      "escolaIds": ["uuid-escola"],
      "serieIds": ["uuid-serie"],
      "turmaIds": ["uuid-turma"]
    }
  ],
  "redes": [{ "id": "uuid-cidade", "nome": "Rede Municipal" }],
  "municipios": [{ "id": "uuid-cidade", "redeId": "uuid-cidade", "nome": "Jaru" }],
  "escolas": [{ "id": "uuid", "municipioId": "uuid-cidade", "nome": "EMEF Centro" }],
  "series": [{ "id": "uuid", "nome": "3º Ano" }],
  "turmas": [{ "id": "uuid", "escolaId": "uuid", "serieId": "uuid", "nome": "3º Ano A", "turno": "Matutino" }]
}
```

O front filtra `avaliacoes` por `ano` + `edicao` (e, se quiser, por `escolaIds`). `turno`: `Matutino` | `Vespertino` | `Noturno` | `Integral`. Avaliações `cancelada` não entram.

### `GET /afirme-reading/resultados` → `200`

Query:

| Param | Obrigatório | Notas |
|---|---|---|
| `avaliacaoId` | **sim** | id do instrumento (`evaluationId` também aceito) |
| `ano` | não | se enviado, deve bater com a avaliação |
| `edicao` | não | se enviado, deve bater com `evaluationKind` |
| `redeId`, `municipioId`, `escolaId`, `serieId`, `turmaId`, `turno` | não | recorte **dentro** da avaliação |
| `por`, `itemId` | não | `escola` \| `turma` \| `estudante` |

Sem `avaliacaoId` → `400`. Avaliação inexistente / sem permissão → `404`.

```json
{
  "avaliacaoId": "uuid-da-avaliacao",
  "avaliacaoTitulo": "Diagnóstico 1º bimestre",
  "avaliacaoStatus": "em_andamento",
  "ano": 2026,
  "edicao": "formativa",
  "tituloEdicao": "Avaliação Formativa 2026",
  "escopoLabel": "Rede Municipal · Jaru · EMEF Centro · Todas as séries · Todas as turmas",
  "emitidoEm": "2026-08-26T13:06:02.000Z",
  "criterios": {
    "pesosIfl": "PL1: peso 0 · PL2: peso 1 · PL3: peso 2,5 · PL4: peso 4 · LI: peso 6 · LF: peso 10",
    "iflDescricao": "IFL = soma (percentual de cada nível × peso do nível) / 100. Escala 0 a 10. Só entram estudantes com status presente.",
    "fluencia": "Leitor Fluente (LF): mais de 65 palavras corretas no texto e precisão ≥ 90%. …"
  },
  "indicadores": {},
  "indicadoresAnteriores": null,
  "leituraAnalitica": "Na avaliação formativa 2026, foram previstos 120 estudantes. …",
  "alertas": [],
  "porEscola": [],
  "porTurma": [],
  "estudantes": []
}
```

`indicadoresAnteriores`: edição anterior **do mesmo ciclo** (turmas/escolas em comum). `formativa`←`entrada`, `saida`←`formativa`. `null` se não houver — o front esconde Δ. O delta já vem em `indicadores.distribuicao[]`.

### `GET /afirme-reading/resultados/estudantes/:id` → `200`

Query: `ano` **ou** `avaliacaoId` (recomendado os dois). `edicao` opcional. Com `avaliacaoId`, a linha do tempo usa o ciclo dessa avaliação.

`linhaDoTempo` sempre 3 itens (`entrada` → `formativa` → `saida`). `exportacao.iflDoNivel` é o peso 0–10 (LI = 6).


