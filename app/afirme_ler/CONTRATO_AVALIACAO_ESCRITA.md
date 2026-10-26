# Afirme Ler — Contrato de API: Avaliação Escrita

Base path: `/afirme-reading/written-tests`

Este contrato cobre a criação da avaliação escrita, a definição das questões dela, a publicação, a
aplicação às turmas (com data de início) e o PDF da prova (caderno de questões). Cartão-resposta,
respostas de aluno, correção e notificações **não existem ainda** e virão em etapas futuras.

A avaliação escrita é **outra coisa** que a avaliação de fluência (`/afirme-reading/evaluations`).
Ela fica em tabelas próprias do município (`reading_written_test`, `reading_written_test_question` e
`reading_written_test_class`) e **não aparece no Afirme Play**.

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
| Listar e ver (`GET`, inclusive turmas e alunos da aplicação e o PDF da prova) | `admin`, `tecadm`, `professor`, `coordenador`, `diretor`, `aplicador` |
| Criar, editar, definir questões, publicar, excluir, aplicar e retirar turma | `admin`, `tecadm`, `professor`, `coordenador`, `diretor` (**sem** `aplicador`) |

Quem pode editar, definir questões, publicar, excluir, aplicar e retirar turma de **uma** avaliação:
quem criou, `admin` e `tecadm` (do município do contexto). Outros perfis de escrita recebem `403`.

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
6. `status` da avaliação: `rascunho` (padrão) ou `publicada`. A aplicação **não** muda esse status;
   o andamento é por turma (seção 8).

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
  "questionsByType": { "multipleChoice": 18, "dictation": 1, "text_production": 1 },
  "appliedClassesCount": 1,
  "nextApplicationStart": "2026-11-12T08:00:00"
}
```

- `questionsByType` sempre traz as três chaves (com `0` quando não há).
- `totalQuestions` conta todas as questões da avaliação.
- `appliedClassesCount`: quantas turmas têm aplicação (qualquer status).
- `nextApplicationStart`: o início mais próximo entre as turmas que ainda **não começaram**
  (`agendada`), em hora local do fuso daquela turma; `null` se não houver.

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

## 8. Aplicação às turmas — regras

1. Só avaliação **publicada** pode ser aplicada.
2. Só turmas que estão em `classIds` da avaliação (definidas na criação).
3. `applicationStart` é obrigatório. `applicationEnd` é opcional; se vier, tem que ser **depois** do início.
4. Aplicar é **upsert por turma**: turma sem aplicação é criada; turma com aplicação que **ainda não
   começou** tem as datas substituídas (incluindo `applicationEnd`: se não vier, fica sem fim).
   Se a aplicação daquela turma **já começou**, o pedido inteiro é recusado (`400`).
5. Retirar turma só antes do início.
6. O pedido é **tudo ou nada**: se uma turma falhar, nenhuma é gravada.
7. Alunos: todos os alunos cuja **turma atual** é a turma aplicada (inclui quem está em subturma
   ADAP dessa turma). Nada é gravado por aluno: se o aluno mudar de turma, passa a aparecer na nova.

### Datas e fuso

Mesmo padrão da avaliação de fluência: a data/hora é guardada **local** (sem fuso) junto com o
`timezone` da aplicação.

- `timezone` opcional; padrão `America/Sao_Paulo`. Precisa ser um nome IANA válido (ex.: `America/Manaus`).
- `applicationStart`/`applicationEnd` em ISO 8601:
  - **sem offset** (`2026-11-12T08:00:00`): é a hora local do `timezone`;
  - **com offset ou `Z`** (`2026-11-12T11:00:00Z`): é convertido para a hora local do `timezone`.
- Nas respostas as datas vêm **sem offset** (hora local) + `timezone`. Segundos fracionários são descartados.
- Datas no passado são aceitas (a turma já entra como `em_andamento`).

### Status da turma (calculado na leitura, não gravado)

| `status` | Quando |
|---|---|
| `agendada` | Agora (no fuso da turma) é antes de `applicationStart` |
| `em_andamento` | A partir de `applicationStart` e antes de `applicationEnd` (ou sem `applicationEnd`) |
| `encerrada` | A partir de `applicationEnd` |
| `null` | Turma da avaliação sem aplicação (`applied: false`) |

### Objeto Turma da aplicação

```json
{
  "classId": "7c9e1a3b-5d7f-4a2c-8e0b-2d4f6a8c0e1b",
  "className": "1º A",
  "school": { "id": "0b3e6a1c-2d4f-4b8a-9c1e-3f5a7b9d1e2f", "name": "Escola Municipal A" },
  "grade": { "id": "5600f4b8-af7e-429d-b03c-f7886c046b39", "name": "1º ano" },
  "applied": true,
  "applicationStart": "2026-11-12T08:00:00",
  "applicationEnd": "2026-11-12T11:30:00",
  "timezone": "America/Sao_Paulo",
  "status": "agendada",
  "studentCount": 25
}
```

Sem aplicação: `applied: false` e `applicationStart`, `applicationEnd`, `timezone`, `status` = `null`
(`studentCount` continua preenchido).

---

## 9. Aplicar às turmas

`POST /afirme-reading/written-tests/<id>/apply`

### Corpo

| Campo | Tipo | Obrigatório | Regra |
|---|---|---|---|
| `classIds` | array de UUID | Sim | Ao menos uma; todas em `classIds` da avaliação |
| `applicationStart` | string ISO 8601 | Sim | Início da aplicação |
| `applicationEnd` | string ISO 8601 | Não | Depois do início |
| `timezone` | string | Não | Padrão `America/Sao_Paulo` |

```json
{
  "classIds": ["7c9e1a3b-5d7f-4a2c-8e0b-2d4f6a8c0e1b", "1d3f5b7a-9c2e-4f6a-8b0d-3e5f7a9c1b2d"],
  "applicationStart": "2026-11-12T08:00:00",
  "applicationEnd": "2026-11-12T11:30:00"
}
```

### Resposta `200`

As turmas enviadas, já com as datas e o status:

```json
{
  "writtenTestId": "6f2c1d0a-7b3e-4f5a-9c8d-1e2f3a4b5c6d",
  "classes": [ { "...": "Objeto Turma da aplicação" } ]
}
```

### Erros (`400`)

| `error` |
|---|
| `Só avaliação publicada pode ser aplicada.` |
| `Informe ao menos uma turma em classIds.` / `classIds deve ser uma lista.` / `classIds contém ID inválido: <valor>` |
| `A turma <nome> não faz parte desta avaliação.` |
| `applicationStart é obrigatório.` |
| `applicationStart deve ser uma data/hora ISO 8601 (ex.: 2026-11-03T08:00:00).` (idem `applicationEnd`) |
| `applicationEnd deve ser depois de applicationStart.` |
| `timezone inválido: <valor>.` |
| `A aplicação da turma <nome> já começou e não pode ser alterada.` |

---

## 10. Turmas da avaliação

`GET /afirme-reading/written-tests/<id>/classes`

Todas as turmas de `classIds` da avaliação, aplicadas ou não, na ordem de `classIds`.

### Resposta `200`

```json
{
  "writtenTestId": "6f2c1d0a-7b3e-4f5a-9c8d-1e2f3a4b5c6d",
  "classes": [ { "...": "Objeto Turma da aplicação" } ]
}
```

---

## 11. Alunos de uma turma aplicada

`GET /afirme-reading/written-tests/<id>/classes/<classId>/students`

Só para turma **aplicada**. Alunos em ordem alfabética.

### Resposta `200`

Objeto Turma da aplicação, mais `writtenTestId` e `students`:

```json
{
  "writtenTestId": "6f2c1d0a-7b3e-4f5a-9c8d-1e2f3a4b5c6d",
  "classId": "7c9e1a3b-5d7f-4a2c-8e0b-2d4f6a8c0e1b",
  "className": "1º A",
  "applied": true,
  "status": "agendada",
  "studentCount": 2,
  "students": [
    { "id": "st-1", "name": "Ana Souza", "registration": "2026001", "subturma": null },
    { "id": "st-2", "name": "Caio Lima", "registration": null,
      "subturma": { "id": "9e8d7c6b-5a4f-4e3d-8c2b-1a0f9e8d7c6b", "name": "ADAP 1" } }
  ],
  "...": "demais campos do Objeto Turma da aplicação"
}
```

`registration` é a matrícula (pode ser `null`). `subturma` é a subturma ADAP da turma, se houver.

### Erros

| Status | `error` |
|---|---|
| 400 | `A avaliação ainda não foi aplicada a esta turma.` |
| 404 | `Turma não encontrada nesta avaliação.` (turma fora de `classIds` ou id inválido) |

---

## 12. Retirar turma da aplicação

`DELETE /afirme-reading/written-tests/<id>/classes/<classId>`

Só antes do início da aplicação daquela turma. A turma continua na avaliação (`classIds`), só deixa de
estar aplicada.

### Resposta `200`

```json
{ "message": "Aplicação da turma retirada com sucesso." }
```

### Erros

| Status | `error` |
|---|---|
| 400 | `A aplicação desta turma já começou e não pode ser retirada.` |
| 404 | `Turma não encontrada nesta avaliação.` |
| 404 | `A avaliação não está aplicada a esta turma.` |

---

## 13. PDF da prova (caderno de questões)

`GET /afirme-reading/written-tests/<id>/pdf`

Gera o caderno de questões na hora (A4) e devolve o arquivo. Não grava nada (nem no banco nem no
armazenamento); chamar de novo gera de novo, já com as questões atuais do banco de questões.

Perfis: todos os do Afirme Ler, **inclusive `aplicador`** (quem imprime/aplica).

### Resposta `200`

- `Content-Type: application/pdf`
- `Content-Disposition: attachment; filename=prova_<titulo>.pdf` — título sem acentos, minúsculo, com
  `_` no lugar de espaços (ex.: `prova_avaliacao_escrita_1o_bimestre.pdf`); título sem letras/números
  vira `prova_avaliacao.pdf`.

No frontend, baixar como blob (a rota exige o header `Authorization`):

```ts
const res = await api.get(`/afirme-reading/written-tests/${id}/pdf`, { responseType: "blob" });
```

### Conteúdo do PDF

- **Cabeçalho**: logo do município (se cadastrada; senão a logo Afirme), município/UF, título, séries e
  linhas em branco para **Nome do aluno**, **Escola**, **Turma** e **Data**.
- **Instruções**: marcar as respostas e responder o ditado e a produção escrita no cartão-resposta.
- **Questões** na ordem da avaliação, numeradas de 1 a 20:
  - `multipleChoice`: enunciado (`formattedText`, ou `text` se vazio), texto de apoio
    (`secondStatement`), imagens e alternativas `A)`, `B)`, `C)`… com texto e/ou imagem;
  - `dictation`: número, enunciado e "Responda no cartão-resposta." — **a palavra ditada não é impressa**;
  - `text_production`: número, comando e "Responda no cartão-resposta.".
- **Nunca** são impressos: gabarito, `isCorrect`, `formattedSolution`, `dictatedWord`, pontuação.
- Fonte grande (enunciado e alternativas em 15pt), questão de múltipla escolha não é quebrada entre
  páginas quando cabe numa página, "Página X de Y" no rodapé.

### Erros

| Status | `error` |
|---|---|
| 400 | `Só avaliação publicada pode gerar a prova.` |
| 400 | `A questão <id> (posição <n>) não existe mais no banco de questões. Não é possível gerar a prova.` |
| 400 | `A questão <id> é do tipo <tipo>, que não é aceito na avaliação escrita. Tipos permitidos: multipleChoice, dictation e text_production.` |
| 404 | `Avaliação escrita não encontrada.` |
| 500 | `Erro interno ao processar a solicitação.` (ex.: falha do gerador de PDF) |

Erros vêm em JSON (`{"error": "..."}`), não em PDF: com `responseType: "blob"`, ler o blob como texto
para mostrar a mensagem.

---

## Fluxo sugerido no frontend

1. `POST /written-tests` com título e escopo (séries → escolas → turmas).
2. Montar a prova com `GET /afirme-reading/questions?type=multipleChoice` (ou `dictation`,
   `text_production`) e enviar a lista com `PUT /written-tests/<id>/questions` a cada alteração.
3. Habilitar "Publicar" quando `totalQuestions === 20`; chamar `POST /written-tests/<id>/publish`.
4. Depois de publicada, os dados e as questões ficam só leitura.
5. Tela de aplicação: `GET /written-tests/<id>/classes`, escolher turmas e data, `POST /written-tests/<id>/apply`.
   Turmas `agendada` podem ser reaplicadas (nova data) ou retiradas; `em_andamento`/`encerrada` não.
6. Lista de alunos de uma turma: `GET /written-tests/<id>/classes/<classId>/students`.
7. Botão "Baixar prova (PDF)" em avaliação publicada: `GET /written-tests/<id>/pdf`.
