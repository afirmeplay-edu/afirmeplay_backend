# Play TV — contrato de API para o frontend

Base URL relativa: **`/play-tv`**. Todas as rotas exigem **`Authorization: Bearer <JWT>`**.

## Contexto de município (obrigatório)

Os dados ficam no schema PostgreSQL **`city_<uuid>`** do município. O backend define o `search_path` pelo:

- JWT (`city_id` / `tenant_id`) para perfis municipais; ou  
- **Admin:** header **`X-City-ID`** (UUID da cidade) ou **`X-City-Slug`**; ou subdomínio do município.

Sem contexto de cidade (ex.: admin na API central sem header), as rotas respondem **400** com mensagem pedindo `X-City-ID` / `X-City-Slug`.

---

## `GET /play-tv/videos`

| Query (opcional) | Descrição |
|------------------|-----------|
| `state`, `municipality` / `municipality_id`, `school` / `school_id`, `grade` / `grade_id`, `subject` / `subject_id`, `class` / `class_id` | Filtros (comportamento por perfil mantido no backend). |

**Resposta 200:** array de objetos vídeo (ordenado pelo backend).

### Objeto vídeo (listagem e detalhe)

| Campo | Tipo | Notas |
|-------|------|--------|
| `id` | string (UUID) | |
| `url` | string | URL HTTP(S) do player (YouTube etc.). |
| `title` | string \| null | Título do vídeo (máx. 100 no POST). |
| `entire_municipality` | boolean | `true` = visível para **todo** o município (escopo municipal). |
| `schools` | `{ id, name }[]` | Vazio se `entire_municipality`; senão, escolas às quais o vídeo foi distribuído. |
| `classes` | `{ id, name }[]` | Turmas restritas (opcional). Se vazio, todas as turmas das escolas (e série) elegíveis. |
| `grade` | `{ id, name }` | Série do vídeo. |
| `subject` | `{ id, name }` | Disciplina. |
| `resources` | array | Ver abaixo. |
| `created_at` | string ISO | |
| `created_by` | `{ id, name }` | |

### Objeto `resources[]`

| `type` | Campos |
|--------|--------|
| `"link"` | `id`, `type`, `title`, `sort_order`, `url` |
| `"file"` | `id`, `type`, `title`, `sort_order`, `file_name`, `mime_type`, `size_bytes` |

**`title` é obrigatório** em todo recurso (nome dado pelo usuário).

---

## `POST /play-tv/videos`

**Headers:** `Content-Type: application/json` (+ auth + contexto cidade se admin).

### Corpo JSON

| Campo | Obrigatório | Descrição |
|-------|-------------|-----------|
| `url` | sim | URL HTTP(S) do vídeo. |
| `grade` | sim | UUID da série (`grade.id`). |
| `subject` | sim | ID da disciplina. |
| `title` | não | Título do vídeo (máx. 100). |
| `entire_municipality` | não | Default `false`. Se `true`: **município inteiro**; só **`admin`** ou **`tecadm`**. |
| `schools` | condicional | Lista de IDs de escola. **Obrigatória** (e não vazia) se `entire_municipality` for `false`. Se `entire_municipality` for `true`, pode ser `[]`. |
| `classes` | não | Lista de UUIDs de turmas (opcional). Turmas devem pertencer às escolas escolhidas **ou**, no caso municipal, a escolas **do mesmo município**. |
| `resources` | não | Somente itens **link** (ver abaixo). Arquivos vão pelo endpoint multipart separado. |

### Item em `resources` (só `type: "link"`)

```json
{
  "type": "link",
  "title": "Nome exibido",
  "url": "https://...",
  "sort_order": 0
}
```

- `title`: obrigatório (máx. 200).  
- `sort_order`: opcional (inteiro; default pela ordem do array).  
- Não envie `type: "file"` aqui; use o upload abaixo.

### Respostas

- **201:** `{ "mensagem": "...", "video": { ... mesmo formato do GET } }`
- **400 / 403 / 404 / 500:** `{ "erro": "..." }` (e eventualmente `detalhes`).

---

## `POST /play-tv/videos/:videoId/resources/file`

Anexa um **arquivo** ao vídeo (MinIO).

**Headers:** `Content-Type: multipart/form-data` + auth.

**Form fields:**

