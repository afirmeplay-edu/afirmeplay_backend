# Afirme Ler — Contrato de API: Banco de Questões

Base path: `/afirme-reading`

Este contrato cobre **somente** o cadastro de questões: criar, listar, ver e editar.
Avaliação/prova, adição de questões em avaliação, PDF, cartão-resposta e exclusão
de questão **não existem ainda** e virão em etapas futuras.

As questões ficam na mesma tabela do Afirme Play (`public.question`), com a coluna
`origin` indicando quem criou:

| `origin` | Quem criou | Visível no Afirme Ler | Visível no Afirme Play | Editável no Afirme Ler |
|---|---|---|---|---|
| `afirme_play` | Afirme Play | Sim (respeitando o escopo) | Sim | **Não** (somente leitura) |
| `afirme_ler` | Afirme Ler | Sim (respeitando o escopo) | **Não** | Sim (respeitando o escopo) |

---

## Requisitos comuns

| Requisito | Detalhe |
|---|---|
| Auth | Header `Authorization: Bearer <JWT>` |
| Feature | Município com a feature `afirme_reading` no plano |
| Município | Igual às demais rotas do Afirme Ler: vem do token; admin pode enviar `X-City-ID` ou `X-City-Slug` |
| Content-Type | `application/json` em `POST` e `PUT` |

### Perfis

| Ação | Perfis |
|---|---|
| Listar e ver (`GET`) | `admin`, `tecadm`, `professor`, `coordenador`, `diretor`, `aplicador` |
| Criar e editar (`POST`, `PUT`) | `admin`, `tecadm`, `professor`, `coordenador`, `diretor` (**sem** `aplicador`) |

### Escopo (visibilidade e edição)

Definido pelo perfil de quem cria, igual ao Afirme Play. O frontend **não** envia o escopo.

| Perfil de quem cria | `scopeType` gravado | Quem vê | Quem edita (se `origin = afirme_ler`) |
|---|---|---|---|
| `admin` | `GLOBAL` | Todos os municípios | Só `admin` |
| `tecadm` | `CITY` (município do token) | Usuários daquele município | `admin` e `tecadm` do mesmo município |
| `professor`, `coordenador`, `diretor` | `PRIVATE` | Só quem criou | `admin` e quem criou |

O município usado para `CITY` é o do contexto da requisição (token, ou header do admin). Admin sem
município no contexto vê `GLOBAL` e as próprias `PRIVATE`.

### Regras da questão do Afirme Ler

1. Só o tipo `multipleChoice` (múltipla escolha). A prova será aplicada no papel e corrigida por cartão-resposta.
2. De 2 a 8 alternativas (letras A a H), cada uma com texto ou imagem.
3. **Exatamente uma** alternativa com `isCorrect: true`.
4. O gabarito (`correct_answer` / `solution`) é calculado pelo backend e gravado como a **letra** da
   alternativa correta (`A`, `B`, `C`…), pela posição dela na lista. Vale na criação e na edição.
   O campo `solution` enviado pelo frontend é ignorado.
5. Pontuação: `value`. Se não vier, grava `1`. Se vier, tem que ser número maior que zero.

### Formato de erro

Erros das rotas de questões:

```json
{ "error": "mensagem em português" }
```

Erros barrados **antes** da rota, pelos decorators compartilhados do backend, vêm em outro formato:

| Situação | Status | Corpo |
|---|---|---|
| Sem token / token inválido | 401 ou 422 | Formato do Flask-JWT-Extended (`{"msg": "..."}`) |
| Perfil fora da lista da rota | 403 | `{"erro": "Acesso negado. Permissões insuficientes.", "role_required": [...], "user_role": "..."}` |
| Município sem a feature `afirme_reading` | 403 | `{"erro": "Plano insuficiente", "mensagem": "..."}` |
| Sem município no contexto (não-admin) | 400 | `{"erro": "Contexto de município obrigatório", "mensagem": "..."}` |

---

## Objeto Questão (resposta)

Todas as rotas devolvem a questão neste formato (o mesmo do Afirme Play, mais `origin` e `scopeType`):

