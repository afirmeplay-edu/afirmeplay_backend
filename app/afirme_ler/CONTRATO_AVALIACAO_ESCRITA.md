# Afirme Ler — Contrato de API: Avaliação Escrita

Base path: `/afirme-reading/written-tests`

Este contrato cobre **somente** a criação da avaliação escrita e a definição das questões dela, com
publicação. Aplicação às turmas, datas de aplicação, PDF da prova, cartão-resposta e correção
**não existem ainda** e virão em etapas futuras.

A avaliação escrita é **outra coisa** que a avaliação de fluência (`/afirme-reading/evaluations`).
Ela fica em tabelas próprias do município (`reading_written_test` e `reading_written_test_question`) e
**não aparece no Afirme Play**.

As questões vêm do banco de questões do Afirme Ler (`/afirme-reading/questions`, ver
`CONTRATO_QUESTOES.md`): `multipleChoice`, `dictation` (ditado) e `text_production` (produção escrita),
de qualquer origem (`afirme_ler` ou `afirme_play`).

---

## Requisitos comuns

| Requisito | Detalhe |
|---|---|
| Auth | Header `Authorization: Bearer <JWT>` |
| Feature | Município com a feature `afirme_reading` no plano |
| Município | **Obrigatório** em todas as rotas. Vem do token; admin envia `X-City-ID` ou `X-City-Slug` |
| Content-Type | `application/json` em `POST` e `PUT` |
| Formato | JSON em camelCase; erros `{ "error": "mensagem em português" }` |

### Perfis

| Ação | Perfis |
|---|---|
| Listar e ver (`GET`) | `admin`, `tecadm`, `professor`, `coordenador`, `diretor`, `aplicador` |
| Criar, editar, definir questões, publicar e excluir | `admin`, `tecadm`, `professor`, `coordenador`, `diretor` (**sem** `aplicador`) |

Quem pode editar, definir questões, publicar e excluir **uma** avaliação: quem criou, `admin` e
`tecadm` (do município do contexto). Outros perfis de escrita recebem `403`.

Na listagem e no detalhe, todos os perfis acima veem todas as avaliações escritas do município.

### Regras

1. **Criação**: `title`, uma ou mais séries (`gradeIds`), escolas (`schoolIds`) e turmas (`classIds`).
   Toda turma tem que ser de uma das escolas **e** de uma das séries escolhidas. Ids que não existem = `400`.
2. **Questões**: o frontend envia a lista **completa e ordenada**; ela substitui a anterior. Cada questão:
   - precisa estar visível ao usuário (mesmo escopo do banco de questões: `GLOBAL`, `CITY` do município,
     `PRIVATE` de quem envia);
   - tem que ser `multipleChoice`, `dictation` ou `text_production`;
   - não pode repetir; no máximo **20** questões.
   - A série da questão **não** precisa ser uma das séries da avaliação.
3. **Publicação**: só com **exatamente 20** questões (todos os tipos contam). Muda `status` para
   `publicada` e grava `publishedAt`.
4. Avaliação **publicada** não pode ter dados nem questões alterados, nem ser excluída (`400`).
5. **Pontuação**: a de cada questão (`value`; vazio = `1`). `totalScore` = soma.
6. `status`: `rascunho` (padrão) ou `publicada`.

### Erros barrados antes da rota

| Situação | Status | Corpo |
|---|---|---|
| Sem token / token inválido | 401 ou 422 | Formato do Flask-JWT-Extended (`{"msg": "..."}`) |
| Perfil fora da lista da rota (ex.: `aplicador` em escrita) | 403 | `{"erro": "Acesso negado. Permissões insuficientes.", "role_required": [...], "user_role": "..."}` |
| Município sem a feature `afirme_reading` | 403 | `{"erro": "Plano insuficiente", "mensagem": "..."}` |
| Sem município no contexto | 400 | `{"erro": "Contexto de município obrigatório", "mensagem": "..."}` |