| Campo | Obrigatório | Descrição |
|-------|-------------|-----------|
| `file` | sim | Arquivo. |
| `title` | sim | Nome do recurso (máx. 200). |
| `sort_order` | não | Inteiro. |

**Limite de tamanho:** padrão **50 MB** (`PLAY_TV_MAX_UPLOAD_MB` no backend).

**201:** `{ "mensagem": "...", "resource": { "id", "type": "file", "title", "file_name", "mime_type", "size_bytes", "sort_order" } }`

**Bucket MinIO:** `play-tv-resources` (deve existir ou estar criado no ambiente).

---

## `GET /play-tv/videos/:videoId/resources/:resourceId/download`

Gera URL temporária de download (presigned, **1 hora**).

**200:**

```json
{
  "download_url": "https://...",
  "expires_in_seconds": 3600,
  "file_name": "original.ext"
}
```

Só para recursos com `type: "file"` e usuário com permissão de ver o vídeo.

---

## `PUT /play-tv/videos/:videoId`

**JSON parcial:** envie só os campos que mudam.

| Campo | Efeito |
|-------|--------|
| `title`, `url`, `grade`, `subject` | Atualizam o vídeo principal (mesmas regras de validação do POST). |
| `entire_municipality` | Só **`admin`** / **`tecadm`** podem ligar. Com `true`, use `schools: []` (ou omita `schools` após marcar municipal). |
| `schools`, `classes` | Se **qualquer** um existir no body, ou se `entire_municipality` vier no body, **escolas e turmas são recalculadas**: junções antigas são substituídas. Municipal ⇒ `schools` deve ser `[]` se enviado. |
| `resources` | **Somente links** (`type: "link"`). Lista **completa** desejada: ítem com `id` atualiza o link; sem `id` cria; links que existiam e não estão na lista são **removidos**. Recursos `file` **não** vão no JSON — continuam no vídeo até `DELETE` do recurso. |

Exemplo de links:

```json
"resources": [
  { "id": "uuid-existente-opcional", "type": "link", "title": "Apostila", "url": "https://...", "sort_order": 0 },
  { "type": "link", "title": "Novo link", "url": "https://..." }
]
```

**Permissão de edição:** leitores comuns não editam. Vídeo em **município inteiro** só **`admin`** e **`tecadm`** podem editar (incluindo título/URL/anexos). Demais perfis editam só vídeos direcionados a escolas que já podiam criar.

**200:** `{ "mensagem": "...", "video": { ... } }`

---

## `DELETE /play-tv/videos/:videoId/resources/:resourceId`

Remove **um** recurso (link ou arquivo). Se for arquivo, remove também do MinIO.

**Roles:** `admin`, `professor`, `diretor`, `coordenador`, `tecadm`, com mesma regra de edição do `PUT` (vídeo municipal só admin/tecadm).

**200:** `{ "mensagem": "Recurso removido" }`

---

## `GET /play-tv/videos/:videoId`

Retorna um objeto vídeo (mesmo formato da listagem).

**403** se o usuário não puder acessar aquele vídeo (escola / série / turma / perfil).

---

## `DELETE /play-tv/videos/:videoId`

Apenas **`admin`**. Remove vídeo, junções e recursos; apaga arquivos relacionados no MinIO.

---

## Resumo de fluxo sugerido (UI)

1. **Criar vídeo** com `POST /play-tv/videos` (links em `resources` se houver).  
2. Para cada PDF/anexo: **`POST .../resources/file`** com `title` + `file`.  
3. **Editar:** `PUT /play-tv/videos/:id` (campos parciais; links via `resources`; trocar escolas/turmas enviando `schools` / `classes` / `entire_municipality` conforme regras acima).  
4. **Remover um anexo ou link:** `DELETE .../resources/:resourceId`.  
5. **Listar / abrir:** `GET /play-tv/videos` e `GET /play-tv/videos/:id`.  
6. Para baixar anexo: **`GET .../resources/:rid/download`** e abrir `download_url`.

### Escopo

- **Todo o município:** `entire_municipality: true`, `schools: []`, mais `grade` / `subject` (e `classes` opcional para restringir turmas dentro do município).  
- **Escola(s) / turma(s):** `entire_municipality: false`, `schools: ["..."]`, opcional `classes: [...]`.

---

## CORS

Headers úteis já tratados na app: `Authorization`, `X-City-ID`, `X-City-Slug` (conforme `create_app`).