```json
{
  "id": "3f1c2a7e-8d4b-4c1e-9a55-0b7e2d9c6f10",
  "number": 1,
  "title": "",
  "description": "",
  "text": "Qual palavra começa com a mesma letra de BOLA?",
  "formattedText": "<p>Qual palavra começa com a mesma letra de BOLA?</p>",
  "secondStatement": "",
  "type": "multipleChoice",
  "alternatives": [
    { "id": "A", "text": "Dado", "isCorrect": false },
    { "id": "B", "text": "Casa", "isCorrect": false },
    { "id": "C", "text": "Bota", "isCorrect": true },
    { "id": "D", "text": "Pato", "isCorrect": false }
  ],
  "options": [
    { "id": "A", "text": "Dado", "isCorrect": false },
    { "id": "B", "text": "Casa", "isCorrect": false },
    { "id": "C", "text": "Bota", "isCorrect": true },
    { "id": "D", "text": "Pato", "isCorrect": false }
  ],
  "solution": "C",
  "correct_answer": "C",
  "formattedSolution": "",
  "skills": ["5a4946d7-0b4f-4e38-ab54-ecc349817fd5"],
  "difficulty": "Básico",
  "value": 1.0,
  "topics": [],
  "version": 1,
  "subject": { "id": "4d29b4f1-7bd7-42c0-84d5-111dc7025b90", "name": "Língua Portuguesa" },
  "grade": { "id": "5600f4b8-af7e-429d-b03c-f7886c046b39", "name": "1º ano" },
  "educationStage": null,
  "createdAt": "2026-10-23T11:00:00",
  "createdBy": { "id": "u-123", "name": "Maria Professora" },
  "updatedAt": "2026-10-23T11:00:00",
  "lastModifiedBy": null,
  "origin": "afirme_ler",
  "scopeType": "PRIVATE"
}
```

Observações:

- `alternatives` e `options` são o mesmo array. Cada alternativa volta só com `id`, `text`, `isCorrect`
  e, se houver, `image` (`{ "id", "type", "width", "height", "minio_bucket", "minio_object_name", "imageUrl" }`,
  com `imageUrl = "/questions/<questionId>/images/<imageId>"`).
- Defaults do formatter do Play quando o campo está vazio no banco: `number` = `1`, `difficulty` = `"Médio"`,
  `type` = `"multipleChoice"`, `value` = `1`, textos = `""`.
- Imagens do enunciado e da solução ficam no HTML como `src="/questions/<questionId>/images/<imageId>"`.
  Essa rota do Play continua servindo a imagem também para questões do Afirme Ler.
- `skills` é um array, mas o backend guarda só **uma** habilidade (UUID de `public.skills`).

---

## 1. Criar questão

`POST /afirme-reading/questions`

Perfis: `admin`, `tecadm`, `professor`, `coordenador`, `diretor`.

### Corpo

Mesmo corpo do `POST /questions` do Afirme Play. `createdBy` **não** é enviado; vem do token.

| Campo | Tipo | Obrigatório | Regra |
|---|---|---|---|
| `text` | string | Sim | Enunciado simples. Não pode ser vazio |
| `formattedText` | string (HTML) | Não | Imagens em base64 (`data:image/...`) são enviadas ao MinIO |
| `secondStatement` | string | Não | Texto de apoio |
| `type` | string | Sim | Só `multipleChoice` (aceita também `multiple_choice`; grava `multipleChoice`) |
| `subjectId` | string | Sim | Id de `public.subject`. Precisa existir |
| `grade` | string (UUID) ou `{ "id": "<uuid>" }` | Sim | Id de `public.grade`. Precisa existir |
| `educationStageId` | string (UUID) | Não | Id de `public.education_stage`. Se enviado, precisa existir. `""` vira `null` |
| `difficulty` | string | Não | Valores usados no Play: `Abaixo do Básico`, `Básico`, `Adequado`, `Avançado` |
| `skills` | string (UUID) ou array | Não | Se vier array, só o primeiro é gravado |
| `value` | number | Não | Maior que zero. Se não vier: `1` |
| `topics` | array | Não | Livre |
| `options` | array | Sim | Ver regras acima: 2 a 8 alternativas, exatamente uma com `isCorrect: true` |
| `formattedSolution` | string (HTML) | Não | Resolução comentada |
| `number`, `title`, `description`, `command`, `subtitle` | — | Não | Mesmos campos opcionais do Play |

Cada alternativa em `options`:

| Campo | Tipo | Regra |
|---|---|---|
| `id` | string | Opcional. Recomendado: a letra (`"A"`, `"B"`…) |
| `text` | string | Texto. Obrigatório se não houver `image` |
| `image` | string (data-URL/base64) ou objeto | Opcional. É enviada ao MinIO |
| `isCorrect` | boolean | `true` em exatamente uma. Precisa ser booleano (`true`/`false`, não `"true"`) |