### Erros comuns das rotas

| Status | `error` |
|---|---|
| 400 | `Corpo da requisição inválido.` |
| 401 | `Usuário não encontrado.` |
| 403 | `Seu perfil não pode criar ou alterar avaliações escritas.` |
| 403 | `Você não tem permissão para alterar esta avaliação.` |
| 404 | `Avaliação escrita não encontrada.` |
| 500 | `Erro interno ao processar a solicitação.` |

---

## Objetos de resposta

### Item da listagem (resumo, sem questões)

```json
{
  "id": "6f2c1d0a-7b3e-4f5a-9c8d-1e2f3a4b5c6d",
  "title": "Avaliação escrita — 1º bimestre",
  "description": "Prova impressa",
  "status": "rascunho",
  "gradeIds": ["5600f4b8-af7e-429d-b03c-f7886c046b39"],
  "schoolIds": ["0b3e6a1c-2d4f-4b8a-9c1e-3f5a7b9d1e2f"],
  "classIds": ["7c9e1a3b-5d7f-4a2c-8e0b-2d4f6a8c0e1b"],
  "createdBy": { "id": "u-123", "name": "Maria Professora" },
  "createdAt": "2026-10-26T11:00:00",
  "updatedAt": "2026-10-26T11:05:00",
  "publishedAt": null,
  "totalQuestions": 20,
  "totalScore": 22.0,
  "questionsByType": { "multipleChoice": 18, "dictation": 1, "text_production": 1 }
}
```

- `questionsByType` sempre traz as três chaves (com `0` quando não há).
- `totalQuestions` conta todas as questões da avaliação.

### Detalhe

Todos os campos do resumo, mais:

```json
{
  "grades": [{ "id": "5600f4b8-af7e-429d-b03c-f7886c046b39", "name": "1º ano" }],
  "schools": [{ "id": "0b3e6a1c-2d4f-4b8a-9c1e-3f5a7b9d1e2f", "name": "Escola Municipal A" }],
  "classes": [
    {
      "id": "7c9e1a3b-5d7f-4a2c-8e0b-2d4f6a8c0e1b",
      "name": "1º A",
      "schoolId": "0b3e6a1c-2d4f-4b8a-9c1e-3f5a7b9d1e2f",
      "gradeId": "5600f4b8-af7e-429d-b03c-f7886c046b39"
    }
  ],
  "questions": [
    {
      "order": 1,
      "id": "8b0e6c1a-2f7d-4f0e-9b1c-3d5a7e9f1a2b",
      "type": "dictation",
      "text": "Escreva a palavra que o aplicador vai ditar.",
      "dictatedWord": "borboleta",
      "value": 1.0,
      "origin": "afirme_ler",
      "scopeType": "PRIVATE",
      "...": "demais campos do Objeto Questão (CONTRATO_QUESTOES.md)"
    }
  ]
}
```

- `questions` vem na ordem da prova (`order` de 1 a N). Cada item é o **Objeto Questão** do banco de
  questões do Afirme Ler mais `order`.
- O detalhe mostra todas as questões da avaliação, mesmo as que o usuário que consulta não veria no
  banco de questões (ex.: questão `PRIVATE` de quem montou a prova).
- Se uma questão foi excluída do banco depois de entrar na avaliação, ela aparece como
  `{ "id": "...", "order": 3, "missing": true }` e a avaliação não pode ser publicada até ser trocada.

---

## 1. Criar avaliação

`POST /afirme-reading/written-tests`

Cria em `rascunho`. `createdBy` vem do token.

### Corpo

| Campo | Tipo | Obrigatório | Regra |
|---|---|---|---|
| `title` | string | Sim | Não pode ser vazio; até 255 caracteres |
| `description` | string | Não | Texto livre |
| `gradeIds` | array de UUID | Sim | Ao menos uma série. Precisam existir |
| `schoolIds` | array de UUID | Sim | Ao menos uma escola do município. Precisam existir |
| `classIds` | array de UUID | Sim | Ao menos uma turma. Cada turma é de uma das escolas e de uma das séries |
| `questions` | array de `{ id, order }` | Não | Mesmas regras de `PUT /<id>/questions` |

