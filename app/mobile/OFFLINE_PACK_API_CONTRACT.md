# Contrato da API mobile — pacote offline (`api_contract_version` **1.0**)

Documento normativo para o **app** consumir **estritamente** o JSON devolvido pelo backend.  
Prefixo HTTP: **`/mobile/v1`**.

---

## 1. `POST /offline-pack/redeem`

### 1.1 Headers obrigatórios

| Header | Valor |
|--------|--------|
| `Content-Type` | `application/json` |
| `X-Device-Id` | UUID v4 (mesmo em todas as chamadas do aparelho) |

Não é obrigatório `X-City-ID` quando o código existe em `public.mobile_offline_pack_registry`.

### 1.2 Corpo (todas as páginas)

```json
{
  "code": "<12 caracteres normalizados, com ou sem hífens>",
  "page": 1,
  "page_size": 50,
  "offline_pack_id": "<uuid retornado na página 1; opcional na pág. 1, recomendado nas seguintes>"
}
```

- **`code`**: obrigatório em **todas** as páginas.  
- **`offline_pack_id`**: na página 1 pode ser omitido; nas páginas `> 1` deve ser o mesmo da página 1 (validação de consistência).

### 1.3 Objeto raiz da resposta (200)

Campos **sempre presentes** em todas as páginas:

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `api_contract_version` | `string` | Fixo `"1.0"` até nova versão documentada. |
| `city_id` | `string` | UUID do município (`public.city.id`). |
| `offline_pack_id` | `string` | UUID do registro no tenant (`mobile_offline_pack_code.id`). |
| `bundle_valid_until` | `string` | ISO 8601 com sufixo `Z` (validade mínima do snapshot para upload). |
| `sync_bundle_version_by_school` | `object` | Mapa **`school_id` (string) → `number` inteiro**. Versão do bundle **por escola**; usar no **`POST /sync/upload`** conforme a escola da submissão. |
| `sync_bundle_version` | `number` \| `null` | Se **exatamente uma** escola em `sync_bundle_version_by_school`, repete esse inteiro; caso contrário **`null`**. O app **deve** usar `sync_bundle_version_by_school[student.school_id]` quando houver várias escolas ou quando este for `null`. |
| `page` | `number` | Página atual (≥ 1). |
| `page_size` | `number` | Tamanho da página. |
| `total_students` | `number` | Total de alunos elegíveis no pacote. |
| `total_pages` | `number` | Total de páginas de alunos (≥ 1). |
| `unchanged` | `boolean` | No offline pack costuma ser `false`. |
| `students` | `array` | Lista de **StudentPayload** (ver §2). |

**Página 1** (`page === 1`): payload completo de provas.

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `student_test_links` | `array` | Lista de `{ "student_id", "test_id" }`. |
| `tests` | `object` | Mapa **`test_id` → objeto metadados da prova** (igual espírito ao `sync/bundle`). |
| `questions_by_test` | `object` | Mapa **`test_id` → array de questões** canónicas (com `order`). |
| `test_content_version` | `object` | Mapa **`test_id` → string** (hash de conteúdo; enviar no upload). |

**Página > 1**:

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `student_test_links` | `array` | Sempre `[]`. |
| `tests` | `object` | Sempre `{}`. |
| `questions_by_test` | `object` | Sempre `{}`. |
| `test_content_version` | `object` | Sempre `{}`. |
| `includes_full_payload` | `boolean` | Presente e `false`. |

---

## 2. `StudentPayload` (cada elemento de `students`)

Ordem das chaves no JSON **não** é garantida; usar nomes exatos.

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|-------------|-----------|
| `id` | `string` | sim | UUID do aluno (`student.id`). |
| `name` | `string` | sim | Nome exibido (campo do aluno). |
| `registration` | `string` \| `null` | sim | Matrícula; pode ser `null`. |
| `email` | `string` \| `null` | sim | E-mail do **`users`** ligado ao aluno (`User.email`); `null` se não houver. **Login offline:** aceitar o mesmo identificador que o web (`registration` **ou** `email`). |
| `user_id` | `string` \| `null` | sim | UUID em `public.users`. |
| `password_hash` | `string` \| `null` | sim | Cópia **literal** de `users.password_hash` para verificação offline (pode ser `pbkdf2:sha256`, `scrypt`, etc., conforme Werkzeug/versão). |
| `class_id` | `string` \| `null` | sim | UUID da turma. |
| `grade_id` | `string` \| `null` | sim | UUID da série/nota. |
| `school_id` | `string` | sim | UUID da escola. |

**Identificação de login no app:** o utilizador pode digitar **matrícula** (`registration`) ou **e-mail** (`email`). O app deve resolver para o registo local cujo `registration` ou `email` (case-insensitive para email) coincidir, e validar a senha com `password_hash` (biblioteca compatível com o formato recebido).

---

## 3. Alinhamento com `GET /mobile/v1/sync/bundle`

O bundle por escola (`sync/bundle`) segue o **mesmo formato** de cada item em `students` (incluindo `email` a partir deste contrato), e os mesmos conceitos de `tests`, `questions_by_test`, `test_content_version`, `student_test_links`.  
Diferenças:

- `sync/bundle` expõe `school_id` e **um** `sync_bundle_version` (escola única no pedido).  
- `redeem` expõe `sync_bundle_version_by_school` e opcionalmente `sync_bundle_version` quando só há uma escola.

---

## 4. Upload (`POST /sync/upload`) — lembrete

Cada item de `submissions` deve incluir o **`sync_bundle_version`** inteiro correspondente à **escola** da submissão:  
`sync_bundle_version_by_school[school_id]` guardado no sync local após o download.

---

## 5. Evolução de versão

Alterações incompatíveis devem incrementar **`api_contract_version`** (ex.: `"2.0"`) e atualizar este ficheiro. O app pode negociar ou recusar versões desconhecidas.