### Exemplo

```http
POST /afirme-reading/questions
Authorization: Bearer <JWT>
Content-Type: application/json
```

```json
{
  "text": "Qual palavra começa com a mesma letra de BOLA?",
  "formattedText": "<p>Qual palavra começa com a mesma letra de BOLA?</p>",
  "type": "multipleChoice",
  "subjectId": "4d29b4f1-7bd7-42c0-84d5-111dc7025b90",
  "grade": "5600f4b8-af7e-429d-b03c-f7886c046b39",
  "difficulty": "Básico",
  "skills": "5a4946d7-0b4f-4e38-ab54-ecc349817fd5",
  "options": [
    { "id": "A", "text": "Dado", "isCorrect": false },
    { "id": "B", "text": "Casa", "isCorrect": false },
    { "id": "C", "text": "Bota", "isCorrect": true },
    { "id": "D", "text": "Pato", "isCorrect": false }
  ]
}
```

### Resposta `201`

Objeto Questão (seção acima), com `origin: "afirme_ler"`, `version: 1`, `correct_answer: "C"`, `value: 1.0`.

### Erros

| Status | `error` |
|---|---|
| 400 | `Corpo da requisição inválido.` |
| 400 | `text é obrigatório.` / `type é obrigatório.` / `subjectId é obrigatório.` / `grade é obrigatório.` |
| 400 | `grade deve ser o UUID de uma série.` / `educationStageId deve ser um UUID.` |
| 400 | `No Afirme Ler só é permitido o tipo multipleChoice (múltipla escolha).` |
| 400 | `options é obrigatório e deve ser uma lista de alternativas.` |
| 400 | `Informe pelo menos 2 alternativas.` / `Informe no máximo 8 alternativas (letras A a H).` |
| 400 | `A alternativa B deve ser um objeto.` / `A alternativa B precisa de texto ou imagem.` |
| 400 | `isCorrect da alternativa B deve ser true ou false.` |
| 400 | `Marque exatamente uma alternativa correta (isCorrect: true).` |
| 400 | `value deve ser um número maior que zero.` |
| 400 | `Disciplina (subjectId) não encontrada.` / `Série (grade) não encontrada.` / `Etapa de ensino (educationStageId) não encontrada.` |
| 400 | `Não foi possível identificar o município para criar conteúdo municipal.` (tecadm sem município) |
| 401 | `Usuário não encontrado.` |
| 403 | `Seu perfil não pode cadastrar ou editar questões.` (ex.: `aplicador`) |
| 500 | `Erro interno ao processar a solicitação.` |

---

## 2. Listar questões

`GET /afirme-reading/questions`

Perfis: `admin`, `tecadm`, `professor`, `coordenador`, `diretor`, `aplicador`.

Lista as questões **visíveis ao usuário** (escopo), das duas origens, mais recentes primeiro.

### Query params

| Param | Tipo | Padrão | Regra |
|---|---|---|---|
| `page` | int | `1` | Maior que zero |
| `per_page` | int | `10` | Maior que zero; máximo `100` (acima disso vira 100) |
| `type` | string | — | `multipleChoice` (ou `multiple_choice`) traz as duas grafias gravadas no banco; outros valores filtram exato |
| `subject_id` | string | — | Id da disciplina |
| `grade_id` | string (UUID) | — | Id da série |
| `difficulty` | string | — | Igualdade exata (ex.: `Básico`) |
| `origin` | string | — | `afirme_play` ou `afirme_ler` |
| `q` | string | — | Busca no enunciado (`text` e `formattedText`), sem diferenciar maiúsculas |

Observação: questões do Play de outros tipos (ex.: `ligar_colunas`) também aparecem se não houver filtro
de `type`. Para montar a prova do Afirme Ler, use `type=multipleChoice`.

### Exemplo

```http
GET /afirme-reading/questions?page=1&per_page=10&type=multipleChoice&subject_id=4d29b4f1-7bd7-42c0-84d5-111dc7025b90&q=bola
Authorization: Bearer <JWT>
```

### Resposta `200`

Mesmo envelope do `GET /test/` do Afirme Play:

```json
{
  "data": [
    { "id": "3f1c2a7e-8d4b-4c1e-9a55-0b7e2d9c6f10", "text": "Qual palavra começa com a mesma letra de BOLA?", "origin": "afirme_ler", "scopeType": "PRIVATE", "...": "demais campos do Objeto Questão" },
    { "id": "da91cd03-645c-4895-9798-5d0124d7ae7f", "text": "2. Qual palavra começa com a mesma letra de BOLA?", "origin": "afirme_play", "scopeType": "GLOBAL", "...": "demais campos do Objeto Questão" }
  ],
  "pagination": {
    "page": 1,
    "per_page": 10,
    "total": 2,
    "pages": 1,
    "has_next": false,
    "has_prev": false,
    "next_num": null,
    "prev_num": null
  }
}
```

### Erros

| Status | `error` |
|---|---|
| 400 | `page deve ser um número inteiro.` / `page deve ser maior que zero.` |
| 400 | `per_page deve ser um número inteiro.` / `per_page deve ser maior que zero.` |
| 400 | `grade_id deve ser um UUID.` |
| 400 | `origin inválido. Valores permitidos: afirme_play, afirme_ler.` |
| 401 | `Usuário não encontrado.` |
| 500 | `Erro interno ao processar a solicitação.` |

---

## 3. Ver questão

`GET /afirme-reading/questions/<id>`

Perfis: `admin`, `tecadm`, `professor`, `coordenador`, `diretor`, `aplicador`.

Aplica o **mesmo filtro de escopo** da listagem: se a questão existe mas não é visível ao usuário,
a resposta é `404`.

### Resposta `200`

Objeto Questão.

### Erros

| Status | `error` |
|---|---|
| 401 | `Usuário não encontrado.` |
| 404 | `Questão não encontrada.` |
| 500 | `Erro interno ao processar a solicitação.` |

---

## 4. Editar questão

`PUT /afirme-reading/questions/<id>`

Perfis: `admin`, `tecadm`, `professor`, `coordenador`, `diretor`.

- Só questões com `origin = "afirme_ler"`. Questões do Afirme Play são somente leitura.
- Só quem tem permissão pelo escopo (tabela "Escopo" acima).
- Atualização **parcial**: envie só os campos que mudam (mesmos campos e regras da criação).
  Campos ausentes ficam como estão.
- Se `options` vier, substitui a lista inteira de alternativas.
- Tipo e gabarito são **revalidados** no estado final (mesmo sem enviar `options`), e `correct_answer`
  é recalculado como letra.
- `version` sobe 1 a cada edição. `lastModifiedBy` passa a ser o usuário do token.
- `scopeType`, `origin` e `createdBy` não mudam.

### Exemplo

```json
{
  "value": 2,
  "options": [
    { "id": "A", "text": "Dado", "isCorrect": false },
    { "id": "B", "text": "Bola", "isCorrect": true },
    { "id": "C", "text": "Bota", "isCorrect": false }
  ]
}
```

### Resposta `200`

Objeto Questão atualizado (`correct_answer: "B"`, `version` incrementada).

### Erros

Todos os `400` da criação, mais:

| Status | `error` |
|---|---|
| 401 | `Usuário não encontrado.` |
| 403 | `Seu perfil não pode cadastrar ou editar questões.` |
| 403 | `Questões do Afirme Play são somente leitura no Afirme Ler.` |
| 403 | `Você não tem permissão para editar esta questão.` |
| 404 | `Questão não encontrada.` (não existe ou não é visível ao usuário) |
| 500 | `Erro interno ao processar a solicitação.` |

---

## Efeito no Afirme Play

Questões com `origin = "afirme_ler"`:

- não aparecem em `GET /questions/`, `GET /questions/batch`, `GET /questions/recent`, contadores de
  questões dos dashboards/estatísticas, nem no sorteio de questões de competições;
- respondem `404` em `GET /questions/<id>`, `PUT /questions/<id>`, `DELETE /questions/<id>` e
  `GET /questions/<id>/quantidade-respostas`, e são ignoradas em `DELETE /questions` (em massa);
- são recusadas em `POST /test`, `PUT /test/<id>` e `POST /competitions/<id>/questions`:

```json
{
  "error": "Questões do Afirme Ler não podem ser usadas no Afirme Play.",
  "question_ids": ["3f1c2a7e-8d4b-4c1e-9a55-0b7e2d9c6f10"]
}
```

(`question_ids` só nas rotas de `/test`.)

A rota de imagem `GET /questions/<id>/images/<imageId>` continua funcionando para as duas origens.