Ids repetidos em `gradeIds`, `schoolIds` ou `classIds` são gravados uma vez só.

### Exemplo

```json
{
  "title": "Avaliação escrita — 1º bimestre",
  "description": "Prova impressa",
  "gradeIds": ["5600f4b8-af7e-429d-b03c-f7886c046b39"],
  "schoolIds": ["0b3e6a1c-2d4f-4b8a-9c1e-3f5a7b9d1e2f"],
  "classIds": ["7c9e1a3b-5d7f-4a2c-8e0b-2d4f6a8c0e1b"],
  "questions": [
    { "id": "8b0e6c1a-2f7d-4f0e-9b1c-3d5a7e9f1a2b", "order": 1 },
    { "id": "3f1c2a7e-8d4b-4c1e-9a55-0b7e2d9c6f10", "order": 2 }
  ]
}
```

### Resposta `201`

Detalhe da avaliação, com `status: "rascunho"` e `publishedAt: null`.

### Erros (`400`)

| `error` |
|---|
| `title é obrigatório.` / `title deve ter no máximo 255 caracteres.` / `description deve ser um texto.` |
| `Informe ao menos uma série em gradeIds.` / `Informe ao menos uma escola em schoolIds.` / `Informe ao menos uma turma em classIds.` |
| `gradeIds deve ser uma lista.` (idem `schoolIds`, `classIds`) |
| `gradeIds contém ID inválido: <valor>` (idem `schoolIds`, `classIds`) |
| `Série não encontrada: <id>.` / `Escola não encontrada: <id>.` / `Turma não encontrada: <id>.` |
| `A turma <nome> não pertence às escolas escolhidas.` |
| `A turma <nome> não pertence às séries escolhidas.` |
| Erros de `questions` (seção 6) |

---

## 2. Listar avaliações

`GET /afirme-reading/written-tests`

Mais recentes primeiro.

### Query params

| Param | Tipo | Padrão | Regra |
|---|---|---|---|
| `page` | int | `1` | Maior que zero |
| `per_page` | int | `10` | Maior que zero; máximo `100` (acima disso vira 100) |
| `status` | string | — | `rascunho` ou `publicada` |
| `grade_id` | UUID | — | Avaliações que incluem essa série |
| `school_id` | UUID | — | Avaliações que incluem essa escola |
| `q` | string | — | Busca no título, sem diferenciar maiúsculas |

### Resposta `200`

Mesmo envelope da listagem de questões do Afirme Ler:

```json
{
  "data": [ { "...": "Item da listagem" } ],
  "pagination": {
    "page": 1,
    "per_page": 10,
    "total": 1,
    "pages": 1,
    "has_next": false,
    "has_prev": false,
    "next_num": null,
    "prev_num": null
  }
}
```

### Erros (`400`)

| `error` |
|---|
| `page deve ser um número inteiro.` / `page deve ser maior que zero.` (idem `per_page`) |
| `status inválido. Valores permitidos: rascunho, publicada.` |
| `grade_id deve ser um UUID.` / `school_id deve ser um UUID.` |

---

## 3. Ver avaliação

`GET /afirme-reading/written-tests/<id>`

### Resposta `200`

Detalhe da avaliação. `404` se não existir no município.

---

## 4. Editar avaliação

`PUT /afirme-reading/written-tests/<id>`

- Só em `rascunho`.
- Atualização **parcial** de `title`, `description`, `gradeIds`, `schoolIds` e `classIds`. Campos
  ausentes ficam como estão. Outros campos são ignorados (as questões têm rota própria).
