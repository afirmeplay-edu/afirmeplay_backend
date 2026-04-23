# Calendar — contrato de API para o frontend

Base URL relativa: **`/calendar`**.  
Todas as rotas exigem **`Authorization: Bearer <JWT>`**.

## Contexto de município (obrigatório)

As tabelas do calendário são tenantizadas por schema `city_<uuid>`.  
Para chamadas de admin, envie `X-City-ID` ou `X-City-Slug` quando necessário.

---

## Tipos de target (`targets[]`)

Formato base:

```json
{ "target_type": "CLASS", "target_id": "uuid-ou-id" }
```

Tipos aceitos:

- `ALL` (município inteiro no schema atual; sem `target_id`)
- `ROLE_GROUP` (grupo de role com filtros opcionais)
- `SCHOOL`
- `GRADE`
- `CLASS`
- `USER`
- `MUNICIPALITY` (legado/suportado)

### Regras por role ao criar/editar targets

- **admin / tecadm:** podem usar `ALL` e também outros escopos.
- **professor / diretor / coordenador:** apenas escopos da(s) escola(s) vinculada(s).
- **aluno:** somente para si (`target_type: "USER"` e `target_id = user.id`).

### `ROLE_GROUP` com filtros (escola/série/turma)

Use quando quiser enviar para um grupo específico de role, com recorte opcional:

```json
{
  "target_type": "ROLE_GROUP",
  "target_id": "professor",
  "filters": {
    "school_ids": ["..."],
    "grade_ids": ["..."],
    "class_ids": ["..."]
  }
}
```

`target_id` aceitos em `ROLE_GROUP`:

- `admin`
- `tecadm`
- `diretor`
- `coordenador`
- `professor`
- `aluno`

Os filtros são opcionais e podem ser usados isolados ou combinados.

Exemplos:

- Somente professores da escola X.
- Somente professores da série X.
- Somente professores da turma X.
- Somente professores da escola X + série X.

> Quando combinar filtros, o backend aplica interseção (AND).

### Evento somente para o próprio usuário

```json
{
  "target_type": "USER",
  "target_id": "<meu_user_id>"
}
```

---

## Permissões (edição e visibilidade)

- **Alterar, excluir, publicar, listar destinatários, anexar arquivo ou remover anexo:** apenas o usuário em `created_by.id` (criador). O backend responde **403** para qualquer outro, mesmo com role elevado.
- **Leitura:** `GET /calendar/events/:eventId` e download de arquivo exigem ser **criador** ou **destinatário** materializado (`calendar_event_users`). Caso contrário, **403**.
- **UI:** compare o `sub` / `id` do JWT com `created_by.id` no objeto evento para exibir edição/exclusão (o bloqueio real continua no servidor).

---

## Objeto evento (retorno)

```json
{
  "id": "uuid",
  "title": "Reunião pedagógica",
  "start": "2026-04-10T12:00:00+00:00",
  "end": "2026-04-10T13:00:00+00:00",
  "allDay": false,
  "timezone": "America/Sao_Paulo",
  "created_by": {
    "id": "uuid-do-usuario",
    "role": "admin",
    "name": "Nome no cadastro"
  },
  "extendedProps": {
    "description": "Detalhes",
    "location": "Sala 1",
    "recurrence_rule": null,
    "read": false,
    "eventId": "uuid",
    "metadata": {},
    "resources": [
      { "id": "r1", "type": "link", "title": "Ata", "url": "https://...", "sort_order": 0 },
      { "id": "r2", "type": "file", "title": "PDF", "file_name": "arquivo.pdf", "mime_type": "application/pdf", "size_bytes": 12345, "sort_order": 1 }
    ]
  }
}
```

---

## `POST /calendar/events`

Cria evento.

### Body JSON

| Campo | Obrigatório | Descrição |
|-------|-------------|-----------|
| `title` | sim | Título do evento |
| `start_at` | sim | ISO 8601 |
| `end_at` | não | ISO 8601 |
| `description` | não | Texto |
| `location` | não | Local |
| `all_day` | não | Boolean |
| `timezone` | não | Ex.: `America/Sao_Paulo` |
| `recurrence_rule` | não | Regra de recorrência |
| `is_published` | não | Boolean |
| `visibility_scope` | sim | Valor aceito pelo backend |
| `targets` | sim* | Lista de targets |
| `resources` | não | Lista de links (`type: "link"`) |

\* Na prática de negócio atual, enviar pelo menos 1 target.

### Exemplo