- Se qualquer um de `gradeIds`, `schoolIds` ou `classIds` vier, o escopo inteiro é revalidado
  (os ausentes entram com o valor atual).

### Exemplo

```json
{
  "title": "Avaliação escrita — 1º bimestre (revisada)",
  "schoolIds": ["0b3e6a1c-2d4f-4b8a-9c1e-3f5a7b9d1e2f"],
  "classIds": ["7c9e1a3b-5d7f-4a2c-8e0b-2d4f6a8c0e1b"]
}
```

### Resposta `200`

Detalhe atualizado.

### Erros

Os `400` de escopo e de título da criação, mais:

| Status | `error` |
|---|---|
| 400 | `Avaliação publicada não pode ser alterada.` |

---

## 5. Excluir avaliação

`DELETE /afirme-reading/written-tests/<id>`

Só em `rascunho`. Apaga a avaliação e a lista de questões dela (as questões do banco continuam).

### Resposta `200`

```json
{ "message": "Avaliação excluída com sucesso." }
```

### Erros

| Status | `error` |
|---|---|
| 400 | `Avaliação publicada não pode ser excluída.` |

---

## 6. Definir as questões

`PUT /afirme-reading/written-tests/<id>/questions`

Substitui a lista inteira. Só em `rascunho`. `[]` limpa a lista.

### Corpo

```json
{
  "questions": [
    { "id": "3f1c2a7e-8d4b-4c1e-9a55-0b7e2d9c6f10", "order": 1 },
    { "id": "8b0e6c1a-2f7d-4f0e-9b1c-3d5a7e9f1a2b", "order": 2 },
    { "id": "c4d2a9e7-1b3f-4a6c-8e0d-5f7b9a1c3e5d", "order": 3 }
  ]
}
```

- `order` é a posição na prova. Se não vier, vale a posição do item na lista (1, 2, 3…).
- Os `order` têm que ser únicos e ir de 1 a N (N = quantidade de questões), sem buracos.

### Resposta `200`

Detalhe atualizado, com `questions` na nova ordem.

### Erros (`400`)

| `error` |
|---|
| `questions é obrigatório.` / `questions deve ser uma lista de {id, order}.` |
| `A avaliação aceita no máximo 20 questões.` |
| `Cada questão deve ser um objeto {id, order}.` / `Cada questão precisa de id.` |
| `Questão repetida na avaliação.` |
| `order deve ser um número inteiro.` |
| `Os valores de order devem ser únicos e de 1 a <N>.` |
| `Questão não encontrada ou sem acesso: <id>.` |
| `A questão <id> é do tipo <tipo>, que não é aceito na avaliação escrita. Tipos permitidos: multipleChoice, dictation e text_production.` |
| `Avaliação publicada não pode ser alterada.` |

---

## 7. Publicar

`POST /afirme-reading/written-tests/<id>/publish`

Sem corpo. Exige **exatamente 20** questões (todos os tipos contam) e que todas ainda existam no banco
de questões.

### Resposta `200`

Detalhe com `status: "publicada"` e `publishedAt` preenchido.

### Erros (`400`)

| `error` |
|---|
| `A avaliação precisa ter exatamente 20 questões para ser publicada (hoje tem <N>).` |
| `A questão <id> não existe mais no banco de questões. Troque-a antes de publicar.` |
| `A questão <id> é do tipo <tipo>, que não é aceito na avaliação escrita. ...` |
| `A avaliação já está publicada.` |

---

## Fluxo sugerido no frontend

1. `POST /written-tests` com título e escopo (séries → escolas → turmas).
2. Montar a prova com `GET /afirme-reading/questions?type=multipleChoice` (ou `dictation`,
   `text_production`) e enviar a lista com `PUT /written-tests/<id>/questions` a cada alteração.
3. Habilitar "Publicar" quando `totalQuestions === 20`; chamar `POST /written-tests/<id>/publish`.
4. Depois de publicada, a tela fica só leitura.