```json
{
  "title": "Aviso geral",
  "start_at": "2026-04-10T12:00:00+00:00",
  "end_at": "2026-04-10T13:00:00+00:00",
  "all_day": false,
  "visibility_scope": "MUNICIPALITY",
  "targets": [
    { "target_type": "ALL" }
  ],
  "resources": [
    { "type": "link", "title": "Documento", "url": "https://exemplo.com/doc", "sort_order": 0 }
  ]
}
```

### Exemplo: somente eu

```json
{
  "title": "Lembrete pessoal",
  "start_at": "2026-04-10T12:00:00+00:00",
  "visibility_scope": "USERS",
  "targets": [
    { "target_type": "USER", "target_id": "meu-user-id" }
  ]
}
```

### Exemplo: somente professores da escola X

```json
{
  "title": "Reunião de professores",
  "start_at": "2026-04-10T12:00:00+00:00",
  "visibility_scope": "SCHOOL",
  "targets": [
    {
      "target_type": "ROLE_GROUP",
      "target_id": "professor",
      "filters": {
        "school_ids": ["school-x-id"]
      }
    }
  ]
}
```

**201:** `{ "event": <objeto evento> }`  
**400/403/404/500:** `{ "error": "..." }`

---

## `PUT /calendar/events/:eventId`

Atualização parcial. **Somente o criador** (`created_by.id`).

- Pode atualizar campos do evento.
- Se enviar `targets`, substitui os targets anteriores.
- Se enviar `resources`, considera lista final de **links**:
  - item com `id` atualiza;
  - item sem `id` cria;
  - links antigos omitidos são removidos.
- Recursos de `type: "file"` não entram no JSON de `PUT`.

**200:** `{ "event": <objeto evento> }`  
**403:** não criador.

---

## `GET /calendar/events` (desativado)

Esta rota **não está registrada** no backend por enquanto. Use **`GET /calendar/my-events`** para a agenda do usuário.

---

## `GET /calendar/my-events`

Lista eventos **pertinentes** ao usuário no intervalo:

- em que ele é **destinatário** materializado; ou
- que ele **criou** (mesmo que não haja linha duplicada de destinatário).

### Query

| Query | Obrigatório | Descrição |
|------|-------------|-----------|
| `start` | sim | ISO 8601 |
| `end` | sim | ISO 8601 |

**200:** `Array<objeto evento>`

---

## `POST /calendar/events/:eventId/resources/file`

Anexa arquivo ao evento. **Somente o criador** do evento.

Headers: `Content-Type: multipart/form-data`.

### Form fields

| Campo | Obrigatório | Descrição |
|-------|-------------|-----------|
| `file` | sim | Arquivo |
| `title` | sim | Nome do recurso (máx. 200) |
| `sort_order` | não | Inteiro |

Limite padrão: **50 MB** (`CALENDAR_MAX_UPLOAD_MB`).

**201:**

```json
{
  "resource": {
    "id": "uuid",
    "type": "file",
    "title": "Edital",
    "file_name": "edital.pdf",
    "mime_type": "application/pdf",
    "size_bytes": 123456,
    "sort_order": 0
  }
}
```

---

## `GET /calendar/events/:eventId/resources/:resourceId/download`

Gera URL temporária de download (presigned, 1 hora). **Criador ou destinatário** do evento.

**200:**

```json
{
  "download_url": "https://...",
  "expires_in_seconds": 3600,
  "file_name": "edital.pdf"
}
```

---

## `DELETE /calendar/events/:eventId/resources/:resourceId`

Remove recurso (link ou arquivo). **Somente o criador.**  
Se for arquivo, também remove do armazenamento.

**200:** `{ "success": true }`  
**403:** não criador.

---

## Outros endpoints existentes

- `GET /calendar/events/:eventId` — criador ou destinatário; senão **403**
- `DELETE /calendar/events/:eventId` — **somente criador**
- `POST /calendar/events/:eventId/publish` — **somente criador**
- `GET /calendar/events/:eventId/recipients` — **somente criador**
- `POST /calendar/events/:eventId/read`
- `POST /calendar/events/:eventId/dismiss`
- `GET /calendar/targets/me`

---

## Fluxo sugerido (UI)

1. Listar agenda com `GET /calendar/my-events?start=&end=`.  
2. Criar evento com `POST /calendar/events` (incluindo links em `resources`, se houver).  
3. Usar `created_by.id` do evento vs usuário logado para mostrar editar/excluir/publicar.  
4. Para anexos de arquivo, usar `POST /calendar/events/:id/resources/file` (só criador).  
5. Atualizar evento via `PUT` (só criador; sincronização de links em `resources`).  
6. Para remover recurso, `DELETE /resources/:resourceId` (só criador).  
7. Para baixar arquivo, `GET .../download` (criador ou destinatário).
